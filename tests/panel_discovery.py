#!/usr/bin/env python3
"""
Cross-Model Panel Discovery: Discovery Instrument

Panel composes SAL freely from NL inputs. No expected answer provided.
Compare panel outputs against each other and against the deterministic
composer. Disagreements are the discovery surface:

  - Panel consensus ≠ composer  →  evaluate which is better
  - Panel consensus = composer   →  confirmed mapping
  - Panel split                  →  genuine ambiguity, needs doctrine
  - Panel finds opcode composer missed  →  new trigger candidate
  - Panel says NONE, composer says SAL  →  potential false positive

Usage:
  python tests/panel_discovery.py --anthropic-key KEY --openai-key KEY [--gemini-key KEY]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import (
    SALComposer, MacroRegistry, ASD_BASIS,
    AdaptiveSharedDictionary, validate_composition,
)

# ── Model Clients ────────────────────────────────────────────────────────────

def call_openai(prompt: str, system: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    import urllib.request
    body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 4000,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()


def call_anthropic(prompt: str, system: str, api_key: str, model: str = "claude-haiku-4-5-20251001") -> str:
    import urllib.request
    body = json.dumps({
        "model": model, "max_tokens": 300, "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["content"][0]["text"].strip()


def call_gemini(prompt: str, system: str, api_key: str, model: str = "gemini-2.0-flash") -> str:
    import urllib.request
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": 0, "maxOutputTokens": 300},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── Doctrine (composition system prompt) ─────────────────────────────────────

def build_doctrine() -> str:
    asd = AdaptiveSharedDictionary()
    ns_lines = []
    for ns, ops in sorted(asd._data.items()):
        entries = [f"{op}={defn.replace('_',' ')}" for op, defn in sorted(ops.items())]
        ns_lines.append(f"  {ns}: {', '.join(entries)}")
    listing = "\n".join(ns_lines)
    opcode_count = sum(len(ops) for ops in asd._data.values())

    return f"""SAL encodes agent instructions as deterministic opcode strings.

GRAMMAR: [NS:]OPCODE[@TARGET][OPERATOR INSTRUCTION]
OPERATORS: → THEN  ∧ AND  ∨ OR  ; SEQUENCE  ∥ PARALLEL

Rules:
- @ takes node_id or * (broadcast), never another opcode
- R namespace: every instruction (except ESTOP) needs ⚠, ↺, or ⊘
- ⚠/⊘ require I:§→ precondition
- If no opcode matches the core action: respond NL_PASSTHROUGH
- K:ORD = financial order, NOT food. A:SUM = summarize, NOT arithmetic.
- If SAL bytes >= NL bytes: NL_PASSTHROUGH

{opcode_count} opcodes:
{listing}

