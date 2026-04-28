"""Pangram module tests — Python SDK."""

from __future__ import annotations

import hashlib

from osmp.pangram import (
    EXPECTED_PANGRAM_SHA256,
    PANGRAM_ASD_VERSION,
    PANGRAM_BODY,
    PANGRAM_MACRO_ID,
    PANGRAM_SHA256,
    PANGRAM_SHA256_TRUNCATED_16,
    PANGRAM_UTF8_BYTES,
    emit,
    emit_bytes,
    macro_invocation,
    metadata,
    verify_received,
)


def test_canonical_body_185_bytes():
    assert PANGRAM_UTF8_BYTES == 185


def test_canonical_sha256_matches_registered_fingerprint():
    assert PANGRAM_SHA256 == EXPECTED_PANGRAM_SHA256
    assert PANGRAM_SHA256 == (
        "fcefe9363ab737be174829dd8c12f4ca365fefb3601464514dd2aa4e1e0332ba"
    )


def test_truncated_sha256_is_first_16_hex_chars():
    assert PANGRAM_SHA256_TRUNCATED_16 == PANGRAM_SHA256[:16]
    assert PANGRAM_SHA256_TRUNCATED_16 == "fcefe9363ab737be"


def test_macro_id_is_PANGRAM():
    assert PANGRAM_MACRO_ID == "PANGRAM"


def test_asd_version_pinned_to_v15_1():
    assert PANGRAM_ASD_VERSION == "v15.1"


def test_emit_returns_canonical_body():
    assert emit() == PANGRAM_BODY


def test_emit_bytes_returns_utf8_bytes():
    assert emit_bytes() == PANGRAM_BODY.encode("utf-8")
    assert len(emit_bytes()) == 185


def test_verify_received_canonical_string():
    assert verify_received(PANGRAM_BODY) is True


def test_verify_received_canonical_bytes():
    assert verify_received(PANGRAM_BODY.encode("utf-8")) is True


def test_verify_received_modified_string():
    assert verify_received(PANGRAM_BODY + "X") is False


def test_verify_received_modified_byte():
    bad = bytearray(PANGRAM_BODY.encode("utf-8"))
    bad[0] = bad[0] ^ 1  # flip one bit in first byte
    assert verify_received(bytes(bad)) is False


def test_verify_received_truncated_match():
    assert verify_received(PANGRAM_BODY, truncated=True) is True


def test_verify_received_truncated_mismatch():
    assert verify_received(PANGRAM_BODY + "X", truncated=True) is False


def test_macro_invocation():
    assert macro_invocation() == "A:MACRO[PANGRAM]"


def test_metadata_keys():
    m = metadata()
    expected_keys = {
        "macro_id", "body", "byte_length_utf8", "sha256",
        "sha256_truncated_16", "asd_version", "namespaces_covered",
    }
    assert set(m.keys()) == expected_keys
    assert m["namespaces_covered"] == ["A", "D", "G", "H", "I", "L", "N", "R", "T"]


def test_pangram_validates_against_brigade_validator():
    """Sanity: the canonical pangram must validate against the SAL grammar."""
    from osmp.protocol import validate_composition
    result = validate_composition(PANGRAM_BODY)
    assert result.valid, f"Pangram failed validator: {[i.message for i in result.issues]}"


