"""
OSMP DX Tests — Developer Experience + Agent Experience + Wire Round-Trip

Three categories:
  1. DX: Tier 1 encode/decode in 3 lines, zero setup
  2. Agent DX: LLM calls osmp_encode correctly on first attempt given only tool description
  3. Wire Round-Trip: every canonical SAL vector survives SAL->SAIL->SAL

Run: PYTHONPATH=sdk/python python3 -m pytest tests/test_dx.py -v
"""
import sys, json, pytest

sys.path.insert(0, "sdk/python")


# ── SECTION 1: TIER 1 DX ────────────────────────────────────────────────────

class TestTier1DX:
    """Prove encode/decode works in 3 lines, zero setup."""

    def test_encode_list_to_sequence(self):
        from osmp import encode
        sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
        assert sal == "H:HR@NODE1>120;H:CASREP;M:EVA@*"

    def test_decode_single_frame(self):
        from osmp import decode
        text = decode("H:HR@NODE1>120")
        assert "heart_rate" in text

    def test_decode_sequence(self):
        from osmp import decode
        text = decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
        parts = text.split("; ")
        assert len(parts) == 3
        assert "heart_rate" in parts[0]
        assert "casualty_report" in parts[1]
        assert "evacuation" in parts[2]

    def test_encode_string_passthrough(self):
        from osmp import encode
        sal = "H:HR@NODE1>120;H:CASREP"
        assert encode(sal) == sal

    def test_encode_type_error(self):
        from osmp import encode
        with pytest.raises(TypeError):
            encode(42)

    def test_lookup_returns_definition(self):
        from osmp import lookup
        assert lookup("H:HR") == "heart_rate"
        assert lookup("R:ESTOP") == "emergency_stop"
        assert lookup("I:\u00a7") == "human_operator_confirmation"

    def test_lookup_missing_returns_none(self):
        from osmp import lookup
        assert lookup("Z:BOGUS") is None

    def test_byte_size_correct(self):
        from osmp import byte_size
        assert byte_size("H:HR") == 4
        assert byte_size("R:MOV@BOT1\u21ba") == len("R:MOV@BOT1\u21ba".encode("utf-8"))

    def test_validate_catches_missing_cc(self):
        from osmp import validate
        result = validate("R:MOV@BOT1")
        assert not result.valid
        assert any("CONSEQUENCE" in i.rule.upper() or "consequence" in i.message.lower()
                    for i in result.issues)

    def test_validate_passes_correct_chain(self):
        from osmp import validate
        result = validate("H:HR@NODE1>120")
        assert result.valid

    def test_three_line_demo(self):
        """The README promise: from osmp import encode, decode in 3 lines."""
        from osmp import encode, decode
        sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
        text = decode(sal)
        assert "heart_rate" in text and "casualty_report" in text and "evacuation" in text

    def test_version(self):
        from osmp import __version__
        assert __version__ == "2.0.1"

    def test_tier2_class_api(self):
        """Tier 2: class-based, same results."""
        from osmp.core import OSMP
        o = OSMP()
        sal = o.encode(["H:HR@NODE1>120", "H:CASREP"])
        assert sal == "H:HR@NODE1>120;H:CASREP"
        text = o.decode("H:HR@NODE1>120")
        assert "heart_rate" in text


# ── SECTION 2: AGENT DX ─────────────────────────────────────────────────────

class TestAgentDX:
    """Validate that the MCP tool descriptions contain enough information
    for an agent to call each tool correctly on first attempt.

    These tests verify the tool interface, not the LLM. They confirm that
    the parameter names, types, and descriptions match what a tool-calling
    agent would construct from the tool schema alone."""

    def test_osmp_encode_fields(self):
        """An agent given the osmp_encode schema should produce this call."""
        sys.path.insert(0, "mcp")
        from server import osmp_encode
        result = osmp_encode(namespace="R", opcode="MOV", target="BOT1",
                             consequence_class="\u21ba")
        assert "R:MOV@BOT1\u21ba" == result

    def test_osmp_encode_no_target(self):
        from server import osmp_encode
        assert osmp_encode(namespace="H", opcode="HR") == "H:HR"

    def test_osmp_decode_returns_json(self):
        from server import osmp_decode
        result = json.loads(osmp_decode(sal="H:HR@NODE1>120"))
        assert "frames" in result
        assert result["frames"][0]["namespace"] == "H"
        assert result["frames"][0]["opcode"] == "HR"

    def test_osmp_lookup_by_namespace(self):
        from server import osmp_lookup
        result = json.loads(osmp_lookup(namespace="R"))
        assert result["match_count"] > 10
        opcodes = [r["op"] for r in result["results"]]
        assert "ESTOP" in opcodes
        assert "MOV" in opcodes

    def test_osmp_lookup_by_keyword(self):
        from server import osmp_lookup
        result = json.loads(osmp_lookup(keyword="heart"))
        assert result["match_count"] >= 1
        assert any(r["op"] == "HR" for r in result["results"])

    def test_osmp_validate_pass(self):
        from server import osmp_validate
        result = json.loads(osmp_validate(sal="H:HR@NODE1>120",
                                          nl_input="Heart rate at node 1 above 120"))
        assert result["status"] == "PASS"

    def test_osmp_validate_fail(self):
        from server import osmp_validate
        result = json.loads(osmp_validate(sal="R:MOV@BOT1"))
        assert result["status"] == "FAIL"
        assert result["error_count"] >= 1

    def test_osmp_resolve_icd(self):
        from server import osmp_resolve
        result = osmp_resolve(code="R00.1", corpus="icd")
        assert "R00.1" in result

    def test_osmp_discover_keyword(self):
        from server import osmp_discover
        result = json.loads(osmp_discover(keyword="pneumo", corpus="icd"))
        assert result["total_matches"] >= 1


