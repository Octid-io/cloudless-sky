"""
ISO 20022 MSG Corpus Regression Tests (Finding 34)
==================================================

These tests guard against the Finding 34 regression where the
mdr/iso20022/MDR-ISO20022-MSG-FULL.csv source file existed in the repo
with 810 real ISO 20022 message definitions but no dpack was built from
it and no MCP server tool exposed it for resolution.

The fix has three parts:
  1. tools/build_mdr_iso20022_msg.py packs the source CSV into
     mdr/iso20022/MDR-ISO20022-MSG-blk.dpack with dotted message IDs
     (pacs.008.001.13, camt.053.001.13) as keys verbatim
  2. osmp_mcp/server.py registers "iso_msg" / "iso20022_msg" aliases
     in MDR_CORPORA without breaking the existing "iso" alias
  3. Resolver tools (osmp_resolve, osmp_batch_resolve, osmp_discover)
     accept the new corpus name and route to the new dpack

Patent pending -- inventor Clay Holberg
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
def iso_msg_dpack() -> bytes:
    path = REPO_ROOT / "mdr" / "iso20022" / "MDR-ISO20022-MSG-blk.dpack"
    if not path.exists():
        pytest.skip(f"ISO 20022 MSG dpack not built: run tools/build_mdr_iso20022_msg.py first")
    return path.read_bytes()


@pytest.fixture(scope="module")
def bc() -> BlockCompressor:
    return BlockCompressor()


# ── Canonical payment messages ──────────────────────────────────────────────


class TestCanonicalPaymentMessages:
    """The most important ISO 20022 messages every payment system uses."""

    def test_pacs_008_resolves(self, bc, iso_msg_dpack):
        """pacs.008.001.13 = FIToFICustomerCreditTransfer (the canonical
        cross-border credit transfer message used by every modern payment system)."""
        result = bc.resolve(iso_msg_dpack, "pacs.008.001.13")
        assert result is not None
        assert "FIToFICustomerCreditTransfer" in result
        assert "credit transfer" in result.lower()

    def test_pacs_009_resolves(self, bc, iso_msg_dpack):
        """pacs.009.001.12 = FinancialInstitutionCreditTransfer."""
        result = bc.resolve(iso_msg_dpack, "pacs.009.001.12")
        assert result is not None
        assert "FinancialInstitutionCreditTransfer" in result

    def test_camt_053_resolves(self, bc, iso_msg_dpack):
        """camt.053.001.13 = BankToCustomerStatement."""
        result = bc.resolve(iso_msg_dpack, "camt.053.001.13")
        assert result is not None
        assert "BankToCustomerStatement" in result
        assert "statement" in result.lower()

    def test_camt_054_resolves(self, bc, iso_msg_dpack):
        """camt.054.001.13 = BankToCustomerDebitCreditNotification."""
        result = bc.resolve(iso_msg_dpack, "camt.054.001.13")
        assert result is not None
        assert "BankToCustomerDebitCreditNotification" in result

    def test_pain_001_resolves(self, bc, iso_msg_dpack):
        """pain.001.001.12 = CustomerCreditTransferInitiation (the corporate
        customer payment initiation message)."""
        result = bc.resolve(iso_msg_dpack, "pain.001.001.12")
        assert result is not None
        assert "CustomerCreditTransferInitiation" in result

    def test_acmt_001_resolves(self, bc, iso_msg_dpack):
        """acmt.001.001.08 = AccountOpeningInstruction."""
        result = bc.resolve(iso_msg_dpack, "acmt.001.001.08")
        assert result is not None
        assert "AccountOpeningInstruction" in result


# ── Dotted-form lookup is the canonical path ───────────────────────────────


class TestDottedFormLookup:
    """ISO 20022 message IDs are dotted by canonical convention. The
    resolve method must find them via the verbatim path (no dot
    normalization needed for this corpus)."""

    def test_dotted_form_is_verbatim_lookup(self, bc, iso_msg_dpack):
        """The dotted form must hit the dpack on the first try, not the
        dot-stripped fallback path. We can't directly observe the path
        but we can confirm the lookup succeeds for keys that contain dots."""
        result = bc.resolve(iso_msg_dpack, "pacs.008.001.13")
        assert result is not None

    def test_undotted_form_returns_none(self, bc, iso_msg_dpack):
        """An ISO 20022 caller mistakenly stripping dots should get None,
        not silently match a different message."""
        # pacs00800113 is not a valid ISO 20022 identifier
        result = bc.resolve(iso_msg_dpack, "pacs00800113")
        assert result is None

    def test_unknown_message_returns_none(self, bc, iso_msg_dpack):
        """Unknown but well-formed message IDs return None."""
        result = bc.resolve(iso_msg_dpack, "xxxx.999.999.99")
        assert result is None


# ── Corpus integrity ────────────────────────────────────────────────────────


class TestCorpusIntegrity:
    """Verify the dpack as a whole is healthy."""

    def test_corpus_has_810_messages(self, bc, iso_msg_dpack):
        """The MSG corpus contains 810 ISO 20022 message definitions
        per the source CSV header."""
        all_entries = bc.unpack_all(iso_msg_dpack)
        assert len(all_entries) == 810, (
            f"Expected 810 ISO 20022 message definitions, got {len(all_entries)}. "
            f"The dpack may be stale or built from a different source release."
        )

    def test_all_keys_are_dotted_iso_format(self, bc, iso_msg_dpack):
        """Real ISO 20022 message IDs follow the format
        ``business_area.message.variant.version`` (4 dot-separated segments).
        Sample 100 keys and confirm they all match this pattern."""
        all_entries = bc.unpack_all(iso_msg_dpack)
        sample_keys = list(all_entries.keys())[:100]
        for key in sample_keys:
            parts = key.split(".")
            assert len(parts) == 4, (
                f"ISO 20022 key {key!r} doesn't have 4 dot-separated segments"
            )
            assert parts[0].isalpha(), (
                f"ISO 20022 business area {parts[0]!r} should be alphabetic"
            )
            for segment in parts[1:]:
                assert segment.isdigit(), (
                    f"ISO 20022 segment {segment!r} should be numeric"
                )

    def test_pacs_message_family_is_present(self, bc, iso_msg_dpack):
        """The pacs.* business area (Payments Clearing and Settlement)
        should have multiple variants represented."""
        all_entries = bc.unpack_all(iso_msg_dpack)
        pacs_keys = [k for k in all_entries.keys() if k.startswith("pacs.")]
        assert len(pacs_keys) >= 10, (
            f"Expected at least 10 pacs.* messages in the corpus, "
            f"got {len(pacs_keys)}"
        )


# ── MCP server integration ──────────────────────────────────────────────────


class TestMCPServerIntegration:
    """Verify the MCP server's MDR_CORPORA registration includes the new aliases."""

    def test_iso_msg_alias_registered(self):
        """Both 'iso_msg' and 'iso20022_msg' should be registered in MDR_CORPORA."""
        sys.path.insert(0, str(REPO_ROOT))
        from osmp_mcp.server import MDR_CORPORA
        assert "iso_msg" in MDR_CORPORA
        assert "iso20022_msg" in MDR_CORPORA

    def test_iso_msg_path_points_to_msg_dpack(self):
        """The iso_msg alias must point to the MSG dpack, not the K-ISO dpack."""
        from osmp_mcp.server import MDR_CORPORA
        assert "MSG" in str(MDR_CORPORA["iso_msg"])

    def test_existing_iso_alias_unchanged(self):
        """The existing 'iso' alias must still point to the K-ISO definitions
        corpus for backward compatibility (no breaking change)."""
        from osmp_mcp.server import MDR_CORPORA
        assert "K-ISO" in str(MDR_CORPORA["iso"])

    def test_iso_def_explicit_alias_registered(self):
        """The explicit 'iso_def' alias should also be registered for
        callers who want to be unambiguous about wanting the K-ISO corpus."""
        from osmp_mcp.server import MDR_CORPORA
        assert "iso_def" in MDR_CORPORA
        assert "K-ISO" in str(MDR_CORPORA["iso_def"])

    def test_mcp_load_mdr_can_load_iso_msg(self):
        """The MCP _load_mdr function must successfully load the new corpus."""
        from osmp_mcp.server import _load_mdr
        data = _load_mdr("iso_msg")
        assert data is not None
        assert len(data) > 0
        # Spot-check that resolving against the loaded data works
        bc = BlockCompressor()
        result = bc.resolve(data, "pacs.008.001.13")
        assert result is not None
        assert "FIToFICustomerCreditTransfer" in result


# ── Marker test for the audit finding ──────────────────────────────────────


def test_finding_34_marker():
    """Single-line marker test that explicitly references Finding 34.

    If this test fails, the ISO 20022 MSG corpus is no longer built or the
    MCP server has lost its iso_msg alias registration."""
    path = REPO_ROOT / "mdr" / "iso20022" / "MDR-ISO20022-MSG-blk.dpack"
    if not path.exists():
        pytest.fail(
            "Finding 34 regression: MDR-ISO20022-MSG-blk.dpack does not exist. "
            "Run tools/build_mdr_iso20022_msg.py to regenerate."
        )

    bc = BlockCompressor()
    data = path.read_bytes()
    result = bc.resolve(data, "pacs.008.001.13")
    assert result is not None, (
        "Finding 34 regression: pacs.008.001.13 does not resolve in the "
        "ISO 20022 MSG corpus. The dpack may be empty or corrupted."
    )
    assert "credit transfer" in result.lower(), (
        "Finding 34 regression: pacs.008.001.13 resolves but to the wrong "
        "definition. The dpack may be packed with wrong source data."
    )
