"""
ASD Cross-SDK No-Drift Regression Tests (Finding 9, ADR-001)
============================================================

These tests guard against the Finding 9 regression where the TypeScript
and Go SDK glyph files could silently drift from the canonical Python
source. Before `tools/gen_asd.py` existed, the only mechanism keeping
the three SDKs in sync was developer discipline, and ADR-001 specified
a generation tool that was never built.

Now the tool exists, and these tests wire `gen_asd.py --check` into
the test suite so any divergence between the Python source and the
on-disk TS/Go files triggers a test failure that names the specific
file that drifted.

Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import ASD_BASIS  # noqa: E402


# ── gen_asd.py --check enforcement ─────────────────────────────────────────


class TestGenAsdNoDrift:
    """The on-disk TS and Go glyph files must match what gen_asd.py
    would produce from the canonical Python source. Any drift is a
    regression that must be fixed by running `python3 tools/gen_asd.py`
    (or by updating protocol.py first if the drift represents an
    intended change that hasn't been propagated yet)."""

    def test_gen_asd_check_reports_in_sync(self):
        """Run `python3 tools/gen_asd.py --check` and assert exit 0."""
        tool_path = REPO_ROOT / "tools" / "gen_asd.py"
        if not tool_path.exists():
            pytest.skip("gen_asd.py not present")

        result = subprocess.run(
            [sys.executable, str(tool_path), "--check", "--quiet"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

        if result.returncode != 0:
            pytest.fail(
                f"gen_asd.py --check detected drift.\n"
                f"Run `python3 tools/gen_asd.py` to regenerate.\n\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

    def test_gen_asd_is_idempotent(self):
        """Running gen_asd.py followed by gen_asd.py --check must
        report zero drift. This is a sanity check on the tool itself:
        if the generator is non-deterministic or the check logic is
        wrong, the sequence will produce inconsistent results."""
        tool_path = REPO_ROOT / "tools" / "gen_asd.py"
        if not tool_path.exists():
            pytest.skip("gen_asd.py not present")

        # Write mode
        write_result = subprocess.run(
            [sys.executable, str(tool_path), "--quiet"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert write_result.returncode == 0, (
            f"gen_asd.py write mode failed: {write_result.stderr}"
        )

        # Immediate check mode — should report in sync
        check_result = subprocess.run(
            [sys.executable, str(tool_path), "--check", "--quiet"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert check_result.returncode == 0, (
            "gen_asd.py is not idempotent: write mode followed by check "
            "mode reports drift. This indicates a non-deterministic "
            "generator (e.g., dict iteration order, timestamp in output, "
            "unsorted serialization). "
            f"\n\nSTDOUT:\n{check_result.stdout}"
        )


# ── Direct opcode content comparison ───────────────────────────────────────


class TestASDContentMatch:
    """Parse the TS and Go glyph files directly and verify every
    opcode in ASD_BASIS is present with the exact same meaning string.
    This catches drift that might not be visible to gen_asd.py --check
    if the generator itself has a bug that produces output matching
    an incorrect on-disk state."""

    def test_ts_asd_basis_matches_python(self):
        import re
        ts_path = REPO_ROOT / "sdk" / "typescript" / "src" / "glyphs.ts"
        text = ts_path.read_text(encoding="utf-8")

        m = re.search(
            r'ASD_BASIS[^{]*\{(.+?)^\};',
            text, re.DOTALL | re.MULTILINE,
        )
        assert m is not None, "Could not find ASD_BASIS block in glyphs.ts"
        block = m.group(1)

        parsed: dict[str, dict[str, str]] = {}
        current_ns: str | None = None
        for line in block.splitlines():
            ns_match = re.match(r'\s*"([A-Z])"\s*:\s*\{', line)
            if ns_match:
                current_ns = ns_match.group(1)
                parsed[current_ns] = {}
                continue
            op_match = re.match(r'\s*"([^"]+)"\s*:\s*"([^"]+)"', line)
            if op_match and current_ns:
                parsed[current_ns][op_match.group(1)] = op_match.group(2)

        # Every namespace in Python source must be present in TS
        for ns in ASD_BASIS:
            assert ns in parsed, f"Namespace {ns!r} missing from TS ASD_BASIS"

        # Every opcode in Python source must match TS byte-for-byte
        for ns, ops in ASD_BASIS.items():
            for op, meaning in ops.items():
                ts_meaning = parsed[ns].get(op)
                assert ts_meaning is not None, (
                    f"Opcode {ns}:{op} missing from TS ASD_BASIS"
                )
                assert ts_meaning == meaning, (
                    f"Opcode {ns}:{op} meaning mismatch:\n"
                    f"  Python: {meaning!r}\n"
                    f"  TS:     {ts_meaning!r}"
                )

        # Reverse: no extra opcodes in TS that aren't in Python
        for ns, ops in parsed.items():
            for op in ops:
                assert op in ASD_BASIS.get(ns, {}), (
                    f"Orphan opcode {ns}:{op} in TS not present in Python source"
                )

    def test_go_asd_basis_matches_python(self):
        import re
        go_path = REPO_ROOT / "sdk" / "go" / "osmp" / "glyphs.go"
        text = go_path.read_text(encoding="utf-8")

        m = re.search(
            r'ASDFloorBasis[^{]*\{(.+?)^\}',
            text, re.DOTALL | re.MULTILINE,
        )
        assert m is not None, "Could not find ASDFloorBasis block in glyphs.go"
        block = m.group(1)

        parsed: dict[str, dict[str, str]] = {}
        current_ns: str | None = None
        for line in block.splitlines():
            ns_match = re.match(r'\s*"([A-Z])"\s*:\s*\{', line)
            if ns_match:
                current_ns = ns_match.group(1)
                parsed[current_ns] = {}
                continue
            op_match = re.match(r'\s*"([^"]+)"\s*:\s*"([^"]+)"', line)
            if op_match and current_ns:
                parsed[current_ns][op_match.group(1)] = op_match.group(2)

        for ns in ASD_BASIS:
            assert ns in parsed, f"Namespace {ns!r} missing from Go ASDFloorBasis"

        for ns, ops in ASD_BASIS.items():
            for op, meaning in ops.items():
                go_meaning = parsed[ns].get(op)
                assert go_meaning is not None, (
                    f"Opcode {ns}:{op} missing from Go ASDFloorBasis"
                )
                assert go_meaning == meaning, (
                    f"Opcode {ns}:{op} meaning mismatch:\n"
                    f"  Python: {meaning!r}\n"
                    f"  Go:     {go_meaning!r}"
                )

        for ns, ops in parsed.items():
            for op in ops:
                assert op in ASD_BASIS.get(ns, {}), (
                    f"Orphan opcode {ns}:{op} in Go not present in Python source"
                )

    def test_opcode_counts_match(self):
        """The 352 opcode count appears in docs, the whitepaper, the MCP
        `osmp://about` resource, and the system prompt. Lock it in as a
        test assertion so changes to the dictionary force a coordinated
        update across all those reference sites."""
        total = sum(len(ops) for ops in ASD_BASIS.values())
        assert total == 352, (
            f"ASD_BASIS opcode count changed to {total}. If this was an "
            f"intentional addition or removal, update the whitepaper, "
            f"the osmp://about MCP resource, the system prompt in "
            f"osmp_mcp/server.py, and any patent claim text that "
            f"references the 352 figure."
        )

    def test_namespace_count_matches(self):
        assert len(ASD_BASIS) == 26, (
            f"ASD_BASIS namespace count changed to {len(ASD_BASIS)}. "
            f"Coordinate with whitepaper and patent claims."
        )


# ── Marker test for the audit finding ─────────────────────────────────────


def test_finding_9_marker():
    """Single-line marker that explicitly references Finding 9. If this
    fails, either gen_asd.py is broken or the on-disk SDK files have
    drifted from the canonical Python source."""
    tool_path = REPO_ROOT / "tools" / "gen_asd.py"
    assert tool_path.exists(), (
        "Finding 9 regression: tools/gen_asd.py is missing. "
        "ADR-001 requires this tool for cross-SDK no-drift enforcement."
    )

    result = subprocess.run(
        [sys.executable, str(tool_path), "--check", "--quiet"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"Finding 9 regression: gen_asd.py --check reports drift between "
        f"Python source and on-disk SDK files. "
        f"Run `python3 tools/gen_asd.py` to fix.\n\n{result.stdout}"
    )