def test_pangram_sha256_is_deterministic_across_runs():
    """Re-compute SHA-256 from PANGRAM_BODY independently and compare."""
    h1 = hashlib.sha256(PANGRAM_BODY.encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(PANGRAM_BODY.encode("utf-8")).hexdigest()
    assert h1 == h2 == PANGRAM_SHA256


# ─────────────────────────────────────────────────────────────────────────
# Tier 2 — short-form pangram (LoRa floor)
# ─────────────────────────────────────────────────────────────────────────


def test_pangram_tiny_fits_lora_floor():
    from osmp.pangram import PANGRAM_TINY_UTF8_BYTES
    assert PANGRAM_TINY_UTF8_BYTES <= 51, (
        f"PANGRAM_TINY ({PANGRAM_TINY_UTF8_BYTES}B) violates LoRa floor 51B invariant"
    )


def test_pangram_tiny_canonical_sha256():
    from osmp.pangram import PANGRAM_TINY_SHA256, EXPECTED_PANGRAM_TINY_SHA256
    assert PANGRAM_TINY_SHA256 == EXPECTED_PANGRAM_TINY_SHA256
    assert PANGRAM_TINY_SHA256 == (
        "91c807dbbf3693ca57fb9b10ca39a5092d69de63df19b019217460e5e9c04564"
    )


def test_pangram_tiny_macro_id():
    from osmp.pangram import PANGRAM_TINY_MACRO_ID
    assert PANGRAM_TINY_MACRO_ID == "PANGRAM_TINY"


def test_pangram_tiny_validates_against_brigade_validator():
    from osmp.pangram import PANGRAM_TINY_BODY
    from osmp.protocol import validate_composition
    result = validate_composition(PANGRAM_TINY_BODY)
    assert result.valid, f"PANGRAM_TINY failed validator: {[i.message for i in result.issues]}"


def test_emit_for_tier_standard():
    from osmp.pangram import emit_for_tier, ChannelTier, PANGRAM_BODY
    assert emit_for_tier(ChannelTier.STANDARD) == PANGRAM_BODY


def test_emit_for_tier_lora_floor():
    from osmp.pangram import emit_for_tier, ChannelTier, PANGRAM_TINY_BODY
    assert emit_for_tier(ChannelTier.LORA_FLOOR) == PANGRAM_TINY_BODY


def test_emit_for_tier_unknown_raises():
    from osmp.pangram import emit_for_tier
    import pytest
    with pytest.raises(ValueError):
        emit_for_tier("unknown_tier")


def test_verify_for_tier_canonical_per_tier():
    from osmp.pangram import (
        verify_for_tier, ChannelTier, PANGRAM_BODY, PANGRAM_TINY_BODY,
    )
    # Each canonical body verifies against its own tier
    assert verify_for_tier(PANGRAM_BODY, ChannelTier.STANDARD) is True
    assert verify_for_tier(PANGRAM_TINY_BODY, ChannelTier.LORA_FLOOR) is True


def test_verify_for_tier_cross_tier_rejects():
    from osmp.pangram import (
        verify_for_tier, ChannelTier, PANGRAM_BODY, PANGRAM_TINY_BODY,
    )
    # Standard body does not verify against LoRa-floor canonical, and vice versa
    assert verify_for_tier(PANGRAM_BODY, ChannelTier.LORA_FLOOR) is False
    assert verify_for_tier(PANGRAM_TINY_BODY, ChannelTier.STANDARD) is False


def test_verify_for_tier_truncated_per_tier():
    from osmp.pangram import (
        verify_for_tier, ChannelTier, PANGRAM_BODY, PANGRAM_TINY_BODY,
    )
    assert verify_for_tier(PANGRAM_BODY, ChannelTier.STANDARD, truncated=True) is True
    assert verify_for_tier(PANGRAM_TINY_BODY, ChannelTier.LORA_FLOOR, truncated=True) is True


def test_pangram_tiny_exercises_minimum_primitives():
    """Cluster claim 4 minimum: frame, target, threshold, sequence, conjunction, CC."""
    from osmp.pangram import PANGRAM_TINY_BODY
    sal = PANGRAM_TINY_BODY
    assert ":" in sal  # frame structure
    assert "@" in sal  # target syntax
    assert ">" in sal  # threshold operator
    assert ";" in sal  # sequence operator
    assert "∧" in sal  # conjunction (∧)
    # At least one consequence class designator
    assert any(c in sal for c in "⚠↺⊘"), "no consequence class glyph"
