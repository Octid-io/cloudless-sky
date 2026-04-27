#!/usr/bin/env python3
"""
ZTOLE Lotus reduction on the Mode-3 converged invented opcodes.

For each candidate opcode, iteratively shorten and test panel recognition:
  V:OPEN → V:OPN → V:OP → V:O
  D:DEL → D:DL → D:D
  E:START → E:STRT → E:STA → E:ST → E:S

At each reduction, ask the panel: "given this opcode, what action does it
trigger for input X?" — measure recognition (does the panel agree this
opcode means the original action?).

The shortest form where recognition holds = the LOTUS-OPTIMAL opcode.
Pure ZTOLE methodology per CIP-50 v0.3, claim 15.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Load .env
ENV = REPO / ".env"
if ENV.exists():
    for line in ENV.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            if v:
                os.environ[k] = v

RESULTS = REPO / "tests" / "results"


# Lotus reduction targets — converged invented opcodes from Mode 3
# Each: (full_opcode, original_intent_NL)
LOTUS_TARGETS = [
    ("V:OPEN", "open valve V12", "open a valve"),
    ("V:CLOSE", "close valve V12", "close a valve"),
    ("C:POS", "report control station position", "geographic position of control station"),
    ("N:BCAST", "broadcast my position to all peers", "broadcast a message to all peers"),
    ("E:START", "start the engine", "start an engine or motor"),
    ("S:VIB", "vibration sensor reading from sensor 4A", "vibration sensor reading"),
    ("D:DEL", "delete the database table", "delete data from storage"),
    ("D:DROP", "delete the database table", "drop a database table"),
]


def reductions(opcode: str) -> list[str]:
    """Generate iterative reductions of an opcode (NS:NAME).
    Returns list of progressively shorter forms, longest first.
    Strategy: vowel-strip, then trim from the end.
    """
    ns, name = opcode.split(":")
    forms = [opcode]

    # Vowel-strip: V:OPEN → V:PN, V:CLOSE → V:CLS, D:DEL → D:DL
    no_vowels = "".join(c for c in name if c.upper() not in "AEIOU" or c == name[0])
    if no_vowels and no_vowels != name and len(no_vowels) >= 1:
        forms.append(f"{ns}:{no_vowels}")

    # Progressive trim from end
    cur = name
    while len(cur) > 1:
        cur = cur[:-1]
        candidate = f"{ns}:{cur}"
        if candidate not in forms:
            forms.append(candidate)

    # Also: vowel-strip + trim
    cur = no_vowels
    while len(cur) > 1:
        cur = cur[:-1]
        candidate = f"{ns}:{cur}"
        if candidate not in forms and len(candidate) >= 3:  # NS:X minimum
            forms.append(candidate)

    return forms


# Recognition test prompt: given an opcode, what action does it trigger?
RECOG_PROMPT = """In an instruction protocol, opcodes follow the form NS:OPCODE
(e.g., E:TH = environmental temperature/humidity, R:STOP = robotic stop).

For the opcode below, what natural-language ACTION does it trigger?
Be brief — one short sentence on the first line.

Opcode: {opcode}"""


def call_anthropic(model: str, user: str) -> str:
    body = json.dumps({
        "model": model, "max_tokens": 80,
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


def call_openai(model: str, user: str) -> str:
    body = json.dumps({
        "model": model, "max_tokens": 80, "temperature": 0,
        "messages": [{"role": "user", "content": user}],
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


def first_line(s: str) -> str:
    return s.splitlines()[0].strip() if s else ""


def recognized(model_response: str, intent: str) -> bool:
    """Loose semantic recognition: does the model's response contain key
    semantic anchors from the intent?"""
    resp_low = model_response.lower()
    intent_low = intent.lower()
    # Extract key words from intent (skip stopwords)
    STOPWORDS = {"a", "an", "the", "of", "to", "from", "for", "in", "on",
                 "or", "and", "is", "are", "with"}
    intent_words = [w for w in intent_low.split() if w not in STOPWORDS and len(w) > 2]
    # Recognition = at least 50% of key intent words appear in response
    if not intent_words:
        return False
    matches = sum(1 for w in intent_words if w in resp_low)
    return matches / len(intent_words) >= 0.5


def main():
    MODELS = [
        ("haiku", "claude-haiku-4-5", call_anthropic),
        ("sonnet", "claude-sonnet-4-5", call_anthropic),
        ("gpt-4o-mini", "gpt-4o-mini", call_openai),
    ]

    print("=" * 100)
    print("ZTOLE LOTUS REDUCTION — find shortest opcode that preserves recognition")
    print("=" * 100)

    all_results = []
    for full_opcode, source_nl, intent in LOTUS_TARGETS:
        print(f"\n[{full_opcode}] intent: {intent!r}")
        forms = reductions(full_opcode)
        print(f"  Forms (longest→shortest): {forms[:8]}")

        per_form = []
        last_recognized_form = None
        for form in forms:
            recog_count = 0
            responses = {}
            for label, model, fn in MODELS:
                try:
                    resp = fn(model, RECOG_PROMPT.format(opcode=form))
                    fl = first_line(resp)
                    is_rec = recognized(fl, intent)
                    if is_rec:
                        recog_count += 1
                    responses[label] = {"resp": fl[:80], "recognized": is_rec}
                except Exception as e:
                    responses[label] = {"resp": f"ERR:{e}", "recognized": False}
                time.sleep(0.15)
            recog_rate = recog_count / len(MODELS)
            per_form.append({
                "form": form, "len": len(form), "recog_rate": recog_rate,
                "responses": responses,
            })
            print(f"  {form:14s} ({len(form)}B): recog={recog_count}/{len(MODELS)} ({recog_rate:.0%})")
            for lbl, r in responses.items():
                rec_marker = "✓" if r["recognized"] else "✗"
                print(f"    {rec_marker} {lbl}: {r['resp'][:60]}")
            if recog_rate >= 0.66:
                last_recognized_form = form
            else:
                # Recognition broke — stop reducing
                print(f"  → STOP. Recognition broke at {form}.")
                break

        # Conclusion
        savings_pct = 0
        if last_recognized_form and len(last_recognized_form) < len(full_opcode):
            savings_pct = 100 * (len(full_opcode) - len(last_recognized_form)) / len(full_opcode)
        print(f"  LOTUS-OPTIMAL: {last_recognized_form or full_opcode} (savings: {savings_pct:.1f}%)")

        all_results.append({
            "full_opcode": full_opcode, "intent": intent,
            "lotus_optimal": last_recognized_form or full_opcode,
            "savings_pct": round(savings_pct, 1),
            "per_form": per_form,
        })

    # Save
    out_path = RESULTS / "ztole-lotus-reduction.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": all_results}, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")

    # Summary
    print()
    print("=" * 100)
    print("LOTUS REDUCTION SUMMARY")
    print("=" * 100)
    print(f"{'Original':<14} {'Optimal':<14} {'Savings':<10}")
    for r in all_results:
        print(f"{r['full_opcode']:<14} {r['lotus_optimal']:<14} {r['savings_pct']:>5.1f}%")


if __name__ == "__main__":
    main()
