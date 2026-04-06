"""
OSMP SEC Tests — Security Envelope End-to-End

Covers:
  1. Envelope construction and round-trip (pack -> unpack)
  2. Signature verification (valid sender, wrong key rejected)
  3. AEAD integrity (tamper any byte, unpack returns None)
  4. Replay detection (monotonic sequence counter)
  5. Nonce derivation (node_id + sequence in associated data)
  6. All four wire modes through OSMPWireCodec
  7. Cross-node: two different SecCodecs, same symmetric key
  8. Overhead measurement: SEC adds fixed 87 bytes (2-byte node_id)
  9. Canonical test vectors through SEC and SAIL_SEC modes

Run: PYTHONPATH=sdk/python python3 -m pytest tests/test_sec.py -v
"""

import json
import os
import struct
import sys

import pytest

sys.path.insert(0, "sdk/python")

from osmp.wire import (
    SecCodec,
    SecEnvelope,
    OSMPWireCodec,
    SAILCodec,
    WireMode,
    NODE_ID_LONG,
    SEC_VERSION_1,
)


# ── FIXTURES ────────────────────────────────────────────────────────────────

@pytest.fixture
def keys():
    """Deterministic keys for reproducible tests."""
    return {
        "signing": b"\x01" * 32,
        "symmetric": b"\x02" * 32,
    }


@pytest.fixture
def node_a(keys):
    """Node A: 2-byte node ID."""
    return SecCodec(b"\x00\x01", keys["signing"], keys["symmetric"])


@pytest.fixture
def node_b(keys):
    """Node B: different node ID, same keys (shared secret)."""
    return SecCodec(b"\x00\x02", keys["signing"], keys["symmetric"])


@pytest.fixture
def node_a_long():
    """Node A with 4-byte node ID."""
    return SecCodec(b"\x00\x01\x02\x03", b"\x03" * 32, b"\x04" * 32)


@pytest.fixture
def wire_codec(keys):
    """Unified wire codec with SEC enabled."""
    return OSMPWireCodec(
        node_id=b"\x00\x01",
        signing_key=keys["signing"],
        symmetric_key=keys["symmetric"],
    )


@pytest.fixture
def vectors():
    """Canonical test vectors."""
    with open("protocol/test-vectors/canonical-test-vectors.json") as f:
        return json.load(f)["vectors"]


# ── SECTION 1: ENVELOPE ROUND-TRIP ──────────────────────────────────────────

class TestEnvelopeRoundTrip:
    """Pack a payload, unpack it, verify contents match."""

    def test_basic_round_trip(self, node_a):
        payload = b"H:HR@NODE1>120;H:CASREP;M:EVA@*"
        packed = node_a.pack(payload)
        env = node_a.unpack(packed)
        assert env is not None
        assert env.payload == payload

    def test_node_id_preserved(self, node_a):
        packed = node_a.pack(b"test")
        env = node_a.unpack(packed)
        assert env.node_id == b"\x00\x01"

    def test_wire_mode_preserved(self, node_a):
        packed = node_a.pack(b"test", WireMode.SEC)
        env = node_a.unpack(packed)
        assert env.mode == WireMode.SEC

    def test_sail_sec_mode_preserved(self, node_a):
        packed = node_a.pack(b"\xe0\x80\x8c", WireMode.SAIL_SEC)
        env = node_a.unpack(packed)
        assert env.mode == WireMode.SAIL_SEC

    def test_empty_payload(self, node_a):
        packed = node_a.pack(b"")
        env = node_a.unpack(packed)
        assert env is not None
        assert env.payload == b""

    def test_large_payload(self, node_a):
        payload = os.urandom(4096)
        packed = node_a.pack(payload)
        env = node_a.unpack(packed)
        assert env is not None
        assert env.payload == payload

    def test_long_node_id_round_trip(self, node_a_long):
        payload = b"R:ESTOP"
        packed = node_a_long.pack(payload)
        env = node_a_long.unpack(packed)
        assert env is not None
        assert env.payload == payload
        assert env.node_id == b"\x00\x01\x02\x03"

    def test_utf8_sal_payload(self, node_a):
        """SAL with Unicode glyphs survives SEC envelope."""
        sal = "I:\u00a7\u2192R:MOV@BOT1\u26a0"
        payload = sal.encode("utf-8")
        packed = node_a.pack(payload)
        env = node_a.unpack(packed)
        assert env is not None
        assert env.payload.decode("utf-8") == sal


