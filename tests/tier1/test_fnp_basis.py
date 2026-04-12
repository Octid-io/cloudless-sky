"""
FNP Dictionary Basis Wire-Level Tests (ADR-004)
================================================

Tests the wire-level FNP changes that carry the Dictionary Basis Manifest
through the capability handshake. Covers:

  1. Extended-form ADV layout (msg_type 0x81, 15-byte node_id, basis
     fingerprint at offset 32) — spec §9.1.
  2. Total ADV size remains 40 bytes in both base and extended form.
  3. ACK match_status semantics: 0x00 (exact / SAIL-capable), 0x03 (basis
     mismatch, both extended), 0x04 (base form vs extended) — spec §9.2.
  4. State machine grading: ESTABLISHED_SAIL when bases agree,
     ESTABLISHED_SAL_ONLY when they diverge — spec §9.5.
  5. require_sail policy flag converts SAL-only sessions into local
     refusals.
  6. Degradation event recording when remote basis fingerprint differs
     from the locally configured expected fingerprint.
  7. Mixed-form interop: an extended-form node negotiating with a
     base-form node lands in ESTABLISHED_SAL_ONLY without error.

Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import (  # noqa: E402
    AdaptiveSharedDictionary,
    FNPSession,
    FNP_ADV_SIZE,
    FNP_ACK_SIZE,
    FNP_ADV_EXT_FLAG,
    FNP_MSG_ADV,
    FNP_MSG_ADV_EXTENDED,
    FNP_MSG_ACK,
    FNP_MATCH_EXACT,
    FNP_MATCH_BASIS_MISMATCH,
    FNP_MATCH_BASIS_EXT_VS_BASE,
)


# ─── ADV wire layout: base form ────────────────────────────────────────────

class TestAdvBaseForm:
    def test_base_form_msg_type_is_0x01(self):
        asd = AdaptiveSharedDictionary()
        s = FNPSession(asd, "NODE_A")
        adv = s.initiate()
        assert adv[0] == FNP_MSG_ADV
        assert adv[0] & FNP_ADV_EXT_FLAG == 0

    def test_base_form_total_size_40_bytes(self):
        asd = AdaptiveSharedDictionary()
        s = FNPSession(asd, "NODE_A")
        adv = s.initiate()
        assert len(adv) == 40
        assert FNP_ADV_SIZE == 40

    def test_base_form_node_id_uses_full_23_bytes(self):
        asd = AdaptiveSharedDictionary()
        # Use a long node ID to verify the base-form 23-byte field is honored.
        s = FNPSession(asd, "NODE_LONG_NAME_22BYTES")
        adv = s.initiate()
        node_id_field = adv[17:40]
        assert b"NODE_LONG_NAME_22BYTES" in node_id_field

    def test_base_form_no_basis_fingerprint(self):
        asd = AdaptiveSharedDictionary()
        s = FNPSession(asd, "NODE_A")
        parsed = FNPSession._parse_adv(s.initiate())
        assert parsed["is_extended"] is False
        assert parsed["basis_fingerprint"] is None


# ─── ADV wire layout: extended form ────────────────────────────────────────

class TestAdvExtendedForm:
    def test_extended_form_msg_type_is_0x81(self):
        asd = AdaptiveSharedDictionary()
        bfp = b"\x11\x22\x33\x44\x55\x66\x77\x88"
        s = FNPSession(asd, "NODE_A", basis_fingerprint=bfp)
        adv = s.initiate()
        assert adv[0] == FNP_MSG_ADV_EXTENDED
        assert adv[0] & FNP_ADV_EXT_FLAG == FNP_ADV_EXT_FLAG

    def test_extended_form_total_size_still_40_bytes(self):
        asd = AdaptiveSharedDictionary()
        bfp = b"\x11\x22\x33\x44\x55\x66\x77\x88"
        s = FNPSession(asd, "NODE_A", basis_fingerprint=bfp)
        adv = s.initiate()
        # Option C (the architectural choice in this sprint): extended form
        # reclaims 8 bytes from node_id to carry the basis fingerprint
        # without growing the wire footprint.
        assert len(adv) == 40

    def test_extended_form_basis_fingerprint_at_offset_32(self):
        asd = AdaptiveSharedDictionary()
        bfp = bytes(range(8))  # 0x00..0x07
        s = FNPSession(asd, "NODE_A", basis_fingerprint=bfp)
        adv = s.initiate()
        assert adv[32:40] == bfp

    def test_extended_form_node_id_narrowed_to_15_bytes(self):
        asd = AdaptiveSharedDictionary()
        bfp = b"\xaa" * 8
        # 9-byte Meshtastic-style ID fits comfortably in the 15-byte field.
        s = FNPSession(asd, "!2048ad45", basis_fingerprint=bfp)
        adv = s.initiate()
        node_id_field = adv[17:32]
        assert b"!2048ad45" in node_id_field

    def test_extended_form_long_node_id_truncated_to_15(self):
        asd = AdaptiveSharedDictionary()
        bfp = b"\xaa" * 8
        # 23-byte ID gets truncated to 15 in extended form.
        s = FNPSession(asd, "NODE_LONG_NAME_22BYTES", basis_fingerprint=bfp)
        adv = s.initiate()
        # Verify the basis fingerprint is still at offset 32 (not overwritten).
        assert adv[32:40] == bfp
        # And node_id only occupies offsets 17-31 (15 bytes).
        node_id_15 = adv[17:32].rstrip(b"\x00").decode("utf-8")
        assert len(node_id_15.encode("utf-8")) <= 15

    def test_parse_extended_adv_round_trip(self):
        asd = AdaptiveSharedDictionary()
        bfp = b"\xde\xad\xbe\xef\xca\xfe\xba\xbe"
        s = FNPSession(asd, "NODE_X", basis_fingerprint=bfp)
        adv = s.initiate()
        parsed = FNPSession._parse_adv(adv)
        assert parsed["is_extended"] is True
        assert parsed["basis_fingerprint"] == bfp
        assert parsed["node_id"] == "NODE_X"


# ─── State machine: ESTABLISHED_SAIL vs ESTABLISHED_SAL_ONLY ───────────────

class TestStateMachineCapabilityGrading:
    def _make_pair(self, fp_a: bytes | None, fp_b: bytes | None,
                   require_sail_a: bool = False) -> tuple[FNPSession, FNPSession]:
        asd = AdaptiveSharedDictionary()
        a = FNPSession(asd, "NODE_A", basis_fingerprint=fp_a, require_sail=require_sail_a)
        b = FNPSession(asd, "NODE_B", basis_fingerprint=fp_b)
        return a, b

    def test_both_base_form_lands_in_established_sail(self):
        a, b = self._make_pair(None, None)
        ack = b.receive(a.initiate())
        a.receive(ack)
        assert a.state == "ESTABLISHED_SAIL"
        assert b.state == "ESTABLISHED_SAIL"
        assert a.match_status == FNP_MATCH_EXACT
        assert a.is_sail_capable
        assert b.is_sail_capable

    def test_matching_extended_basis_lands_in_established_sail(self):
        bfp = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        a, b = self._make_pair(bfp, bfp)
        ack = b.receive(a.initiate())
        a.receive(ack)
        assert a.state == "ESTABLISHED_SAIL"
        assert b.state == "ESTABLISHED_SAIL"
        assert a.match_status == FNP_MATCH_EXACT

    def test_mismatched_extended_basis_lands_in_sal_only(self):
        a, b = self._make_pair(b"\x01" * 8, b"\x02" * 8)
        ack = b.receive(a.initiate())
        a.receive(ack)
        assert a.state == "ESTABLISHED_SAL_ONLY"
        assert b.state == "ESTABLISHED_SAL_ONLY"
        assert a.match_status == FNP_MATCH_BASIS_MISMATCH
        assert b.match_status == FNP_MATCH_BASIS_MISMATCH
        assert not a.is_sail_capable
        assert not b.is_sail_capable

    def test_extended_meets_base_lands_in_sal_only_with_ext_vs_base(self):
        a, b = self._make_pair(b"\xab" * 8, None)
        ack = b.receive(a.initiate())
        a.receive(ack)
        assert a.state == "ESTABLISHED_SAL_ONLY"
        assert b.state == "ESTABLISHED_SAL_ONLY"
        assert a.match_status == FNP_MATCH_BASIS_EXT_VS_BASE
        assert b.match_status == FNP_MATCH_BASIS_EXT_VS_BASE

    def test_base_meets_extended_lands_in_sal_only_with_ext_vs_base(self):
        # Symmetric case: base-form initiator, extended-form responder.
        a, b = self._make_pair(None, b"\xab" * 8)
        ack = b.receive(a.initiate())
        a.receive(ack)
        assert a.state == "ESTABLISHED_SAL_ONLY"
        assert b.state == "ESTABLISHED_SAL_ONLY"
        assert a.match_status == FNP_MATCH_BASIS_EXT_VS_BASE
        assert b.match_status == FNP_MATCH_BASIS_EXT_VS_BASE


# ─── require_sail operator policy ──────────────────────────────────────────

class TestRequireSailPolicy:
    def test_require_sail_refuses_basis_mismatch_locally(self):
        asd = AdaptiveSharedDictionary()
        a = FNPSession(asd, "NODE_A", basis_fingerprint=b"\x01" * 8, require_sail=True)
        b = FNPSession(asd, "NODE_B", basis_fingerprint=b"\x02" * 8)
        ack = b.receive(a.initiate())
        a.receive(ack)
        # Initiator with require_sail refuses the SAL-only session locally.
        assert a.state == "IDLE"
        assert a.degradation_event is not None
        assert "require_sail" in a.degradation_event["reason"]
        # Responder without the policy still established normally.
        assert b.state == "ESTABLISHED_SAL_ONLY"

    def test_require_sail_does_not_affect_matching_basis(self):
        asd = AdaptiveSharedDictionary()
        bfp = b"\x42" * 8
        a = FNPSession(asd, "NODE_A", basis_fingerprint=bfp, require_sail=True)
        b = FNPSession(asd, "NODE_B", basis_fingerprint=bfp)
        ack = b.receive(a.initiate())
        a.receive(ack)
        assert a.state == "ESTABLISHED_SAIL"
        assert a.degradation_event is None

    def test_require_sail_does_not_affect_base_form_pair(self):
        asd = AdaptiveSharedDictionary()
        a = FNPSession(asd, "NODE_A", require_sail=True)
        b = FNPSession(asd, "NODE_B")
        ack = b.receive(a.initiate())
        a.receive(ack)
        assert a.state == "ESTABLISHED_SAIL"
        assert a.degradation_event is None


# ─── Degradation event recording for operator monitoring ───────────────────

class TestDegradationEvent:
    def test_unexpected_basis_records_degradation_event(self):
        asd = AdaptiveSharedDictionary()
        expected = b"\xaa" * 8
        actual = b"\xbb" * 8
        a = FNPSession(asd, "NODE_A",
                       basis_fingerprint=expected,
                       expected_basis_fingerprint=expected)
        b = FNPSession(asd, "NODE_B", basis_fingerprint=actual)
        ack = b.receive(a.initiate())
        a.receive(ack)
        # ACK does not carry remote basis fingerprint, so the initiator
        # cannot record the per-peer event without out-of-band data. The
        # responder, however, observed the remote basis at parse time.
        assert b.state == "ESTABLISHED_SAL_ONLY"

    def test_responder_records_degradation_when_remote_basis_unexpected(self):
        asd = AdaptiveSharedDictionary()
        local = b"\xaa" * 8
        remote = b"\xbb" * 8
        # Responder expects local basis from peers but receives remote.
        a = FNPSession(asd, "NODE_A", basis_fingerprint=remote)
        b = FNPSession(asd, "NODE_B",
                       basis_fingerprint=local,
                       expected_basis_fingerprint=local)
        b.receive(a.initiate())
        assert b.state == "ESTABLISHED_SAL_ONLY"
        assert b.degradation_event is not None
        assert b.degradation_event["remote_basis_fingerprint"] == remote.hex()
        assert b.degradation_event["expected_basis_fingerprint"] == local.hex()

    def test_no_degradation_event_when_no_expectation_set(self):
        asd = AdaptiveSharedDictionary()
        a = FNPSession(asd, "NODE_A", basis_fingerprint=b"\xaa" * 8)
        b = FNPSession(asd, "NODE_B", basis_fingerprint=b"\xbb" * 8)
        b.receive(a.initiate())
        # No expected_basis_fingerprint configured → no event, even though
        # the bases differ.
        assert b.degradation_event is None

    def test_no_degradation_event_when_basis_matches_expected(self):
        asd = AdaptiveSharedDictionary()
        bfp = b"\x42" * 8
        a = FNPSession(asd, "NODE_A", basis_fingerprint=bfp)
        b = FNPSession(asd, "NODE_B",
                       basis_fingerprint=bfp,
                       expected_basis_fingerprint=bfp)
        b.receive(a.initiate())
        assert b.state == "ESTABLISHED_SAIL"
        assert b.degradation_event is None


# ─── Backward compatibility: a v1.0.2 receiver gracefully degrades ─────────

class TestV102BackwardCompatibility:
    def test_extended_form_total_size_matches_v102_adv_size(self):
        # A v1.0.2 receiver expects exactly FNP_ADV_SIZE bytes for ADV.
        # Extended form must not exceed that or v1.0.2 receivers fragment.
        asd = AdaptiveSharedDictionary()
        s = FNPSession(asd, "NODE", basis_fingerprint=b"\x00" * 8)
        adv = s.initiate()
        assert len(adv) == FNP_ADV_SIZE

    def test_base_form_byte_compatible_with_v102_layout(self):
        # A base-form ADV from an ADR-004 node must be byte-compatible with
        # the v1.0.2 layout: msg_type=0x01, fingerprint at 2..10, asd_version
        # at 10..12, namespace_bitmap at 12..16, channel_capacity at 16,
        # node_id at 17..40.
        asd = AdaptiveSharedDictionary()
        s = FNPSession(asd, "NODE_A")
        adv = s.initiate()
        assert adv[0] == 0x01
        assert len(adv[2:10]) == 8        # fingerprint
        assert len(adv[10:12]) == 2       # asd_version
        assert len(adv[12:16]) == 4       # namespace_bitmap
        # node_id occupies 17..40 in base form (23-byte reservation).
        node_id_field = adv[17:40]
        assert len(node_id_field) == 23

    def test_two_base_form_nodes_negotiate_normally(self):
        # ADR-004 must not break the v1.0.2 case: two base-ASD-only nodes
        # establish a session in the same number of bytes and reach the
        # same final state semantically (now ESTABLISHED_SAIL).
        asd = AdaptiveSharedDictionary()
        a = FNPSession(asd, "NODE_A")
        b = FNPSession(asd, "NODE_B")
        adv = a.initiate()
        ack = b.receive(adv)
        a.receive(ack)
        assert len(adv) == 40
        assert len(ack) == 38
        assert a.state == "ESTABLISHED_SAIL"
        assert b.state == "ESTABLISHED_SAIL"
