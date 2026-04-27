#!/usr/bin/env python3
"""
Weakness measurement harness for the deterministic SDK composer.

Loads the panel-discovery test vectors (30 chips with expected SAL +
historical model panel responses) and scores the current Python composer
against them, classifying each result into a failure mode bucket so we
can see WHICH weakness is dominant and whether fixes move the needle.

Failure modes (mutually exclusive, evaluated in order):
  EXACT          — composer SAL exactly matches one of the expected SAL strings
  OPCODE_MATCH   — composer SAL covers the expected opcode set (order/glyphs may differ)
  OVER_COMPOSED  — composer produced MORE opcodes than expected; spurious additions
  UNDER_COMPOSED — composer produced FEWER opcodes than expected; missing pieces
  WRONG_OPCODE   — composer produced a different opcode set than expected
  NO_COMPOSE     — composer returned None (passthrough)
  EXPECTED_EMPTY — no expected_sal in vector (genuinely out-of-scope)

Compares composer hit-rate to the historical panel hit-rates from
panel-discovery-results.json so we can see whether the deterministic
composer is now better or worse than the LLM panel was.

Usage:
  python tests/weakness_measure.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import SALComposer

OPCODE_RE = re.compile(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)')


def opcodes_in(sal: str | None) -> set[tuple[str, str]]:
    if not sal:
        return set()
    return set(OPCODE_RE.findall(sal))


def classify(composer_sal: str | None, expected_sals: list[str] | None) -> str:
    if not expected_sals:
        return "EXPECTED_EMPTY"
    if not composer_sal:
        return "NO_COMPOSE"
    # Exact match
    if composer_sal in expected_sals:
        return "EXACT"
    composer_set = opcodes_in(composer_sal)
    # Try each expected variant
    for exp in expected_sals:
        exp_set = opcodes_in(exp)
        if composer_set == exp_set:
            return "OPCODE_MATCH"
    # Best-overlap analysis vs first expected
    best_match = max(
        (opcodes_in(exp) for exp in expected_sals),
        key=lambda exp_set: len(composer_set & exp_set),
    )
    overlap = composer_set & best_match
    composer_extra = composer_set - best_match
    expected_extra = best_match - composer_set
    if not expected_extra and composer_extra:
        return "OVER_COMPOSED"
    if not composer_extra and expected_extra:
        return "UNDER_COMPOSED"
    if overlap:
        return "PARTIAL_OVERLAP"
    return "WRONG_OPCODE"


def main() -> int:
    vectors_path = REPO_ROOT / "tests" / "panel-discovery-results.json"
    with open(vectors_path, encoding="utf-8") as f:
        vectors = json.load(f)

    composer = SALComposer()

    print("=" * 95)
    print(f"WEAKNESS MEASURE — {len(vectors)} chips from panel-discovery-results.json")
    print("=" * 95)
    print()

    bucket = Counter()
    examples: dict[str, list[tuple[str, str | None, str | None]]] = {}
    for v in vectors:
        nl = v["nl"]
        expected = v.get("expected_sal") or []
        try:
            got = composer.compose(nl)
        except Exception as e:
            got = f"ERR:{type(e).__name__}"
        verdict = classify(got, expected)
        bucket[verdict] += 1
        examples.setdefault(verdict, []).append(
            (nl, expected[0] if expected else None, got)
        )

    total = len(vectors)
    print("OUTCOME DISTRIBUTION:")
    for verdict in [
        "EXACT", "OPCODE_MATCH", "PARTIAL_OVERLAP",
        "OVER_COMPOSED", "UNDER_COMPOSED",
        "WRONG_OPCODE", "NO_COMPOSE", "EXPECTED_EMPTY",
    ]:
        n = bucket.get(verdict, 0)
        print(f"  {verdict:18s}: {n:>3}/{total}  ({100*n/total:5.1f}%)")
    print()

    print("HISTORICAL PANEL HIT RATE (for comparison):")
    panel_refusal = {"claude-sonnet": 30, "gpt-5": 30, "gemini-flash": 30,
                     "claude-haiku": 7, "gpt-4o-mini": 11}
    for m, r in panel_refusal.items():
        print(f"  {m:18s}: {(total-r):>2}/{total} composed  ({100*(total-r)/total:.1f}%)")
    print()

    composed = sum(bucket.get(k, 0) for k in [
        "EXACT", "OPCODE_MATCH", "PARTIAL_OVERLAP",
        "OVER_COMPOSED", "UNDER_COMPOSED", "WRONG_OPCODE",
    ])
    print(f"COMPOSER:           {composed}/{total} composed something  ({100*composed/total:.1f}%)")
    print(f"   of which:")
    correct = bucket.get("EXACT", 0) + bucket.get("OPCODE_MATCH", 0)
    print(f"     CORRECT:        {correct}/{total} ({100*correct/total:.1f}%)")
    print(f"     OVER_COMPOSED:  {bucket.get('OVER_COMPOSED',0)}/{total}")
    print(f"     UNDER_COMPOSED: {bucket.get('UNDER_COMPOSED',0)}/{total}")
    print(f"     WRONG_OPCODE:   {bucket.get('WRONG_OPCODE',0)}/{total}")
    print(f"     PARTIAL:        {bucket.get('PARTIAL_OVERLAP',0)}/{total}")
    print()

    # Show 3 examples of OVER_COMPOSED (the dominant failure)
    if examples.get("OVER_COMPOSED"):
        print("OVER_COMPOSED examples (composer added spurious opcodes):")
        for nl, exp, got in examples["OVER_COMPOSED"][:5]:
            print(f"  NL: {nl}")
            print(f"    expected: {exp}")
            print(f"    got:      {got}")
        print()

    if examples.get("WRONG_OPCODE"):
        print("WRONG_OPCODE examples (composer picked wrong opcode entirely):")
        for nl, exp, got in examples["WRONG_OPCODE"][:5]:
            print(f"  NL: {nl}")
            print(f"    expected: {exp}")
            print(f"    got:      {got}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
