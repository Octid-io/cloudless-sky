// Pangram module tests — Go SDK.
//
// Verifies cross-SDK byte-identical SHA-256 with Python and TypeScript via
// the ExpectedPangramSHA256 constant shared across all three SDKs.

package osmp_test

import (
	"crypto/sha256"
	"encoding/hex"
	"testing"

	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)

func TestPangramBody185Bytes(t *testing.T) {
	if osmp.PangramUTF8Bytes != 185 {
		t.Errorf("expected 185 UTF-8 bytes, got %d", osmp.PangramUTF8Bytes)
	}
}

func TestPangramSHA256MatchesExpected(t *testing.T) {
	if osmp.PangramSHA256 != osmp.ExpectedPangramSHA256 {
		t.Errorf("computed %s != expected %s", osmp.PangramSHA256, osmp.ExpectedPangramSHA256)
	}
	want := "fcefe9363ab737be174829dd8c12f4ca365fefb3601464514dd2aa4e1e0332ba"
	if osmp.PangramSHA256 != want {
		t.Errorf("PangramSHA256 = %s, want %s", osmp.PangramSHA256, want)
	}
}

func TestPangramTruncatedSHA256(t *testing.T) {
	if osmp.PangramSHA256Truncated16 != osmp.PangramSHA256[:16] {
		t.Errorf("truncated %s != first-16 of full %s", osmp.PangramSHA256Truncated16, osmp.PangramSHA256[:16])
	}
	if osmp.PangramSHA256Truncated16 != "fcefe9363ab737be" {
		t.Errorf("truncated SHA = %s, want fcefe9363ab737be", osmp.PangramSHA256Truncated16)
	}
}

func TestPangramMacroID(t *testing.T) {
	if osmp.PangramMacroID != "PANGRAM" {
		t.Errorf("macro id = %q, want PANGRAM", osmp.PangramMacroID)
	}
}

func TestPangramASDVersion(t *testing.T) {
	if osmp.PangramASDVersion != "v15.1" {
		t.Errorf("ASD version = %q, want v15.1", osmp.PangramASDVersion)
	}
}

func TestEmitPangram(t *testing.T) {
	if osmp.EmitPangram() != osmp.PangramBody {
		t.Errorf("EmitPangram returned non-canonical body")
	}
}

func TestEmitPangramBytes(t *testing.T) {
	b := osmp.EmitPangramBytes()
	if string(b) != osmp.PangramBody {
		t.Errorf("EmitPangramBytes returned non-canonical bytes")
	}
	if len(b) != 185 {
		t.Errorf("EmitPangramBytes returned %d bytes, want 185", len(b))
	}
}

func TestVerifyReceivedCanonical(t *testing.T) {
	if !osmp.VerifyReceivedString(osmp.PangramBody, false) {
		t.Errorf("canonical body did not verify")
	}
	if !osmp.VerifyReceived(osmp.EmitPangramBytes(), false) {
		t.Errorf("canonical bytes did not verify")
	}
}

func TestVerifyReceivedModified(t *testing.T) {
	if osmp.VerifyReceivedString(osmp.PangramBody+"X", false) {
		t.Errorf("modified body should not verify")
	}
	bad := []byte(osmp.PangramBody)
	bad[0] = bad[0] ^ 1
	if osmp.VerifyReceived(bad, false) {
		t.Errorf("bit-flipped first byte should not verify")
	}
}

func TestVerifyReceivedTruncated(t *testing.T) {
	if !osmp.VerifyReceivedString(osmp.PangramBody, true) {
		t.Errorf("canonical body should verify with truncated hash")
	}
	if osmp.VerifyReceivedString(osmp.PangramBody+"X", true) {
		t.Errorf("modified body should not verify with truncated hash")
	}
}

func TestPangramMacroInvocation(t *testing.T) {
	got := osmp.PangramMacroInvocation()
	want := "A:MACRO[PANGRAM]"
	if got != want {
		t.Errorf("PangramMacroInvocation = %q, want %q", got, want)
	}
}

func TestPangramMetadata(t *testing.T) {
	m := osmp.PangramMetadataInfo()
	if m.MacroID != "PANGRAM" || m.ByteLengthUTF8 != 185 || m.ASDVersion != "v15.1" {
		t.Errorf("metadata structural fields wrong: %+v", m)
	}
	wantNS := []string{"A", "D", "G", "H", "I", "L", "N", "R", "T"}
	if len(m.NamespacesCovered) != len(wantNS) {
		t.Errorf("namespaces covered = %d, want %d", len(m.NamespacesCovered), len(wantNS))
	}
	for i, ns := range wantNS {
		if m.NamespacesCovered[i] != ns {
			t.Errorf("namespace[%d] = %q, want %q", i, m.NamespacesCovered[i], ns)
		}
	}
}

