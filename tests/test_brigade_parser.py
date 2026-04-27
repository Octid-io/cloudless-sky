#!/usr/bin/env python3
"""Test the brigade parser — runs parse() on every corpus chip and prints
the ParsedRequest IR so we can validate the structural extraction before
building stations on top."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "sdk" / "python"))

from osmp.brigade.parser import parse

corpus = json.load(open(REPO / "tests" / "input-classes" / "corpus.json"))

print("=" * 100)
print("BRIGADE PARSER TEST — IR for every corpus chip")
print("=" * 100)
print()

for c in corpus["inputs"]:
    pr = parse(c["nl"])
    print(f"[{c['id']}] {c['nl']!r}")
    print(f"  expected: {c.get('expected_sal', [])[:1]}")
    print(f"  ir: {pr}")
    if pr.has_chain():
        for i, seg in enumerate(pr.chain_segments):
            print(f"    seg {i}: {seg}")
    print()
