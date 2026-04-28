/**
 * Pangram Handshake — canonical demonstration instruction.
 *
 * The Pangram Handshake is a single canonical demonstration instruction
 * registered under a fixed macro identifier and byte-identical across all
 * conforming OSMP implementations. A sender transmits the pangram as the first
 * or among the first messages of a bridged session to a receiver in a
 * pre-acquisition state. The receiver, by deterministic decode (dictionary
 * lookup) or by inference-driven single-shot exemplar pattern recognition,
 * acquires operational capability in the protocol from one transmission.
 *
 * The pangram body exercises every essential grammatical primitive of SAL
 * across nine namespaces. Receivers verify the canonical form by SHA-256 hash
 * compare; mismatch causes reversion to pre-acquisition state without applying
 * received content (bounded-infection property).
 *
 * Cross-SDK byte-identical to Python `osmp.pangram` and Go `osmp.Pangram*`.
 *
 * Patent pending. Inventor: Clay Holberg. License: Apache 2.0.
 */

import { createHash } from "crypto";

// ── Canonical pangram body ──────────────────────────────────────────────────
//
// Locked at v15.1 of the OSMP Adaptive Shared Dictionary (released 2026-04-26).
// Any change to this string changes the SHA-256 and breaks cross-implementation
// hash-verify.

export const PANGRAM_BODY: string =
  "I:§→R:MOV@DRONE1[lat:34.05,lon:-118.25]⚠;" +
  "H:HR>130→H:ALERT@*∧L:LOG@AUDIT;" +
  "I:§→D:DEL@RECORD42⊘;" +
  "G:POS@FLEET?∧T:SCHED[every:1h];" +
  "A:MACRO[MESH:HLTH]→⊤;" +
  "N:CFG[Δ:{ttl:30}]↺";

export const PANGRAM_MACRO_ID: string = "PANGRAM";
export const PANGRAM_ASD_VERSION: string = "v15.1";

export const PANGRAM_SHA256: string = createHash("sha256")
  .update(Buffer.from(PANGRAM_BODY, "utf-8"))
  .digest("hex");

export const PANGRAM_SHA256_TRUNCATED_16: string = PANGRAM_SHA256.slice(0, 16);

export const PANGRAM_UTF8_BYTES: number = Buffer.byteLength(PANGRAM_BODY, "utf-8");

// Canonical SHA-256, hardcoded for cross-SDK verification. Any divergence
// between PANGRAM_SHA256 (computed) and this constant indicates the pangram
// body was modified without updating the registered fingerprint.
export const EXPECTED_PANGRAM_SHA256: string =
  "fcefe9363ab737be174829dd8c12f4ca365fefb3601464514dd2aa4e1e0332ba";

if (PANGRAM_SHA256 !== EXPECTED_PANGRAM_SHA256) {
  throw new Error(
    `Pangram body has been modified — computed SHA-256 ${PANGRAM_SHA256} ` +
      `does not match registered fingerprint ${EXPECTED_PANGRAM_SHA256}. ` +
      `Restore the canonical body or coordinate a registered fingerprint update.`,
  );
}

// ── Tier 2: short-form pangram (LoRa-floor channels) ───────────────────────
//
// Tier-indexed canonical pangram for channel capabilities that cannot
// accommodate the standard-form 185-byte body. Constructed against the same
// v15.1 ASD basis but trimmed to fit the 51-byte LoRa floor while still
// exercising frame structure, target syntax, threshold operator, sequence
// operator, conjunction operator, a consequence class designator, the I:§
// authorization precondition, the THEN operator, and the query suffix.

export const PANGRAM_TINY_BODY: string =
  "I:§→R:MOV@D⚠;H:HR>120→L:LOG@*?∧G:POS↺";

export const PANGRAM_TINY_MACRO_ID: string = "PANGRAM_TINY";

export const PANGRAM_TINY_SHA256: string = createHash("sha256")
  .update(Buffer.from(PANGRAM_TINY_BODY, "utf-8"))
  .digest("hex");

export const PANGRAM_TINY_SHA256_TRUNCATED_16: string =
  PANGRAM_TINY_SHA256.slice(0, 16);

export const PANGRAM_TINY_UTF8_BYTES: number = Buffer.byteLength(
  PANGRAM_TINY_BODY,
  "utf-8",
);

export const EXPECTED_PANGRAM_TINY_SHA256: string =
  "91c807dbbf3693ca57fb9b10ca39a5092d69de63df19b019217460e5e9c04564";

if (PANGRAM_TINY_SHA256 !== EXPECTED_PANGRAM_TINY_SHA256) {
  throw new Error(
    `PANGRAM_TINY body has been modified — computed SHA-256 ` +
      `${PANGRAM_TINY_SHA256} does not match registered fingerprint ` +
      `${EXPECTED_PANGRAM_TINY_SHA256}. Restore the canonical body or ` +
      `coordinate a registered fingerprint update.`,
  );
}

