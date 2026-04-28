"""
Pangram Handshake — canonical demonstration instruction.

A single canonical demonstration instruction registered under a fixed macro
identifier and byte-identical across all conforming OSMP implementations. A
sender transmits the pangram as the first or among the first messages of a
session to a receiver in a pre-acquisition state. The receiver, by
deterministic decode (dictionary lookup) or by inference-driven single-shot
exemplar pattern recognition, acquires operational capability in the protocol
from one transmission.

The pangram body exercises a representative subset of SAL grammar across
nine namespaces. Receivers verify the canonical form by SHA-256 hash compare;
mismatch causes reversion to pre-acquisition state without applying received
content.

Patent pending. Inventor: Clay Holberg. License: Apache 2.0.
"""

from __future__ import annotations

import hashlib

# ── Canonical pangram body ──────────────────────────────────────────────────
#
# Locked at v15.1 of the OSMP Adaptive Shared Dictionary (released 2026-04-26).
# Any change to this string changes the SHA-256 and breaks cross-implementation
# hash-verify. Only modify in coordination with all conforming SDK releases and
# under a coordinated dictionary version bump.

PANGRAM_BODY: str = (
    "I:§→R:MOV@DRONE1[lat:34.05,lon:-118.25]⚠;"
    "H:HR>130→H:ALERT@*∧L:LOG@AUDIT;"
    "I:§→D:DEL@RECORD42⊘;"
    "G:POS@FLEET?∧T:SCHED[every:1h];"
    "A:MACRO[MESH:HLTH]→⊤;"
    "N:CFG[Δ:{ttl:30}]↺"
)

# Macro identifier under which the pangram is registered in the shared dictionary.
PANGRAM_MACRO_ID: str = "PANGRAM"

# ASD basis version against which the pangram body was constructed.
PANGRAM_ASD_VERSION: str = "v15.1"

# Computed once at import; matches the canonical SHA-256 fingerprint that every
# conforming SDK must produce from PANGRAM_BODY.
PANGRAM_SHA256: str = hashlib.sha256(PANGRAM_BODY.encode("utf-8")).hexdigest()

# 16-character truncated form for bandwidth-constrained channels.
PANGRAM_SHA256_TRUNCATED_16: str = PANGRAM_SHA256[:16]

# UTF-8 byte length of the canonical body.
PANGRAM_UTF8_BYTES: int = len(PANGRAM_BODY.encode("utf-8"))

# Canonical SHA-256, hardcoded for cross-SDK verification.
# Any divergence between PANGRAM_SHA256 (computed) and this constant indicates
# the pangram body was modified without updating the registered fingerprint.
EXPECTED_PANGRAM_SHA256: str = (
    "fcefe9363ab737be174829dd8c12f4ca365fefb3601464514dd2aa4e1e0332ba"
)

# Self-check at import: catch accidental modification of PANGRAM_BODY.
if PANGRAM_SHA256 != EXPECTED_PANGRAM_SHA256:
    raise RuntimeError(
        f"Pangram body has been modified — computed SHA-256 {PANGRAM_SHA256} "
        f"does not match registered fingerprint {EXPECTED_PANGRAM_SHA256}. "
        f"Restore the canonical body or coordinate a registered fingerprint update."
    )


# ── Tier 2: short-form pangram (LoRa-floor channels) ───────────────────────
#
# Tier-indexed canonical pangram for channel capabilities that cannot
# accommodate the standard-form 185-byte body. Constructed against the same
# v15.1 ASD basis but trimmed to fit the 51-byte LoRa floor while still
# exercising frame structure, target syntax, threshold operator, sequence
# operator, conjunction operator, a consequence class designator, the I:§
# authorization precondition, the THEN operator, and the query suffix.

PANGRAM_TINY_BODY: str = (
    "I:§→R:MOV@D⚠;H:HR>120→L:LOG@*?∧G:POS↺"
)

PANGRAM_TINY_MACRO_ID: str = "PANGRAM_TINY"

