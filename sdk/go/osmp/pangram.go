// Pangram Handshake — canonical demonstration instruction.
//
// The Pangram Handshake is a single canonical demonstration instruction
// registered under a fixed macro identifier and byte-identical across all
// conforming OSMP implementations. A sender transmits the pangram as the first
// or among the first messages of a bridged session to a receiver in a
// pre-acquisition state. The receiver, by deterministic decode (dictionary
// lookup) or by inference-driven single-shot exemplar pattern recognition,
// acquires operational capability in the protocol from one transmission.
//
// The pangram body exercises every essential grammatical primitive of SAL
// across nine namespaces. Receivers verify the canonical form by SHA-256 hash
// compare; mismatch causes reversion to pre-acquisition state without applying
// received content (bounded-infection property).
//
// Cross-SDK byte-identical to Python osmp.pangram and TypeScript src/pangram.ts.
//
// Patent pending. Inventor: Clay Holberg. License: Apache 2.0.

package osmp

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

// ── Canonical pangram body ──────────────────────────────────────────────────
//
// Locked at v15.1 of the OSMP Adaptive Shared Dictionary (released 2026-04-26).
// Any change to this string changes the SHA-256 and breaks cross-implementation
// hash-verify.

const PangramBody = "I:§→R:MOV@DRONE1[lat:34.05,lon:-118.25]⚠;" +
	"H:HR>130→H:ALERT@*∧L:LOG@AUDIT;" +
	"I:§→D:DEL@RECORD42⊘;" +
	"G:POS@FLEET?∧T:SCHED[every:1h];" +
	"A:MACRO[MESH:HLTH]→⊤;" +
	"N:CFG[Δ:{ttl:30}]↺"

const (
	PangramMacroID    = "PANGRAM"
	PangramASDVersion = "v15.1"
)

// ExpectedPangramSHA256 is the canonical SHA-256, hardcoded for cross-SDK
// verification. Any divergence between the computed SHA-256 (PangramSHA256)
// and this constant indicates the pangram body was modified without updating
// the registered fingerprint.
const ExpectedPangramSHA256 = "fcefe9363ab737be174829dd8c12f4ca365fefb3601464514dd2aa4e1e0332ba"

// ── Tier 2: short-form pangram (LoRa-floor channels) ───────────────────────
//
// Tier-indexed canonical pangram for channel capabilities that cannot
// accommodate the standard-form 185-byte body. Constructed against the same
// v15.1 ASD basis but trimmed to fit the 51-byte LoRa floor while still
// exercising frame structure, target syntax, threshold operator, sequence
// operator, conjunction operator, a consequence class designator, the I:§
// authorization precondition, the THEN operator, and the query suffix.

const PangramTinyBody = "I:§→R:MOV@D⚠;H:HR>120→L:LOG@*?∧G:POS↺"

const PangramTinyMacroID = "PANGRAM_TINY"

const ExpectedPangramTinySHA256 = "91c807dbbf3693ca57fb9b10ca39a5092d69de63df19b019217460e5e9c04564"

var PangramTinySHA256 string
var PangramTinySHA256Truncated16 string
var PangramTinyUTF8Bytes int

// ChannelTier indicates the receiver's channel capability for pangram selection.
type ChannelTier string

const (
	ChannelTierStandard  ChannelTier = "standard"   // ≤ ~220 bytes; uses PangramBody
	ChannelTierLoraFloor ChannelTier = "lora_floor" // ≤ 51 bytes; uses PangramTinyBody
)

// PangramSHA256 is computed at package load and verified against
// ExpectedPangramSHA256 in init().
var PangramSHA256 string

// PangramSHA256Truncated16 is the 16-character truncated form for
// bandwidth-constrained channels.
var PangramSHA256Truncated16 string

// PangramUTF8Bytes is the UTF-8 byte length of the canonical body.
var PangramUTF8Bytes int

func init() {
	sum := sha256.Sum256([]byte(PangramBody))
	PangramSHA256 = hex.EncodeToString(sum[:])
	PangramSHA256Truncated16 = PangramSHA256[:16]
	PangramUTF8Bytes = len(PangramBody)

	if PangramSHA256 != ExpectedPangramSHA256 {
		panic(fmt.Sprintf(
			"Pangram body has been modified — computed SHA-256 %s does not "+
				"match registered fingerprint %s. Restore the canonical body "+
				"or coordinate a registered fingerprint update.",
			PangramSHA256, ExpectedPangramSHA256,
		))
	}

	// Tier 2 (PANGRAM_TINY) — LoRa floor short-form
	tinySum := sha256.Sum256([]byte(PangramTinyBody))
	PangramTinySHA256 = hex.EncodeToString(tinySum[:])
	PangramTinySHA256Truncated16 = PangramTinySHA256[:16]
	PangramTinyUTF8Bytes = len(PangramTinyBody)

	if PangramTinySHA256 != ExpectedPangramTinySHA256 {
		panic(fmt.Sprintf(
			"PangramTiny body has been modified — computed SHA-256 %s does "+
				"not match registered fingerprint %s.",
			PangramTinySHA256, ExpectedPangramTinySHA256,
		))
	}
	if PangramTinyUTF8Bytes > 51 {
		panic(fmt.Sprintf(
			"PangramTiny (%dB) exceeds LoRa floor 51B; tier 2 invariant violated.",
			PangramTinyUTF8Bytes,
		))
	}
}