if (PANGRAM_TINY_UTF8_BYTES > 51) {
  throw new Error(
    `PANGRAM_TINY (${PANGRAM_TINY_UTF8_BYTES}B) exceeds LoRa floor 51B; ` +
      `tier 2 invariant violated.`,
  );
}

// ── Channel tier enumeration ───────────────────────────────────────────────

export enum ChannelTier {
  LoraFloor = "lora_floor", // ≤ 51 bytes; uses PANGRAM_TINY
  Standard = "standard", // ≤ ~220 bytes; uses PANGRAM
}

/**
 * Return the canonical pangram body appropriate for the channel tier.
 * The sender selects a tier based on the receiver's advertised channel
 * capability (e.g., via Frame Negotiation Protocol) or on observed channel
 * behavior.
 */
export function emitForTier(tier: ChannelTier = ChannelTier.Standard): string {
  if (tier === ChannelTier.Standard) return PANGRAM_BODY;
  if (tier === ChannelTier.LoraFloor) return PANGRAM_TINY_BODY;
  throw new Error(`Unknown channel tier: ${String(tier)}`);
}

/**
 * Verify a received pangram against the tier-appropriate canonical hash.
 */
export function verifyForTier(
  received: Buffer | Uint8Array | string,
  tier: ChannelTier = ChannelTier.Standard,
  options: { truncated?: boolean } = {},
): boolean {
  const bytes =
    typeof received === "string"
      ? Buffer.from(received, "utf-8")
      : Buffer.from(received);
  const receivedHash = createHash("sha256").update(bytes).digest("hex");
  let expected: string;
  if (tier === ChannelTier.Standard) expected = PANGRAM_SHA256;
  else if (tier === ChannelTier.LoraFloor) expected = PANGRAM_TINY_SHA256;
  else throw new Error(`Unknown channel tier: ${String(tier)}`);
  if (options.truncated) {
    return receivedHash.slice(0, 16) === expected.slice(0, 16);
  }
  return receivedHash === expected;
}

// ─────────────────────────────────────────────────────────────────────────────
// Verification API (bounded-infection property)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Verify that a received byte sequence matches the canonical pangram.
 *
 * Computes SHA-256 of the received bytes and compares to the registered
 * canonical hash. Returns true on match, false on mismatch. A receiver that
 * invokes this function and observes false MUST revert to its pre-acquisition
 * state without applying the received content (bounded-infection property).
 *
 * @param received - the received pangram payload, as Buffer/Uint8Array or
 *                   UTF-8 string.
 * @param options.truncated - if true, compare only the first 16 hex characters
 *                            of the hash (acceptable for bandwidth-constrained
 *                            channels; NOT recommended for safety-critical
 *                            handshakes).
 */
export function verifyReceived(
  received: Buffer | Uint8Array | string,
  options: { truncated?: boolean } = {},
): boolean {
  const bytes =
    typeof received === "string"
      ? Buffer.from(received, "utf-8")
      : Buffer.from(received);
  const receivedHash = createHash("sha256").update(bytes).digest("hex");
  if (options.truncated) {
    return receivedHash.slice(0, 16) === PANGRAM_SHA256_TRUNCATED_16;
  }
  return receivedHash === PANGRAM_SHA256;
}

/**
 * Return the canonical pangram body as a UTF-8 string.
 *
 * The first agent in a bridged-session handshake transmits this string to the
 * second agent. The receiver invokes verifyReceived() on the received bytes
 * before acquiring grammar from the demonstration.
 */
export function emit(): string {
  return PANGRAM_BODY;
}

/** Return the canonical pangram body as a UTF-8 byte Buffer. */
export function emitBytes(): Buffer {
  return Buffer.from(PANGRAM_BODY, "utf-8");
}

// ─────────────────────────────────────────────────────────────────────────────
// Macro registration helper
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Return the macro-invocation form of the pangram.
 *
 * Equivalent to A:MACRO[PANGRAM]. A sender that knows the receiver already
 * has the canonical pangram body in its dictionary can transmit the macro
 * invocation (14 bytes) instead of the full body (185 bytes); the receiver
 * expands locally. For a receiver in pre-acquisition state, the sender
 * transmits the full body via emit().
 */
export function macroInvocation(): string {
  return `A:MACRO[${PANGRAM_MACRO_ID}]`;
}

export interface PangramMetadata {
  macroId: string;
  body: string;
  byteLengthUtf8: number;
  sha256: string;
  sha256Truncated16: string;
  asdVersion: string;
  namespacesCovered: string[];
}

/** Return a metadata object summarizing the pangram registration. */
export function metadata(): PangramMetadata {
  return {
    macroId: PANGRAM_MACRO_ID,
    body: PANGRAM_BODY,
    byteLengthUtf8: PANGRAM_UTF8_BYTES,
    sha256: PANGRAM_SHA256,
    sha256Truncated16: PANGRAM_SHA256_TRUNCATED_16,
    asdVersion: PANGRAM_ASD_VERSION,
    namespacesCovered: ["A", "D", "G", "H", "I", "L", "N", "R", "T"],
  };
}
