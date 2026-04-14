"""
Real Cryptography Verification Tests (Findings 4/31)
====================================================

These tests verify that the SecCodec is actually doing real Ed25519 +
ChaCha20-Poly1305 cryptography, not the HMAC-SHA256 placeholder it shipped
with. The properties tested are cryptographic guarantees that the placeholder
silently failed to provide:

  1. Ed25519 signatures are actually 64 bytes of real RFC 8032 output, not
     two concatenated SHA256 digests.
  2. Wrong sender public keys cause verification to fail (placeholder used
     symmetric HMAC and accepted any matching key).
  3. ChaCha20-Poly1305 actually encrypts the payload — the on-wire bytes
     differ from the plaintext input (placeholder shipped plaintext).
  4. AEAD integrity rejects tampering anywhere in the envelope.
  5. Cross-codec verification: codec A signs, codec B verifies with A's
     public key, and verification succeeds.
  6. Wire format compatibility with the placeholder: 87-byte overhead for
     a 2-byte node_id envelope (1 mode + 2 nid + 4 seq + 16 tag + 64 sig).

The test suite intentionally uses deterministic seeds so that any future
regression will produce a reproducible cryptographic mismatch.

Patent pending -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.wire import SecCodec, WireMode  # noqa: E402


# ── Test fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def alice_keys():
    """Deterministic Ed25519 + ChaCha20-Poly1305 keys for Alice."""
    return {
        "node_id": b"\xa0\x01",
        "signing_key": bytes(range(32)),                  # 0x00..0x1f
        "symmetric_key": bytes(range(32, 64)),            # 0x20..0x3f
    }


@pytest.fixture
def bob_keys():
    """Deterministic Ed25519 + ChaCha20-Poly1305 keys for Bob."""
    return {
        "node_id": b"\xb0\x02",
        "signing_key": bytes(range(64, 96)),              # 0x40..0x5f
        "symmetric_key": bytes(range(32, 64)),            # SAME symmetric as Alice
    }


@pytest.fixture
def alice(alice_keys):
    return SecCodec(**alice_keys)


@pytest.fixture
def bob(bob_keys):
    return SecCodec(**bob_keys)


# ── Real Ed25519 properties ─────────────────────────────────────────────────


class TestEd25519Properties:
    """Verify that signatures are actually Ed25519, not HMAC-SHA256."""

    def test_signature_length_64_bytes(self, alice):
        sig = alice._sign(b"hello world")
        assert len(sig) == 64

    def test_signature_is_deterministic(self, alice):
        """Ed25519 signatures over the same message and key are deterministic
        per RFC 8032 (unlike ECDSA which is randomized)."""
        sig1 = alice._sign(b"deterministic message")
        sig2 = alice._sign(b"deterministic message")
        assert sig1 == sig2

    def test_different_messages_different_signatures(self, alice):
        sig_a = alice._sign(b"message A")
        sig_b = alice._sign(b"message B")
        assert sig_a != sig_b

    def test_different_keys_different_signatures(self, alice, bob):
        msg = b"identical message"
        assert alice._sign(msg) != bob._sign(msg)

    def test_alice_signature_verifies_with_alice_pubkey(self, alice):
        sig = alice._sign(b"signed by alice")
        assert alice._verify(b"signed by alice", sig) is True

    def test_alice_signature_fails_with_bob_pubkey(self, alice, bob):
        sig = alice._sign(b"signed by alice")
        # Verify with bob's public key, not alice's
        assert alice._verify(
            b"signed by alice", sig, verify_key=bob.public_signing_key
        ) is False

    def test_tampered_signature_rejected(self, alice):
        sig = alice._sign(b"original message")
        tampered = bytes([sig[0] ^ 0x01]) + sig[1:]
        assert alice._verify(b"original message", tampered) is False

    def test_tampered_message_rejected(self, alice):
        sig = alice._sign(b"original message")
        assert alice._verify(b"tampered message", sig) is False

    def test_public_key_is_32_bytes(self, alice):
        pk = alice.public_signing_key
        assert len(pk) == 32

    def test_public_key_is_deterministic_from_seed(self, alice_keys):
        codec1 = SecCodec(**alice_keys)
        codec2 = SecCodec(**alice_keys)
        assert codec1.public_signing_key == codec2.public_signing_key


# ── Real ChaCha20-Poly1305 properties ───────────────────────────────────────


class TestChaCha20Poly1305Properties:
    """Verify that the AEAD layer is actually encrypting, not just authenticating."""

    def test_payload_is_actually_encrypted(self, alice):
        """The placeholder shipped plaintext on the wire. Real AEAD must
        produce ciphertext that differs from the input."""
        plaintext = b"this is a secret payload that should not appear in plaintext"
        envelope = alice.pack(plaintext)
        # The plaintext substring must NOT appear in the envelope bytes
        assert plaintext not in envelope, (
            "Findings 4/31 regression: payload appears in plaintext on the wire. "
            "ChaCha20-Poly1305 should produce ciphertext."
        )

    def test_auth_tag_length_16_bytes(self, alice):
        """ChaCha20-Poly1305 produces a 16-byte Poly1305 tag."""
        envelope = alice.pack(b"test payload")
        parsed = alice.unpack(envelope)
        assert parsed is not None
        assert len(parsed.auth_tag) == 16

    def test_tampering_payload_rejected(self, alice):
        envelope = alice.pack(b"original payload")
        # Flip a bit in the payload region (byte 10 is in the payload)
        tampered = envelope[:10] + bytes([envelope[10] ^ 0x01]) + envelope[11:]
        result = alice.unpack(tampered)
        assert result is None

    def test_tampering_header_rejected(self, alice):
        envelope = alice.pack(b"original payload")
        # Flip a bit in the seq counter region (header byte 4)
        tampered = envelope[:4] + bytes([envelope[4] ^ 0x01]) + envelope[5:]
        result = alice.unpack(tampered)
        assert result is None

    def test_tampering_auth_tag_rejected(self, alice):
        envelope = alice.pack(b"original payload")
        # auth_tag is 16 bytes, located at -80 from end (signature is last 64)
        tag_offset = len(envelope) - 80
        tampered = (envelope[:tag_offset]
                    + bytes([envelope[tag_offset] ^ 0x01])
                    + envelope[tag_offset + 1:])
        result = alice.unpack(tampered)
        assert result is None

    def test_roundtrip_decrypts_to_original(self, alice):
        plaintext = b"hello, world, this is the OSMP security envelope"
        envelope = alice.pack(plaintext)
        parsed = alice.unpack(envelope)
        assert parsed is not None
        assert parsed.payload == plaintext


# ── Cross-codec interop ─────────────────────────────────────────────────────


class TestCrossCodecInterop:
    """Two codecs sharing a symmetric key but with distinct Ed25519 keypairs.

    This is the realistic deployment model: nodes share a network key
    distributed by an out-of-band MDR identity service, and each node has
    its own Ed25519 identity for signing."""

    def test_alice_and_bob_share_symmetric_key(self, alice_keys, bob_keys):
        assert alice_keys["symmetric_key"] == bob_keys["symmetric_key"]

    def test_bob_can_verify_alice_envelope(self, alice, bob):
        """Bob receives an envelope from Alice. Bob has Alice's public key
        out-of-band. Bob's verify call must succeed."""
        envelope = alice.pack(b"hello bob, from alice")
        # Bob constructs a fresh codec with the symmetric key but uses
        # Alice's public key for verification
        bob_with_alice_pubkey = SecCodec(
            node_id=b"\xb0\x02",
            signing_key=bytes(range(64, 96)),
            symmetric_key=bytes(range(32, 64)),
            verify_key=alice.public_signing_key,
        )
        parsed = bob_with_alice_pubkey.unpack(envelope)
        assert parsed is not None
        assert parsed.payload == b"hello bob, from alice"

    def test_envelope_from_alice_fails_without_alice_pubkey(self, alice, bob):
        """Without Alice's public key, Bob's loopback verification fails
        because Bob would try to verify with his own (wrong) public key."""
        envelope = alice.pack(b"hello bob, from alice")
        # Bob uses default loopback verification (his own pubkey)
        parsed = bob.unpack(envelope)
        assert parsed is None