# ── SECTION 2: SIGNATURE VERIFICATION ───────────────────────────────────────

class TestSignatureVerification:
    """Verify that wrong signing key is rejected."""

    def test_valid_signature_accepted(self, node_a):
        packed = node_a.pack(b"test")
        assert node_a.unpack(packed) is not None

    def test_wrong_signing_key_rejected(self, keys):
        sender = SecCodec(b"\x00\x01", b"\xAA" * 32, keys["symmetric"])
        receiver = SecCodec(b"\x00\x01", b"\xBB" * 32, keys["symmetric"])
        packed = sender.pack(b"test")
        assert receiver.unpack(packed) is None

    def test_wrong_symmetric_key_rejected(self, keys):
        sender = SecCodec(b"\x00\x01", keys["signing"], b"\xCC" * 32)
        receiver = SecCodec(b"\x00\x01", keys["signing"], b"\xDD" * 32)
        packed = sender.pack(b"test")
        assert receiver.unpack(packed) is None

    def test_both_keys_wrong_rejected(self):
        sender = SecCodec(b"\x00\x01", b"\x11" * 32, b"\x22" * 32)
        receiver = SecCodec(b"\x00\x01", b"\x33" * 32, b"\x44" * 32)
        packed = sender.pack(b"test")
        assert receiver.unpack(packed) is None


# ── SECTION 3: TAMPER DETECTION ─────────────────────────────────────────────

class TestTamperDetection:
    """Flip bytes in the envelope, verify unpack rejects."""

    def test_flip_payload_byte(self, node_a):
        packed = node_a.pack(b"H:HR@NODE1>120")
        tampered = bytearray(packed)
        mid = len(tampered) // 2
        tampered[mid] ^= 0xFF
        assert node_a.unpack(bytes(tampered)) is None

    def test_flip_auth_tag_byte(self, node_a):
        packed = node_a.pack(b"test")
        tampered = bytearray(packed)
        tag_start = len(tampered) - 64 - 16
        tampered[tag_start] ^= 0xFF
        assert node_a.unpack(bytes(tampered)) is None

    def test_flip_signature_byte(self, node_a):
        packed = node_a.pack(b"test")
        tampered = bytearray(packed)
        tampered[-1] ^= 0xFF
        assert node_a.unpack(bytes(tampered)) is None

    def test_flip_header_byte(self, node_a):
        packed = node_a.pack(b"test")
        tampered = bytearray(packed)
        tampered[0] ^= 0xFF
        assert node_a.unpack(bytes(tampered)) is None

    def test_flip_sequence_byte(self, node_a):
        packed = node_a.pack(b"test")
        tampered = bytearray(packed)
        tampered[3] ^= 0xFF  # sequence counter area
        assert node_a.unpack(bytes(tampered)) is None

    def test_truncated_envelope_rejected(self, node_a):
        packed = node_a.pack(b"test")
        assert node_a.unpack(packed[:50]) is None

    def test_too_short_rejected(self, node_a):
        assert node_a.unpack(b"\x00" * 10) is None

    def test_every_byte_position_tamper(self, node_a):
        """Flip every single byte position. Every one must fail."""
        packed = node_a.pack(b"H:HR@NODE1>120;H:CASREP")
        for i in range(len(packed)):
            tampered = bytearray(packed)
            tampered[i] ^= 0xFF
            result = node_a.unpack(bytes(tampered))
            assert result is None, f"Tamper at byte {i} was not detected"


# ── SECTION 4: REPLAY DETECTION ─────────────────────────────────────────────

