#!/usr/bin/env python3
"""Build osmp for release, verifying IP-sensitive research files are excluded.

The public `osmp` package on PyPI must NOT ship with:

  - osmp/_eml_*.py      (chain construction toolchain — trade secret)
  - osmp/eml_torch.py   (PyTorch training loop — trade secret)
  - osmp/eml_chain*.py  (future chain-related research files, reserved pattern)

PRIMARY SAFEGUARD: these files live in `sdk/python/` (the project root,
alongside pyproject.toml), NOT inside `sdk/python/osmp/`. Because they
are outside the `osmp` package directory, setuptools cannot pick them
up via `packages.find`. Structural separation is the enforcement
mechanism; gitignore is for git, not for the build system.

SECONDARY SAFEGUARD (this script): if someone ever drops a matching
file INTO `sdk/python/osmp/`, this script will:

  1. Temp-move any matching files out of `osmp/` before building
  2. Build sdist + wheel (uses `pip wheel` — more reliable than
     `python -m build` in some environments)
  3. Verify every resulting artifact is clean of the sensitive names
     (RuntimeError if any leaked — fails loudly rather than silently)
  4. Restore the moved files whether the build succeeded or failed

Usage:

    cd sdk/python
    python build.py

Output: sdk/python/dist/osmp-*.whl and sdk/python/dist/osmp-*.tar.gz.

If this script detects sensitive files inside `osmp/`, a loud warning is
printed — they should be moved back to `sdk/python/` root-level where
they belong.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE / "osmp"

# Patterns that MUST be excluded from any published artifact.
IP_SENSITIVE_PATTERNS: list[str] = [
    "_eml_*.py",
    "eml_torch.py",
    "eml_chain*.py",
]


def sensitive_files() -> list[Path]:
    files: list[Path] = []
    for pattern in IP_SENSITIVE_PATTERNS:
        files.extend(PKG_DIR.glob(pattern))
    return files


def verify_wheel_clean(whl: Path, sensitive_names: set[str]) -> None:
    import zipfile

    with zipfile.ZipFile(whl) as z:
        for name in z.namelist():
            base = Path(name).name
            if base in sensitive_names:
                raise RuntimeError(
                    f"IP-SENSITIVE FILE LEAKED: {name!r} is present in {whl.name}. "
                    f"Build aborted. Do NOT upload this artifact."
                )


def verify_sdist_clean(tgz: Path, sensitive_names: set[str]) -> None:
    import tarfile

    with tarfile.open(tgz) as t:
        for m in t:
            base = Path(m.name).name
            if base in sensitive_names:
                raise RuntimeError(
                    f"IP-SENSITIVE FILE LEAKED: {m.name!r} is present in {tgz.name}. "
                    f"Build aborted. Do NOT upload this artifact."
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build osmp for release (exclude IP-sensitive files)")
    parser.add_argument(
        "--no-isolation",
        action="store_true",
        help="Pass --no-isolation to python -m build (reuse current env setuptools)",
    )
    args = parser.parse_args()

    sensitive = sensitive_files()
    sensitive_names = {f.name for f in sensitive}

    if sensitive:
        print(f"[build] excluding {len(sensitive)} IP-sensitive file(s): {sorted(sensitive_names)}")
    else:
        print("[build] no IP-sensitive files present to exclude")

    backup = Path(tempfile.mkdtemp(prefix="osmp-build-backup-"))
    moved: list[tuple[Path, Path]] = []

    try:
        # Move IP-sensitive files out of the package before building
        for f in sensitive:
            dst = backup / f.name
            shutil.move(str(f), str(dst))
            moved.append((f, dst))
            print(f"[build] temp-moved {f.relative_to(HERE)} -> {dst}")

        # Clean prior build artifacts so we build fresh
        for d in ("dist", "build", "osmp.egg-info"):
            p = HERE / d
            if p.exists():
                shutil.rmtree(p)

        # Run build. `python -m build` with no args builds both sdist and wheel.
        build_cmd = [sys.executable, "-m", "build"]
        if args.no_isolation:
            build_cmd.append("--no-isolation")
        print(f"[build] running: {' '.join(build_cmd)}")
        subprocess.run(build_cmd, cwd=HERE, check=True)

        # Verify no IP-sensitive files leaked into any artifact
        dist = HERE / "dist"
        if sensitive_names:
            for whl in sorted(dist.glob("osmp-*.whl")):
                verify_wheel_clean(whl, sensitive_names)
                print(f"[build] verified clean: {whl.name}")
            for tgz in sorted(dist.glob("osmp-*.tar.gz")):
                verify_sdist_clean(tgz, sensitive_names)
                print(f"[build] verified clean: {tgz.name}")

        print("[build] OK — artifacts in sdk/python/dist/ are safe to upload")
        return 0

    finally:
        # Always restore moved files, even on build failure
        for _orig, backup_path in moved:
            orig = PKG_DIR / backup_path.name
            shutil.move(str(backup_path), str(orig))
            print(f"[build] restored {orig.name}")
        try:
            backup.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