PANGRAM_TINY_SHA256: str = hashlib.sha256(
    PANGRAM_TINY_BODY.encode("utf-8")
).hexdigest()

PANGRAM_TINY_SHA256_TRUNCATED_16: str = PANGRAM_TINY_SHA256[:16]

PANGRAM_TINY_UTF8_BYTES: int = len(PANGRAM_TINY_BODY.encode("utf-8"))

EXPECTED_PANGRAM_TINY_SHA256: str = (
    "91c807dbbf3693ca57fb9b10ca39a5092d69de63df19b019217460e5e9c04564"
)

if PANGRAM_TINY_SHA256 != EXPECTED_PANGRAM_TINY_SHA256:
    raise RuntimeError(
        f"PANGRAM_TINY body has been modified — computed SHA-256 "
        f"{PANGRAM_TINY_SHA256} does not match registered fingerprint "
        f"{EXPECTED_PANGRAM_TINY_SHA256}. Restore the canonical body or "
        f"coordinate a registered fingerprint update."
    )

# Sanity: PANGRAM_TINY must fit the LoRa floor (51 bytes) by definition of
# its tier; assert at import to catch accidental growth.
if PANGRAM_TINY_UTF8_BYTES > 51:
    raise RuntimeError(
        f"PANGRAM_TINY ({PANGRAM_TINY_UTF8_BYTES}B) exceeds LoRa floor 51B; "
        f"tier 2 invariant violated."
    )


# ── Channel tier enumeration ───────────────────────────────────────────────


class ChannelTier:
    """Channel capability tier for pangram selection.

    The sender selects a tier based on the receiver's advertised channel
    capability (e.g., via Frame Negotiation Protocol) or on observed channel
    behavior. STANDARD is the default; LORA_FLOOR is for channels with
    payload size below the standard-form pangram's byte envelope.
    """

    LORA_FLOOR: str = "lora_floor"  # ≤ 51 bytes; uses PANGRAM_TINY
    STANDARD: str = "standard"      # ≤ ~220 bytes; uses PANGRAM


def emit_for_tier(tier: str = ChannelTier.STANDARD) -> str:
    """Return the canonical pangram body appropriate for the channel tier.

    Args:
      tier: ChannelTier.LORA_FLOOR or ChannelTier.STANDARD.

    Returns:
      The byte-identical canonical body for the tier; sender uses this in
      the handshake transmission.

    Raises:
      ValueError: if tier is not a known ChannelTier value.
    """
    if tier == ChannelTier.STANDARD:
        return PANGRAM_BODY
    if tier == ChannelTier.LORA_FLOOR:
        return PANGRAM_TINY_BODY
    raise ValueError(
        f"Unknown channel tier: {tier!r}. "
        f"Use ChannelTier.STANDARD or ChannelTier.LORA_FLOOR."
    )


def verify_for_tier(
    received: bytes | str,
    tier: str = ChannelTier.STANDARD,
    *,
    truncated: bool = False,
) -> bool:
    """Verify a received pangram against the tier-appropriate canonical hash.

    Args:
      received: the received pangram payload, bytes or UTF-8 string.
      tier: the tier the receiver advertised (or the sender's chosen tier
            for transmission).
      truncated: if True, compare only the first 16 hex characters.

    Returns:
      True if the received payload's SHA-256 matches the tier's canonical
      hash; False otherwise.
    """
    if isinstance(received, str):
        received_bytes = received.encode("utf-8")
    else:
        received_bytes = received
    received_hash = hashlib.sha256(received_bytes).hexdigest()

    if tier == ChannelTier.STANDARD:
        expected = PANGRAM_SHA256
    elif tier == ChannelTier.LORA_FLOOR:
        expected = PANGRAM_TINY_SHA256
    else:
        raise ValueError(
            f"Unknown channel tier: {tier!r}. "
            f"Use ChannelTier.STANDARD or ChannelTier.LORA_FLOOR."
        )

    if truncated:
        return received_hash[:16] == expected[:16]
    return received_hash == expected


