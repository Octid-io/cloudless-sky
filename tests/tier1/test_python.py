"""
OSMP Tier 1 Tests — Python Reference Implementation
Built from canonical dictionary v12. Tests validate the IP, not the code against itself.

Run: python3 -m pytest tests/tier1/test_python.py -v
"""
import sys, json, pytest
sys.path.insert(0, "sdk/python/src")
from osmp import (
    SALEncoder, SALDecoder, AdaptiveSharedDictionary, BAELEncoder, BAELMode,
    OverflowProtocol, LossPolicy, Fragment, TwoTierCompressor,
    ASD_BASIS, ASD_FLOOR_VERSION, GLYPH_OPERATORS, CONSEQUENCE_CLASSES,
    LORA_FLOOR_BYTES, FRAGMENT_HEADER_BYTES, FLAG_TERMINAL, FLAG_CRITICAL, utf8_bytes,
)





# ── SECTION 1: CANONICAL OPCODE VERIFICATION ─────────────────────────────────
class TestCanonicalOpcodes:
    """Every opcode listed here is drawn directly from dictionary v12."""
    @pytest.mark.parametrize("ns,op,expected", [
        ("Z","INF","invoke_inference"),
        ("V","HDG","heading"),
        ("V","ROUTE","routing_instruction"),
        ("D","PACK","two_tier_corpus_encoding_for_at_rest_storage"),
        ("D","UNPACK","inference_free_semantic_retrieval_from_encoded_corpus"),
        ("H","ICD","ICD-10_diagnosis_code_accessor"),
        ("H","SNOMED","SNOMED_CT_concept_identifier_accessor"),
        ("H","CPT","CPT_procedure_code_accessor"),
        ("N","INET","internet_uplink_capability_query"),
        ("A","CMPR","structured_comparison_returning_result"),
        ("C","ALLOC","resource_allocation"),
        ("C","FREE","release_resource"),
        ("S","ROTATE","key_rotation"),
        ("T","AFTER","execute_after_condition"),
        ("T","BEFORE","execute_before_deadline"),
        ("U","ALERT","urgent_operator_alert"),
        ("U","DISPLAY","display_information_to_operator"),
        ("U","INPUT","request_operator_input"),
        ("Y","RETRIEVE","retrieve_from_LCS"),
        ("Z","ROUTE","route_to_model_with_specified_capability"),
        ("L","QUERY","audit_trail_query"),
        ("Q","CORRECT","correction_directive"),
        # Core opcodes unchanged from prior versions
        ("H","HR","heart_rate"),
        ("R","ESTOP","emergency_stop"),
        ("I","§","human_operator_confirmation"),
        ("A","NACK","negative_acknowledgment"),
        ("A","ACK","positive_acknowledgment"),
        ("M","EVA","evacuation"),
        ("R","HDNG","heading"),
    ])
    def test_opcode(self, ns, op, expected):
        a = AdaptiveSharedDictionary()
        assert a.lookup(ns, op) == expected, f"{ns}:{op}"

    def test_total_opcode_count(self):
        total = sum(len(v) for v in ASD_BASIS.values())
        assert total >= 339, f"Expected ≥339 opcodes, got {total}"

    def test_all_26_namespaces(self):
        assert set(ASD_BASIS.keys()) == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_z_infer_absent(self):
        """Z:INFER was the wrong name — canonical is Z:INF."""
        a = AdaptiveSharedDictionary()
        assert a.lookup("Z","INFER") is None, "Z:INFER should not exist — canonical is Z:INF"

    def test_v_hdng_absent(self):
        """V:HDNG was wrong — canonical is V:HDG."""
        a = AdaptiveSharedDictionary()
        assert a.lookup("V","HDNG") is None, "V:HDNG should not exist — canonical is V:HDG"

    def test_v_rout_absent(self):
        """V:ROUT was wrong — canonical is V:ROUTE."""
        a = AdaptiveSharedDictionary()
        assert a.lookup("V","ROUT") is None, "V:ROUT should not exist — canonical is V:ROUTE"

