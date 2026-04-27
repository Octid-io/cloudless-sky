#!/usr/bin/env python3
"""
ZTOLE Lotus on mnemonic double-letter namespaces.

Validates Clay's hypothesis: dropping AB=BA bidirectional rule lets us use
mnemonic double-letter prefixes (CS:POS for control station, VL:CL for valve
close, EN:START for engine, VB:SNS for vibration) — testing whether these
double-letter forms are panel-recognized where the single-letter forms
failed.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV = REPO / ".env"
if ENV.exists():
    for line in ENV.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            if v:
                os.environ[k] = v

RESULTS = REPO / "tests" / "results"

# Test pairs: (single-letter form that failed, mnemonic double-letter alternative, intent)
TEST_PAIRS = [
    ("C:POS",     "CS:POS",   "geographic position of control station"),
    ("E:START",   "EN:START", "start an engine or motor"),
    ("S:VIB",     "VB:SNS",   "vibration sensor reading"),
    ("V:OPE",     "VL:OPE",   "open a valve"),
    ("V:CL",      "VL:CL",    "close a valve"),
    ("D:DROP",    "DB:DROP",  "drop a database table"),
    # Sanity controls — single-letter that DID work
    ("N:BCST",    "NW:BCST",  "broadcast a message to all peers (network)"),
    ("R:STOP",    "RB:STOP",  "robotic stop / actuator stop"),
]

RECOG_PROMPT = """In an instruction protocol, opcodes follow the form NS:OPCODE
where NS is a 1-2 letter namespace and OPCODE is the action.
Examples:
  E:TH = environmental temperature/humidity sensor
  R:STOP = robotic emergency-stop
  H:HR = heart rate measurement

For the opcode below, what natural-language ACTION does it trigger?
Be brief — one short sentence on the first line.

Opcode: {opcode}"""


def call_anthropic(model: str, user: str) -> str:
    body = json.dumps({"model": model, "max_tokens": 80,
                        "messages": [{"role": "user", "content": user}]}).encode()
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


def call_openai(model: str, user: str) -> str:
    body = json.dumps({"model": model, "max_tokens": 80, "temperature": 0,
                        "messages": [{"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        return d["choices"][0]["message"].get("content", "").strip()
    except Exception as e:
        return f"ERR:{e}"


def first_line(s: str) -> str:
    return s.splitlines()[0].strip() if s else ""


def recognized(resp: str, intent: str) -> bool:
    rl = resp.lower()
    il = intent.lower()
    STOPWORDS = {"a", "an", "the", "of", "to", "from", "for", "in", "on", "or", "and", "is", "are", "with"}
    words = [w for w in il.split() if w not in STOPWORDS and len(w) > 2]
    if not words:
        return False
    return sum(1 for w in words if w in rl) / len(words) >= 0.5


def main():
    MODELS = [
        ("haiku", "claude-haiku-4-5", call_anthropic),
        ("sonnet", "claude-sonnet-4-5", call_anthropic),
        ("gpt-4o-mini", "gpt-4o-mini", call_openai),
    ]
    print("=" * 100)
    print("ZTOLE LOTUS — single-letter vs mnemonic double-letter namespace comparison")
    print("=" * 100)

    results = []
    for single, double, intent in TEST_PAIRS:
        print(f"\nIntent: {intent!r}")
        for opcode in (single, double):
            recog_count = 0
            responses = {}
            for label, model, fn in MODELS:
                try:
                    resp = fn(model, RECOG_PROMPT.format(opcode=opcode))
                    fl = first_line(resp)
                    is_rec = recognized(fl, intent)
                    if is_rec:
                        recog_count += 1
                    responses[label] = {"resp": fl[:70], "recognized": is_rec}
                except Exception as e:
                    responses[label] = {"resp": f"ERR:{e}", "recognized": False}
                time.sleep(0.15)
            rate = recog_count / len(MODELS)
            verdict = "✓" if rate >= 0.66 else "✗"
            print(f"  {verdict} {opcode:<10s} ({len(opcode)}B): recog={recog_count}/{len(MODELS)} ({rate:.0%})")
            for lbl, r in responses.items():
                m = "✓" if r["recognized"] else "✗"
                print(f"    {m} {lbl:14s}: {r['resp'][:60]}")
            results.append({
                "intent": intent, "opcode": opcode, "len": len(opcode),
                "recog_rate": rate, "responses": responses,
            })

    # Summary: pair improvement
    print()
    print("=" * 100)
    print("SUMMARY — single vs double mnemonic")
    print("=" * 100)
    print(f"{'Intent':<50} {'single':<14} {'double':<14} {'delta':<10}")
    pairs = list(zip(results[::2], results[1::2]))
    for s, d in pairs:
        s_rate = s["recog_rate"]
        d_rate = d["recog_rate"]
        delta = d_rate - s_rate
        marker = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        print(f"{s['intent'][:50]:<50} {s['opcode']+f' ({s_rate:.0%})':<14} {d['opcode']+f' ({d_rate:.0%})':<14} {marker}{abs(delta):.0%}")

    out_path = RESULTS / "ztole-lotus-doubles.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