# ── Wire format compatibility ───────────────────────────────────────────────


class TestWireFormatCompatibility:
    """The real-crypto SecCodec must produce envelopes with the same byte
    layout as the placeholder so cross-SDK and historical compat is preserved."""

    def test_short_node_id_overhead_87_bytes(self, alice):
        """2-byte node_id envelope: 1 (mode) + 2 (nid) + 4 (seq) + N (payload)
        + 16 (tag) + 64 (sig) = 87 + N."""
        envelope = alice.pack(b"")
        assert len(envelope) == 87

    def test_long_node_id_overhead_89_bytes(self):
        """4-byte node_id envelope: 1 + 4 + 4 + N + 16 + 64 = 89 + N."""
        codec = SecCodec(
            node_id=b"\xa0\x01\x02\x03",
            signing_key=bytes(range(32)),
            symmetric_key=bytes(range(32, 64)),
        )
        envelope = codec.pack(b"")
        assert len(envelope) == 89

    def test_payload_size_preserved(self, alice):
        """Real ChaCha20-Poly1305 produces ciphertext the same length as
        plaintext (the tag is separate). The envelope grows by overhead+payload."""
        for n in [0, 1, 10, 50, 100, 500]:
            envelope = alice.pack(b"X" * n)
            assert len(envelope) == 87 + n

    def test_envelope_unpacks_to_correct_seq(self, alice):
        """Sequence counters must be monotonic and visible in the parsed envelope."""
        envelope1 = alice.pack(b"first")
        envelope2 = alice.pack(b"second")
        parsed1 = alice.unpack(envelope1)
        parsed2 = alice.unpack(envelope2)
        assert parsed1.seq_counter == 1
        assert parsed2.seq_counter == 2