// EmitForTier returns the canonical pangram body appropriate for the channel
// tier. The sender selects a tier based on the receiver's advertised channel
// capability (e.g., via Frame Negotiation Protocol) or on observed channel
// behavior.
func EmitForTier(tier ChannelTier) string {
	switch tier {
	case ChannelTierStandard:
		return PangramBody
	case ChannelTierLoraFloor:
		return PangramTinyBody
	default:
		panic(fmt.Sprintf("unknown channel tier: %s", tier))
	}
}

// VerifyForTier verifies a received pangram against the tier-appropriate
// canonical hash. Returns true on match, false on mismatch.
func VerifyForTier(received []byte, tier ChannelTier, truncated bool) bool {
	sum := sha256.Sum256(received)
	receivedHash := hex.EncodeToString(sum[:])
	var expected string
	switch tier {
	case ChannelTierStandard:
		expected = PangramSHA256
	case ChannelTierLoraFloor:
		expected = PangramTinySHA256
	default:
		panic(fmt.Sprintf("unknown channel tier: %s", tier))
	}
	if truncated {
		return receivedHash[:16] == expected[:16]
	}
	return receivedHash == expected
}

// VerifyForTierString is a convenience wrapper around VerifyForTier for
// string input (interpreted as UTF-8).
func VerifyForTierString(received string, tier ChannelTier, truncated bool) bool {
	return VerifyForTier([]byte(received), tier, truncated)
}

// ─────────────────────────────────────────────────────────────────────────────
// Verification API (bounded-infection property)
// ─────────────────────────────────────────────────────────────────────────────

// VerifyReceived verifies that a received byte sequence matches the canonical
// pangram. Computes SHA-256 of the received bytes and compares to the
// registered canonical hash. Returns true on match, false on mismatch.
//
// A receiver that invokes this function and observes false MUST revert to its
// pre-acquisition state without applying the received content (bounded-
// infection property).
//
// If truncated is true, compares only the first 16 hex characters of the hash
// (acceptable for bandwidth-constrained channels; NOT recommended for
// safety-critical handshakes).
func VerifyReceived(received []byte, truncated bool) bool {
	sum := sha256.Sum256(received)
	receivedHash := hex.EncodeToString(sum[:])
	if truncated {
		return receivedHash[:16] == PangramSHA256Truncated16
	}
	return receivedHash == PangramSHA256
}

// VerifyReceivedString is a convenience wrapper around VerifyReceived for
// string inputs. The string is interpreted as UTF-8.
func VerifyReceivedString(received string, truncated bool) bool {
	return VerifyReceived([]byte(received), truncated)
}

// EmitPangram returns the canonical pangram body as a UTF-8 string.
//
// The first agent in a bridged-session handshake transmits this string to the
// second agent. The receiver invokes VerifyReceived() on the received bytes
// before acquiring grammar from the demonstration.
func EmitPangram() string {
	return PangramBody
}

// EmitPangramBytes returns the canonical pangram body as UTF-8 bytes.
func EmitPangramBytes() []byte {
	return []byte(PangramBody)
}

// ─────────────────────────────────────────────────────────────────────────────
// Macro registration helper
// ─────────────────────────────────────────────────────────────────────────────

// PangramMacroInvocation returns the macro-invocation form of the pangram,
// equivalent to A:MACRO[PANGRAM]. A sender that knows the receiver already has
// the canonical pangram body in its dictionary can transmit this 14-byte
// invocation instead of the full 185-byte body; the receiver expands locally.
// For a receiver in pre-acquisition state, the sender transmits the full body
// via EmitPangram().
func PangramMacroInvocation() string {
	return fmt.Sprintf("A:MACRO[%s]", PangramMacroID)
}

// PangramMetadata is a metadata struct summarizing the pangram registration.
type PangramMetadata struct {
	MacroID            string   `json:"macro_id"`
	Body               string   `json:"body"`
	ByteLengthUTF8     int      `json:"byte_length_utf8"`
	SHA256             string   `json:"sha256"`
	SHA256Truncated16  string   `json:"sha256_truncated_16"`
	ASDVersion         string   `json:"asd_version"`
	NamespacesCovered  []string `json:"namespaces_covered"`
}

// PangramMetadataInfo returns a metadata struct summarizing the pangram
// registration, useful for prosecution exhibits and cross-SDK parity tests.
func PangramMetadataInfo() PangramMetadata {
	return PangramMetadata{
		MacroID:           PangramMacroID,
		Body:              PangramBody,
		ByteLengthUTF8:    PangramUTF8Bytes,
		SHA256:            PangramSHA256,
		SHA256Truncated16: PangramSHA256Truncated16,
		ASDVersion:        PangramASDVersion,
		NamespacesCovered: []string{"A", "D", "G", "H", "I", "L", "N", "R", "T"},
	}
}
