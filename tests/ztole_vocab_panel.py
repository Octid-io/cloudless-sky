#!/usr/bin/env python3
"""
ZTOLE Mode 1 — convergence measurement on disputed vocab chips.

For each input, run cold-doctrine compose against haiku, gpt-4o-mini, and
sonnet. Tally what opcode each model picks. Convergence = false vocab gap
(input reduces to existing opcode). Divergence = true gap (no existing
opcode captures intent uniformly).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "sdk" / "python"))

from osmp.protocol import AdaptiveSharedDictionary

# Load .env
ENV = REPO / ".env"
if ENV.exists():
    for line in ENV.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            if v:
                os.environ[k] = v

CORPUS = REPO / "tests" / "input-classes" / "corpus-ztole-vocab.json"
RESULTS = REPO / "tests" / "results"
OPCODE_RE = re.compile(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)')


def build_doctrine() -> str:
    asd = AdaptiveSharedDictionary()
    ns_lines = []
    for ns in sorted(asd._data.keys()):
        ops = asd._data[ns]
        entries = [f"{op}={defn.replace('_', ' ')}" for op, defn in sorted(ops.items())]
        ns_lines.append(f"  {ns}: {', '.join(entries)}")
    listing = "\n".join(ns_lines)
    opcode_count = sum(len(ops) for ops in asd._data.values())
    return f"""SAL encodes agent instructions as deterministic opcode strings.

GRAMMAR: [NS:]OPCODE[@TARGET][OPERATOR INSTRUCTION]
OPERATORS: \u2192 THEN  \u2227 AND  \u2228 OR  ; SEQUENCE  \u2225 PARALLEL

Rules:
- @ takes node_id or * (broadcast), never another opcode
- R namespace: every instruction (except ESTOP) needs \u26a0, \u21bb, or \u2298
- \u26a0/\u2298 require I:\u00a7\u2192 precondition
- If no opcode matches the core action: respond NL_PASSTHROUGH
- If SAL bytes >= NL bytes: NL_PASSTHROUGH

{opcode_count} opcodes in current ASD:
{listing}

Compose SAL for the instruction. If no opcodes in the listing match the core action, respond: NL_PASSTHROUGH
Respond with ONLY the SAL string on the first line. No explanation."""


def call_anthropic(model: str, system: str, user: str) -> str:
    body = json.dumps({
        "model": model, "max_tokens": 200, "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        for b in d.get("content", []):
            if b.get("type") == "text":
                return b.get("text", "").strip()
    except Exception as e:
        return f"ERR:{e}"
    return ""


def call_openai(model: str, system: str, user: str) -> str:
    body = json.dumps({
        "model": model, "max_tokens": 200, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        return d["choices"][0]["message"].get("content", "").strip()
    except Exception as e:
        return f"ERR:{e}"


def parse_first_line(text: str) -> str:
    if not text:
        return ""
    return text.splitlines()[0].strip()


def opcodes_in(sal: str) -> set[tuple[str, str]]:
    return set(OPCODE_RE.findall(sal)) if sal else set()


def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    inputs = corpus["inputs"]
    doctrine = build_doctrine()

    MODELS = [
        ("haiku", "claude-haiku-4-5", call_anthropic),
        ("sonnet", "claude-sonnet-4-5", call_anthropic),
        ("gpt-4o-mini", "gpt-4o-mini", call_openai),
    ]

    results = []
    print("=" * 100)
    print("ZTOLE MODE 1 — CONVERGENCE ON DISPUTED VOCAB CHIPS")
    print("=" * 100)

    for chip in inputs:
        nl = chip["nl"]
        print(f"\n[{chip['id']}] {nl!r}")
        print(f"  hypothesis: {chip['note'][:80]}...")
        per_model = {}
        for label, model, fn in MODELS:
            try:
                resp = fn(model, doctrine, nl)
                first = parse_first_line(resp)
                ops = opcodes_in(first)
                per_model[label] = {"sal": first, "opcodes": list(ops)}
                print(f"  {label:14s}: {first[:80]}  opcodes={list(ops)}")
            except Exception as e:
                per_model[label] = {"sal": f"ERR:{e}", "opcodes": []}
                print(f"  {label:14s}: ERR {e}")
            time.sleep(0.2)

        # Convergence analysis
        all_opcodes = []
        for v in per_model.values():
            all_opcodes.extend(v["opcodes"])
        opcode_counts = Counter(all_opcodes)
        if opcode_counts:
            top = opcode_counts.most_common(3)
            print(f"  CONVERGENCE: {dict(top)}")
            consensus = top[0][0] if top[0][1] >= 2 else None
            verdict = ("CONVERGED" if consensus
                        else "DIVERGED" if len(opcode_counts) > 1
                        else "UNANIMOUS_REFUSE" if not all_opcodes
                        else "SINGLE_VOTE")
            print(f"  VERDICT: {verdict} (consensus={consensus})")
        else:
            verdict = "ALL_PASSTHROUGH"
            consensus = None
            print(f"  VERDICT: {verdict}")

        results.append({
            "id": chip["id"], "nl": nl, "note": chip["note"],
            "per_model": per_model,
            "verdict": verdict, "consensus": consensus,
        })

    # Save
    out_path = RESULTS / "ztole-vocab-convergence.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