# ── SECTION 3: WIRE CODEC ROUND-TRIP ────────────────────────────────────────

class TestWireRoundTrip:
    """Every canonical SAL vector must survive SAL -> SAIL -> SAL."""

    @pytest.fixture
    def codec(self):
        from osmp.wire import SAILCodec
        return SAILCodec()

    @pytest.fixture
    def vectors(self):
        with open("protocol/test-vectors/canonical-test-vectors.json") as f:
            return json.load(f)["vectors"]

    def test_all_vectors_round_trip(self, codec, vectors):
        """Every canonical vector: encode to SAIL, decode back, exact match."""
        failures = []
        for v in vectors:
            sal = v["encoded"]
            try:
                sail_bytes = codec.encode(sal)
                decoded = codec.decode(sail_bytes)
                if decoded != sal:
                    failures.append(f"{v['id']}: {sal!r} -> {decoded!r}")
            except Exception as e:
                failures.append(f"{v['id']}: {sal!r} ERROR: {e}")
        assert not failures, f"SAIL round-trip failures:\n" + "\n".join(failures)

    def test_sail_smaller_for_nontrivial(self, codec, vectors):
        """SAIL encoding should be smaller than SAL for non-trivial instructions.
        Very short SAL strings (< 15 bytes) may inflate by 1-2 bytes due to
        SAIL header overhead. This is expected and acceptable."""
        inflated_nontrivial = []
        for v in vectors:
            sal = v["encoded"]
            sal_bytes = len(sal.encode("utf-8"))
            if sal_bytes < 15:
                continue  # short strings may inflate due to header overhead
            try:
                sail_len = len(codec.encode(sal))
                if sail_len > sal_bytes:
                    inflated_nontrivial.append(
                        f"{v['id']}: SAL {sal_bytes}B -> SAIL {sail_len}B (+{sail_len - sal_bytes})")
            except Exception:
                pass
        assert not inflated_nontrivial, (
            f"SAIL inflated vs SAL on non-trivial vectors:\n" + "\n".join(inflated_nontrivial))

    @pytest.mark.parametrize("sal", [
        "H:HR@NODE1>120",
        "R:MOV@BOT1\u21ba",
        "I:\u00a7\u2192R:MOV@BOT1\u26a0",
        "H:HR@NODE1>120\u2192H:CASREP\u2227M:EVA@*",
        "E:GPS@NODE1?0",
        "M:EVA@*",
        "R:ESTOP",
    ])
    def test_individual_round_trips(self, codec, sal):
        """Key SAL patterns round-trip through SAIL."""
        assert codec.decode(codec.encode(sal)) == sal

    def test_consequence_class_preserved(self, codec):
        """All three consequence classes survive SAIL encoding."""
        for cc, name in [("\u26a0", "HAZARDOUS"), ("\u21ba", "REVERSIBLE"), ("\u2298", "IRREVERSIBLE")]:
            sal = f"R:MOV@BOT1{cc}"
            decoded = codec.decode(codec.encode(sal))
            assert decoded == sal, f"{name} consequence class lost in round-trip"

    def test_compound_operators_preserved(self, codec):
        """Compound operators (\u2192, \u2227, \u2228, ;) survive SAIL encoding."""
        for op in ["\u2192", "\u2227", "\u2228", ";"]:
            sal = f"A:ACK{op}A:NACK"
            decoded = codec.decode(codec.encode(sal))
            assert decoded == sal, f"Operator {op!r} lost in round-trip"

    def test_broadcast_target_preserved(self, codec):
        """Broadcast target @* survives SAIL."""
        sal = "M:EVA@*"
        assert codec.decode(codec.encode(sal)) == sal

    def test_slot_values_preserved(self, codec):
        """Colon-delimited slot values survive SAIL."""
        sal = "R:TORCH@PHONE1:ON\u21ba"
        assert codec.decode(codec.encode(sal)) == sal