class TestReplayDetection:
    """Monotonic sequence counter prevents replay."""

    def test_sequence_increments(self, node_a):
        p1 = node_a.pack(b"msg1")
        p2 = node_a.pack(b"msg2")
        p3 = node_a.pack(b"msg3")
        e1 = node_a.unpack(p1)
        e2 = node_a.unpack(p2)
        e3 = node_a.unpack(p3)
        assert e1.seq_counter == 1
        assert e2.seq_counter == 2
        assert e3.seq_counter == 3

    def test_sequence_is_monotonic(self, node_a):
        seqs = []
        for i in range(100):
            packed = node_a.pack(b"test")
            env = node_a.unpack(packed)
            seqs.append(env.seq_counter)
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 100  # all unique

    def test_sequence_starts_at_one(self, keys):
        fresh = SecCodec(b"\x00\x01", keys["signing"], keys["symmetric"])
        packed = fresh.pack(b"first")
        env = fresh.unpack(packed)
        assert env.seq_counter == 1

    def test_replayed_packet_has_same_sequence(self, node_a):
        """A replayed packet has the same seq as the original.
        Application layer must reject seq <= last_seen."""
        packed = node_a.pack(b"original")
        e1 = node_a.unpack(packed)
        e2 = node_a.unpack(packed)  # same bytes
        assert e1.seq_counter == e2.seq_counter
        # Both unpack successfully (SecCodec doesn't enforce replay).
        # The application layer checks seq_counter > last_seen.

    def test_sequence_in_wire_format(self, node_a):
        """Sequence counter is at bytes 3-6 (2-byte node_id) or 5-8 (4-byte)."""
        packed = node_a.pack(b"test")
        # mode(1) + node_id(2) + seq(4)
        seq_bytes = packed[3:7]
        seq = struct.unpack(">I", seq_bytes)[0]
        assert seq == 1


# ── SECTION 5: NONCE / ASSOCIATED DATA ──────────────────────────────────────

class TestNonceDerivation:
    """Associated data includes mode + node_id + sequence."""

    def test_different_node_ids_produce_different_envelopes(self, keys):
        a = SecCodec(b"\x00\x01", keys["signing"], keys["symmetric"])
        b = SecCodec(b"\x00\x02", keys["signing"], keys["symmetric"])
        pa = a.pack(b"same payload")
        pb = b.pack(b"same payload")
        # Different node_id means different AEAD associated data,
        # so auth tags differ even with same keys and payload
        assert pa != pb

    def test_same_payload_different_sequence_different_envelope(self, node_a):
        p1 = node_a.pack(b"same")
        p2 = node_a.pack(b"same")
        assert p1 != p2  # different seq counter

    def test_cross_node_same_keys_can_verify(self, keys):
        """Node A packs, Node B (same keys, different node_id) can still unpack
        because AEAD uses the header from the wire, not the receiver's node_id."""
        sender = SecCodec(b"\x00\x01", keys["signing"], keys["symmetric"])
        receiver = SecCodec(b"\x00\x02", keys["signing"], keys["symmetric"])
        packed = sender.pack(b"cross-node message")
        env = receiver.unpack(packed)
        assert env is not None
        assert env.payload == b"cross-node message"
        assert env.node_id == b"\x00\x01"  # sender's node_id


# ── SECTION 6: UNIFIED WIRE CODEC — ALL FOUR MODES ─────────────────────────

