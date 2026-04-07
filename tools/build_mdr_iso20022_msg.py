#!/usr/bin/env python3
"""
build_mdr_iso20022_msg.py
=========================

Pack the ISO 20022 message definitions corpus into a binary D:PACK/BLK
domain corpus dpack for use as an MDR loaded by the OSMP MCP server.
This script is the answer to Finding 34 from the Octid-io/cloudless-sky
audit (April 2026): the source CSV
``mdr/iso20022/MDR-ISO20022-MSG-FULL.csv`` exists in the repo with 810
real ISO 20022 message definitions, but no dpack was built from it and
no MCP server tool exposed it for resolution.

Source data
-----------
``mdr/iso20022/MDR-ISO20022-MSG-FULL.csv`` is a 583 KiB CSV file
containing 810 ISO 20022 message definitions sourced from the ISO 20022
eRepository (release 2025-04-24). The file format is::

    OSMP MDR - ISO 20022 Message Definitions (Full eRepository)
    Source: ISO 20022 eRepository 2025-04-24
    Messages: 810,...
    Docket: OSMP-001-UTIL (patent pending),Inventor: Clay Holberg

    message_id,message_name,definition
    acmt.001.001.08,AccountOpeningInstructionV08,"Scope The..."
    pacs.008.001.13,FIToFICustomerCreditTransferV13,"Scope The..."
    ...

Each row has three fields:
  - ``message_id``: the canonical ISO 20022 dotted message identifier
    (e.g. ``pacs.008.001.13``, ``camt.053.001.13``)
  - ``message_name``: the camel-case message class name
    (e.g. ``FIToFICustomerCreditTransferV13``)
  - ``definition``: the official ISO 20022 description text, which may
    contain commas (and is therefore CSV-quoted)

Output dpack format
-------------------
The dpack uses the **dotted ISO 20022 message ID** as the lookup key
verbatim. Unlike ICD-10-CM (where CMS publishes codes with dots stripped
as the canonical storage form), ISO 20022 publishes message identifiers
with dots as the canonical lingua franca form. Every SWIFT message,
every payment system, every banking integration documents these
identifiers as ``pacs.008.001.13`` -- there is no "stripped" canonical
form to compete with.

The value stored against each key is a single SAL-friendly string:
``message_name: definition``. This format keeps the resolve output
compact for one-shot LLM lookups while preserving both the human-readable
class name and the official scope text.

Usage
-----
::

    python3 tools/build_mdr_iso20022_msg.py
    python3 tools/build_mdr_iso20022_msg.py --source mdr/iso20022/MDR-ISO20022-MSG-FULL.csv
    python3 tools/build_mdr_iso20022_msg.py --output mdr/iso20022/MDR-ISO20022-MSG-blk.dpack
    python3 tools/build_mdr_iso20022_msg.py --verify

The ``--verify`` flag runs the build, then resolves a curated set of
canonical payment, statement, and account messages to confirm the
lookup interface works end-to-end. Returns non-zero exit if any
verification case fails.

Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import BlockCompressor  # noqa: E402


# Default paths
DEFAULT_SOURCE = REPO_ROOT / "mdr" / "iso20022" / "MDR-ISO20022-MSG-FULL.csv"
DEFAULT_OUTPUT = REPO_ROOT / "mdr" / "iso20022" / "MDR-ISO20022-MSG-blk.dpack"


# Verification vectors -- canonical ISO 20022 messages every payment
# system in the world supports. Each tuple is
# (message_id, expected_class_name_substring, expected_definition_substring).
VERIFICATION_VECTORS = [
    ("pacs.008.001.13", "FIToFICustomerCreditTransferV13", "credit transfer"),
    ("pacs.009.001.12", "FinancialInstitutionCreditTransferV12", "financial institution"),
    ("camt.053.001.13", "BankToCustomerStatementV13", "statement"),
    ("camt.054.001.13", "BankToCustomerDebitCreditNotificationV13", "debit"),
    ("pain.001.001.12", "CustomerCreditTransferInitiationV12", "initiation"),
    ("acmt.001.001.08", "AccountOpeningInstructionV08", "account opening"),
]


def parse_source(source_path: Path) -> list[tuple[str, str]]:
    """Parse the ISO 20022 MSG-FULL CSV file.

    Skips the metadata header (4 lines) and the column header line, then
    parses each data row using the standard csv module so quoted definitions
    containing commas are handled correctly.

    Returns a list of (message_id, "class_name: definition") tuples sorted
    by message_id (which the BlockCompressor.pack method requires).
    """
    if not source_path.exists():
        raise FileNotFoundError(
            f"ISO 20022 source file not found at {source_path}"
        )

    entries: list[tuple[str, str]] = []
    with open(source_path, "r", encoding="utf-8", newline="") as f:
        # Skip the 4-line metadata header and the blank line and the column header
        for _ in range(6):
            next(f, None)

        reader = csv.reader(f)
        for row_no, row in enumerate(reader, start=7):
            if not row or not row[0].strip():
                continue
            if len(row) < 3:
                print(
                    f"WARNING: row {row_no} skipped (expected 3 fields, got {len(row)}): "
                    f"{row!r}",
                    file=sys.stderr,
                )
                continue
            message_id = row[0].strip()
            message_name = row[1].strip()
            definition = row[2].strip()
            # Compose a single value string: "ClassName: definition text"
            value = f"{message_name}: {definition}"
            entries.append((message_id, value))

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

    Returns True if every case resolves to a description containing both
    the expected class name and definition substrings; False if any
    case fails.
    """
    bc = BlockCompressor()
    data = dpack_path.read_bytes()

    all_ok = True
    print()
    print(f"Verifying {dpack_path.name} against {len(VERIFICATION_VECTORS)} canonical vectors:")
    print()
    for message_id, expected_name, expected_def in VERIFICATION_VECTORS:
        result = bc.resolve(data, message_id)
        if result is None:
            print(f"  FAIL  {message_id:18} -> Not found")
            all_ok = False
            continue
        if expected_name.lower() not in result.lower():
            print(f"  FAIL  {message_id:18} -> {result[:60]!r} "
                  f"(expected class name {expected_name!r})")
            all_ok = False
            continue
        if expected_def.lower() not in result.lower():
            print(f"  FAIL  {message_id:18} -> {result[:60]!r} "
                  f"(expected definition substring {expected_def!r})")
            all_ok = False
            continue
        print(f"  OK    {message_id:18} -> {result[:60]}")

    print()
    if all_ok:
        print(f"All {len(VERIFICATION_VECTORS)} verification vectors PASSED.")
    else:
        print(f"VERIFICATION FAILED. The dpack does not satisfy the canonical "
              f"lookup contract.")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack the ISO 20022 message definitions corpus into a "
                    "dpack (Finding 34).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source", type=Path, default=DEFAULT_SOURCE,
        help=f"Path to the ISO 20022 MSG-FULL CSV (default: {DEFAULT_SOURCE.relative_to(REPO_ROOT)})",
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
    print(f"Parsed {len(entries):,} ISO 20022 message definitions.")

    # Spot-check the canonical payment messages
    print()
    print("Source spot-check (5 canonical message IDs):")
    by_key = dict(entries)
    sample_keys = ["pacs.008.001.13", "camt.053.001.13", "pain.001.001.12",
                   "acmt.001.001.08", "pacs.009.001.12"]
    for k in sample_keys:
        v = by_key.get(k)
        if v:
            print(f"  {k:18} -> {v[:60]}")
        else:
            print(f"  {k:18} -> NOT FOUND IN SOURCE")

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
