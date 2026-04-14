"""
Bridge Pure-SAL Detection Regression Tests (Finding 48)
=======================================================

These tests guard against the Finding 48 regression where the bridge's
``_is_pure_sal`` method used substring search to check whether a message
was entirely valid SAL. The substring approach returned True for natural
language messages that happened to contain a SAL frame anywhere in them
(e.g. "authorize via I:§ before proceeding"), causing the bridge to
misroute mixed-mode messages as pure SAL and silently empty the
detected_frames list.

The fix uses an anchored strip-and-residue approach: a message is pure
SAL if and only if removing every valid SAL frame (with target, slots,
brackets, and consequence class tail), every chain operator, and every
whitespace character leaves nothing behind.

Both Python and TypeScript SDKs had the identical bug. Both were fixed
in the same session. This test pins the Python behavior; the equivalent
TS test lives in sdk/typescript/tests/bridge.test.ts.

Patent pending -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.bridge import SALBridge  # noqa: E402


# ── Mixed-mode messages must NOT be pure SAL ─────────────────────────────


class TestMixedModeRejection:
    """Natural language messages that contain a SAL substring must be
    classified as mixed-mode, with the SAL frame surfaced through
    detected_frames rather than the entire message being routed to sal."""

    @pytest.fixture
    def bridge(self):
        b = SALBridge("TEST_NODE")
        b.register_peer("PEER1")
        return b

    def test_nl_with_section_glyph_is_not_pure_sal(self, bridge):
        """The original bug: 'authorize via I:§ before proceeding' was
        misclassified as pure SAL because the substring search found
        I:§ inside the message."""
        result = bridge.receive(
            "authorize via I:§ before proceeding", "PEER1"
        )
        assert result.passthrough is True, (
            "Finding 48 regression: NL message containing I:§ classified "
            "as pure SAL instead of mixed-mode."
        )
        assert "I:§" in result.detected_frames

    def test_nl_with_standard_frame_is_not_pure_sal(self, bridge):
        result = bridge.receive(
            "patient has H:HR@PATIENT1 of 120 bpm right now", "PEER1"
        )
        assert result.passthrough is True
        assert "H:HR" in result.detected_frames

    def test_nl_with_multiple_frames_is_not_pure_sal(self, bridge):
        result = bridge.receive(
            "process H:HR and then M:EVA when ready please", "PEER1"
        )
        assert result.passthrough is True
        assert "H:HR" in result.detected_frames
        assert "M:EVA" in result.detected_frames

    def test_lowercase_text_with_no_frames_is_nl_passthrough(self, bridge):
        result = bridge.receive("just a regular sentence", "PEER1")
        assert result.passthrough is True
        assert result.detected_frames == []


# ── Pure SAL messages must still be recognized ─────────────────────────


class TestPureSalRecognition:
    """The fix must not over-correct: legitimate pure-SAL messages
    must still be routed through the SAL path, not the NL passthrough."""

    @pytest.fixture
    def bridge(self):
        b = SALBridge("TEST_NODE")
        b.register_peer("PEER1")
        return b

    def test_simple_frame_is_pure_sal(self, bridge):
        result = bridge.receive("H:HR@NODE1", "PEER1")
        assert result.passthrough is False
        assert result.sal == "H:HR@NODE1"

    def test_section_glyph_alone_is_pure_sal(self, bridge):
        result = bridge.receive("I:§", "PEER1")
        assert result.passthrough is False
        assert result.sal == "I:§"

    def test_chain_with_then_operator_is_pure_sal(self, bridge):
        result = bridge.receive("I:§\u2192R:MOV@DRONE1\u26a0", "PEER1")
        assert result.passthrough is False

    def test_sequence_with_semicolon_is_pure_sal(self, bridge):
        result = bridge.receive("A:PING;A:PONG", "PEER1")
        assert result.passthrough is False

    def test_frame_with_slot_is_pure_sal(self, bridge):
        result = bridge.receive("H:HR@NODE1:ALERT:120", "PEER1")
        assert result.passthrough is False

    def test_frame_with_bracket_is_pure_sal(self, bridge):
        result = bridge.receive("H:ICD[J930]", "PEER1")
        assert result.passthrough is False


# ── Edge cases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary conditions for the residue-stripping pure-SAL check."""

    @pytest.fixture
    def bridge(self):
        b = SALBridge("TEST_NODE")
        b.register_peer("PEER1")
        return b

    def test_empty_message(self, bridge):
        result = bridge.receive("", "PEER1")
        assert result.passthrough is True

    def test_whitespace_only(self, bridge):
        result = bridge.receive("   ", "PEER1")
        assert result.passthrough is True

    def test_lowercase_pseudo_frame_rejected(self, bridge):
        """Lowercase namespace doesn't match the bridge regex."""
        result = bridge.receive("h:hr is the value", "PEER1")
        assert result.passthrough is True
        assert result.detected_frames == []

    def test_substring_frame_inside_word_rejected(self, bridge):
        """noticedH:HR is a concatenation; the word boundary in the
        bridge regex must prevent this from being detected as SAL."""
        result = bridge.receive("noticedH:HR happened", "PEER1")
        assert result.detected_frames == []


# ── Marker test ────────────────────────────────────────────────────────


def test_finding_48_marker():
    """Single-line marker that explicitly references Finding 48. If
    this fails, the bridge has reverted to substring-match pure-SAL
    detection and natural language messages are being misrouted."""
    bridge = SALBridge("TEST_NODE")
    bridge.register_peer("PEER1")
    result = bridge.receive(
        "authorize via I:§ before proceeding", "PEER1"
    )
    assert result.passthrough is True, (
        "Finding 48 regression: bridge._is_pure_sal returned True for "
        "an NL message containing a SAL substring. The bridge must "
        "use anchored frame detection, not substring search."
    )
    assert "I:§" in result.detected_frames, (
        "Finding 48 regression: detected_frames empty for an NL "
        "message containing I:§."
    )
