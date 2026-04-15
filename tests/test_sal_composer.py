#!/usr/bin/env python3
"""
Layer 2 Deterministic Sweep: SALComposer against composition fidelity vectors.

No models in the loop. Pure code. Measures the deterministic floor
of the generation index + keyword matching pipeline.

Usage:
  python tests/test_sal_composer.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import SALComposer, validate_composition, ASD_BASIS

# ── Helpers ──────────────────────────────────────────────────────────────────

def extract_ns_ops(sal: str) -> set[tuple[str, str]]:
    """Extract (namespace, opcode) pairs from a SAL string."""
    pairs = set()
    for m in re.finditer(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)', sal):
        pairs.add((m.group(1), m.group(2)))
    return pairs


def extract_operators(sal: str) -> set[str]:
    """Extract glyph operators from SAL."""
    ops = set()
    for ch in sal:
        if ch in '\u2192\u2227\u2228\u2194\u2225;':
            ops.add(ch)
    return ops


# ── Sweep ────────────────────────────────────────────────────────────────────

def run_sweep():
    vectors_path = REPO_ROOT / "tests" / "composition-fidelity-test-v1.json"
    with open(vectors_path) as f:
        data = json.load(f)

    composer = SALComposer()

    total = 0
    passed = 0
    failed_vectors = []

    print("=" * 80)
    print("LAYER 2 DETERMINISTIC SWEEP — SALComposer + Generation Index")
    print("=" * 80)
    print()

    for v in data["vectors"]:
        total += 1
        vid = v["id"]
        nl = v["natural_language"]
        expected_mode = v["expected_mode"]
        expected_sals = v.get("expected_sal") or []

        # Compose
        sal = composer.compose(nl)
        actual_mode = "FULL_OSMP" if sal is not None else "NL_PASSTHROUGH"

        # ── Score ────────────────────────────────────────────────────
        ok = True
        notes = []

        # Mode check
        if expected_mode == "NL_PASSTHROUGH":
            if actual_mode != "NL_PASSTHROUGH":
                ok = False
                notes.append(f"MODE: expected NL_PASSTHROUGH, got {actual_mode} ({sal})")
        elif expected_mode in ("FULL_OSMP", "FULL_OSMP_OMEGA"):
            if actual_mode != "FULL_OSMP":
                ok = False
                notes.append(f"MODE: expected {expected_mode}, composed None")
        elif expected_mode == "CONDITIONAL":
            pass  # both OSMP and NL_PASSTHROUGH are valid
        elif expected_mode == "NL_OR_HITL":
            if actual_mode == "FULL_OSMP":
                ok = False
                notes.append(f"MODE: expected NL_PASSTHROUGH/HITL, got FULL_OSMP ({sal})")

        # Namespace/opcode check (only for SAL vectors that composed)
        if sal and expected_sals:
            actual_pairs = extract_ns_ops(sal)
            actual_ns = {p[0] for p in actual_pairs}
            actual_ops = {p[1] for p in actual_pairs}

            best_ns_overlap = 0
            best_op_overlap = 0
            for esal in expected_sals:
                expected_pairs = extract_ns_ops(esal)
                e_ns = {p[0] for p in expected_pairs}
                e_ops = {p[1] for p in expected_pairs}

                if e_ns:
                    ns_overlap = len(e_ns & actual_ns) / len(e_ns)
                    best_ns_overlap = max(best_ns_overlap, ns_overlap)
                if e_ops:
                    # Strip consequence class glyphs for comparison
                    clean_e = {re.sub(r'[\u26a0\u21ba\u2298]', '', o) for o in e_ops}
                    clean_a = {re.sub(r'[\u26a0\u21ba\u2298]', '', o) for o in actual_ops}
                    op_overlap = len(clean_e & clean_a) / len(clean_e)
                    best_op_overlap = max(best_op_overlap, op_overlap)

            if best_ns_overlap < 0.5:
                ok = False
                all_expected_ns = set()
                for esal in expected_sals:
                    for p in extract_ns_ops(esal):
                        all_expected_ns.add(p[0])
                notes.append(f"NS: expected {all_expected_ns}, got {actual_ns}")

            if best_op_overlap < 0.5:
                ok = False
                all_expected_ops = set()
                for esal in expected_sals:
                    for p in extract_ns_ops(esal):
                        all_expected_ops.add(p[1])
                notes.append(f"OP: expected {all_expected_ops}, got {actual_ops}")

        # Safety check on composed SAL
        if sal:
            result = validate_composition(sal, nl=nl)
            if result.errors:
                for issue in result.errors:
                    notes.append(f"SAFETY: {issue.rule} — {issue.message}")

            # Check for hallucinated opcodes
            for m in re.finditer(r'([A-Z]):([A-Z0-9]+)', sal):
                ns, op = m.group(1), m.group(2)
                if ns in ASD_BASIS:
                    if op not in ASD_BASIS[ns]:
                        ok = False
                        notes.append(f"HALLUCINATION: {ns}:{op} not in ASD")

        # ── Report ───────────────────────────────────────────────────
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed_vectors.append(vid)

        # Print each vector
        icon = "+" if ok else "X"
        print(f"  [{icon}] {vid:8s} {status}  NL: {nl[:55]}{'...' if len(nl) > 55 else ''}")
        if sal:
            print(f"           SAL: {sal}")
        if expected_sals:
            print(f"           EXP: {expected_sals[0]}")
        for note in notes:
            print(f"           >> {note}")
        if notes or not ok:
            print()

    # ── Summary ──────────────────────────────────────────────────────────
    print()
    print("=" * 80)
    pct = (passed / total * 100) if total else 0
    print(f"RESULT: {passed}/{total} ({pct:.1f}%)")
    print(f"PASSED: {passed}  FAILED: {total - passed}")
    if failed_vectors:
        print(f"FAILED VECTORS: {', '.join(failed_vectors)}")
    print("=" * 80)

    # Return exit code
    return 0 if pct >= 90 else 1


if __name__ == "__main__":
    sys.exit(run_sweep())