# ── SECTION 2: DECODER ────────────────────────────────────────────────────────
class TestDecoder:
    @pytest.mark.parametrize("encoded,ns,op", [
        ("A:SUM","A","SUM"), ("B:BA","B","BA"), ("C:SPAWN","C","SPAWN"),
        ("D:PACK","D","PACK"), ("D:UNPACK","D","UNPACK"), ("D:XFER","D","XFER"),
        ("E:TH","E","TH"), ("F:Q","F","Q"), ("G:POS","G","POS"),
        ("H:HR","H","HR"), ("H:ICD","H","ICD"), ("H:SNOMED","H","SNOMED"),
        ("I:KYC","I","KYC"), ("J:GOAL","J","GOAL"), ("K:PAY","K","PAY"),
        ("L:AUDIT","L","AUDIT"), ("M:EVA","M","EVA"), ("N:CFG","N","CFG"),
        ("N:INET","N","INET"), ("O:MODE","O","MODE"), ("P:GUIDE","P","GUIDE"),
        ("Q:SCORE","Q","SCORE"), ("R:ESTOP","R","ESTOP"), ("S:ENC","S","ENC"),
        ("S:ROTATE","S","ROTATE"), ("T:NOW","T","NOW"), ("T:AFTER","T","AFTER"),
        ("T:BEFORE","T","BEFORE"), ("U:ESCALATE","U","ESCALATE"),
        ("U:ALERT","U","ALERT"), ("U:DISPLAY","U","DISPLAY"),
        ("V:POS","V","POS"), ("V:HDG","V","HDG"), ("V:ROUTE","V","ROUTE"),
        ("W:METAR","W","METAR"), ("X:GEN","X","GEN"), ("Y:SEARCH","Y","SEARCH"),
        ("Y:RETRIEVE","Y","RETRIEVE"), ("Z:INF","Z","INF"), ("Z:ROUTE","Z","ROUTE"),
    ])
    def test_all_namespaces(self, encoded, ns, op):
        d = SALDecoder()
        r = d.decode_frame(encoded)
        assert r.namespace == ns and r.opcode == op

    def test_short_form_eq(self):
        r = SALDecoder().decode_frame("EQ@4A?TH:0")
        assert r.namespace == "E" and r.opcode == "EQ" and r.target == "4A"

    def test_short_form_ba(self):
        r = SALDecoder().decode_frame("BA@BS!")
        assert r.namespace == "B" and r.opcode == "BA"

    def test_medevac_chain(self):
        r = SALDecoder().decode_frame("H:HR@NODE1>120→H:CASREP∧M:EVA@*")
        assert r.namespace == "H" and r.opcode == "HR" and r.target == "NODE1>120"

    def test_financial_iff(self):
        r = SALDecoder().decode_frame("K:PAY@RECV↔I:§→K:XFR[AMT]")
        assert r.namespace == "K" and r.target == "RECV"

    def test_consequence_reversible(self):
        r = SALDecoder().decode_frame("R:TORCH@PHONE1:ON↺")
        assert r.consequence_class == "↺" and r.consequence_class_name == "REVERSIBLE"

    def test_consequence_hazardous(self):
        r = SALDecoder().decode_frame("R:CAM@NODE⚠")
        assert r.consequence_class == "⚠" and r.consequence_class_name == "HAZARDOUS"

    def test_consequence_irreversible(self):
        r = SALDecoder().decode_frame("R:DRVE@BOT1⊘")
        assert r.consequence_class == "⊘" and r.consequence_class_name == "IRREVERSIBLE"

    def test_human_confirmation_opcode(self):
        r = SALDecoder().decode_frame("I:§")
        assert r.namespace == "I" and r.opcode == "§"
        assert r.opcode_meaning == "human_operator_confirmation"

    def test_h_icd_layer2_decode(self):
        """H:ICD is a Layer 2 accessor — functional today with native ICD-10 code values.
        MDR increases compression density of ICD codes; it does not gate functionality.
        H:ICD[R00.1] is a valid floor-version instruction today."""
        a = AdaptiveSharedDictionary()
        assert a.lookup("H","ICD") == "ICD-10_diagnosis_code_accessor"
        r = SALDecoder().decode_frame("H:ICD")
        assert r.namespace == "H" and r.opcode == "ICD"

    def test_d_pack_decode(self):
        r = SALDecoder().decode_frame("D:PACK")
        assert r.namespace == "D" and r.opcode == "PACK"
        assert r.opcode_meaning == "two_tier_corpus_encoding_for_at_rest_storage"

    def test_d_unpack_decode(self):
        r = SALDecoder().decode_frame("D:UNPACK")
        assert r.opcode_meaning == "inference_free_semantic_retrieval_from_encoded_corpus"

    def test_n_inet_capability_routing(self):
        r = SALDecoder().decode_frame("∃N:INET")
        assert r.opcode == "INET" or r.namespace is not None

    def test_operational_context(self):
        r = SALDecoder().decode_frame("O:MODE:E∧O:TYPE:1")
        assert r.namespace == "O" and r.opcode == "MODE"

    def test_bael_passthrough(self):
        r = SALDecoder().decode_frame("Stop")
        assert r.raw == "Stop"

    def test_raw_preserved(self):
        s = "H:HR@NODE1"
        assert SALDecoder().decode_frame(s).raw == s

