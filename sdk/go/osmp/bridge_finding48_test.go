// Bridge Pure-SAL Detection Regression Tests (Finding 48)
//
// Mirrors tests/test_bridge_pure_sal.py (Python) and
// sdk/typescript/tests/bridge.test.ts (TypeScript). The bug was
// identical in all three SDKs: bridge isPureSAL used substring match
// to verify each frame, so a natural-language message containing a
// SAL substring was misclassified as pure SAL and routed to the wrong
// code path in Receive.
//
// The fix uses an anchored strip-and-residue approach: a message is
// pure SAL if and only if removing every valid SAL frame (with target,
// slots, brackets, and consequence class tail), every chain operator,
// and every whitespace character leaves nothing behind.
//
// Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
// License: Apache 2.0

package osmp_test

import (
	"testing"

	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)

func newTestBridge(t *testing.T) *osmp.SALBridge {
	t.Helper()
	b := osmp.NewSALBridge("TEST_NODE", nil, true)
	b.RegisterPeer("PEER1", false)
	return b
}

func containsFrame(frames []string, target string) bool {
	for _, f := range frames {
		if f == target {
			return true
		}
	}
	return false
}

// ── Mixed-mode messages must NOT be pure SAL ───────────────────────────

func TestFinding48_NLWithSectionGlyphIsNotPureSAL(t *testing.T) {
	// The original bug: "authorize via I:§ before proceeding" was
	// misclassified as pure SAL because the substring search found
	// I:§ inside the message.
	b := newTestBridge(t)
	result := b.Receive("authorize via I:§ before proceeding", "PEER1")

	if !result.Passthrough {
		t.Fatalf("Finding 48 regression: NL message containing I:§ "+
			"classified as pure SAL instead of mixed-mode. "+
			"sal=%q passthrough=%v", result.SAL, result.Passthrough)
	}
	if !containsFrame(result.DetectedFrames, "I:§") {
		t.Errorf("expected I:§ in detected frames, got %v", result.DetectedFrames)
	}
}

func TestFinding48_NLWithStandardFrameIsNotPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("patient has H:HR@PATIENT1 of 120 bpm right now", "PEER1")

	if !result.Passthrough {
		t.Fatalf("expected passthrough=true, got sal=%q", result.SAL)
	}
	if !containsFrame(result.DetectedFrames, "H:HR") {
		t.Errorf("expected H:HR in detected frames, got %v", result.DetectedFrames)
	}
}

func TestFinding48_NLWithMultipleFramesIsNotPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("process H:HR and then M:EVA when ready please", "PEER1")

	if !result.Passthrough {
		t.Fatalf("expected passthrough=true, got sal=%q", result.SAL)
	}
	if !containsFrame(result.DetectedFrames, "H:HR") {
		t.Errorf("expected H:HR in detected frames, got %v", result.DetectedFrames)
	}
	if !containsFrame(result.DetectedFrames, "M:EVA") {
		t.Errorf("expected M:EVA in detected frames, got %v", result.DetectedFrames)
	}
}

func TestFinding48_LowercaseTextIsNLPassthrough(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("just a regular sentence", "PEER1")

	if !result.Passthrough {
		t.Errorf("expected passthrough=true for plain NL, got passthrough=false")
	}
	if len(result.DetectedFrames) != 0 {
		t.Errorf("expected empty detected frames, got %v", result.DetectedFrames)
	}
}

// ── Pure SAL messages must still be recognized ────────────────────────

func TestFinding48_SimpleFrameIsPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("H:HR@NODE1", "PEER1")

	if result.Passthrough {
		t.Errorf("expected passthrough=false for pure SAL, got true")
	}
	if result.SAL != "H:HR@NODE1" {
		t.Errorf("expected sal=H:HR@NODE1, got %q", result.SAL)
	}
}

func TestFinding48_SectionGlyphAloneIsPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("I:§", "PEER1")

	if result.Passthrough {
		t.Errorf("expected passthrough=false for I:§, got true")
	}
	if result.SAL != "I:§" {
		t.Errorf("expected sal=I:§, got %q", result.SAL)
	}
}

func TestFinding48_ChainWithThenOperatorIsPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("I:§\u2192R:MOV@DRONE1\u26a0", "PEER1")

	if result.Passthrough {
		t.Errorf("expected passthrough=false for I:§→R:MOV⚠, got true; sal=%q", result.SAL)
	}
}

func TestFinding48_SequenceWithSemicolonIsPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("A:PING;A:PONG", "PEER1")

	if result.Passthrough {
		t.Errorf("expected passthrough=false for A:PING;A:PONG, got true")
	}
}

func TestFinding48_FrameWithSlotIsPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("H:HR@NODE1:ALERT:120", "PEER1")

	if result.Passthrough {
		t.Errorf("expected passthrough=false for H:HR@NODE1:ALERT:120, got true")
	}
}

func TestFinding48_FrameWithBracketIsPureSAL(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("H:ICD[J930]", "PEER1")

	if result.Passthrough {
		t.Errorf("expected passthrough=false for H:ICD[J930], got true")
	}
}

// ── Edge cases ────────────────────────────────────────────────────────

func TestFinding48_EmptyMessage(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("", "PEER1")
	if !result.Passthrough {
		t.Errorf("expected empty message to be passthrough")
	}
}

func TestFinding48_WhitespaceOnly(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("   ", "PEER1")
	if !result.Passthrough {
		t.Errorf("expected whitespace-only message to be passthrough")
	}
}

func TestFinding48_LowercasePseudoFrameRejected(t *testing.T) {
	b := newTestBridge(t)
	result := b.Receive("h:hr is the value", "PEER1")
	if !result.Passthrough {
		t.Errorf("expected lowercase pseudo-frame to be passthrough")
	}
	if len(result.DetectedFrames) != 0 {
		t.Errorf("expected empty detected frames, got %v", result.DetectedFrames)
	}
}

// ── Marker test ───────────────────────────────────────────────────────

func TestFinding48_Marker(t *testing.T) {
	// Single-line marker that explicitly references Finding 48. If
	// this fails, the bridge has reverted to substring-match pure-SAL
	// detection and natural language messages are being misrouted.
	b := newTestBridge(t)
	result := b.Receive("authorize via I:§ before proceeding", "PEER1")

	if !result.Passthrough {
		t.Fatalf("Finding 48 regression: bridge.isPureSAL returned true " +
			"for an NL message containing a SAL substring. The bridge " +
			"must use anchored frame detection, not substring search.")
	}
	if !containsFrame(result.DetectedFrames, "I:§") {
		t.Errorf("Finding 48 regression: detected frames empty for an NL " +
			"message containing I:§")
	}
}
