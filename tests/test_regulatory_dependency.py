"""
Regulatory Dependency (Rule 8) Regression Tests
================================================

These tests guard against the Findings 29/30 regression where the
regulatory_dependency parser silently dropped frames containing the §
glyph (the human-authorization presence marker, used in I:§).

The original bug: _CHAIN_FRAME_RE and _PREREQ_RE used the character
class [A-Z][A-Z0-9]* for opcode bodies, which excludes §. When a future
MDR added a REQUIRES rule like "R:⚠MOV REQUIRES:I:§", the parser would
silently drop I:§ from the chain opcode set and report a Rule 8
violation even when human authorization was present in the chain.

The fix factors out a shared _OPCODE_PATTERN constant referenced by all
four regexes in protocol.py (NS_TARGET_RE, FRAME_NS_OP_RE, PREREQ_RE,
CHAIN_FRAME_RE) so any future glyph additions only require one change
and stay consistent across the validator and the regulatory_dependency
parser.

Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import (  # noqa: E402
    _CHAIN_FRAME_RE,
    _PREREQ_RE,
    _FRAME_NS_OP_RE,
    _NS_TARGET_RE,
    _NS_PATTERN,
    _OPCODE_PATTERN,
    _extract_chain_frames,
    _prereq_satisfied,
    _validate_regulatory_dependencies,
    DependencyRule,
)


# ── Building block constants ────────────────────────────────────────────────


class TestSharedRegexBuildingBlocks:
    """Verify the single source of truth for namespace and opcode patterns."""

    def test_ns_pattern_matches_tier1_and_tier2(self):
        import re
        ns_re = re.compile(rf"^{_NS_PATTERN}$")
        assert ns_re.match("A")    # Tier 1
        assert ns_re.match("Z")    # Tier 1
        assert ns_re.match("AB")   # Tier 2
        assert ns_re.match("XY")   # Tier 2
        assert not ns_re.match("ABC")  # Three chars: Tier 3 not yet allocated
        assert not ns_re.match("a")    # lowercase rejected
        assert not ns_re.match("")

    def test_opcode_pattern_accepts_section_glyph(self):
        import re
        op_re = re.compile(rf"^{_OPCODE_PATTERN}$")
        # Standard alphanumeric opcodes
        assert op_re.match("HR")
        assert op_re.match("MOV")
        assert op_re.match("ICD")
        assert op_re.match("KYC")
        # The § glyph alone (used as I:§)
        assert op_re.match("§")
        # § mixed with letters (theoretical future opcode)
        assert op_re.match("A§")
        assert op_re.match("§A")
        # Single-letter opcode (Tier 1 valid)
        assert op_re.match("Q")
        # Numeric continuation
        assert op_re.match("F1")
        assert op_re.match("A2B")
        # Reject lowercase, empty, leading digit
        assert not op_re.match("hr")
        assert not op_re.match("")
        assert not op_re.match("1HR")


# ── _CHAIN_FRAME_RE ─────────────────────────────────────────────────────────


class TestChainFrameRegex:
    """The chain frame extractor must see I:§ and Tier 2 namespaces."""

    def test_section_glyph_alone(self):
        matches = _CHAIN_FRAME_RE.findall("I:§")
        assert matches == [("I", "§", "", "")]

    def test_section_glyph_in_chain(self):
        matches = _CHAIN_FRAME_RE.findall("I:§→R:MOV")
        ns_op_pairs = {(ns, op) for ns, op, *_ in matches}
        assert ("I", "§") in ns_op_pairs
        assert ("R", "MOV") in ns_op_pairs

    def test_section_glyph_with_consequence_class(self):
        # R:MOV with HAZARDOUS class, gated on human authorization
        matches = _CHAIN_FRAME_RE.findall("I:§∧R:MOV⚠")
        ns_op_pairs = {(ns, op) for ns, op, *_ in matches}
        assert ("I", "§") in ns_op_pairs
        assert ("R", "MOV") in ns_op_pairs

    def test_tier2_namespace_still_works(self):
        # When Tier 2 prefixes are eventually allocated, the regex should
        # match them too (this test was previously a failure mode of the
        # old [A-Z]:[A-Z]{2,} pattern in some bridges).
        matches = _CHAIN_FRAME_RE.findall("AB:CD")
        assert matches == [("AB", "CD", "", "")]


# ── _PREREQ_RE ──────────────────────────────────────────────────────────────


class TestPrereqRegex:
    """The prerequisite parser must see I:§ as a valid REQUIRES target."""

    def test_section_glyph_prereq(self):
        m = _PREREQ_RE.match("I:§")
        assert m is not None
        assert m.group(1) == "I"
        assert m.group(2) == "§"
        assert m.group(3) is None  # no slot

    def test_section_glyph_with_slot(self):
        m = _PREREQ_RE.match("I:§[OPERATOR]")
        assert m is not None
        assert m.group(1) == "I"
        assert m.group(2) == "§"
        assert m.group(3) == "OPERATOR"

    def test_standard_opcode_still_works(self):
        m = _PREREQ_RE.match("F:BVLOS[P]")
        assert m is not None
        assert m.group(1) == "F"
        assert m.group(2) == "BVLOS"
        assert m.group(3) == "P"


# ── _FRAME_NS_OP_RE ─────────────────────────────────────────────────────────


class TestFrameNsOpRegex:
    """The frame extractor must see I:§ at the start of a frame."""

    def test_section_glyph_at_frame_start(self):
        m = _FRAME_NS_OP_RE.match("I:§")
        assert m is not None
        assert m.groups() == ("I", "§")

    def test_section_glyph_followed_by_target(self):
        m = _FRAME_NS_OP_RE.match("I:§@OPERATOR1")
        assert m is not None
        assert m.groups() == ("I", "§")


# ── End-to-end Rule 8 enforcement ───────────────────────────────────────────


class TestRule8WithSectionGlyph:
    """Real-world REQUIRES rule scenarios that would have hit the bug."""

    def test_extract_chain_frames_sees_section_glyph(self):
        """The bug: I:§ was invisible to _extract_chain_frames."""
        sal = "I:§→R:MOV⚠"
        frames, opcodes = _extract_chain_frames(sal)
        assert "I:§" in opcodes, (
            "I:§ must appear in the chain opcode set; if missing, "
            "any REQUIRES rule depending on it will fire false-positive"
        )
        assert "R:MOV" in opcodes

    def test_extract_chain_frames_with_and_operator(self):
        sal = "I:§∧R:MOV⚠"
        frames, opcodes = _extract_chain_frames(sal)
        assert "I:§" in opcodes
        assert "R:MOV" in opcodes

    def test_extract_chain_frames_with_then_reverse(self):
        sal = "R:MOV⚠→I:§"
        frames, opcodes = _extract_chain_frames(sal)
        assert "I:§" in opcodes
        assert "R:MOV" in opcodes

    def test_prereq_satisfied_by_section_glyph(self):
        """A REQUIRES rule of the form REQUIRES:I:§ is satisfied iff
        I:§ appears in the chain opcode set."""
        chain_frames = set()
        chain_opcodes = {"I:§", "R:MOV"}
        assert _prereq_satisfied("I:§", chain_frames, chain_opcodes) is True
        assert _prereq_satisfied("I:OTHER", chain_frames, chain_opcodes) is False

    def test_prereq_not_satisfied_when_section_glyph_absent(self):
        """Critical: if I:§ is NOT in the chain, the prereq must fail."""
        chain_frames = set()
        chain_opcodes = {"R:MOV"}
        assert _prereq_satisfied("I:§", chain_frames, chain_opcodes) is False

    def test_validate_regulatory_dependencies_section_glyph_present(self):
        """End-to-end: a chain with I:§ satisfies a rule that requires it."""
        rule = DependencyRule(
            entry="R:MOV",
            namespace="R",
            opcode="MOV",
            slot_value="",
            requires_raw="REQUIRES:I:§",
            alternatives=[["I:§"]],
        )
        # Chain HAS I:§, so the rule should pass with no issues
        issues = _validate_regulatory_dependencies("I:§→R:MOV⚠", [rule])
        assert issues == [], (
            f"Chain contains I:§; Rule 8 should not flag it, but got: {issues}"
        )

    def test_validate_regulatory_dependencies_section_glyph_absent(self):
        """End-to-end: a chain without I:§ violates a rule that requires it."""
        rule = DependencyRule(
            entry="R:MOV",
            namespace="R",
            opcode="MOV",
            slot_value="",
            requires_raw="REQUIRES:I:§",
            alternatives=[["I:§"]],
        )
        issues = _validate_regulatory_dependencies("R:MOV⚠", [rule])
        assert len(issues) >= 1, (
            "Chain lacks I:§; Rule 8 should flag the violation"
        )
        assert any("REGULATORY_DEPENDENCY" in i.rule for i in issues)


# ── Regression marker ───────────────────────────────────────────────────────


def test_findings_29_30_marker():
    """Single-line marker test that explicitly references Findings 29/30
    in the audit. If this test fails, the shared _OPCODE_PATTERN constant
    has been broken."""
    import re
    # Both regexes must accept § in the opcode position
    op_re = re.compile(rf"^{_OPCODE_PATTERN}$")
    assert op_re.match("§"), (
        "Findings 29/30 regression: _OPCODE_PATTERN must accept § "
        "(human authorization presence marker, used in I:§). "
        "See sdk/python/osmp/protocol.py for the shared constant."
    )