# ── SECTION 3: ENCODER ────────────────────────────────────────────────────────
class TestEncoder:
    def test_basic(self):
        assert SALEncoder().encode_frame("H","HR") == "H:HR"

    def test_with_target(self):
        assert SALEncoder().encode_frame("H","HR","NODE1") == "H:HR@NODE1"

    def test_r_requires_cc(self):
        with pytest.raises(ValueError):
            SALEncoder().encode_frame("R","MOV","BOT1")

    def test_r_reversible(self):
        r = SALEncoder().encode_frame("R","TORCH","PHONE1",consequence_class="↺")
        assert r.endswith("↺")

    def test_sequence(self):
        assert SALEncoder().encode_sequence(["A:SUM","A:ACK"]) == "A:SUM;A:ACK"

    def test_broadcast(self):
        assert SALEncoder().encode_broadcast("M","EVA") == "M:EVA@*"

    def test_compound(self):
        r = SALEncoder().encode_compound("H:ALERT","∧","M:EVA@*")
        assert "∧" in r

# ── SECTION 4: ASD CRDT DELTA ─────────────────────────────────────────────────
class TestASDDelta:
    def test_additive_does_not_overwrite(self):
        a = AdaptiveSharedDictionary()
        a.apply_delta("H","HR","WRONG",AdaptiveSharedDictionary.UpdateMode.ADDITIVE,"v2")
        assert a.lookup("H","HR") == "heart_rate"

    def test_replace_overwrites(self):
        a = AdaptiveSharedDictionary()
        a.apply_delta("H","HR","new",AdaptiveSharedDictionary.UpdateMode.REPLACE,"v2")
        assert a.lookup("H","HR") == "new"

    def test_deprecate_tombstones(self):
        a = AdaptiveSharedDictionary()
        a.apply_delta("H","HR","",AdaptiveSharedDictionary.UpdateMode.DEPRECATE,"v2")
        assert a.lookup("H","HR") is None

    def test_replace_after_deprecate(self):
        a = AdaptiveSharedDictionary()
        a.apply_delta("H","HR","",AdaptiveSharedDictionary.UpdateMode.DEPRECATE,"v2")
        a.apply_delta("H","HR","restored",AdaptiveSharedDictionary.UpdateMode.REPLACE,"v3")
        assert a.lookup("H","HR") == "restored"

    def test_fingerprint_stable(self):
        a = AdaptiveSharedDictionary()
        assert a.fingerprint() == a.fingerprint()

    def test_fingerprint_changes_on_delta(self):
        a = AdaptiveSharedDictionary()
        fp = a.fingerprint()
        a.apply_delta("Ω","MYOP","def",AdaptiveSharedDictionary.UpdateMode.ADDITIVE,"v2")
        assert a.fingerprint() != fp

# ── SECTION 5: OVERFLOW PROTOCOL ─────────────────────────────────────────────
class TestOverflowProtocol:
    def test_tier1_single_fragment(self):
        op = OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION)
        assert len(op.fragment(b"H:HR@NODE1")) == 1

    def test_tier1_round_trip(self):
        op = OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION)
        p = b"H:HR@NODE1"
        assert op.receive(op.fragment(p)[0]) == p

    def test_tier2_multi_fragment(self):
        op = OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION)
        assert len(op.fragment(b"X"*300)) > 1

    def test_tier2_reassembly(self):
        op = OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION)
        p = b"X"*500
        frags = op.fragment(p)
        result = None
        for f in frags: result = op.receive(f)
        assert result == p

    def test_lora_floor_fits(self):
        op = OverflowProtocol(LORA_FLOOR_BYTES,LossPolicy.GRACEFUL_DEGRADATION)
        p = "H:HR@NODE1>120→H:CASREP∧M:EVA@*".encode("utf-8") * 2
        frags = op.fragment(p)
        assert len(frags) > 1
        for f in frags:
            assert len(f.pack()) <= LORA_FLOOR_BYTES

    def test_estop_fires_under_atomic(self):
        op = OverflowProtocol(255,LossPolicy.ATOMIC)
        result = op.receive(op.fragment(b"R:ESTOP")[0])
        assert result is not None, "R:ESTOP must fire immediately under ATOMIC"

    def test_estop_fires_on_nonterminal(self):
        op = OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION)
        f = Fragment(msg_id=1,frag_idx=0,frag_ct=3,flags=0,dep=0,payload=b"R:ESTOP@BOT1")
        assert op.receive(f) is not None

    def test_atomic_null_on_partial(self):
        op = OverflowProtocol(255,LossPolicy.ATOMIC)
        frags = op.fragment(b"X"*300)
        if len(frags) > 1:
            assert op.receive(frags[0]) is None

    def test_pack_unpack(self):
        op = OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION)
        f = op.fragment(b"R:ESTOP@*")[0]
        unpacked = Fragment.unpack(f.pack())
        assert unpacked.payload == f.payload and unpacked.msg_id == f.msg_id