func TestPangramCrossSDKParity(t *testing.T) {
	// Re-compute SHA-256 here using Go's stdlib and compare to the registered
	// constant. The TypeScript and Python SDKs do the same against the same
	// EXPECTED_PANGRAM_SHA256; if all three match, byte-identicalness holds.
	sum := sha256.Sum256([]byte(osmp.PangramBody))
	got := hex.EncodeToString(sum[:])
	if got != osmp.ExpectedPangramSHA256 {
		t.Errorf("cross-SDK parity broken: re-computed %s != expected %s", got, osmp.ExpectedPangramSHA256)
	}
}

// ─────────────────────────────────────────────────────────────────────────
// Tier 2 — short-form pangram (LoRa floor)
// ─────────────────────────────────────────────────────────────────────────

func TestPangramTinyFitsLoraFloor(t *testing.T) {
	if osmp.PangramTinyUTF8Bytes > 51 {
		t.Errorf("PANGRAM_TINY (%dB) violates LoRa floor 51B invariant", osmp.PangramTinyUTF8Bytes)
	}
}

func TestPangramTinyCanonicalSHA256(t *testing.T) {
	if osmp.PangramTinySHA256 != osmp.ExpectedPangramTinySHA256 {
		t.Errorf("computed %s != expected %s", osmp.PangramTinySHA256, osmp.ExpectedPangramTinySHA256)
	}
	want := "91c807dbbf3693ca57fb9b10ca39a5092d69de63df19b019217460e5e9c04564"
	if osmp.PangramTinySHA256 != want {
		t.Errorf("PangramTinySHA256 = %s, want %s", osmp.PangramTinySHA256, want)
	}
}

func TestPangramTinyMacroID(t *testing.T) {
	if osmp.PangramTinyMacroID != "PANGRAM_TINY" {
		t.Errorf("macro id = %q, want PANGRAM_TINY", osmp.PangramTinyMacroID)
	}
}

func TestEmitForTier(t *testing.T) {
	if osmp.EmitForTier(osmp.ChannelTierStandard) != osmp.PangramBody {
		t.Errorf("EmitForTier(Standard) returned non-canonical body")
	}
	if osmp.EmitForTier(osmp.ChannelTierLoraFloor) != osmp.PangramTinyBody {
		t.Errorf("EmitForTier(LoraFloor) returned non-canonical short-form body")
	}
}

func TestVerifyForTierCanonical(t *testing.T) {
	if !osmp.VerifyForTierString(osmp.PangramBody, osmp.ChannelTierStandard, false) {
		t.Errorf("standard body did not verify against standard tier")
	}
	if !osmp.VerifyForTierString(osmp.PangramTinyBody, osmp.ChannelTierLoraFloor, false) {
		t.Errorf("tiny body did not verify against LoRa-floor tier")
	}
}

func TestVerifyForTierCrossRejects(t *testing.T) {
	if osmp.VerifyForTierString(osmp.PangramBody, osmp.ChannelTierLoraFloor, false) {
		t.Errorf("standard body should not verify against LoRa-floor tier")
	}
	if osmp.VerifyForTierString(osmp.PangramTinyBody, osmp.ChannelTierStandard, false) {
		t.Errorf("tiny body should not verify against standard tier")
	}
}

func TestPangramTinyMinimumPrimitives(t *testing.T) {
	body := osmp.PangramTinyBody
	for _, p := range []string{":", "@", ">", ";", "∧"} {
		if !contains(body, p) {
			t.Errorf("PANGRAM_TINY missing required primitive %q", p)
		}
	}
	hasCC := false
	for _, cc := range []string{"⚠", "↺", "⊘"} {
		if contains(body, cc) {
			hasCC = true
			break
		}
	}
	if !hasCC {
		t.Errorf("PANGRAM_TINY missing consequence class designator")
	}
}

func contains(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}

func TestPangramTinyCrossSDKParity(t *testing.T) {
	sum := sha256.Sum256([]byte(osmp.PangramTinyBody))
	got := hex.EncodeToString(sum[:])
	if got != osmp.ExpectedPangramTinySHA256 {
		t.Errorf("tier 2 cross-SDK parity broken: %s != %s", got, osmp.ExpectedPangramTinySHA256)
	}
}
