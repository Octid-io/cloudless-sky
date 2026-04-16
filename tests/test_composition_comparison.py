#!/usr/bin/env python3
"""
Composition Comparison Test: Three paths to SAL, same 30 vectors.

Path 1 (Deterministic): SALComposer keyword/phrase pipeline — no model
Path 2 (LLM Direct):    Model with doctrine writes SAL directly
Path 3 (LLM → JSON):    Model extracts structured intent as JSON,
                         deterministic code maps JSON to SAL

All three paths scored against expected_sal from the fidelity suite.
Measures composition accuracy, not decode or interpretation.

Usage:
  python tests/test_composition_comparison.py --anthropic-key KEY --openai-key KEY
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
    SALComposer,
    MacroRegistry,
    ASD_BASIS,
    validate_composition,
    ComposedIntent,
)

# ── Model Clients ────────────────────────────────────────────────────────────

def call_openai(prompt: str, system: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    import urllib.request
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 300,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


def call_anthropic(prompt: str, system: str, api_key: str, model: str = "claude-haiku-4-5-20251001") -> str:
    import urllib.request
    body = json.dumps({
        "model": model,
        "max_tokens": 300,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"].strip()


# ── Doctrine (extracted from MCP server system_prompt resource) ──────────────

def build_doctrine() -> str:
    """Build the composition doctrine string (same as osmp://system_prompt)."""
    from osmp.protocol import AdaptiveSharedDictionary
    asd = AdaptiveSharedDictionary()

    _DEF_OVERRIDES = {
        "A:CMPR": "structured comparison", "A:DA": "delegate to agent",
        "A:MACRO": "macro invocation", "A:MDR": "corpus version",
        "D:PACK": "corpus encode", "D:UNPACK": "corpus decode",
        "E:TH": "temp+humidity", "I:§": "human confirm",
        "J:HANDOFF": "transfer execution", "R:RTH": "return home",
        "S:OPEN": "unseal payload", "Z:TOPP": "top-p sampling",
    }

    def _abbrev(ns, op, defn):
        key = f"{ns}:{op}"
        if key in _DEF_OVERRIDES:
            return _DEF_OVERRIDES[key]
        d = defn.replace("_", " ")
        words = d.split()
        return " ".join(words[:2]) if len(words) > 2 else d

    ns_lines = []
    for ns, ops in sorted(asd._data.items()):
        parts = [f"{op}({_abbrev(ns, op, defn)})" for op, defn in sorted(ops.items())]
        ns_lines.append(f"  {ns}: {' '.join(parts)}")

    opcode_count = sum(len(ops) for ops in asd._data.values())
    namespace_listing = "\n".join(ns_lines)

    return f"""SAL encodes agent instructions as deterministic opcode strings. Decode is deterministic. No inference.

GRAMMAR: [NS:]OPCODE[@TARGET][OPERATOR INSTRUCTION]
OPERATORS: → THEN  ∧ AND  ∨ OR  ; SEQUENCE  ∥ PARALLEL
TARGET: @NODE_ID or @* (broadcast)  QUERY: ?SLOT  PARAM: [value]

NAMESPACE SELECTION BY DOMAIN:
Patient/clinical → H. Environmental sensor → E. Weather data → W. AI inference → Z.
Energy grid → X. Building ops → B. Municipal emergency → M. Robotics/physical → R.
Crypto/security → S. Financial → K. Cognitive/planning → J. Time/scheduling → T.
Audit/compliance → L. Maintenance → P. Human operator → U. Identity/auth → I.

KEY DISAMBIGUATION:
K:ORD = financial order (ISO 20022), NOT food. A:SUM = summarize, NOT arithmetic.
S:SIGN = crypto signature, NOT legal. Z:TEMP = sampling temperature, NOT physical.
H:ALERT = clinical threshold, NOT general. W:FIRE = weather fire data, NOT building fire.
Building fire = B:ALRM + M:EVA. "order tacos" = NL passthrough. "send email" = NL passthrough.

R NAMESPACE: Every R instruction (except ESTOP) requires consequence class (⚠↺⊘).
⚠/⊘ require I:§→ precondition. Aerial=⚠. Ground+humans=⚠. Peripheral=↺.

BYTE CHECK: If SAL >= NL bytes, use NL passthrough.
If no opcode matches the core action: NL passthrough. Never force-fit.

{opcode_count} opcodes:
{namespace_listing}"""


# ── Scoring ──────────────────────────────────────────────────────────────────

def extract_ns_ops(sal: str) -> set[tuple[str, str]]:
    pairs = set()
    for m in re.finditer(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)', sal):
        pairs.add((m.group(1), re.sub(r'[\u26a0\u21ba\u2298]', '', m.group(2))))
    return pairs


def score_sal(actual: str | None, vector: dict) -> dict:
    """Score composed SAL against expected. Returns {mode, ns, op, safety, total}."""
    expected_mode = vector["expected_mode"]
    expected_sals = vector.get("expected_sal") or []
    scores = {"mode": 0, "ns": 0, "op": 0, "safety": 0, "total": 0}

    actual_mode = "FULL_OSMP" if actual else "NL_PASSTHROUGH"

    # Mode score
    if expected_mode == "NL_PASSTHROUGH":
        scores["mode"] = 1 if actual is None else 0
    elif expected_mode in ("FULL_OSMP", "FULL_OSMP_OMEGA"):
        scores["mode"] = 1 if actual is not None else 0
    elif expected_mode == "CONDITIONAL":
        scores["mode"] = 1  # both paths valid
    elif expected_mode == "NL_OR_HITL":
        scores["mode"] = 1 if actual is None else 0

    if actual and expected_sals:
        actual_pairs = extract_ns_ops(actual)
        actual_ns = {p[0] for p in actual_pairs}
        actual_ops = {p[1] for p in actual_pairs}

        best_ns = 0
        best_op = 0
        for esal in expected_sals:
            e_pairs = extract_ns_ops(esal)
            e_ns = {p[0] for p in e_pairs}
            e_ops = {p[1] for p in e_pairs}
            if e_ns:
                best_ns = max(best_ns, len(e_ns & actual_ns) / len(e_ns))
            if e_ops:
                best_op = max(best_op, len(e_ops & actual_ops) / len(e_ops))

        scores["ns"] = 1 if best_ns >= 0.5 else 0
        scores["op"] = 1 if best_op >= 0.5 else 0
    elif actual is None and expected_mode in ("NL_PASSTHROUGH", "NL_OR_HITL", "CONDITIONAL"):
        scores["ns"] = 1
        scores["op"] = 1

    # Safety score
    scores["safety"] = 1
    if actual:
        result = validate_composition(actual, nl=vector["natural_language"])
        if any(e.rule in ("HALLUCINATED_OPCODE", "CONSEQUENCE_CLASS_OMISSION",
                          "AUTHORIZATION_OMISSION", "NAMESPACE_AS_TARGET")
               for e in result.errors):
            scores["safety"] = 0

    scores["total"] = sum(scores[k] for k in ["mode", "ns", "op", "safety"])
    return scores


def parse_sal_from_response(text: str) -> str | None:
    """Extract SAL from model response. Handles various output formats."""
    text = text.strip()
    # Direct SAL (no wrapper)
    if re.match(r'^[A-Z\u03a9]:[\w\u00a7]', text.split('\n')[0]):
        return text.split('\n')[0].strip()
    # [SAL: ...] wrapper
    m = re.search(r'\[SAL:\s*(.+?)\]', text)
    if m:
        return m.group(1).strip()
    # ```sal ... ``` block
    m = re.search(r'```(?:sal)?\s*\n?(.+?)\n?```', text, re.DOTALL)
    if m:
        return m.group(1).strip().split('\n')[0]
    # "SAL:" prefix
    m = re.search(r'SAL:\s*(.+)', text)
    if m:
        return m.group(1).strip()
    # NL_PASSTHROUGH indicators
    if any(kw in text.lower() for kw in ["nl_passthrough", "passthrough", "natural language", "no opcode", "no sal"]):
        return None
    # Last resort: first line that looks like SAL
    for line in text.split('\n'):
        line = line.strip()
        if re.match(r'^[A-Z]:[\w\u00a7]', line):
            return line
    return None


def parse_json_intent(text: str) -> dict | None:
    """Extract JSON intent from model response."""
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    text = re.sub(r'^```\s*', '', text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


# ── Prompts ──────────────────────────────────────────────────────────────────

DIRECT_COMPOSE_PROMPT = """Compose SAL for the following instruction. Follow the doctrine exactly.
If no opcodes match the core action, respond with exactly: NL_PASSTHROUGH
If opcodes match, respond with ONLY the SAL string on the first line. No explanation.

Instruction: {nl}"""

JSON_INTENT_PROMPT = """Extract the structured intent from this instruction as JSON. Return ONLY JSON.
{{
  "actions": ["list of domain action keywords that map to protocol opcodes"],
  "conditions": ["threshold expressions like >130, <38"],
  "targets": ["node IDs or device names"],
  "parameters": {{"key": "value pairs like icd: J930, temperature: 0.3"}},
  "should_compose": true/false (false if no protocol opcodes apply, e.g. food orders, emails)
}}

Instruction: {nl}"""


# ── Test Runner ──────────────────────────────────────────────────────────────

def run_comparison(call_model, model_name: str):
    vectors_path = REPO_ROOT / "tests" / "composition-fidelity-test-v1.json"
    with open(vectors_path) as f:
        data = json.load(f)

    composer = SALComposer()
    doctrine = build_doctrine()

    print(f"\n{'='*78}")
    print(f"COMPOSITION COMPARISON — {model_name}")
    print(f"{'='*78}")
    print(f"Path 1: Deterministic (SALComposer keyword/phrase, no model)")
    print(f"Path 2: LLM Direct (model writes SAL with doctrine)")
    print(f"Path 3: LLM → JSON (model extracts intent, code maps to SAL)")
    print(f"{'='*78}\n")

    results = []

    for v in data["vectors"]:
        vid = v["id"]
        nl = v["natural_language"]
        row = {"id": vid, "nl": nl, "expected_mode": v["expected_mode"]}

        # ── Path 1: Deterministic ────────────────────────────────────
        sal_1 = composer.compose(nl)
        row["p1_sal"] = sal_1
        row["p1_scores"] = score_sal(sal_1, v)

        # ── Path 2: LLM Direct Compose ──────────────────────────────
        try:
            raw = call_model(DIRECT_COMPOSE_PROMPT.format(nl=nl), doctrine)
            sal_2 = parse_sal_from_response(raw)
            row["p2_sal"] = sal_2
            row["p2_raw"] = raw[:120]
            row["p2_scores"] = score_sal(sal_2, v)
        except Exception as e:
            row["p2_sal"] = None
            row["p2_scores"] = {"mode": 0, "ns": 0, "op": 0, "safety": 0, "total": 0}
            row["p2_error"] = str(e)[:80]
        time.sleep(0.3)

        # ── Path 3: LLM → JSON → SAL ────────────────────────────────
        try:
            raw = call_model(JSON_INTENT_PROMPT.format(nl=nl), "You are an intent extraction engine. Return ONLY valid JSON.")
            intent_dict = parse_json_intent(raw)
            if intent_dict and not intent_dict.get("should_compose", True) == False:
                # Build ComposedIntent from JSON
                intent = ComposedIntent(
                    actions=intent_dict.get("actions", []),
                    conditions=intent_dict.get("conditions", []),
                    targets=intent_dict.get("targets", []),
                    parameters=intent_dict.get("parameters", {}),
                    raw=nl,
                )
                sal_3 = composer.compose(nl, intent=intent)
            else:
                sal_3 = None  # Model said don't compose
            row["p3_sal"] = sal_3
            row["p3_raw"] = raw[:120]
            row["p3_scores"] = score_sal(sal_3, v)
        except Exception as e:
            row["p3_sal"] = None
            row["p3_scores"] = {"mode": 0, "ns": 0, "op": 0, "safety": 0, "total": 0}
            row["p3_error"] = str(e)[:80]
        time.sleep(0.3)

        # ── Print ────────────────────────────────────────────────────
        s1 = row["p1_scores"]["total"]
        s2 = row["p2_scores"]["total"]
        s3 = row["p3_scores"]["total"]
        best = max(s1, s2, s3)
        w = "1" if s1 == best and s1 > s2 and s1 > s3 else \
            "2" if s2 == best and s2 > s1 and s2 > s3 else \
            "3" if s3 == best and s3 > s1 and s3 > s2 else "="
        print(f"  {vid}  D:{s1}/4  LLM:{s2}/4  JSON:{s3}/4  [{w}]  {nl[:42]}")

        results.append(row)

    # ── Summary ──────────────────────────────────────────────────────
    n = len(results)
    max_pts = n * 4

    for path, label in [("p1", "Deterministic"), ("p2", "LLM Direct"), ("p3", "LLM→JSON")]:
        total = sum(r[f"{path}_scores"]["total"] for r in results)
        pct = total / max_pts * 100
        mode_s = sum(r[f"{path}_scores"]["mode"] for r in results)
        ns_s = sum(r[f"{path}_scores"]["ns"] for r in results)
        op_s = sum(r[f"{path}_scores"]["op"] for r in results)
        safe_s = sum(r[f"{path}_scores"]["safety"] for r in results)
        print(f"\n  {label:16s}  {total}/{max_pts} ({pct:.1f}%)")
        print(f"    Mode: {mode_s}/{n}  NS: {ns_s}/{n}  OP: {op_s}/{n}  Safety: {safe_s}/{n}")

    print(f"\n{'='*78}\n")
    return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Composition Comparison Test")
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--anthropic-model", default="claude-haiku-4-5-20251001")
    args = parser.parse_args()

    all_results = {}

    if args.anthropic_key:
        def call_claude(prompt, system):
            return call_anthropic(prompt, system, args.anthropic_key, args.anthropic_model)
        all_results["claude"] = run_comparison(call_claude, f"Claude ({args.anthropic_model})")

    if args.openai_key:
        def call_gpt(prompt, system):
            return call_openai(prompt, system, args.openai_key, args.openai_model)
        all_results["openai"] = run_comparison(call_gpt, f"OpenAI ({args.openai_model})")

    if not all_results:
        print("ERROR: No API keys.")
        return 1

    report_path = REPO_ROOT / "tests" / "composition-comparison-results.json"
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