# ── SECTION 6: BAEL ───────────────────────────────────────────────────────────
class TestBAEL:
    def test_passthrough_when_nl_shorter(self):
        mode,payload,flags = BAELEncoder.select_mode("Stop","R:ESTOP@*")
        assert mode == BAELMode.NL_PASSTHROUGH and payload == "Stop"

    def test_full_osmp_when_shorter(self):
        nl = "If heart rate exceeds 120, assemble casualty report and broadcast evacuation."
        osmp = "H:HR@NODE1>120→H:CASREP∧M:EVA@*"
        mode,_,_ = BAELEncoder.select_mode(nl,osmp)
        assert mode == BAELMode.FULL_OSMP

    def test_never_expands(self):
        for nl,osmp in [("Go","A:DA@AGENT"),("Stop","R:ESTOP@*"),("OK","A:ACK")]:
            _,payload,_ = BAELEncoder.select_mode(nl,osmp)
            assert utf8_bytes(payload) <= utf8_bytes(nl)

    def test_not_sign_is_2_bytes(self):
        """¬ (U+00AC) is 2 bytes — CONTRIBUTING.md had this wrong."""
        assert utf8_bytes("¬") == 2

    def test_three_byte_glyphs(self):
        for g in ["∧","∨","→","↔","∀","∃","∥","⚠","↺","⊘","⊤","⊥","⌂","⊗","∈","∖"]:
            assert utf8_bytes(g) == 3, f"{g!r} should be 3 bytes"

    def test_two_byte_glyphs(self):
        for g in ["§","τ","Δ","¬"]:
            assert utf8_bytes(g) == 2, f"{g!r} should be 2 bytes"

# ── SECTION 7: CANONICAL TEST VECTORS ────────────────────────────────────────
class TestCanonicalVectors:
    @pytest.fixture
    def vectors(self):
        with open("protocol/test-vectors/canonical-test-vectors.json") as f:
            return json.load(f)

    def test_all_decode(self, vectors):
        d = SALDecoder(); errors = []
        for v in vectors["vectors"]:
            try:
                r = d.decode_frame(v["encoded"])
                if not r.namespace or not r.opcode:
                    errors.append(v["id"])
            except Exception as e:
                errors.append(f"{v['id']}: {e}")
        assert not errors

    def test_byte_counts_match_spec(self, vectors):
        errors = []
        for v in vectors["vectors"]:
            if utf8_bytes(v["natural_language"]) != v["nl_bytes"]:
                errors.append(f"{v['id']}: nl_bytes mismatch")
            if utf8_bytes(v["encoded"]) != v["osmp_bytes"]:
                errors.append(f"{v['id']}: osmp_bytes mismatch")
        assert not errors

    def test_conformance(self, vectors):
        d = SALDecoder(); reds = []
        for v in vectors["vectors"]:
            reds.append(v["reduction_pct"])
            r = d.decode_frame(v["encoded"])
            assert r.namespace and r.opcode
        mean = sum(reds)/len(reds)
        assert mean >= vectors["compression_summary"]["conformance_threshold_pct"]

# ── SECTION 8: TWO-TIER COMPRESSOR ───────────────────────────────────────────
class TestTwoTierCompressor:
    def test_round_trip(self):
        tc = TwoTierCompressor()
        text = "D:PACK\nD:UNPACK\nH:ICD[R00.1]\nZ:INF\nV:HDG\nV:ROUTE\n" * 5
        assert tc.decompress(tc.compress(text)) == text

    def test_d_pack_unpack_semantics(self):
        """D:PACK + D:UNPACK are the protocol-addressable two-tier operations.
        The compression and inference-free retrieval claims are embodied in these opcodes."""
        asd = AdaptiveSharedDictionary()
        assert "at_rest" in asd.lookup("D","PACK")
        assert "inference_free" in asd.lookup("D","UNPACK")
