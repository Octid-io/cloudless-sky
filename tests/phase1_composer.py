#!/usr/bin/env python3
"""
Phase 1 — Composer rule coverage harness.

Runs the deterministic Python SDK composer against the domain-stratified
corpus (tests/input-classes/corpus.json) and classifies each result into
the doctrine verdict buckets:

  CORRECT, SAFE_BRIDGE, SAFE_PASSTHROUGH, REFUSED_MALFORMED,
  INVALID, WRONG

WRONG and INVALID must both be 0 to ship. CORRECT is the drive-up metric.

Output: prints per-domain + aggregate stats, dumps detailed per-input
results to tests/results/phase1-composer-{ITER}.json.

Usage:
  python tests/phase1_composer.py [--iter N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import SALComposer, validate_composition

CORPUS_PATH = REPO_ROOT / "tests" / "input-classes" / "corpus.json"
RESULTS_DIR = REPO_ROOT / "tests" / "results"
RESULTS_DIR.mkdir(exist_ok=True)

OPCODE_RE = re.compile(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)')

# Modifier markers in NL — when present in residue, bridge mode is forbidden
# even if the namespace policy allows it (per taxonomy doctrine).
MODIFIER_MARKERS = re.compile(
    r'\b(unless|only if|except|but not|without|after|before|while|if not)\b',
    re.IGNORECASE,
)


def opcodes_in(sal: str | None) -> set[tuple[str, str]]:
    if not sal:
        return set()
    return set(OPCODE_RE.findall(sal))


def equivalent_sal(emitted: str, expected_list: list[str]) -> bool:
    """Equivalence check: exact string match OR opcode-set match against any expected."""
    if not emitted:
        return False
    if emitted in expected_list:
        return True
    emitted_ops = opcodes_in(emitted)
    for exp in expected_list:
        if emitted_ops == opcodes_in(exp):
            return True
    return False


def classify(emitted_sal: str | None,
             expected_sal: list[str],
             expected_verdict: str | None,
             nl: str) -> tuple[str, str]:
    """
    Returns (verdict, reason). Verdict is one of:
      CORRECT, SAFE_BRIDGE, SAFE_PASSTHROUGH, REFUSED_MALFORMED,
      INVALID, WRONG
    """
    # Out-of-scope chips have explicit expected_verdict
    if expected_verdict == "SAFE_PASSTHROUGH":
        if emitted_sal is None:
            return "SAFE_PASSTHROUGH", "composer correctly passed through"
        # Composer emitted SAL for an out-of-scope input — that's WRONG
        return "WRONG", f"emitted SAL for OOS input: {emitted_sal}"

    if expected_verdict == "REFUSED_MALFORMED":
        if emitted_sal is None:
            # Composer returned None — counts as REFUSED_MALFORMED for now
            # (composer doesn't yet emit a distinct refused-malformed signal)
            return "REFUSED_MALFORMED", "composer returned None for malformed input"
        return "WRONG", f"emitted SAL for malformed input: {emitted_sal}"

    # In-scope chip
    if emitted_sal is None:
        return "SAFE_PASSTHROUGH", "composer returned None for in-scope input (coverage gap)"

    # Validate the emitted SAL
    val = validate_composition(emitted_sal, nl=nl)
    if not val.valid:
        # Find the first error
        errs = [i for i in val.issues if i.severity == "error"]
        return "INVALID", f"validator rejected: {errs[0].message if errs else 'unknown'}"

    # Check equivalence
    if equivalent_sal(emitted_sal, expected_sal):
        return "CORRECT", "exact or opcode-set match"

    # Grammar-valid SAL that doesn't match expected → WRONG
    return "WRONG", f"valid SAL but does not match any expected variant"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iter", type=str, default="baseline",
                        help="Iteration label for output filename")
    args = parser.parse_args()

    with open(CORPUS_PATH, encoding="utf-8") as f:
        corpus = json.load(f)

    composer = SALComposer()
    inputs = corpus["inputs"]
    total = len(inputs)

    bucket = Counter()
    by_domain = defaultdict(lambda: Counter())
    detailed = []

    for inp in inputs:
        nl = inp["nl"]
        expected = inp.get("expected_sal", [])
        ev = inp.get("expected_verdict")
        domain = inp["domain"]
        try:
            got = composer.compose(nl)
        except Exception as e:
            got = None
            verdict = "INVALID"
            reason = f"compose raised {type(e).__name__}: {e}"
        else:
            verdict, reason = classify(got, expected, ev, nl)

        bucket[verdict] += 1
        by_domain[domain][verdict] += 1
        detailed.append({
            "id": inp["id"],
            "domain": domain,
            "shape": inp.get("shape"),
            "nl": nl,
            "expected": expected,
            "expected_verdict": ev,
            "got": got,
            "verdict": verdict,
            "reason": reason,
        })

    # ── Print summary ─────────────────────────────────────────────────
    print("=" * 95)
    print(f"PHASE 1 — COMPOSER RULE COVERAGE — iteration={args.iter}")
    print("=" * 95)
    print()
    print(f"AGGREGATE ({total} inputs):")
    bar_pct = lambda n: f"{n}/{total} ({100*n/total:5.1f}%)"
    print(f"  CORRECT            : {bar_pct(bucket.get('CORRECT', 0))}")
    print(f"  SAFE_BRIDGE        : {bar_pct(bucket.get('SAFE_BRIDGE', 0))}")
    print(f"  SAFE_PASSTHROUGH   : {bar_pct(bucket.get('SAFE_PASSTHROUGH', 0))}")
    print(f"  REFUSED_MALFORMED  : {bar_pct(bucket.get('REFUSED_MALFORMED', 0))}")
    print(f"  INVALID            : {bar_pct(bucket.get('INVALID', 0))}  [bar: 0]")
    print(f"  WRONG              : {bar_pct(bucket.get('WRONG', 0))}  [bar: 0 — FATAL]")
    print()

    safe = sum(bucket.get(k, 0) for k in
               ("CORRECT", "SAFE_BRIDGE", "SAFE_PASSTHROUGH", "REFUSED_MALFORMED"))
    fatal = bucket.get("WRONG", 0) + bucket.get("INVALID", 0)
    print(f"  SAFE total         : {bar_pct(safe)}")
    print(f"  FATAL total        : {bar_pct(fatal)}")
    print()

    print("PER-DOMAIN:")
    print(f"  {'domain':<25} {'tot':>4} {'CORR':>5} {'PASS':>5} {'WRONG':>6} {'INVAL':>6}")
    for domain in sorted(by_domain.keys()):
        row = by_domain[domain]
        n = sum(row.values())
        print(f"  {domain:<25} {n:>4} {row.get('CORRECT',0):>5} "
              f"{row.get('SAFE_PASSTHROUGH',0)+row.get('REFUSED_MALFORMED',0):>5} "
              f"{row.get('WRONG',0):>6} {row.get('INVALID',0):>6}")
    print()

    # ── Show all WRONG and INVALID — these block ship ─────────────────
    fatal_examples = [d for d in detailed if d["verdict"] in ("WRONG", "INVALID")]
    if fatal_examples:
        print(f"FATAL CASES ({len(fatal_examples)}):")
        for d in fatal_examples:
            print(f"  [{d['verdict']}] [{d['id']}] {d['nl']!r}")
            print(f"     expected: {d['expected']}")
            print(f"     got:      {d['got']!r}")
            print(f"     reason:   {d['reason']}")
        print()
    else:
        print("NO FATAL CASES — WRONG=0, INVALID=0")
        print()

    # ── Save detailed results ─────────────────────────────────────────
    out_path = RESULTS_DIR / f"phase1-composer-{args.iter}.json"
    out = {
        "iteration": args.iter,
        "corpus_version": corpus.get("version"),
        "summary": {
            "total": total,
            "buckets": dict(bucket),
            "safe": safe,
            "fatal": fatal,
            "correct_pct": round(100 * bucket.get("CORRECT", 0) / total, 2),
            "wrong_pct": round(100 * bucket.get("WRONG", 0) / total, 2),
            "invalid_pct": round(100 * bucket.get("INVALID", 0) / total, 2),
            "by_domain": {d: dict(c) for d, c in by_domain.items()},
        },
        "detailed": detailed,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Detailed results: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
