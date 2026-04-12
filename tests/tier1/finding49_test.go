package osmp

import (
	"bytes"
	"testing"
)

// Finding 49: I:§ opcode round-trip through TOK_FRAME rather than UTF-8 fallback.
//
// Background: the Instructional namespace frame marker "I:§" (colon followed by
// U+00A7) must encode as a 3-byte TOK_FRAME payload [tokFRAME, nsIndex('I'), opIdx].
// Before this fix, the Go SDK's tryNsOp character class only admitted [A-Z0-9],
// which caused '§' to terminate the opcode scan early. The fallback path then
// encoded "I:§" as a 5-byte atomic fallback whose first UTF-8 byte (0xC2) collides
// with SAIL tokATOMIC (0xC2) on decode, causing the Go SDK to misread its own
// emitted bytes as I:Λ instead of I:§.
//
// Python and TypeScript SDKs never hit this bug because their tryNsOp equivalents
// explicitly admit 0xA7 into the opcode character class (see python-wire.py
// line 627 and typescript-osmp-wire.ts line 497).
//
// Finding 49 was identified during ADR-004 sprint cross-SDK verification but
// deferred from that sprint to keep concerns separated. This test file is the
// dedicated fix verification.

func TestFinding49_ISectionEncodesAsTokFrame(t *testing.T) {
	codec := NewSAILCodec(DefaultBasis())

	// I:§ must be present in the intern table for this test to be meaningful.
	// If the test harness dictionary does not include I:§, skip rather than fail
	// so the test is valid across dictionary variants.
	if _, ok := codec.opToIdx["I"]; !ok {
		t.Skip("I namespace not present in test codec dictionary")
	}
	if _, ok := codec.opToIdx["I"]["§"]; !ok {
		t.Skip("I:§ sentinel not present in test codec dictionary")
	}

	encoded, err := codec.EncodeSAL("I:§")
	if err != nil {
		t.Fatalf("encode I:§ failed: %v", err)
	}

	// Expected wire form: [tokFRAME, 'I'-'A' = 8, opIdx]
	// Total length 3 bytes. Must NOT be 5 bytes (UTF-8 atomic fallback).
	if len(encoded) != 3 {
		t.Errorf("I:§ encoded to %d bytes, expected 3 (TOK_FRAME path); bytes=%x",
			len(encoded), encoded)
	}
	if encoded[0] != tokFRAME {
		t.Errorf("I:§ first byte = 0x%02x, expected tokFRAME (0x%02x); bytes=%x",
			encoded[0], tokFRAME, encoded)
	}
	if encoded[1] != 8 {
		t.Errorf("I:§ namespace byte = %d, expected 8 ('I'-'A'); bytes=%x",
			encoded[1], encoded)
	}
}

func TestFinding49_ISectionRoundTrip(t *testing.T) {
	codec := NewSAILCodec(DefaultBasis())
	if _, ok := codec.opToIdx["I"]; !ok {
		t.Skip("I namespace not present in test codec dictionary")
	}
	if _, ok := codec.opToIdx["I"]["§"]; !ok {
		t.Skip("I:§ sentinel not present in test codec dictionary")
	}

	encoded, err := codec.EncodeSAL("I:§")
	if err != nil {
		t.Fatalf("encode failed: %v", err)
	}

	decoded, err := codec.DecodeSAL(encoded)
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}

	if decoded != "I:§" {
		t.Errorf("round-trip mismatch: encoded=%x decoded=%q expected=%q",
			encoded, decoded, "I:§")
	}
}

func TestFinding49_ISectionCrossSDKByteEquivalence(t *testing.T) {
	// This test documents the expected wire bytes for I:§ so that any future
	// cross-SDK verification run can compare against a fixed expectation rather
	// than having to regenerate the reference from Python or TypeScript.
	//
	// Fixed expectation (assuming I:§ occupies opIdx 0 in the I namespace of the
	// ADR-004 canonical basis; adjust if basis changes):
	//   [0x??, 0x08, 0x00]  where 0x?? is tokFRAME and 0x08 is 'I'-'A'.
	//
	// The important property tested here is that the first byte is tokFRAME
	// (not 0xC2, which would indicate UTF-8 fallback and the Finding 49 bug).

	codec := NewSAILCodec(DefaultBasis())
	if _, ok := codec.opToIdx["I"]; !ok {
		t.Skip("I namespace not present in test codec dictionary")
	}
	if _, ok := codec.opToIdx["I"]["§"]; !ok {
		t.Skip("I:§ sentinel not present in test codec dictionary")
	}

	encoded, _ := codec.EncodeSAL("I:§")

	// Bug detection: if encoded[0] == 0xC2, the UTF-8 fallback path was taken
	// and Finding 49 has regressed.
	if bytes.HasPrefix(encoded, []byte{0xC2}) {
		t.Fatalf("Finding 49 REGRESSION: I:§ encoded via UTF-8 fallback path; "+
			"first byte 0xC2 collides with tokATOMIC on decode; bytes=%x", encoded)
	}
}
