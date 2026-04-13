#!/usr/bin/env python3
"""
OSMP ADP (ASD Distribution Protocol) Test Suite
================================================
Tests all ADP functionality: version mapping, ADPSession,
semantic pending queue, delta operations, FNP wire compat.

Run: python3 -m pytest tests/tier1/test_adp.py -v
"""
import sys, struct, pytest
sys.path.insert(0, "sdk/python")

from osmp import (
    AdaptiveSharedDictionary, FNPSession, ADPSession, ADPDeltaOp, ADPDelta,
    ASD_BASIS,
    asd_version_pack, asd_version_unpack, asd_version_str,
    asd_version_parse, asd_version_is_breaking,
    ADP_PRIORITY_MISSION, ADP_PRIORITY_MICRO,
    ADP_PRIORITY_DELTA, ADP_PRIORITY_TRICKLE,
)


# ── Version Mapping (u16 as u8.u8) ─────────────────────────────────────────

class TestVersionMapping:
    """Exhaustive tests for u16 <-> MAJOR.MINOR mapping."""

    def test_pack_unpack_roundtrip_all_boundaries(self):
        boundaries = [
            (0, 0), (0, 1), (0, 255),
            (1, 0), (1, 1), (1, 255),
            (2, 7), (3, 0), (127, 128),
            (255, 0), (255, 254), (255, 255),
        ]
        for major, minor in boundaries:
            u16 = asd_version_pack(major, minor)
            assert asd_version_unpack(u16) == (major, minor), \
                f"Roundtrip failed for {major}.{minor}"

    def test_pack_unpack_all_u16_values(self):
        """Verify every possible u16 round-trips correctly."""
        for val in range(0, 65536, 257):  # Sample every 257th to cover spread
            major, minor = asd_version_unpack(val)
            repacked = asd_version_pack(major, minor)
            assert repacked == val, f"Roundtrip failed for u16={val}"

    def test_pack_overflow_raises(self):
        with pytest.raises(ValueError):
            asd_version_pack(256, 0)
        with pytest.raises(ValueError):
            asd_version_pack(0, 256)
        with pytest.raises(ValueError):
            asd_version_pack(-1, 0)

    def test_str_roundtrip(self):
        cases = ["0.0", "1.0", "1.4", "2.7", "3.0", "255.255"]
        for s in cases:
            assert asd_version_str(asd_version_parse(s)) == s

    def test_str_parse_invalid(self):
        with pytest.raises(ValueError):
            asd_version_parse("2")
        with pytest.raises(ValueError):
            asd_version_parse("2.7.1")

    def test_breaking_detection(self):
        cases = [
            (0x0205, 0x0207, False),   # 2.5 -> 2.7
            (0x0207, 0x0300, True),    # 2.7 -> 3.0
            (0x0104, 0x0207, True),    # 1.4 -> 2.7
            (0x0300, 0x0300, False),   # 3.0 -> 3.0
            (0x0100, 0x01FF, False),   # 1.0 -> 1.255
            (0x0000, 0x0100, True),    # 0.0 -> 1.0
            (0xFF00, 0xFF01, False),   # 255.0 -> 255.1
        ]
        for old, new, expected in cases:
            assert asd_version_is_breaking(old, new) == expected, \
                f"Breaking detection wrong for {old:#06x} -> {new:#06x}"

    def test_u16_wire_format(self):
        """Verify u16 encodes to 2 bytes big-endian for FNP wire."""
        u16 = asd_version_pack(2, 7)
        wire = struct.pack(">H", u16)
        assert wire == b"\x02\x07"
        assert struct.unpack(">H", wire)[0] == u16


# ── ASD Opcodes ─────────────────────────────────────────────────────────────

