#!/usr/bin/env python3
"""
ZTOLE Modes 2 + 3 on the 8 disputed vocab chips.

Mode 2 — Discovery: compare brigade composer output vs panel output.
  Buckets per chip:
    - CONFIRMED: composer + panel agree on opcode
    - COMPOSER_ONLY: composer emits, panel passthroughs
    - PANEL_ONLY: panel emits, composer passthroughs (panel found something composer missed)
    - DISAGREE: both emit but pick different opcodes
    - ALL_NONE: nobody composed

Mode 3 — Free generation: panel given NO doctrine, asked to invent an opcode
  for the input. Measure convergence on what they invent.
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
sys.path.insert(0, str(REPO / "sdk" / "python"))

from osmp.brigade import Orchestrator

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


# ─────────────────────────────────────────────────────────────────────────────
# Mode 3 — Free-generation prompt (no doctrine, models invent the opcode)
# ─────────────────────────────────────────────────────────────────────────────

FREE_GEN_PROMPT = """You're designing an instruction protocol where each action
maps to a single uppercase namespace letter (A-Z) and an uppercase opcode name
(typically 2-6 letters). Examples:
  E:TH = environmental temperature/humidity sensor
  R:STOP = robotic emergency-stop
  H:HR = heart rate measurement
  N:CFG = network configuration

For the input below, propose ONE opcode (NS:OPCODE) that captures the action.
If multiple are reasonable, pick the most natural. Respond with ONLY the
NS:OPCODE on the first line. No explanation.

Input: {nl}"""


def call_anthropic(model: str, system: str, user: str) -> str:
    body = json.dumps({
        "model": model, "max_tokens": 100, "system": system,
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
        "model": model, "max_tokens": 100, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}] if system else [{"role": "user", "content": user}],
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

    # Load Mode 1 results for Mode 2 comparison
    mode1_path = RESULTS / "ztole-vocab-convergence.json"
    mode1_data = json.load(open(mode1_path, encoding="utf-8"))
    mode1_by_id = {r["id"]: r for r in mode1_data["results"]}

    orch = Orchestrator()

    MODELS = [
        ("haiku", "claude-haiku-4-5", call_anthropic),
        ("sonnet", "claude-sonnet-4-5", call_anthropic),
        ("gpt-4o-mini", "gpt-4o-mini", call_openai),
    ]

    print("=" * 100)
    print("ZTOLE MODE 2 — DISCOVERY (composer vs panel)")
    print("=" * 100)

    mode2_results = []
    for chip in inputs:
        nl = chip["nl"]
        composer_sal = orch.compose(nl)
        composer_ops = opcodes_in(composer_sal) if composer_sal else set()

        # Panel data from Mode 1
        m1 = mode1_by_id.get(chip["id"], {})
        panel_ops = set()
        for label, info in (m1.get("per_model", {}) or {}).items():
            for op in info.get("opcodes", []):
                panel_ops.add(tuple(op))

        # Discovery categorization
        if not composer_ops and not panel_ops:
            cat = "ALL_NONE"
        elif composer_ops and not panel_ops:
            cat = "COMPOSER_ONLY"
        elif panel_ops and not composer_ops:
            cat = "PANEL_ONLY"
        elif composer_ops & panel_ops:
            cat = "CONFIRMED" if composer_ops == panel_ops else "PARTIAL_OVERLAP"
        else:
            cat = "DISAGREE"

        panel_only_ops = panel_ops - composer_ops
        composer_only_ops = composer_ops - panel_ops

        print(f"\n[{chip['id']}] {nl!r}")
        print(f"  composer: {composer_sal!r}  opcodes={list(composer_ops)}")
        print(f"  panel:    {list(panel_ops)}")
        print(f"  category: {cat}")
        if panel_only_ops:
            print(f"  PANEL FOUND (composer missed): {list(panel_only_ops)}")
        if composer_only_ops:
            print(f"  COMPOSER FOUND (panel missed): {list(composer_only_ops)}")

        mode2_results.append({
            "id": chip["id"], "nl": nl,
            "composer_sal": composer_sal,
            "composer_opcodes": list(composer_ops),
            "panel_opcodes": list(panel_ops),
            "category": cat,
            "panel_found_new": list(panel_only_ops),
            "composer_found_new": list(composer_only_ops),
        })

    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("ZTOLE MODE 3 — FREE GENERATION (no doctrine, panel invents)")
    print("=" * 100)

    mode3_results = []
    for chip in inputs:
        nl = chip["nl"]
        prompt = FREE_GEN_PROMPT.format(nl=nl)
        per_model = {}

        for label, model, fn in MODELS:
            try:
                resp = fn(model, "", prompt)  # NO doctrine system prompt
                first = parse_first_line(resp)
                ops = opcodes_in(first)
                per_model[label] = {"emit": first, "opcodes": list(ops)}
            except Exception as e:
                per_model[label] = {"emit": f"ERR:{e}", "opcodes": []}
            time.sleep(0.2)

        # Convergence on invented opcodes
        invented = []
        for v in per_model.values():
            invented.extend(v["opcodes"])
        counts = Counter(invented)

        print(f"\n[{chip['id']}] {nl!r}")
        for label in ("haiku", "sonnet", "gpt-4o-mini"):
            v = per_model.get(label, {})
            print(f"  {label:14s}: {v.get('emit', '')[:60]}  -> {v.get('opcodes', [])}")
        if counts:
            print(f"  INVENTED OPCODES: {dict(counts.most_common())}")
            top = counts.most_common(1)[0]
            consensus_op = top[0] if top[1] >= 2 else None
            verdict = ("CONVERGED_INVENT" if consensus_op
                        else "DIVERGED_INVENT")
            print(f"  VERDICT: {verdict} (consensus={consensus_op})")
        else:
            consensus_op = None
            verdict = "NO_INVENT"
            print(f"  VERDICT: {verdict}")

        mode3_results.append({
            "id": chip["id"], "nl": nl,
            "per_model": per_model,
            "invented_counts": {f"{ns}:{op}": c for (ns, op), c in counts.items()},
            "consensus_invented": list(consensus_op) if consensus_op else None,
            "verdict": verdict,
        })

    # Save
    out = {"mode2": mode2_results, "mode3": mode3_results}
    out_path = RESULTS / "ztole-modes-2-3.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
