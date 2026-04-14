#!/usr/bin/env python3
"""
build_mdr_icd10cm.py
====================

Regenerate the ICD-10-CM domain corpus dpack from the canonical CMS source
file. This script is the answer to Finding 33 from the Octid-io/cloudless-sky
audit (April 2026): the original dpack was packed with synthetic 4-character
sequential keys instead of real ICD-10-CM code numbers, which made the MCP
`osmp_resolve` tool effectively unusable for clinical workflows.

Source data
-----------
The CMS National Center for Health Statistics (NCHS) releases the canonical
ICD-10-CM code descriptions as a tab-separated text file inside the FY release
ZIP. The file format is::

    A000\\tCholera due to Vibrio cholerae 01, biovar cholerae
    A001\\tCholera due to Vibrio cholerae 01, biovar eltor
    A009\\tCholera, unspecified
    A0100\\tTyphoid fever, unspecified
    ...

Keys are real ICD-10-CM codes with the decimal point stripped (J93.0 → J930,
I25.10 → I2510, A01.05 → A0105). Descriptions are the canonical CMS
human-readable strings.

The current canonical release for FY2026 is downloadable from::

    https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026/

Specifically the file ``icd10cm-Code Descriptions-2026.zip`` which contains
``icd10cm-codes-2026.txt`` (74,719 codes for FY2026).

This script reads ``mdr/icd10cm/icd10cm-codes-2026.txt`` (committed alongside
the dpack for reproducibility) and produces ``MDR-ICD10CM-FY2026-blk.dpack``
using the BlockCompressor from the OSMP Python SDK.

Output dpack format
-------------------
The dpack uses real ICD-10-CM codes (no decimal point) as the lookup keys.
After packing, ``BlockCompressor.resolve(dpack, "J930")`` returns the
canonical CMS description string. The resolve method also accepts the
dotted form ``"J93.0"`` (normalized by stripping the dot) so callers can
pass either form interchangeably.

Usage
-----
::

    python3 tools/build_mdr_icd10cm.py
    python3 tools/build_mdr_icd10cm.py --source mdr/icd10cm/icd10cm-codes-2026.txt
    python3 tools/build_mdr_icd10cm.py --output mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack
    python3 tools/build_mdr_icd10cm.py --verify

The ``--verify`` flag runs the build, then resolves a curated set of canonical
test codes (J93.0, R00.1, I25.10, etc.) to confirm the lookup interface works
end-to-end. Returns non-zero exit if any verification case fails.

Patent pending -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import BlockCompressor  # noqa: E402


# Default paths
DEFAULT_SOURCE = REPO_ROOT / "mdr" / "icd10cm" / "icd10cm-codes-2026.txt"
DEFAULT_OUTPUT = REPO_ROOT / "mdr" / "icd10cm" / "MDR-ICD10CM-FY2026-blk.dpack"


# Verification vectors — real ICD-10-CM codes that an LLM is likely to use.
# Each tuple is (input_form, expected_canonical_key, expected_description_substring).
# The input_form may be either dotted ("J93.0") or undotted ("J930"); the
# resolver normalizes both to the dpack key by stripping dots.
VERIFICATION_VECTORS = [
    ("J93.0",  "J930",  "Spontaneous tension pneumothorax"),
    ("J930",   "J930",  "Spontaneous tension pneumothorax"),
    ("J93.9",  "J939",  "Pneumothorax, unspecified"),
    ("R00.1",  "R001",  "Bradycardia"),
    ("I25.10", "I2510", "Atherosclerotic heart disease"),
    ("A00.0",  "A000",  "Cholera"),
    ("Z00.00", "Z0000", "general adult medical examination"),
    ("E11.9",  "E119",  "Type 2 diabetes"),
    # Pure-undotted form an LLM might emit:
    ("J9311",  "J9311", "Primary spontaneous pneumothorax"),
    ("I25110", "I25110", "Atherosclerotic heart disease"),
]


def parse_source(source_path: Path) -> list[tuple[str, str]]:
    """Parse the CMS canonical tab-separated codes file.

    The file uses CRLF line endings and tab separators. Each line is
    ``CODE\\tDESCRIPTION``. Returns a list of (code, description) tuples
    sorted by code (which the BlockCompressor.pack method requires).
    """
    if not source_path.exists():
        raise FileNotFoundError(
            f"CMS source file not found at {source_path}\n"
            f"Download from https://ftp.cdc.gov/pub/Health_Statistics/NCHS/"
            f"Publications/ICD10CM/2026/icd10cm-Code Descriptions-2026.zip "
            f"and extract icd10cm-codes-2026.txt to that path."
        )

    entries: list[tuple[str, str]] = []
    raw = source_path.read_bytes().decode("utf-8")
    for line_no, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        # The CMS file uses tabs and may contain multiple spaces inside the
        # description. The first whitespace run separates the code from the
        # description.
        parts = line.split(None, 1)
        if len(parts) != 2:
            print(
                f"WARNING: line {line_no} skipped (no description): {line!r}",
                file=sys.stderr,
            )
            continue
        code, description = parts[0], parts[1]
        entries.append((code, description))

    # BlockCompressor.pack requires entries sorted by key for binary search
    entries.sort(key=lambda e: e[0])
    return entries


def build_dpack(entries: list[tuple[str, str]], output_path: Path) -> int:
    """Pack entries into a DBLK binary at output_path. Returns byte size."""
    bc = BlockCompressor(use_dict=False)
    dpack = bc.pack(entries)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(dpack)
    return len(dpack)


def verify(dpack_path: Path) -> bool:
    """Resolve every VERIFICATION_VECTOR against the built dpack.

    Returns True if every case resolves to a description containing the
    expected substring; False if any case fails.
    """
    bc = BlockCompressor()
    data = dpack_path.read_bytes()

    all_ok = True
    print()
    print(f"Verifying {dpack_path.name} against {len(VERIFICATION_VECTORS)} canonical vectors:")
    print()
    for input_form, expected_key, expected_substring in VERIFICATION_VECTORS:
        result = bc.resolve(data, input_form)
        if result is None:
            print(f"  FAIL  {input_form:8} -> Not found "
                  f"(expected key {expected_key} -> {expected_substring!r})")
            all_ok = False
            continue
        if expected_substring.lower() not in result.lower():
            print(f"  FAIL  {input_form:8} -> {result[:60]!r} "
                  f"(expected substring {expected_substring!r})")
            all_ok = False
            continue
        print(f"  OK    {input_form:8} -> {result[:60]}")

    print()
    if all_ok:
        print(f"All {len(VERIFICATION_VECTORS)} verification vectors PASSED.")
    else:
        print(f"VERIFICATION FAILED. The dpack does not satisfy the canonical "
              f"lookup contract.")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the ICD-10-CM domain corpus dpack from the "
                    "canonical CMS source file (Finding 33).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source", type=Path, default=DEFAULT_SOURCE,
        help=f"Path to the CMS icd10cm-codes-YYYY.txt file (default: {DEFAULT_SOURCE.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Path to write the dpack file (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Run the canonical verification suite after building.",
    )
    args = parser.parse_args()

    print(f"Reading source: {args.source}")
    entries = parse_source(args.source)
    print(f"Parsed {len(entries):,} ICD-10-CM codes.")

    # Spot-check a few canonical examples to make sure the parser worked
    sample_keys = ["J930", "I2510", "R001", "A000", "Z000"]
    by_key = dict(entries)
    print()
    print("Source spot-check (5 canonical codes):")
    for k in sample_keys:
        desc = by_key.get(k)
        if desc:
            print(f"  {k:8} -> {desc[:60]}")
        else:
            print(f"  {k:8} -> NOT FOUND IN SOURCE")

    print()
    print(f"Building dpack: {args.output}")
    size = build_dpack(entries, args.output)
    print(f"Wrote {size:,} bytes ({size/1024:.1f} KiB).")

    if args.verify:
        if not verify(args.output):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