Compose SAL for the instruction. If no opcodes match, respond: NL_PASSTHROUGH
Respond with ONLY the SAL string on the first line. No explanation."""


# ── Parse SAL from model response ────────────────────────────────────────────

def parse_sal(text: str) -> str | None:
    text = text.strip()
    if "NL_PASSTHROUGH" in text.upper() or "NONE" in text.upper()[:20]:
        return None
    # First line that looks like SAL
    for line in text.split("\n"):
        line = line.strip()
        if re.match(r'^[A-Z\u03a9]:[\w\u00a7]', line):
            return line
    # [SAL: ...] wrapper
    m = re.search(r'\[SAL:\s*(.+?)\]', text)
    if m:
        return m.group(1).strip()
    return text.split("\n")[0].strip() if text else None


def extract_ns_ops(sal: str) -> set[tuple[str, str]]:
    pairs = set()
    for m in re.finditer(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)', sal):
        pairs.add((m.group(1), re.sub(r'[\u26a0\u21ba\u2298]', '', m.group(2))))
    return pairs


# ── Discovery Analysis ───────────────────────────────────────────────────────

def classify_result(composer_sal, panel_sals, expected_sals):
    """Classify a result into discovery categories."""
    composer_ops = extract_ns_ops(composer_sal) if composer_sal else set()
    expected_ops = set()
    for esal in (expected_sals or []):
        expected_ops |= extract_ns_ops(esal)

    # Get panel consensus
    panel_valid = {k: v for k, v in panel_sals.items() if v is not None}
    panel_none = {k for k, v in panel_sals.items() if v is None}

    if not panel_valid:
        if composer_sal:
            return "COMPOSER_ONLY", "Panel all NONE, composer produced SAL"
        return "ALL_NONE", "Everyone agrees: NL passthrough"

    # Find panel consensus opcodes
    panel_ops_list = [extract_ns_ops(v) for v in panel_valid.values()]
    # Common opcodes across majority of panel
    all_ops = set()
    for ops in panel_ops_list:
        all_ops |= ops
    consensus_ops = set()
    for op in all_ops:
        count = sum(1 for ops in panel_ops_list if op in ops)
        if count >= len(panel_valid) / 2:
            consensus_ops.add(op)

    if not consensus_ops:
        return "PANEL_SPLIT", "Panel disagrees with each other"

    # Compare consensus to composer
    if composer_sal is None:
        return "PANEL_FINDS_NEW", f"Panel found opcodes composer missed: {consensus_ops}"

    consensus_ns = {op[0] for op in consensus_ops}
    composer_ns = {op[0] for op in composer_ops}

    if consensus_ops == composer_ops:
        return "CONFIRMED", "Panel and composer agree"

    if consensus_ns & composer_ns:
        # Namespace overlap but different opcodes
        new_ops = consensus_ops - composer_ops
        if new_ops:
            return "PARTIAL_NEW", f"Panel found additional opcodes: {new_ops}"
        return "PARTIAL_MATCH", "Partial overlap"

    return "DISAGREE", f"Panel consensus {consensus_ops} vs composer {composer_ops}"


# ── Main ─────────────────────────────────────────────────────────────────────

def run_discovery(panel: dict[str, callable]):
    vectors_path = REPO_ROOT / "tests" / "composition-fidelity-test-v1.json"
    with open(vectors_path) as f:
        data = json.load(f)

    composer = SALComposer()
    doctrine = build_doctrine()

    print(f"\n{'='*78}")
    print(f"Cross-Model Panel Discovery — DISCOVERY INSTRUMENT")
    print(f"{'='*78}")
    print(f"Panel: {', '.join(panel.keys())} ({len(panel)} models)")
    print(f"Vectors: {len(data['vectors'])}")
    print(f"Method: Each model composes freely. Compare against each other + composer.")
    print(f"{'='*78}\n")

    results = []

    for v in data["vectors"]:
        vid = v["id"]
        nl = v["natural_language"]
        expected_sals = v.get("expected_sal")
        expected_mode = v["expected_mode"]

        # Deterministic composer
        composer_sal = composer.compose(nl)

        # Panel compositions
        panel_sals = {}
        panel_raw = {}
        for model_name, call_fn in panel.items():
            try:
                raw = call_fn(f"Compose SAL:\n{nl}", doctrine)
                panel_raw[model_name] = raw[:150]
                panel_sals[model_name] = parse_sal(raw)
            except Exception as e:
                panel_raw[model_name] = f"ERROR: {str(e)[:80]}"
                panel_sals[model_name] = None
            time.sleep(0.3)

        # Classify
        category, detail = classify_result(composer_sal, panel_sals, expected_sals)

        row = {
            "id": vid, "nl": nl, "expected_mode": expected_mode,
            "expected_sal": expected_sals,
            "composer_sal": composer_sal,
            "panel_sals": panel_sals,
            "panel_raw": panel_raw,
            "category": category,
            "detail": detail,
        }
        results.append(row)

        # Print
        c_short = (composer_sal or "NONE")[:25]
        icon = {"CONFIRMED": "+", "ALL_NONE": "+", "PANEL_FINDS_NEW": "!",
                "DISAGREE": "?", "PANEL_SPLIT": "~", "COMPOSER_ONLY": "-",
                "PARTIAL_NEW": "!", "PARTIAL_MATCH": "~"}.get(category, "?")
        print(f"  [{icon}] {vid}  {category:16s}  {nl[:40]}")
        print(f"       composer: {c_short}")
        for mn, sal in panel_sals.items():
            s = (sal or "NONE")[:35]
            match = "=" if sal == composer_sal else ("~" if sal else "X")
            print(f"       {mn:12s} [{match}]: {s}")
        if category not in ("CONFIRMED", "ALL_NONE"):
            print(f"       >> {detail}")
        print()

    # ── Summary ──────────────────────────────────────────────────────
    categories = {}
    for r in results:
        cat = r["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"{'='*78}")
    print(f"DISCOVERY SUMMARY")
    print(f"{'='*78}")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat:20s}  {count}/{len(results)}")

    # Actionable items
    discoveries = [r for r in results if r["category"] in ("PANEL_FINDS_NEW", "DISAGREE", "PARTIAL_NEW")]
    false_pos = [r for r in results if r["category"] == "COMPOSER_ONLY"]
    ambiguous = [r for r in results if r["category"] == "PANEL_SPLIT"]

    if discoveries:
        print(f"\nDISCOVERIES ({len(discoveries)} — panel found mappings composer missed):")
        for r in discoveries:
            print(f"  {r['id']}: {r['nl'][:50]}")
            print(f"    composer: {r['composer_sal']}")
            for mn, sal in r["panel_sals"].items():
                if sal:
                    print(f"    {mn}: {sal}")
            print(f"    >> {r['detail']}")

    if false_pos:
        print(f"\nPOTENTIAL FALSE POSITIVES ({len(false_pos)} — composer SAL, panel all NONE):")
        for r in false_pos:
            print(f"  {r['id']}: {r['nl'][:50]}  composer={r['composer_sal']}")

    if ambiguous:
        print(f"\nAMBIGUOUS ({len(ambiguous)} — panel disagrees with each other):")
        for r in ambiguous:
            print(f"  {r['id']}: {r['nl'][:50]}")
            for mn, sal in r["panel_sals"].items():
                print(f"    {mn}: {sal or 'NONE'}")

    print(f"{'='*78}\n")

    # Write report
    report_path = REPO_ROOT / "tests" / "panel-discovery-results.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"Report: {report_path}")

    return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cross-Model Panel Discovery Discovery")
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"))
    args = parser.parse_args()

    panel = {}
    if args.anthropic_key:
        panel["claude-sonnet"] = lambda p, s, k=args.anthropic_key: call_anthropic(p, s, k, "claude-sonnet-4-5-20241022")
        panel["claude-haiku"] = lambda p, s, k=args.anthropic_key: call_anthropic(p, s, k, "claude-haiku-4-5-20251001")
    if args.openai_key:
        panel["gpt-5"] = lambda p, s, k=args.openai_key: call_openai(p, s, k, "gpt-5")
        panel["gpt-4o-mini"] = lambda p, s, k=args.openai_key: call_openai(p, s, k, "gpt-4o-mini")
    if args.gemini_key:
        panel["gemini-flash"] = lambda p, s, k=args.gemini_key: call_gemini(p, s, k, "gemini-2.0-flash")

    if len(panel) < 2:
        print("ERROR: Need at least 2 panel models.")
        return 1

    run_discovery(panel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