# ── Constructor validation ──────────────────────────────────────────────────


class TestConstructorValidation:
    """Real cryptographic primitives have strict key sizes. The constructor
    must reject malformed keys instead of silently working with garbage
    (the placeholder accepted any byte length)."""

    def test_signing_key_must_be_32_bytes(self):
        with pytest.raises(ValueError, match="signing_key must be 32 bytes"):
            SecCodec(node_id=b"\x00\x01", signing_key=b"\x00" * 16)

    def test_symmetric_key_must_be_32_bytes(self):
        with pytest.raises(ValueError, match="symmetric_key must be 32 bytes"):
            SecCodec(
                node_id=b"\x00\x01",
                signing_key=b"\x00" * 32,
                symmetric_key=b"\x00" * 16,
            )

    def test_verify_key_must_be_32_bytes(self):
        with pytest.raises(ValueError, match="verify_key must be 32 bytes"):
            SecCodec(
                node_id=b"\x00\x01",
                signing_key=b"\x00" * 32,
                symmetric_key=b"\x00" * 32,
                verify_key=b"\x00" * 16,
            )

    def test_node_id_must_be_2_or_4_bytes(self):
        with pytest.raises(ValueError, match="node_id must be 2 or 4 bytes"):
            SecCodec(node_id=b"\x00\x01\x02")


# ── Marker test for findings ────────────────────────────────────────────────


def test_findings_4_31_marker():
    """Single-line marker that explicitly references Findings 4/31. If this
    test fails, the SecCodec has lost its real cryptographic implementation
    and reverted to a placeholder."""
    codec = SecCodec(
        node_id=b"\x00\x01",
        signing_key=bytes(range(32)),
        symmetric_key=bytes(range(32, 64)),
    )
    plaintext = b"the marker payload"
    envelope = codec.pack(plaintext)
    assert plaintext not in envelope, (
        "Findings 4/31 regression: SecCodec is shipping plaintext on the wire. "
        "ChaCha20-Poly1305 must encrypt the payload."
    )
    parsed = codec.unpack(envelope)
    assert parsed is not None
    assert parsed.payload == plaintext, (
        "Findings 4/31 regression: roundtrip failed."
    )
