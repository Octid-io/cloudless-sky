"""
SALBridge Frame Detection Regression Tests (Finding 13)
=======================================================

These tests guard against the Finding 13 regression where the SALBridge
frame detection regex `\\b([A-Z]):([A-Z]{2,})\\b` silently missed:

1. The § glyph in opcode position (I:§ — human authorization marker)
2. Tier 2 namespaces (AB:CD style two-character prefixes)
3. Single-letter opcodes (Z:Q, A:Q, etc.)

The fix uses the shared _OPCODE_PATTERN constant from protocol.py and a
simpler `\\b(NS):(OP)` form that works identically across Python re,
JavaScript, and Go RE2. The bridge regex no longer hardcodes character
classes; it composes from the same building blocks as the validator and
the regulatory_dependency parser.

Patent pending -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import _SAL_FRAME_RE_BRIDGE  # noqa: E402
from osmp.bridge import SALBridge  # noqa: E402
from osmp import AdaptiveSharedDictionary  # noqa: E402


# ── Direct regex tests ──────────────────────────────────────────────────────


class TestBridgeFrameRegex:
    """Verify _SAL_FRAME_RE_BRIDGE captures the right (ns, op) tuples."""

    def test_section_glyph_in_natural_language(self):
        """The original failure: I:§ was invisible to the bridge regex."""
        msg = "operator should authorize via I:§ before R:MOV"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert ("I", "§") in matches
        assert ("R", "MOV") in matches

    def test_tier2_namespace(self):
        """Tier 2 (two-letter) namespaces were excluded by the old regex."""
        msg = "the AB:CD frame is valid"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == [("AB", "CD")]

    def test_single_letter_opcode(self):
        """Single-letter opcodes like Z:Q were rejected by [A-Z]{2,}."""
        msg = "send Z:Q to the model"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == [("Z", "Q")]

    def test_standard_alphanumeric_opcode(self):
        """The classic case still works."""
        msg = "the operator should send H:HR@NODE1>120 now"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == [("H", "HR")]

    def test_does_not_truncate_long_opcode(self):
        """H:HRRATE must match as HRRATE, not be truncated to HR."""
        msg = "send H:HRRATE now"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == [("H", "HRRATE")]

    def test_lowercase_rejected(self):
        """Lowercase namespace:opcode is not SAL."""
        msg = "a:hr is not valid"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == []

    def test_multiple_frames_in_message(self):
        """A bridge inbound message with multiple SAL frames."""
        msg = "process H:HR and then M:EVA when ready"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert ("H", "HR") in matches
        assert ("M", "EVA") in matches

    def test_punctuation_terminator(self):
        """Trailing punctuation should not break the match."""
        msg = "just H:HR."
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == [("H", "HR")]


# ── Substring rejection ─────────────────────────────────────────────────────


class TestBridgeFrameSubstringRejection:
    """The bridge regex must NOT match SAL-shaped substrings inside words.
    These cases would have produced false positives with a looser pattern."""

    def test_aab_does_not_yield_ab_inside(self):
        """AAB:CD is not a valid bridge frame; AB inside AAB is not a match."""
        msg = "AAB:CD"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == []

    def test_xab_does_not_yield_ab_inside(self):
        msg = "XAB:CD"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == []

    def test_lowercase_concatenation_rejected(self):
        """noticedH:HR has H:HR concatenated to a lowercase word."""
        msg = "noticedH:HR"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == []

    def test_lowercase_concatenation_with_space_accepted(self):
        """A space restores the word boundary."""
        msg = "noticed H:HR"
        matches = _SAL_FRAME_RE_BRIDGE.findall(msg)
        assert matches == [("H", "HR")]


# ── End-to-end bridge integration ───────────────────────────────────────────


class TestBridgeFrameDetection:
    """Verify the SALBridge._detect_sal_frames method actually returns
    the right opcodes when called against natural language messages."""

    @pytest.fixture
    def bridge(self):
        return SALBridge("TEST_NODE")

    def test_bridge_detects_section_glyph_frame(self, bridge):
        """End-to-end: I:§ in a natural-language message must be detected
        as a valid SAL frame and resolved against the ASD."""
        bridge.register_peer("PEER1")
        msg = "authorize via I:§ before proceeding"
        # Use the internal detection method directly to bypass policy
        frames = bridge._detect_sal_frames(msg)
        # I:§ is in the ASD as the human authorization presence marker
        assert ("I", "§") in frames

    def test_bridge_detects_standard_frame(self, bridge):
        bridge.register_peer("PEER1")
        msg = "send H:HR@NODE1>120 to operator"
        frames = bridge._detect_sal_frames(msg)
        assert ("H", "HR") in frames

    def test_bridge_ignores_unknown_opcode(self, bridge):
        """A SAL-shaped string with an opcode not in the ASD must NOT
        be counted as a valid frame."""
        bridge.register_peer("PEER1")
        msg = "send Z:NOTREAL to operator"
        frames = bridge._detect_sal_frames(msg)
        assert ("Z", "NOTREAL") not in frames


# ── Marker test for the audit finding ───────────────────────────────────────


def test_finding_13_marker():
    """Single-line marker test that explicitly references Finding 13.
    If this test fails, the bridge regex has lost its support for I:§
    or single-letter opcodes."""
    matches = _SAL_FRAME_RE_BRIDGE.findall("I:§ and Z:Q together")
    assert ("I", "§") in matches, (
        "Finding 13 regression: bridge regex must accept I:§ "
        "(human authorization marker)."
    )
    assert ("Z", "Q") in matches, (
        "Finding 13 regression: bridge regex must accept single-letter opcodes."
    )
