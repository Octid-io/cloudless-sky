#!/usr/bin/env python3
"""
gen_asd.py — Cross-SDK ASD Generator (Finding 9)
=================================================

Regenerate the TypeScript and Go glyph/ASD tables from the canonical
Python source in sdk/python/osmp/protocol.py. This tool is the
enforcement mechanism for ADR-001: the canonical semantic dictionary
is the single source of truth, the Python SDK is the first derivation,
and the TypeScript and Go SDKs are pure derivations of the Python
source with no independent opcode definitions.

Before this tool existed, the TS and Go glyph files were maintained
by hand, which led to silent drift when the dictionary moved from v12
to v13 to v14 and the SDK files were not updated in lockstep. Finding 9
from the audit called this out: the ADR specified this tool but the
tool did not exist, so the ADR's guarantee was not actually enforced.

Now the tool exists and runs in two modes:

  python3 tools/gen_asd.py           — regenerate TS and Go files
  python3 tools/gen_asd.py --check   — verify on-disk files match what
                                        generation would produce; exit
                                        non-zero if there's drift
                                        (CI enforcement hook for
                                        Finding 32)

The generated files carry a clear auto-generated banner that tells
future editors to modify protocol.py and run this tool instead of
editing the derived files directly. Any manual edit to glyphs.ts or
glyphs.go will be silently overwritten on the next generation run.

Source constants (all from sdk/python/osmp/protocol.py):
  - ASD_FLOOR_VERSION
  - GLYPH_OPERATORS
  - COMPOUND_OPERATORS
  - CONSEQUENCE_CLASSES
  - OUTCOME_STATES
  - PARAMETER_DESIGNATORS
  - LOSS_POLICIES
  - DICT_UPDATE_MODES
  - ASD_BASIS

Target files:
  - sdk/typescript/src/glyphs.ts    (full record objects with nl arrays)
  - sdk/go/osmp/glyphs.go          (simpler maps: glyph -> name only
                                     for the glyph tables, and the
                                     full ASDFloorBasis)
  - sdk/typescript/tests/asd_fingerprint.test.ts
                                    (canonical fingerprint constant and
                                     opcode count — auto-patched between
                                     the AUTO-UPDATED markers)

Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import (  # noqa: E402
    ASD_BASIS,
    ASD_FLOOR_VERSION,
    COMPOUND_OPERATORS,
    CONSEQUENCE_CLASSES,
    DICT_UPDATE_MODES,
    GLYPH_OPERATORS,
    LOSS_POLICIES,
    OUTCOME_STATES,
    PARAMETER_DESIGNATORS,
)


# ── Target paths ───────────────────────────────────────────────────────────

TS_OUTPUT = REPO_ROOT / "sdk" / "typescript" / "src" / "glyphs.ts"
GO_OUTPUT = REPO_ROOT / "sdk" / "go" / "osmp" / "glyphs.go"
TS_FINGERPRINT_TEST = REPO_ROOT / "sdk" / "typescript" / "tests" / "asd_fingerprint.test.ts"


# ── Dictionary version detection ──────────────────────────────────────────

def detect_dictionary_version() -> str:
    """Find the current dictionary CSV and return its version token.

    Looks for files matching protocol/OSMP-semantic-dictionary-v*.csv
    and returns the highest version number found. Falls back to
    'unknown' if no dictionary file is present.
    """
    protocol_dir = REPO_ROOT / "protocol"
    if not protocol_dir.exists():
        return "unknown"
    candidates = sorted(protocol_dir.glob("OSMP-semantic-dictionary-v*.csv"))
    if not candidates:
        return "unknown"
    # Extract version number from filename
    latest = candidates[-1].stem
    for part in latest.split("-"):
        if part.startswith("v") and part[1:].isdigit():
            return part
    return "unknown"


DICT_VERSION = detect_dictionary_version()


# ── TypeScript serialization ──────────────────────────────────────────────

def _ts_string_literal(s: str) -> str:
    """Emit a JavaScript string literal, escaping as necessary."""
    return json.dumps(s, ensure_ascii=False)


def _ts_string_array(items: list[str]) -> str:
    """Emit a JavaScript string array."""
    return "[" + ", ".join(_ts_string_literal(x) for x in items) + "]"


def _ts_operator_entry(glyph: str, entry: dict, include_nl: bool = True,
                       extra_fields: dict | None = None) -> str:
    """Emit a single TS operator entry like:
    "∧": { unicode: "U+2227", name: "AND", nl: ["and", "&", "also"] },
    """
    parts = [
        f'unicode: {_ts_string_literal(entry["unicode"])}',
        f'name: {_ts_string_literal(entry["name"])}',
    ]
    if extra_fields:
        for k, v in extra_fields.items():
            if isinstance(v, bool):
                parts.append(f'{k}: {"true" if v else "false"}')
            elif isinstance(v, (int, float)):
                parts.append(f'{k}: {v}')
            else:
                parts.append(f'{k}: {_ts_string_literal(str(v))}')
    if include_nl and "nl" in entry:
        parts.append(f'nl: {_ts_string_array(entry["nl"])}')
    return f'  {_ts_string_literal(glyph)}: {{ {", ".join(parts)} }},'


def generate_ts() -> str:
    lines: list[str] = []
    lines.append("/**")
    lines.append(" * OSMP Glyph Tables and ASD Basis Set")
    lines.append(f" * AUTO-GENERATED from sdk/python/osmp/protocol.py "
                 f"(dictionary {DICT_VERSION})")
    lines.append(" *")
    lines.append(" * DO NOT EDIT — regenerate via: python3 tools/gen_asd.py")
    lines.append(" * Edits to this file will be silently overwritten on the "
                 "next generation run.")
    lines.append(" *")
    lines.append(" * Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg")
    lines.append(" * License: Apache 2.0")
    lines.append(" */")
    lines.append("")
    lines.append(f'export const ASD_FLOOR_VERSION = '
                 f'{_ts_string_literal(ASD_FLOOR_VERSION)};')
    lines.append("")

    # GLYPH_OPERATORS
    lines.append("export const GLYPH_OPERATORS: Record<string, "
                 "{ unicode: string; name: string; nl: string[] }> = {")
    for glyph, entry in GLYPH_OPERATORS.items():
        lines.append(_ts_operator_entry(glyph, entry))
    lines.append("};")
    lines.append("")

    # COMPOUND_OPERATORS
    lines.append("export const COMPOUND_OPERATORS: Record<string, "
                 "{ unicode: string; name: string; nl: string[] }> = {")
    for glyph, entry in COMPOUND_OPERATORS.items():
        lines.append(_ts_operator_entry(glyph, entry))
    lines.append("};")
    lines.append("")

    # CONSEQUENCE_CLASSES
    lines.append("export const CONSEQUENCE_CLASSES: Record<string, "
                 "{ unicode: string; name: string; hitlRequired: boolean }> = {")
    for glyph, entry in CONSEQUENCE_CLASSES.items():
        lines.append(_ts_operator_entry(
            glyph, entry, include_nl=False,
            extra_fields={"hitlRequired": entry["hitl_required"]},
        ))
    lines.append("};")
    lines.append("")

    # OUTCOME_STATES (simple glyph -> name)
    lines.append("export const OUTCOME_STATES: Record<string, string> = {")
    for glyph, entry in OUTCOME_STATES.items():
        name = entry["name"] if isinstance(entry, dict) else entry
        lines.append(f'  {_ts_string_literal(glyph)}: '
                     f'{_ts_string_literal(name)},')
    lines.append("};")
    lines.append("")

    # PARAMETER_DESIGNATORS
    lines.append("export const PARAMETER_DESIGNATORS: Record<string, "
                 "{ unicode: string; name: string; bytes: number }> = {")
    for glyph, entry in PARAMETER_DESIGNATORS.items():
        lines.append(_ts_operator_entry(
            glyph, entry, include_nl=False,
            extra_fields={"bytes": entry["bytes"]},
        ))
    lines.append("};")
    lines.append("")

    # LOSS_POLICIES
    lines.append("// Category 5 — Loss Tolerance Policy Designators")
    lines.append("// Configuration syntax: N:CFG@[nodeID]:FRAG[Phi|Gamma|Lambda]:tau[n]")
    lines.append("export const LOSS_POLICIES: Record<string, "
                 "{ unicode: string; name: string; bytes: number; legacy: string }> = {")
    for glyph, entry in LOSS_POLICIES.items():
        lines.append(_ts_operator_entry(
            glyph, entry, include_nl=False,
            extra_fields={
                "bytes": entry["bytes"],
                "legacy": entry["legacy"],
            },
        ))
    lines.append("};")
    lines.append("")

    # DICT_UPDATE_MODES
    lines.append("// Category 6 — Dictionary Update Mode Designators")
    lines.append("// REPLACE (←) requires mandatory FLAGS[C]: retransmit on loss, no graceful degradation.")
    lines.append("export const DICT_UPDATE_MODES: Record<string, "
                 "{ unicode: string; name: string; bytes: number }> = {")
    for glyph, entry in DICT_UPDATE_MODES.items():
        lines.append(_ts_operator_entry(
            glyph, entry, include_nl=False,
            extra_fields={"bytes": entry["bytes"]},
        ))
    lines.append("};")
    lines.append("")

    # ASD_BASIS
    total_opcodes = sum(len(ops) for ops in ASD_BASIS.values())
    lines.append(f"// ASD_BASIS — {len(ASD_BASIS)} namespaces, "
                 f"{total_opcodes} opcodes")
    lines.append(f"// Source: dictionary {DICT_VERSION}")
    lines.append("export const ASD_BASIS: Record<string, Record<string, string>> = {")
    for ns in sorted(ASD_BASIS.keys()):
        lines.append(f'  {_ts_string_literal(ns)}: {{')
        for op in sorted(ASD_BASIS[ns].keys()):
            meaning = ASD_BASIS[ns][op]
            lines.append(f'    {_ts_string_literal(op)}: '
                         f'{_ts_string_literal(meaning)},')
        lines.append("  },")
    lines.append("};")
    lines.append("")

    return "\n".join(lines)


# ── Go serialization ──────────────────────────────────────────────────────

def _go_string_literal(s: str) -> str:
    """Emit a Go string literal. Uses JSON escaping which is a superset
    of Go's string escape rules for the printable ASCII + Unicode range
    we care about here."""
    return json.dumps(s, ensure_ascii=False)


def generate_go() -> str:
    lines: list[str] = []
    lines.append("// Package osmp: auto-generated glyph tables and ASD basis set.")
    lines.append("//")
    lines.append(f"// AUTO-GENERATED from sdk/python/osmp/protocol.py "
                 f"(dictionary {DICT_VERSION})")
    lines.append("//")
    lines.append("// DO NOT EDIT — regenerate via: python3 tools/gen_asd.py")
    lines.append("// Edits to this file will be silently overwritten on the "
                 "next generation run.")
    lines.append("//")
    lines.append("// Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg")
    lines.append("// License: Apache 2.0")
    lines.append("package osmp")
    lines.append("")
    lines.append(f"// ASDFloorVersion is the guaranteed minimum vocabulary floor.")
    lines.append(f"const ASDFloorVersion = {_go_string_literal(ASD_FLOOR_VERSION)}")
    lines.append("")

    # GlyphOperators (simplified: glyph -> name only, matching existing format)
    lines.append("// GlyphOperators — Category 1: Logical and Compositional Operators.")
    lines.append(f"// Source: dictionary {DICT_VERSION} Section 1, Category 1")
    lines.append("var GlyphOperators = map[string]string{")
    for glyph, entry in GLYPH_OPERATORS.items():
        name = entry["name"]
        unicode = entry["unicode"]
        nbytes = entry.get("bytes", len(glyph.encode("utf-8")))
        lines.append(f'\t{_go_string_literal(glyph)}: '
                     f'{_go_string_literal(name)}, '
                     f'// {unicode} {nbytes}B')
    lines.append("}")
    lines.append("")

    # ConsequenceClasses
    lines.append("// ConsequenceClasses — Category 2: Consequence Class Designators.")
    lines.append("// Required on every R: namespace instruction except ESTOP.")
    lines.append("// HAZARDOUS and IRREVERSIBLE require I:§ human-in-the-loop precondition.")
    lines.append("var ConsequenceClasses = map[string]string{")
    for glyph, entry in CONSEQUENCE_CLASSES.items():
        lines.append(f'\t{_go_string_literal(glyph)}: '
                     f'{_go_string_literal(entry["name"])}, '
                     f'// {entry["unicode"]} hitl={str(entry["hitl_required"]).lower()}')
    lines.append("}")
    lines.append("")

    # LossPolicyGlyphs
    lines.append("// LossPolicyGlyphs — Category 5: Loss Tolerance Policy Designators.")
    lines.append("// Greek uppercase letters whose mathematical meanings map to policy semantics.")
    lines.append("// Config: N:CFG@[nodeID]:FRAG[Φ|Γ|Λ]:τ[n]")
    lines.append("var LossPolicyGlyphs = map[string]string{")
    for glyph, entry in LOSS_POLICIES.items():
        lines.append(f'\t{_go_string_literal(glyph)}: '
                     f'{_go_string_literal(entry["name"])}, '
                     f'// {entry["unicode"]} {entry["bytes"]}B '
                     f'legacy={entry["legacy"]}')
    lines.append("}")
    lines.append("")

    # DictUpdateModeGlyphs
    lines.append("// DictUpdateModeGlyphs — Category 6: Dictionary Update Mode Designators.")
    lines.append("// REPLACE (←) requires mandatory FLAGS[C]: retransmit on loss, no graceful degradation.")
    lines.append("var DictUpdateModeGlyphs = map[string]string{")
    for glyph, entry in DICT_UPDATE_MODES.items():
        lines.append(f'\t{_go_string_literal(glyph)}: '
                     f'{_go_string_literal(entry["name"])}, '
                     f'// {entry["unicode"]} {entry["bytes"]}B')
    lines.append("}")
    lines.append("")

    # ASDFloorBasis
    total_opcodes = sum(len(ops) for ops in ASD_BASIS.values())
    lines.append("// ASDFloorBasis is the compiled-in ASD basis set.")
    lines.append(f"// Source: dictionary {DICT_VERSION} "
                 f"({len(ASD_BASIS)} namespaces, {total_opcodes} opcodes)")
    lines.append("var ASDFloorBasis = map[string]map[string]string{")
    for ns in sorted(ASD_BASIS.keys()):
        lines.append(f'\t{_go_string_literal(ns)}: {{')
        for op in sorted(ASD_BASIS[ns].keys()):
            meaning = ASD_BASIS[ns][op]
            lines.append(f'\t\t{_go_string_literal(op)}: '
                         f'{_go_string_literal(meaning)},')
        lines.append("\t},")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ── Test constant patching ────────────────────────────────────────────────

def patch_ts_fingerprint_test() -> str:
    """Patch the auto-generated constants in the TS fingerprint test.

    Reads the existing test file and replaces:
      - the CANONICAL_FINGERPRINT_V{N} constant (value and version tag)
      - the opcode-count comment in the auto-updated block
      - the total-opcode toBe() assertion
      - all references to the old variable name throughout the file

    Returns the fully patched file content, suitable for comparison in
    --check mode or writing in generation mode.
    """
    from osmp.protocol import AdaptiveSharedDictionary

    content = TS_FINGERPRINT_TEST.read_text(encoding="utf-8")
    fp = AdaptiveSharedDictionary().fingerprint()
    n_opcodes = sum(len(ops) for ops in ASD_BASIS.values())
    ver = DICT_VERSION          # e.g., "v15"
    ver_num = ver[1:]           # e.g., "15"

    # Replace the auto-updated block between markers
    new_block = (
        f"// --- AUTO-UPDATED by tools/gen_asd.py --- do not edit manually ---\n"
        f"// The canonical ASD fingerprint for dictionary {ver} "
        f"({n_opcodes} opcodes, {len(ASD_BASIS)} namespaces).\n"
        f"// This value MUST match the output of the equivalent Python computation:\n"
        f"//\n"
        f"//   python3 -c \"import sys; sys.path.insert(0, 'sdk/python'); \\\\\n"
        f"//     from osmp.protocol import AdaptiveSharedDictionary; \\\\\n"
        f"//     print(AdaptiveSharedDictionary().fingerprint())\"\n"
        f"//\n"
        f"// If this test fails, run: python3 tools/gen_asd.py\n"
        f"// That regenerates glyphs AND this constant from the canonical Python source.\n"
        f"const CANONICAL_FINGERPRINT_V{ver_num} = \"{fp}\";\n"
        f"// --- END AUTO-UPDATED ---"
    )
    content = re.sub(
        r"// --- AUTO-UPDATED by tools/gen_asd\.py ---.*?// --- END AUTO-UPDATED ---",
        new_block,
        content,
        flags=re.DOTALL,
    )

    # Update all references to old fingerprint variable names
    content = re.sub(
        r"CANONICAL_FINGERPRINT_V\d+",
        f"CANONICAL_FINGERPRINT_V{ver_num}",
        content,
    )

    # Update the total opcode count assertion
    content = re.sub(
        r"expect\(total\)\.toBe\(\d+\)",
        f"expect(total).toBe({n_opcodes})",
        content,
    )

    return content


# ── Drift detection ───────────────────────────────────────────────────────

def show_diff(path: Path, new_content: str) -> bool:
    """Show a unified diff between on-disk file and new content.

    Returns True if there's drift (files differ), False if identical.
    """
    if not path.exists():
        print(f"  (file does not exist, would be created)")
        return True

    existing = path.read_text(encoding="utf-8")
    if existing == new_content:
        return False

    diff = difflib.unified_diff(
        existing.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"{path} (on disk)",
        tofile=f"{path} (would generate)",
        lineterm="",
    )
    sys.stdout.writelines(diff)
    print()
    return True


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate TS/Go glyph tables from canonical Python source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check for drift without writing. Exits non-zero if the "
             "on-disk TS or Go glyph files don't match what generation "
             "would produce. Use this as a CI enforcement hook.",
    )
    parser.add_argument(
        "--ts-only", action="store_true",
        help="Regenerate only the TypeScript file",
    )
    parser.add_argument(
        "--go-only", action="store_true",
        help="Regenerate only the Go file",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    targets: list[tuple[str, Path, str]] = []
    if not args.go_only:
        targets.append(("TypeScript", TS_OUTPUT, generate_ts()))
        targets.append(("TS fingerprint test", TS_FINGERPRINT_TEST,
                         patch_ts_fingerprint_test()))
    if not args.ts_only:
        targets.append(("Go", GO_OUTPUT, generate_go()))

    if not args.quiet:
        n = sum(len(ops) for ops in ASD_BASIS.values())
        print(f"Dictionary version: {DICT_VERSION}")
        print(f"ASD_BASIS: {len(ASD_BASIS)} namespaces, {n} opcodes")
        print()

    if args.check:
        drift_found = False
        for label, path, content in targets:
            if not args.quiet:
                print(f"Checking {label}: {path.relative_to(REPO_ROOT)}")
            if show_diff(path, content):
                drift_found = True
                if not args.quiet:
                    print(f"  DRIFT DETECTED in {label} file")
            else:
                if not args.quiet:
                    print(f"  OK (in sync)")
        if drift_found:
            print()
            print("DRIFT: the on-disk SDK files do not match what would be")
            print("generated from the Python source. Run `python3 "
                  "tools/gen_asd.py` to regenerate, or edit the Python")
            print("source first if the drift represents an intended change.")
            return 1
        return 0

    # Write mode
    for label, path, content in targets:
        if not args.quiet:
            print(f"Writing {label}: {path.relative_to(REPO_ROOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if not args.quiet:
            print(f"  {len(content):,} bytes written")

    if not args.quiet:
        print()
        print("Generation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