# ─────────────────────────────────────────────────────────────────────────────
# Verification API (bounded-infection property)
# ─────────────────────────────────────────────────────────────────────────────


def verify_received(received: bytes | str, *, truncated: bool = False) -> bool:
    """Verify that a received byte sequence matches the canonical pangram.

    Computes SHA-256 of the received bytes and compares to the registered
    canonical hash. Returns True on match, False on mismatch. A receiver that
    invokes this function and observes False MUST revert to its pre-acquisition
    state without applying the received content (bounded-infection property).

    Args:
      received: the received pangram payload, as bytes or as UTF-8 string.
      truncated: if True, compare only the first 16 hex characters of the hash
                 (acceptable for bandwidth-constrained channels; NOT
                 recommended for safety-critical handshakes).

    Returns:
      True if the received payload's hash matches the canonical pangram; False
      otherwise.
    """
    if isinstance(received, str):
        received_bytes = received.encode("utf-8")
    else:
        received_bytes = received
    received_hash = hashlib.sha256(received_bytes).hexdigest()
    if truncated:
        return received_hash[:16] == PANGRAM_SHA256_TRUNCATED_16
    return received_hash == PANGRAM_SHA256


def emit() -> str:
    """Return the canonical pangram body as a UTF-8 string.

    The first agent in a bridged-session handshake transmits this string to
    the second agent as the first or among the first messages. The receiver
    invokes verify_received() on the received bytes before acquiring grammar
    from the demonstration.
    """
    return PANGRAM_BODY


def emit_bytes() -> bytes:
    """Return the canonical pangram body as UTF-8 bytes.

    Equivalent to emit().encode("utf-8"); convenience for transports that
    operate on byte buffers directly.
    """
    return PANGRAM_BODY.encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Macro registration helper
# ─────────────────────────────────────────────────────────────────────────────


def macro_invocation() -> str:
    """Return the macro-invocation form of the pangram.

    Equivalent to A:MACRO[PANGRAM]. A sender that knows the receiver already
    has the canonical pangram body in its dictionary can transmit the macro
    invocation (14 bytes) instead of the full body (185 bytes); the receiver
    expands locally. For a receiver in pre-acquisition state, the sender
    transmits the full body via emit().
    """
    return f"A:MACRO[{PANGRAM_MACRO_ID}]"


def metadata() -> dict:
    """Return a dict summarizing the pangram registration.

    Useful for prosecution exhibits, MCP `osmp://pangram` resource population,
    and cross-SDK parity test reporting.
    """
    return {
        "macro_id": PANGRAM_MACRO_ID,
        "body": PANGRAM_BODY,
        "byte_length_utf8": PANGRAM_UTF8_BYTES,
        "sha256": PANGRAM_SHA256,
        "sha256_truncated_16": PANGRAM_SHA256_TRUNCATED_16,
        "asd_version": PANGRAM_ASD_VERSION,
        "namespaces_covered": ["A", "D", "G", "H", "I", "L", "N", "R", "T"],
    }


__all__ = [
    # Standard tier (185-byte pangram)
    "PANGRAM_BODY",
    "PANGRAM_MACRO_ID",
    "PANGRAM_ASD_VERSION",
    "PANGRAM_SHA256",
    "PANGRAM_SHA256_TRUNCATED_16",
    "PANGRAM_UTF8_BYTES",
    "EXPECTED_PANGRAM_SHA256",
    "verify_received",
    "emit",
    "emit_bytes",
    "macro_invocation",
    "metadata",
    # LoRa-floor tier (48-byte pangram)
    "PANGRAM_TINY_BODY",
    "PANGRAM_TINY_MACRO_ID",
    "PANGRAM_TINY_SHA256",
    "PANGRAM_TINY_SHA256_TRUNCATED_16",
    "PANGRAM_TINY_UTF8_BYTES",
    "EXPECTED_PANGRAM_TINY_SHA256",
    # Tier-aware API
    "ChannelTier",
    "emit_for_tier",
    "verify_for_tier",
]
