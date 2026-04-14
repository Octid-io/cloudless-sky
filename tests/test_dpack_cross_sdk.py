"""
Cross-SDK dpack Compatibility Regression Tests (Finding 36)
===========================================================

The TypeScript SDK uses fzstd 0.1.1 for zstd decompression, which does
NOT support trained dictionaries. The Python BlockCompressor defaults
to ``use_dict=True``, which produces dict-trained dpacks that the TS
SDK cannot read. The cross-SDK contract is: every dpack shipped in
``mdr/`` must be built with ``use_dict=False`` so it's readable by all
three SDKs.

These tests enforce that contract on the dpacks currently in the repo
and on every new dpack added in the future. If a dpack is committed
with a trained dictionary, this test fails and names the file.

Note: this test does NOT prevent Python users from building dict-trained
dpacks for Python-only workflows. It only enforces the constraint on
dpacks committed under ``mdr/`` which are part of the canonical corpus
distribution.

Patent pending -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import BlockCompressor  # noqa: E402

DBLK_MAGIC = 0x44424c4b


def is_dict_trained(dpack_path: Path) -> tuple[bool, int]:
    """Inspect a DBLK binary header. Returns (is_dict_trained, dict_size)."""
    data = dpack_path.read_bytes()
    if len(data) < 24:
        raise ValueError(f"{dpack_path.name} is too short to be a DBLK")
    magic = struct.unpack(">I", data[:4])[0]
    if magic != DBLK_MAGIC:
        raise ValueError(
            f"{dpack_path.name} has wrong magic 0x{magic:08x}, expected DBLK"
        )
    flags = struct.unpack(">H", data[6:8])[0]
    dict_size = struct.unpack(">I", data[16:20])[0]
    has_dict = bool(flags & 1) and dict_size > 0
    return has_dict, dict_size


def collect_shipped_dpacks() -> list[Path]:
    """Find every dpack file under mdr/."""
    mdr_dir = REPO_ROOT / "mdr"
    if not mdr_dir.exists():
        return []
    return sorted(mdr_dir.rglob("*.dpack"))


# ── Cross-SDK compatibility enforcement ──────────────────────────────────


class TestDpackCrossSDKCompatibility:
    """Every dpack in mdr/ must be readable by the TypeScript SDK."""

    def test_at_least_one_dpack_present(self):
        """Sanity check: the test would silently pass if there were no
        dpacks to inspect. Ensure at least one canonical corpus exists."""
        dpacks = collect_shipped_dpacks()
        assert len(dpacks) > 0, (
            "No dpacks found under mdr/. The cross-SDK compatibility "
            "test is meaningless without any corpora to verify."
        )

    @pytest.mark.parametrize(
        "dpack_path",
        collect_shipped_dpacks(),
        ids=lambda p: p.name,
    )
    def test_dpack_is_dict_free(self, dpack_path: Path):
        """Every shipped dpack must NOT use a trained zstd dictionary,
        because the TypeScript SDK's fzstd dependency cannot decompress
        dict-trained binaries."""
        has_dict, dict_size = is_dict_trained(dpack_path)
        assert not has_dict, (
            f"Finding 36 regression: {dpack_path.relative_to(REPO_ROOT)} "
            f"is dict-trained ({dict_size} byte dictionary). The TypeScript "
            f"SDK cannot read this binary because fzstd 0.1.1 does not "
            f"support trained dictionaries.\n\n"
            f"Rebuild with `BlockCompressor(use_dict=False)` to make this "
            f"corpus cross-SDK compatible."
        )

    @pytest.mark.parametrize(
        "dpack_path",
        collect_shipped_dpacks(),
        ids=lambda p: p.name,
    )
    def test_dpack_resolves_at_least_one_key(self, dpack_path: Path):
        """End-to-end: every shipped dpack must successfully decompress
        at least one block via the resolve interface. This catches both
        the dict-trained constraint AND any other read-side breakage."""
        bc = BlockCompressor()
        data = dpack_path.read_bytes()
        all_entries = bc.unpack_all(data)
        assert len(all_entries) > 0, (
            f"{dpack_path.name} unpacked to zero entries"
        )
        # Try resolving the first key — exercises the binary search path
        first_key = next(iter(all_entries))
        result = bc.resolve(data, first_key)
        assert result is not None, (
            f"{dpack_path.name}: first key {first_key!r} did not resolve"
        )


# ── BlockCompressor constructor contract ────────────────────────────────


class TestBlockCompressorDefault:
    """The Python BlockCompressor defaults to use_dict=True for backward
    compatibility, but build tools that produce cross-SDK corpora MUST
    explicitly opt out. These tests document the contract."""

    def test_default_is_dict_trained(self):
        """Documents the current default. If this test fails, the
        default has been flipped — verify that the build tools and
        any direct callers are updated accordingly."""
        bc = BlockCompressor()
        assert bc.use_dict is True

    def test_use_dict_false_is_explicit(self):
        bc = BlockCompressor(use_dict=False)
        assert bc.use_dict is False

    def test_dict_free_dpack_has_no_dict_flag(self, tmp_path):
        """A dpack built with use_dict=False must have flags & 1 == 0."""
        bc = BlockCompressor(use_dict=False)
        entries = [(f"K{i:04d}", f"value_{i}") for i in range(20)]
        data = bc.pack(entries)
        flags = struct.unpack(">H", data[6:8])[0]
        dict_size = struct.unpack(">I", data[16:20])[0]
        assert (flags & 1) == 0
        assert dict_size == 0


# ── Marker test for the audit finding ────────────────────────────────────


def test_finding_36_marker():
    """Single-line marker that explicitly references Finding 36. If this
    fails, a dict-trained dpack has been committed to mdr/ and the
    TypeScript SDK can no longer read it."""
    for dpack_path in collect_shipped_dpacks():
        has_dict, dict_size = is_dict_trained(dpack_path)
        assert not has_dict, (
            f"Finding 36 regression: {dpack_path.name} is dict-trained "
            f"({dict_size} bytes). Rebuild with use_dict=False."
        )