class TestUnifiedWireCodec:
    """All four modes through OSMPWireCodec round-trip."""

    SAL_SAMPLES = [
        "H:HR@NODE1>120",
        "R:MOV@BOT1\u21ba",
        "H:HR@NODE1>120;H:CASREP;M:EVA@*",
        "I:\u00a7\u2192R:MOV@BOT1\u26a0",
        "E:GPS@NODE1?0",
        "M:EVA@*",
        "R:ESTOP",
    ]

    @pytest.mark.parametrize("sal", SAL_SAMPLES)
    def test_mnemonic_round_trip(self, wire_codec, sal):
        encoded = wire_codec.encode(sal, WireMode.MNEMONIC)
        assert wire_codec.decode(encoded, WireMode.MNEMONIC) == sal

    @pytest.mark.parametrize("sal", SAL_SAMPLES)
    def test_sail_round_trip(self, wire_codec, sal):
        encoded = wire_codec.encode(sal, WireMode.SAIL)
        assert wire_codec.decode(encoded, WireMode.SAIL) == sal

    @pytest.mark.parametrize("sal", SAL_SAMPLES)
    def test_sec_round_trip(self, wire_codec, sal):
        encoded = wire_codec.encode(sal, WireMode.SEC)
        assert wire_codec.decode(encoded, WireMode.SEC) == sal

    @pytest.mark.parametrize("sal", SAL_SAMPLES)
    def test_sail_sec_round_trip(self, wire_codec, sal):
        encoded = wire_codec.encode(sal, WireMode.SAIL_SEC)
        assert wire_codec.decode(encoded, WireMode.SAIL_SEC) == sal

    def test_sec_rejects_tampered(self, wire_codec):
        encoded = wire_codec.encode("H:HR@NODE1>120", WireMode.SEC)
        tampered = bytearray(encoded)
        tampered[len(tampered) // 2] ^= 0xFF
        with pytest.raises(ValueError, match="Security envelope verification failed"):
            wire_codec.decode(bytes(tampered), WireMode.SEC)

    def test_sail_sec_rejects_tampered(self, wire_codec):
        encoded = wire_codec.encode("H:HR@NODE1>120", WireMode.SAIL_SEC)
        tampered = bytearray(encoded)
        tampered[len(tampered) // 2] ^= 0xFF
        with pytest.raises(ValueError, match="Security envelope verification failed"):
            wire_codec.decode(bytes(tampered), WireMode.SAIL_SEC)


# ── SECTION 7: OVERHEAD MEASUREMENT ────────────────────────────────────────

class TestOverheadMeasurement:
    """SEC envelope adds fixed overhead. Measure it."""

    def test_sec_overhead_2byte_node(self, node_a):
        payload = b"H:HR@NODE1>120"
        packed = node_a.pack(payload)
        overhead = len(packed) - len(payload)
        # mode(1) + node_id(2) + seq(4) + auth_tag(16) + signature(64) = 87
        assert overhead == 87

    def test_sec_overhead_4byte_node(self, node_a_long):
        payload = b"H:HR@NODE1>120"
        packed = node_a_long.pack(payload)
        overhead = len(packed) - len(payload)
        # mode(1) + node_id(4) + seq(4) + auth_tag(16) + signature(64) = 89
        assert overhead == 89

    def test_overhead_property(self, node_a):
        packed = node_a.pack(b"test")
        env = node_a.unpack(packed)
        assert env.overhead_bytes == 87
        assert env.total_bytes == 87 + len(b"test")

    def test_measure_all_modes(self, wire_codec):
        result = wire_codec.measure("H:HR@NODE1>120;H:CASREP;M:EVA@*")
        assert result["OSMP"]["roundtrip"] is True
        assert result["OSMP-SAIL"]["roundtrip"] is True
        assert result["OSMP-SEC"]["roundtrip"] is True
        assert result["OSMP-SAIL-SEC"]["roundtrip"] is True
        # SAIL should be smaller than mnemonic
        assert result["OSMP-SAIL"]["bytes"] < result["OSMP"]["bytes"]
        # SEC adds overhead
        assert result["OSMP-SEC"]["bytes"] > result["OSMP"]["bytes"]


# ── SECTION 8: CANONICAL VECTORS THROUGH SEC MODES ─────────────────────────

class TestCanonicalVectorsSEC:
    """Every canonical test vector must survive SEC and SAIL_SEC modes."""

    def test_all_vectors_sec_round_trip(self, wire_codec, vectors):
        failures = []
        for v in vectors:
            sal = v["encoded"]
            try:
                encoded = wire_codec.encode(sal, WireMode.SEC)
                decoded = wire_codec.decode(encoded, WireMode.SEC)
                if decoded != sal:
                    failures.append(f"{v['id']}: SEC mismatch {sal!r} -> {decoded!r}")
            except Exception as e:
                failures.append(f"{v['id']}: SEC error: {e}")
        assert not failures, "SEC round-trip failures:\n" + "\n".join(failures)

    def test_all_vectors_sail_sec_round_trip(self, wire_codec, vectors):
        failures = []
        for v in vectors:
            sal = v["encoded"]
            try:
                encoded = wire_codec.encode(sal, WireMode.SAIL_SEC)
                decoded = wire_codec.decode(encoded, WireMode.SAIL_SEC)
                if decoded != sal:
                    failures.append(f"{v['id']}: SAIL_SEC mismatch {sal!r} -> {decoded!r}")
            except Exception as e:
                failures.append(f"{v['id']}: SAIL_SEC error: {e}")
        assert not failures, "SAIL_SEC round-trip failures:\n" + "\n".join(failures)

    def test_all_vectors_tamper_detected(self, wire_codec, vectors):
        """Every vector: tamper one byte in SEC envelope, verify rejection."""
        for v in vectors[:10]:  # first 10 for speed
            sal = v["encoded"]
            encoded = wire_codec.encode(sal, WireMode.SEC)
            tampered = bytearray(encoded)
            tampered[len(tampered) // 2] ^= 0xFF
            with pytest.raises(ValueError):
                wire_codec.decode(bytes(tampered), WireMode.SEC)
