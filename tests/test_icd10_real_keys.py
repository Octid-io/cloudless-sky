"""
ICD-10-CM Real CMS Keys Regression Tests (Finding 33)
=====================================================

These tests guard against the Finding 33 regression where the ICD-10-CM
domain corpus dpack used synthetic 4-character sequential keys instead of
real ICD-10 codes from the canonical CMS source.

The fix has two parts:
  1. The dpack is regenerated from the canonical CMS source file
     (mdr/icd10cm/icd10cm-codes-2026.txt, 74,719 codes for FY2026)
     using real ICD-10-CM codes as keys (with decimal points stripped,
     which is the canonical CMS storage format).
  2. BlockCompressor.resolve() accepts both dotted and undotted input
     forms by trying the verbatim form first and falling back to a
     dot-stripped form if not found. This lets clinical callers pass
     either "J93.0" (the form an LLM trained on real ICD documentation
     produces) or "J930" (the canonical CMS dpack key) interchangeably.

Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import BlockCompressor  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def icd_dpack() -> bytes:
    path = REPO_ROOT / "mdr" / "icd10cm" / "MDR-ICD10CM-FY2026-blk.dpack"
    if not path.exists():
        pytest.skip(f"ICD dpack not built: run tools/build_mdr_icd10cm.py first")
    return path.read_bytes()


@pytest.fixture(scope="module")
def bc() -> BlockCompressor:
    return BlockCompressor()


# ── Real CMS keys are present ───────────────────────────────────────────────


class TestRealICD10Keys:
    """Verify the dpack contains real ICD-10-CM codes from CMS, not
    synthetic 4-char sequential addresses."""

    def test_j930_resolves(self, bc, icd_dpack):
        """J930 = Spontaneous tension pneumothorax (Clay's benchmark example)."""
        result = bc.resolve(icd_dpack, "J930")
        assert result is not None
        assert "tension pneumothorax" in result.lower()

    def test_j939_resolves(self, bc, icd_dpack):
        """J939 = Pneumothorax, unspecified."""
        result = bc.resolve(icd_dpack, "J939")
        assert result is not None
        assert "pneumothorax" in result.lower()
        assert "unspecified" in result.lower()

    def test_six_char_laterality_code(self, bc, icd_dpack):
        """I25110 = Atherosclerotic heart disease w/ unstable angina (6 chars)."""
        result = bc.resolve(icd_dpack, "I25110")
        assert result is not None
        assert "atherosclerotic" in result.lower()
        assert "unstable angina" in result.lower()

    def test_seven_char_encounter_qualifier(self, bc, icd_dpack):
        """T84030A = displacement of internal right hip prosthetic joint, initial encounter (7 chars).

        7th-character extension codes are the longest in ICD-10 and the
        most expensive to carry on the wire. They must work."""
        result = bc.resolve(icd_dpack, "T84030A")
        assert result is not None
        # Just confirm it resolves to anything; the exact text is CMS-controlled
        assert len(result) > 0

    def test_three_char_parent_category(self, bc, icd_dpack):
        """J93 = parent category for pneumothorax. Some 3-char codes are
        valid lookup targets when no greater specificity exists."""
        result = bc.resolve(icd_dpack, "J93")
        # 3-char parents may or may not be present depending on whether
        # CMS includes the parent or only the children. Either is correct.
        if result is not None:
            assert "pneumothorax" in result.lower()

    def test_synthetic_key_no_longer_present(self, bc, icd_dpack):
        """The synthetic key J083 should NOT resolve to pneumothorax content
        anymore. (Previously the dpack had J083 -> Spontaneous tension
        pneumothorax as a fake mapping.)"""
        result = bc.resolve(icd_dpack, "J083")
        # If J083 happens to be a real CMS code (it's not in FY2026), it
        # should resolve to its real meaning, not pneumothorax.
        if result is not None:
            assert "tension pneumothorax" not in result.lower()

    def test_unknown_code_returns_none(self, bc, icd_dpack):
        """A code that doesn't exist in the corpus must return None."""
        assert bc.resolve(icd_dpack, "ZZZZZZZ") is None


# ── Dot normalization (resolve UX feature) ─────────────────────────────────


class TestDotNormalization:
    """Verify BlockCompressor.resolve() accepts both dotted and undotted forms."""

    def test_dotted_form_resolves(self, bc, icd_dpack):
        """J93.0 should resolve via dot normalization to the J930 key."""
        result = bc.resolve(icd_dpack, "J93.0")
        assert result is not None
        assert "tension pneumothorax" in result.lower()

    def test_undotted_form_resolves(self, bc, icd_dpack):
        """J930 should resolve directly via the verbatim path."""
        result = bc.resolve(icd_dpack, "J930")
        assert result is not None
        assert "tension pneumothorax" in result.lower()

    def test_dotted_and_undotted_return_same_text(self, bc, icd_dpack):
        """The two input forms must resolve to identical descriptions."""
        dotted = bc.resolve(icd_dpack, "I25.10")
        undotted = bc.resolve(icd_dpack, "I2510")
        assert dotted is not None
        assert undotted is not None
        assert dotted == undotted

    def test_dotted_six_char_form(self, bc, icd_dpack):
        """I25.110 (dotted) and I25110 (undotted) must both work."""
        dotted = bc.resolve(icd_dpack, "I25.110")
        undotted = bc.resolve(icd_dpack, "I25110")
        assert dotted is not None
        assert undotted is not None
        assert dotted == undotted

    def test_unknown_dotted_form_returns_none(self, bc, icd_dpack):
        """Unknown dotted code should still return None after normalization."""
        assert bc.resolve(icd_dpack, "ZZZ.99") is None

    def test_dot_normalization_is_lazy(self, bc, icd_dpack):
        """Verbatim lookup must succeed first; dot normalization is fallback only.

        We can't easily test this directly without instrumenting resolve(),
        but we can confirm that codes WITHOUT dots take the verbatim path
        by resolving a code we know has no dotted equivalent."""
        # T84030A is a 7-char encounter qualifier; no dot normalization needed
        result = bc.resolve(icd_dpack, "T84030A")
        assert result is not None  # If this fails, verbatim path is broken


# ── Corpus integrity ────────────────────────────────────────────────────────


class TestCorpusIntegrity:
    """Verify the dpack as a whole is healthy."""

    def test_corpus_size_matches_cms_fy2026(self, bc, icd_dpack):
        """FY2026 ICD-10-CM contains 74,719 codes per the CMS canonical release."""
        all_entries = bc.unpack_all(icd_dpack)
        assert len(all_entries) == 74719, (
            f"Expected 74,719 ICD-10-CM codes (FY2026 canonical CMS count), "
            f"got {len(all_entries)}. The dpack may be stale or built from "
            f"a different fiscal year."
        )

    def test_corpus_keys_are_real_icd10_format(self, bc, icd_dpack):
        """Real ICD-10 codes start with a letter A-Z (or specific subsets).
        Synthetic 4-char addresses might not follow this pattern."""
        all_entries = bc.unpack_all(icd_dpack)
        sample_keys = list(all_entries.keys())[:100]
        for key in sample_keys:
            assert len(key) >= 3, f"Key too short: {key!r}"
            assert len(key) <= 7, f"Key too long: {key!r}"
            assert key[0].isalpha(), f"Key doesn't start with letter: {key!r}"
            assert key[0].isupper(), f"Key not uppercase: {key!r}"


# ── Marker test for the audit finding ──────────────────────────────────────


def test_finding_33_marker():
    """Single-line marker test that explicitly references Finding 33.

    If this test fails, the ICD-10-CM dpack has reverted to synthetic keys
    or BlockCompressor.resolve() has lost dot normalization."""
    bc = BlockCompressor()
    path = REPO_ROOT / "mdr" / "icd10cm" / "MDR-ICD10CM-FY2026-blk.dpack"
    if not path.exists():
        pytest.skip("ICD dpack not built")
    data = path.read_bytes()

    # Two equivalent calls must return the same result via different paths
    via_dot = bc.resolve(data, "J93.0")
    via_undotted = bc.resolve(data, "J930")
    assert via_dot is not None, (
        "Finding 33 regression: dot-normalized lookup failed. "
        "BlockCompressor.resolve() must accept dotted ICD-10 input."
    )
    assert via_dot == via_undotted, (
        "Finding 33 regression: J93.0 and J930 returned different results. "
        "The dot normalization fallback is broken."
    )
    assert "tension pneumothorax" in via_dot.lower(), (
        "Finding 33 regression: J93.0 does not resolve to its real CMS "
        "description. The dpack may be using synthetic keys instead of "
        "real ICD-10 codes from the canonical CMS source."
    )
