#!/usr/bin/env python3
"""Phase 1 brigade composer — runs the kitchen brigade against the corpus."""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "sdk" / "python"))

from osmp.brigade import Orchestrator
from osmp.protocol import validate_composition

import os
CORPUS_PATH = REPO / "tests" / "input-classes" / os.environ.get("CORPUS_FILE", "corpus.json")
RESULTS_DIR = REPO / "tests" / "results"
RESULTS_DIR.mkdir(exist_ok=True)

OPCODE_RE = re.compile(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)')


def opcodes_in(sal):
    if not sal:
        return set()
    return set(OPCODE_RE.findall(sal))


def equivalent(emitted, expected_list):
    if not emitted:
        return False
    if emitted in expected_list:
        return True
    em_ops = opcodes_in(emitted)
    if not em_ops:
        return False
    for e in expected_list:
        if em_ops == opcodes_in(e):
            return True
    return False


def classify(sal, expected, expected_verdict, nl):
    if expected_verdict == "SAFE_PASSTHROUGH":
        return ("SAFE_PASSTHROUGH", "correct passthrough") if sal is None else ("WRONG", f"emitted SAL for OOS: {sal}")
    if expected_verdict == "REFUSED_MALFORMED":
        return ("REFUSED_MALFORMED", "rejected malformed") if sal is None else ("WRONG", f"emitted SAL for malformed: {sal}")
    if sal is None:
        return ("SAFE_PASSTHROUGH", "in-scope passthrough")
    v = validate_composition(sal, nl=nl)
    if not v.valid:
        return ("INVALID", f"validator: {v.issues[0].message if v.issues else '?'}")
    if equivalent(sal, expected):
        return ("CORRECT", "match")
    return ("WRONG", "valid SAL but doesn't match expected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iter", default="brigade-v1")
    args = parser.parse_args()

    corpus = json.load(open(CORPUS_PATH, encoding="utf-8"))
    inputs = corpus["inputs"]

    orch = Orchestrator()

    bucket = Counter()
    by_domain = defaultdict(lambda: Counter())
    detailed = []

    for inp in inputs:
        nl = inp["nl"]
        try:
            got = orch.compose(nl)
        except Exception as e:
            got = None
            verdict = "INVALID"
            reason = f"compose raised {type(e).__name__}: {e}"
        else:
            verdict, reason = classify(got, inp.get("expected_sal", []),
                                       inp.get("expected_verdict"), nl)
        bucket[verdict] += 1
        by_domain[inp.get("domain", "EDGE")][verdict] += 1
        detailed.append({
            "id": inp["id"], "domain": inp.get("domain", "EDGE"), "nl": nl,
            "expected": inp.get("expected_sal", []),
            "expected_verdict": inp.get("expected_verdict"),
            "got": got, "verdict": verdict, "reason": reason,
        })

    total = len(inputs)
    print("=" * 95)
    print(f"BRIGADE COMPOSER — iteration={args.iter}")
    print("=" * 95)
    print()
    print(f"AGGREGATE ({total}):")
    bar = lambda n: f"{n}/{total} ({100*n/total:5.1f}%)"
    for v in ("CORRECT", "SAFE_PASSTHROUGH", "REFUSED_MALFORMED", "INVALID", "WRONG"):
        print(f"  {v:18s}: {bar(bucket.get(v, 0))}")
    print()

    safe = sum(bucket.get(k, 0) for k in ("CORRECT", "SAFE_PASSTHROUGH", "REFUSED_MALFORMED"))
    fatal = bucket.get("WRONG", 0) + bucket.get("INVALID", 0)
    print(f"  SAFE total:  {bar(safe)}")
    print(f"  FATAL total: {bar(fatal)}")
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

    fatal_examples = [d for d in detailed if d["verdict"] in ("WRONG", "INVALID")]
    if fatal_examples:
        print(f"FATAL ({len(fatal_examples)}):")
        for d in fatal_examples:
            print(f"  [{d['verdict']}] [{d['id']}] {d['nl']!r}")
            print(f"    expected: {d['expected'][:1]}")
            print(f"    got:      {d['got']!r}")
            print(f"    reason:   {d['reason']}")
        print()
    else:
        print("ZERO FATAL.")
        print()

    out = {
        "iteration": args.iter,
        "summary": {
            "total": total,
            "buckets": dict(bucket),
            "safe": safe, "fatal": fatal,
            "correct_pct": round(100*bucket.get("CORRECT",0)/total, 2),
            "wrong_pct": round(100*bucket.get("WRONG",0)/total, 2),
            "invalid_pct": round(100*bucket.get("INVALID",0)/total, 2),
            "by_domain": {d: dict(c) for d, c in by_domain.items()},
        },
        "detailed": detailed,
    }
    with open(RESULTS_DIR / f"phase1-brigade-{args.iter}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Saved: tests/results/phase1-brigade-{args.iter}.json")


if __name__ == "__main__":
    main()