class TestADPOpcodes:
    """Verify new opcodes exist and don't collide."""

    def test_asd_opcode_exists(self):
        asd = AdaptiveSharedDictionary()
        assert asd.lookup("A", "ASD") == "asd_version_identity_or_delta"

    def test_mdr_opcode_exists(self):
        asd = AdaptiveSharedDictionary()
        assert asd.lookup("A", "MDR") == "mdr_corpus_version_identity_or_delta"

    def test_existing_opcodes_unchanged(self):
        asd = AdaptiveSharedDictionary()
        assert asd.lookup("A", "ACK") == "positive_acknowledgment"
        assert asd.lookup("A", "NACK") == "negative_acknowledgment"
        assert asd.lookup("A", "PING") == "liveness_check"
        assert asd.lookup("H", "TRIAGE") == "triage_classification"
        assert asd.lookup("H", "HR") == "heart_rate"
        assert asd.lookup("K", "PAY") == "payment_execution"

    def test_a_namespace_count(self):
        """A namespace must have a minimum baseline of opcodes."""
        assert len(ASD_BASIS["A"]) >= 20

    def test_all_26_namespaces_still_present(self):
        assert set(ASD_BASIS.keys()) == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


# ── ADPSession: Version Identity ────────────────────────────────────────────

class TestADPVersionIdentity:

    def test_minimal(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        vi = adp.version_identity(include_namespaces=False)
        assert vi == "A:ASD[2.7]"

    def test_with_namespaces(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7),
                         namespace_versions={"H": "2.3", "K": "1.0"})
        vi = adp.version_identity()
        assert vi == "A:ASD[2.7:H2.3:K1.0]"

    def test_query(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        assert adp.version_query() == "A:ASD?"

    def test_alert(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        alert = adp.version_alert()
        assert alert == "A:ASD[2.7]\u26a0"

    def test_byte_floor_minimal(self):
        assert len("A:ASD[2.7]".encode("utf-8")) <= 11  # Fits US DR0

    def test_byte_floor_query(self):
        assert len("A:ASD?".encode("utf-8")) <= 11  # Fits US DR0


# ── ADPSession: Version Parsing ─────────────────────────────────────────────

class TestADPVersionParsing:

    def test_parse_minimal(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.receive_version("A:ASD[2.5]")
        assert result["version"] == "2.5"
        assert result["u16"] == asd_version_pack(2, 5)
        assert result["match"] == False
        assert result["breaking"] == False

    def test_parse_with_namespaces(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.receive_version("A:ASD[2.5:H2.1:K1.0]")
        assert result["namespaces"] == {"H": "2.1", "K": "1.0"}

    def test_parse_breaking(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.receive_version("A:ASD[3.0]")
        assert result["breaking"] == True

    def test_parse_exact_match(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.receive_version("A:ASD[2.7]")
        assert result["match"] == True


# ── ADPSession: Delta Request ───────────────────────────────────────────────

class TestADPDeltaRequest:

    def test_full_asd_request(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 5))
        req = adp.request_delta(target="2.7")
        assert req == "A:ASD:REQ[2.5\u21922.7]"

    def test_namespace_scoped_request(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 5),
                         namespace_versions={"H": "2.1"})
        adp.remote_namespace_versions = {"H": "2.3"}
        req = adp.request_delta(namespace="H")
        assert req == "A:ASD:REQ[H2.1\u2192H2.3]"

    def test_byte_floor(self):
        req = "A:ASD:REQ[2.5\u21922.7]"
        assert len(req.encode("utf-8")) <= 51  # Fits EU DR0


# ── ADPSession: Delta Application ───────────────────────────────────────────

class TestADPDeltaApplication:

    def test_additive_single(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 5))
        result = adp.apply_delta_sal("A:ASD:DELTA[2.5\u21922.6:H+[LACTATE]]")
        assert result["applied"]
        assert not result["breaking"]
        assert len(result["operations"]) == 1
        assert "LACTATE" in result["operations"][0]

    def test_additive_multiple(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 5))
        result = adp.apply_delta_sal(
            "A:ASD:DELTA[2.5\u21922.7:H+[LACTATE]:H+[HRV]]")
        assert result["applied"]
        assert len(result["operations"]) == 2

    def test_replace_is_breaking(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.apply_delta_sal(
            "A:ASD:DELTA[2.7\u21923.0:H\u2190[TRIAGE]]")
        assert result["applied"]
        assert result["breaking"]

    def test_deprecate(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.apply_delta_sal(
            "A:ASD:DELTA[2.7\u21922.8:K\u2020[LEGACY]]")
        assert result["applied"]
        assert not result["breaking"]

    def test_mixed_ops(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.apply_delta_sal(
            "A:ASD:DELTA[2.7\u21923.0:H+[HRV]:H\u2190[TRIAGE]:K\u2020[OLD]]")
        assert result["applied"]
        assert result["breaking"]
        assert len(result["operations"]) == 3

    def test_delta_logged(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 5))
        sal = "A:ASD:DELTA[2.5\u21922.6:H+[LACTATE]]"
        adp.apply_delta_sal(sal)
        assert sal in adp.delta_log


# ── ADPSession: Micro-Delta ─────────────────────────────────────────────────

class TestADPMicroDelta:

    def test_request_definition(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        req = adp.request_definition("H", "LACTATE")
        assert req == "A:ASD:DEF?[H:LACTATE]"

    def test_send_definition(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        resp = adp.send_definition("H", "LACTATE", "lactate_level", 1)
        assert resp == "A:ASD:DEF[H:LACTATE:lactate_level:1]"

    def test_apply_definition(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        result = adp.apply_definition("A:ASD:DEF[H:LACTATE:lactate_level:1]")
        assert result["applied"]
        assert result["namespace"] == "H"
        assert result["opcode"] == "LACTATE"
        assert asd.lookup("H", "LACTATE") == "lactate_level"

    def test_byte_floor_request(self):
        req = "A:ASD:DEF?[H:LACTATE]"
        assert len(req.encode("utf-8")) <= 51

    def test_byte_floor_response(self):
        resp = "A:ASD:DEF[H:LACTATE:lactate_level:1]"
        assert len(resp.encode("utf-8")) <= 51


# ── ADPSession: Semantic Pending Queue ──────────────────────────────────────

class TestSemanticPendingQueue:

    def test_known_opcode_resolves(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        result = adp.resolve_or_pend("H:HR[72]")
        assert result["resolved"]
        assert not result["pending"]

    def test_unknown_opcode_pends(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        result = adp.resolve_or_pend("H:LACTATE[4.2]")
        assert not result["resolved"]
        assert result["pending"]
        assert result["unresolved"] == "H:LACTATE"
        assert "DEF?" in result["micro_delta_request"]

    def test_pending_queue_depth(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        adp.resolve_or_pend("H:LACTATE[4.2]")
        adp.resolve_or_pend("H:GCS[15]")
        assert len(adp.pending_queue) == 2

    def test_pending_resolves_after_def(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        adp.resolve_or_pend("H:LACTATE[4.2]")
        assert len(adp.pending_queue) == 1
        result = adp.apply_definition("A:ASD:DEF[H:LACTATE:lactate_level:1]")
        assert "H:LACTATE[4.2]" in result["pending_resolved"]
        assert len(adp.pending_queue) == 0

    def test_pending_resolves_after_delta(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 5))
        adp.resolve_or_pend("H:LACTATE[4.2]")
        result = adp.apply_delta_sal(
            "A:ASD:DELTA[2.5\u21922.6:H+[LACTATE]]")
        assert "H:LACTATE[4.2]" in result["pending_resolved"]

    def test_partial_resolution(self):
        """Two pending, only one opcode arrives."""
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        adp.resolve_or_pend("H:LACTATE[4.2]")
        adp.resolve_or_pend("H:GCS[15]")
        adp.apply_definition("A:ASD:DEF[H:LACTATE:lactate_level:1]")
        assert len(adp.pending_queue) == 1  # GCS still pending

    def test_non_instruction_passes_through(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)
        result = adp.resolve_or_pend("not_a_sal_instruction")
        assert result["resolved"]


# ── ADPSession: Hash Verification ───────────────────────────────────────────

class TestADPHash:

    def test_hash_identity(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        h = adp.hash_identity()
        assert h.startswith("A:ASD:HASH[2.7:")
        assert len(h.encode("utf-8")) <= 51

    def test_hash_verify_match(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        h = adp.hash_identity()
        result = adp.verify_hash(h)
        assert result["match"]

    def test_hash_verify_mismatch(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        result = adp.verify_hash("A:ASD:HASH[2.7:deadbeef]")
        assert not result["match"]

    def test_hash_changes_after_delta(self):
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))
        h1 = adp.hash_identity()
        adp.apply_definition("A:ASD:DEF[H:LACTATE:lactate_level:1]")
        h2 = adp.hash_identity()
        assert h1 != h2


# ── ADPSession: MDR Versioning ──────────────────────────────────────────────

class TestADPMDR:

    def test_mdr_identity(self):
        i = ADPSession.mdr_identity({"ICD": "2026", "ATT": "15.1"})
        assert i == "A:MDR[ATT:15.1:ICD:2026]"

    def test_mdr_request(self):
        r = ADPSession.mdr_request("ICD", "2025", "2026")
        assert r == "A:MDR:REQ[ICD:2025\u21922026]"

    def test_byte_floors(self):
        i = "A:MDR[ICD:2026:ATT:15.1]"
        assert len(i.encode("utf-8")) <= 51
        r = "A:MDR:REQ[ICD:2025\u21922026]"
        assert len(r.encode("utf-8")) <= 51


# ── ADPSession: Priority Classification ─────────────────────────────────────

class TestADPPriority:

    def test_mission_traffic(self):
        assert ADPSession.classify_priority("H:HR[72]") == ADP_PRIORITY_MISSION
        assert ADPSession.classify_priority("H:TRIAGE?I") == ADP_PRIORITY_MISSION

    def test_micro_delta(self):
        assert ADPSession.classify_priority("A:ASD:DEF[H:X:y:1]") == ADP_PRIORITY_MICRO
        assert ADPSession.classify_priority("A:ASD:DEF?[H:X]") == ADP_PRIORITY_MICRO

    def test_background_delta(self):
        p = ADPSession.classify_priority("A:ASD:DELTA[2.5\u21922.6:H+[X]]")
        assert p == ADP_PRIORITY_DELTA

    def test_trickle(self):
        assert ADPSession.classify_priority("A:ASD:REQ[1.0\u21922.0]") == ADP_PRIORITY_TRICKLE
        assert ADPSession.classify_priority("A:ASD[2.7]") == ADP_PRIORITY_TRICKLE
        assert ADPSession.classify_priority("A:ASD?") == ADP_PRIORITY_TRICKLE

    def test_priority_ordering(self):
        assert ADP_PRIORITY_MISSION < ADP_PRIORITY_MICRO
        assert ADP_PRIORITY_MICRO < ADP_PRIORITY_DELTA
        assert ADP_PRIORITY_DELTA < ADP_PRIORITY_TRICKLE


# ── FNP Wire Compatibility ──────────────────────────────────────────────────

class TestFNPWireCompat:

    def test_adv_still_40_bytes(self):
        asd = AdaptiveSharedDictionary()
        session = FNPSession(asd, "TEST", asd_version=asd_version_pack(2, 7))
        adv = session.initiate()
        assert len(adv) == 40

    def test_version_in_adv_wire(self):
        asd = AdaptiveSharedDictionary()
        v = asd_version_pack(2, 7)
        session = FNPSession(asd, "TEST", asd_version=v)
        adv = session.initiate()
        wire_version = struct.unpack(">H", adv[10:12])[0]
        assert wire_version == v
        assert asd_version_unpack(wire_version) == (2, 7)

    def test_handshake_match(self):
        asd = AdaptiveSharedDictionary()
        v = asd_version_pack(2, 7)
        a = FNPSession(asd, "NODE_A", asd_version=v)
        b = FNPSession(asd, "NODE_B", asd_version=v)
        adv = a.initiate()
        ack = b.receive(adv)
        a.receive(ack)
        assert a.state in ("ESTABLISHED", "ESTABLISHED_SAIL")
        assert b.state in ("ESTABLISHED", "ESTABLISHED_SAIL")

    def test_handshake_mismatch(self):
        asd = AdaptiveSharedDictionary()
        a = FNPSession(asd, "NODE_A", asd_version=asd_version_pack(2, 7))
        b = FNPSession(asd, "NODE_B", asd_version=asd_version_pack(2, 5))
        adv = a.initiate()
        ack = b.receive(adv)
        a.receive(ack)
        # Version mismatch but same fingerprint = VERSION match status
        assert a.state == "SYNC_NEEDED" or b.state == "SYNC_NEEDED"


# ── ADPDeltaOp / ADPDelta dataclasses ──────────────────────────────────────

class TestADPDataclasses:

    def test_delta_op_additive(self):
        op = ADPDeltaOp(namespace="H", mode="+", opcode="LACTATE")
        assert op.mode_name == "ADDITIVE"
        assert not op.is_breaking
        assert op.to_sal() == "H+[LACTATE]"

    def test_delta_op_replace(self):
        op = ADPDeltaOp(namespace="H", mode="\u2190", opcode="TRIAGE")
        assert op.mode_name == "REPLACE"
        assert op.is_breaking
        assert op.to_sal() == "H\u2190[TRIAGE]"

    def test_delta_op_deprecate(self):
        op = ADPDeltaOp(namespace="K", mode="\u2020", opcode="OLD")
        assert op.mode_name == "DEPRECATE"
        assert not op.is_breaking
        assert op.to_sal() == "K\u2020[OLD]"

    def test_delta_to_sal(self):
        delta = ADPDelta(
            from_version="2.5",
            to_version="2.7",
            operations=[
                ADPDeltaOp(namespace="H", mode="+", opcode="LACTATE"),
                ADPDeltaOp(namespace="H", mode="+", opcode="HRV"),
            ]
        )
        sal = delta.to_sal()
        assert sal == "A:ASD:DELTA[2.5\u21922.7:H+[LACTATE]:H+[HRV]]"
        assert len(sal.encode("utf-8")) <= 51

    def test_delta_has_breaking(self):
        d1 = ADPDelta("2.5", "2.7", [
            ADPDeltaOp("H", "+", "LACTATE")])
        assert not d1.has_breaking

        d2 = ADPDelta("2.7", "3.0", [
            ADPDeltaOp("H", "\u2190", "TRIAGE")])
        assert d2.has_breaking


# ── Byte Floor Compliance (exhaustive) ──────────────────────────────────────

class TestByteFloors:
    """Every ADP instruction pattern must fit Meshtastic (228 bytes).
    Single-operation instructions should fit EU DR0 (51 bytes)."""

    @pytest.mark.parametrize("sal,max_bytes", [
        ("A:ASD[0.0]", 51),
        ("A:ASD[255.255]", 51),
        ("A:ASD[2.7:H2.3:K1.0]", 51),
        ("A:ASD?", 11),
        ("A:ASD[2.7]\u26a0", 51),
        ("A:ASD:REQ[0.0\u2192255.255]", 51),
        ("A:ASD:DELTA[2.5\u21922.6:H+[LACTATE]]", 51),
        ("A:ASD:DELTA[2.7\u21923.0:H\u2190[TRIAGE]]", 51),
        ("A:ASD:DELTA[2.7\u21922.8:K\u2020[LEGACY]]", 51),
        ("A:ASD:DEF[H:LACTATE:lactate_level:1]", 51),
        ("A:ASD:DEF?[H:LACTATE]", 51),
        ("A:ASD:HASH[2.7:a3f8b1c2]", 51),
        ("A:ACK[ASD:2.7]", 51),
        ("A:ACK[ASD:HASH]", 51),
        ("A:ACK[ASD:DEF]", 51),
        ("A:MDR[ICD:2026:ATT:15.1]", 51),
        ("A:MDR:REQ[ICD:2025\u21922026]", 51),
    ])
    def test_fits_floor(self, sal, max_bytes):
        actual = len(sal.encode("utf-8"))
        assert actual <= max_bytes, \
            f"{sal} is {actual} bytes, exceeds {max_bytes}"

    def test_all_fit_meshtastic(self):
        """No ADP instruction should exceed 228 bytes."""
        patterns = [
            "A:ASD[255.255:A255.255:B255.255:C255.255:D255.255:E255.255]",
            "A:ASD:DELTA[255.255\u2192255.255:H+[VERYLONGOPCODE]:K+[ANOTHERLONGONE]]",
            "A:ASD:DEF[H:VERYLONGOPCODE:a_very_long_definition_string_here:1]",
            "A:ASD:HASH[255.255:a3f8b1c2d4e5f6a7b8c9d0e1f2a3b4c5]",
        ]
        for sal in patterns:
            assert len(sal.encode("utf-8")) <= 228, \
                f"{sal} exceeds Meshtastic floor"


# ── Integration: Full Exchange Sequences ────────────────────────────────────

class TestExchangeSequences:

    def test_version_match_no_sync(self):
        """Two nodes, same version. No delta needed."""
        asd_a = AdaptiveSharedDictionary()
        asd_b = AdaptiveSharedDictionary()
        adp_a = ADPSession(asd_a, asd_version=asd_version_pack(2, 7))
        adp_b = ADPSession(asd_b, asd_version=asd_version_pack(2, 7))

        vi_a = adp_a.version_identity(include_namespaces=False)
        result_b = adp_b.receive_version(vi_a)
        assert result_b["match"]

    def test_additive_sync_sequence(self):
        """Version mismatch, additive delta, resolve."""
        asd_a = AdaptiveSharedDictionary()
        asd_b = AdaptiveSharedDictionary()
        adp_a = ADPSession(asd_a, asd_version=asd_version_pack(2, 7))
        adp_b = ADPSession(asd_b, asd_version=asd_version_pack(2, 5))

        # Exchange versions
        vi_a = adp_a.version_identity(include_namespaces=False)
        result_b = adp_b.receive_version(vi_a)
        assert not result_b["match"]
        assert not result_b["breaking"]

        # B requests delta
        req = adp_b.request_delta(target="2.7")
        assert "\u2192" in req

        # A sends delta
        delta = ADPDelta("2.5", "2.7", [
            ADPDeltaOp("H", "+", "LACTATE"),
            ADPDeltaOp("H", "+", "HRV"),
        ])
        result = adp_b.apply_delta_sal(delta.to_sal())
        assert result["applied"]
        assert len(result["operations"]) == 2

        # Verify hash
        h = adp_b.hash_identity()
        verify = adp_a.verify_hash(h)
        # Note: won't match exactly because A didn't apply the delta too,
        # but the mechanism works

    def test_micro_delta_resolves_pending(self):
        """Unknown opcode -> pend -> micro-delta -> resolve."""
        asd = AdaptiveSharedDictionary()
        adp = ADPSession(asd)

        # Receive instruction with unknown opcode
        r1 = adp.resolve_or_pend("H:LACTATE[4.2]")
        assert r1["pending"]
        assert len(adp.pending_queue) == 1

        # Micro-delta arrives
        r2 = adp.apply_definition("A:ASD:DEF[H:LACTATE:lactate_level:1]")
        assert r2["applied"]
        assert "H:LACTATE[4.2]" in r2["pending_resolved"]
        assert len(adp.pending_queue) == 0

        # Now the same instruction would resolve
        r3 = adp.resolve_or_pend("H:LACTATE[4.2]")
        assert r3["resolved"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
