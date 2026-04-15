#!/usr/bin/env python3
"""
Layer 3 Agent-to-Agent Semantic Roundtrip Test (v2)

Three paths, domain-specific scoring, filtered to valid compositions.

  Path A (Raw NL):       NL text -> Agent B interprets
  Path B (Bridge/Decode): NL -> compose -> SAL -> decode to NL -> Agent B interprets
  Path C (Native SAL):   NL -> compose -> SAL -> Agent B interprets SAL directly

Scoring: targeted domain/action/threshold/target questions scored against
ground truth. Measures disambiguation precision, not OSMP identifier recall.

Usage:
  python tests/test_agent_roundtrip.py --anthropic-key KEY --openai-key KEY
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import (
    SALComposer,
    SALDecoder,
    MacroRegistry,
    ASD_BASIS,
    validate_composition,
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
        "max_tokens": 200,
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
        "max_tokens": 200,
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


# ── Ground Truth & Questions ─────────────────────────────────────────────────
# Each FULL_OSMP vector gets domain-specific multiple-choice questions.
# The answers are derived from the test vector's expected SAL and scoring notes.

DOMAIN_MAP = {
    "H": "medical/clinical", "E": "environmental/sensor", "W": "weather",
    "R": "robotics/physical", "S": "cryptography/security", "D": "data transfer",
    "K": "financial", "M": "municipal/emergency", "B": "building",
    "J": "cognitive/planning", "Z": "AI inference", "U": "human operator",
    "I": "identity/authorization", "G": "geospatial", "T": "time/scheduling",
    "L": "audit/compliance", "X": "energy", "P": "maintenance/procedural",
    "Q": "quality/evaluation", "V": "maritime", "A": "agentic protocol",
}

VECTOR_QUESTIONS = {
    "CF-001": {
        "domain": "medical/clinical",
        "action": "heart rate monitoring with threshold alert",
        "threshold": "130",
        "has_target": False,
    },
    "CF-002": {
        "domain": "environmental/sensor",
        "action": "temperature and humidity reading",
        "threshold": None,
        "has_target": True,
        "target_hint": "4A",
    },
    "CF-003": {
        "domain": "cryptography/security",
        "action": "key generation then signing then data transfer",
        "threshold": None,
        "has_target": True,
        "target_hint": "BRAVO",
    },
    "CF-004": {
        "domain": "robotics/physical",
        "action": "emergency stop",
        "threshold": None,
        "has_target": False,
    },
    "CF-005": {
        "domain": "financial",
        "action": "payment with human authorization gate",
        "threshold": None,
        "has_target": False,
    },
    "CF-006": {
        "domain": "cognitive/planning",
        "action": "task handoff to another agent",
        "threshold": None,
        "has_target": True,
        "target_hint": "BETA",
    },
    "CF-007": {
        "domain": "AI inference",
        "action": "model inference with temperature and sampling parameters",
        "threshold": "0.3",
        "has_target": False,
    },
    "CF-008": {
        "domain": "building",
        "action": "fire alarm and evacuation",
        "threshold": None,
        "has_target": False,
    },
    "CF-009": {
        "domain": "weather",
        "action": "wind and visibility observation",
        "threshold": None,
        "has_target": False,
    },
    "CF-010": {
        "domain": "robotics/physical",
        "action": "robot movement with safety zone constraint",
        "threshold": None,
        "has_target": True,
        "target_hint": "alpha",
    },
    "CF-019": {
        "domain": "agentic protocol",
        "action": "summarize content",
        "threshold": None,
        "has_target": False,
    },
    "CF-022": {
        "domain": "energy",
        "action": "wind energy generation status check",
        "threshold": None,
        "has_target": False,
    },
    "CF-023": {
        "domain": "medical/clinical",
        "action": "identity verification then blood pressure check then casualty report and evacuation",
        "threshold": "180",
        "has_target": True,
        "target_hint": "base camp",
    },
    "CF-028": {
        "domain": "robotics/physical",
        "action": "drone movement to coordinates",
        "threshold": None,
        "has_target": True,
        "target_hint": "35.7",
    },
    "CF-029": {
        "domain": "medical/clinical",
        "action": "diagnosis code lookup then casualty report then medevac",
        "threshold": None,
        "has_target": True,
        "target_hint": "MEDEVAC",
    },
    "CF-030": {
        "domain": "time/scheduling",
        "action": "maintenance window scheduling for grid controller",
        "threshold": None,
        "has_target": False,
    },
}


# ── Extraction Prompt ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a precise intent extraction engine. Given a message, answer these 4 questions.
Return ONLY a JSON object with exactly these fields:

{
  "domain": "one of: medical/clinical, environmental/sensor, weather, robotics/physical, cryptography/security, data transfer, financial, municipal/emergency, building, cognitive/planning, AI inference, human operator, identity/authorization, geospatial, time/scheduling, audit/compliance, energy, maintenance/procedural, quality/evaluation, maritime, agentic protocol",
  "action": "brief description of the core action being requested (5-15 words)",
  "threshold": "numeric threshold value if present, or null",
  "target": "target device/node/location identifier if present, or null"
}

Be precise. Pick the SINGLE most relevant domain. Describe the action concisely.
Do not explain. Return only the JSON object."""


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_response(response: dict, truth: dict) -> dict:
    """Score a model response against ground truth. Returns per-dimension scores."""
    scores = {}

    # Domain match (exact or substring)
    resp_domain = (response.get("domain") or "").lower()
    truth_domain = truth["domain"].lower()
    scores["domain"] = 1 if (truth_domain in resp_domain or resp_domain in truth_domain) else 0

    # Action match (keyword overlap)
    resp_action = (response.get("action") or "").lower()
    truth_action = truth["action"].lower()
    truth_keywords = {w for w in truth_action.split() if len(w) > 3}
    if truth_keywords:
        matched = sum(1 for kw in truth_keywords if kw in resp_action)
        scores["action"] = 1 if matched >= len(truth_keywords) * 0.4 else 0
    else:
        scores["action"] = 1

    # Threshold match
    if truth.get("threshold"):
        resp_threshold = str(response.get("threshold") or "")
        scores["threshold"] = 1 if truth["threshold"] in resp_threshold else 0
    else:
        scores["threshold"] = 1  # no threshold expected, auto-pass

    # Target match
    if truth.get("has_target"):
        resp_target = str(response.get("target") or "").upper()
        hint = truth.get("target_hint", "").upper()
        scores["target"] = 1 if (hint and hint in resp_target) else 0
    else:
        scores["target"] = 1  # no target expected, auto-pass

    return scores


def parse_json_response(text: str) -> dict:
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
    return {}


# ── Test Runner ──────────────────────────────────────────────────────────────

def run_test(call_model, model_name: str):
    """Run the three-path roundtrip test."""
    vectors_path = REPO_ROOT / "tests" / "composition-fidelity-test-v1.json"
    with open(vectors_path) as f:
        data = json.load(f)

    composer = SALComposer()
    decoder = SALDecoder()

    # Filter: only FULL_OSMP vectors where composition succeeds AND we have ground truth
    test_vectors = []
    for v in data["vectors"]:
        if v["id"] not in VECTOR_QUESTIONS:
            continue
        if v["expected_mode"] not in ("FULL_OSMP", "FULL_OSMP_OMEGA"):
            continue
        sal = composer.compose(v["natural_language"])
        if sal is None:
            continue
        test_vectors.append((v, sal))

    print(f"\n{'='*78}")
    print(f"LAYER 3 SEMANTIC ROUNDTRIP v2 — {model_name}")
    print(f"{'='*78}")
    print(f"Vectors: {len(test_vectors)} (FULL_OSMP, composition succeeded)")
    print(f"Path A: Raw NL -> model extracts intent")
    print(f"Path B: NL -> SAL -> decode NL -> model extracts intent (bridge)")
    print(f"Path C: NL -> SAL -> model reads SAL directly (native)")
    print(f"{'='*78}\n")

    results = []

    for v, sal in test_vectors:
        vid = v["id"]
        nl = v["natural_language"]
        truth = VECTOR_QUESTIONS[vid]
        decoded_nl = decoder.decode_natural_language(sal)

        row = {"id": vid, "nl": nl, "sal": sal, "decoded_nl": decoded_nl}

        # ── Path A: Raw NL ───────────────────────────────────────────
        try:
            raw_a = call_model(f"Extract the intent:\n\n{nl}", SYSTEM_PROMPT)
            resp_a = parse_json_response(raw_a)
            row["path_a"] = score_response(resp_a, truth)
            row["path_a_raw"] = resp_a
        except Exception as e:
            row["path_a"] = {"domain": 0, "action": 0, "threshold": 0, "target": 0}
            row["path_a_error"] = str(e)[:80]

        time.sleep(0.3)

        # ── Path B: Decoded NL (bridge) ──────────────────────────────
        try:
            raw_b = call_model(
                f"Extract the intent from this decoded protocol message:\n\n{decoded_nl}",
                SYSTEM_PROMPT,
            )
            resp_b = parse_json_response(raw_b)
            row["path_b"] = score_response(resp_b, truth)
            row["path_b_raw"] = resp_b
        except Exception as e:
            row["path_b"] = {"domain": 0, "action": 0, "threshold": 0, "target": 0}
            row["path_b_error"] = str(e)[:80]

        time.sleep(0.3)

        # ── Path C: Raw SAL (native) ─────────────────────────────────
        try:
            raw_c = call_model(
                f"Extract the intent from this SAL protocol instruction:\n\n{sal}",
                SYSTEM_PROMPT,
            )
            resp_c = parse_json_response(raw_c)
            row["path_c"] = score_response(resp_c, truth)
            row["path_c_raw"] = resp_c
        except Exception as e:
            row["path_c"] = {"domain": 0, "action": 0, "threshold": 0, "target": 0}
            row["path_c_error"] = str(e)[:80]

        time.sleep(0.3)

        # ── Print row ────────────────────────────────────────────────
        sa = sum(row["path_a"].values())
        sb = sum(row["path_b"].values())
        sc = sum(row["path_c"].values())
        winner = "A" if sa > sb and sa > sc else "B" if sb > sa and sb > sc else "C" if sc > sa and sc > sb else "="
        print(f"  {vid}  A:{sa}/4  B:{sb}/4  C:{sc}/4  [{winner}]  {nl[:45]}")

        results.append(row)

    # ── Summary ──────────────────────────────────────────────────────
    n = len(results)
    if n == 0:
        print("No vectors to test.")
        return results

    dims = ["domain", "action", "threshold", "target"]

    print(f"\n{'='*78}")
    print(f"RESULTS — {model_name}  ({n} vectors)")
    print(f"{'='*78}")

    totals = {}
    for path in ["path_a", "path_b", "path_c"]:
        totals[path] = {d: sum(r[path][d] for r in results) for d in dims}
        totals[path]["total"] = sum(totals[path][d] for d in dims)

    path_labels = {"path_a": "Raw NL", "path_b": "Bridge (decoded NL)", "path_c": "Native SAL"}
    max_pts = n * 4

    for path in ["path_a", "path_b", "path_c"]:
        pct = totals[path]["total"] / max_pts * 100
        print(f"  {path_labels[path]:25s}  {totals[path]['total']}/{max_pts}  ({pct:.1f}%)")

    print()
    print(f"  {'Dimension':<14s}  {'Raw NL':>8s}  {'Bridge':>8s}  {'Native':>8s}")
    print(f"  {'-'*14}  {'-'*8}  {'-'*8}  {'-'*8}")
    for d in dims:
        va = totals["path_a"][d]
        vb = totals["path_b"][d]
        vc = totals["path_c"][d]
        best = max(va, vb, vc)
        def fmt(v):
            return f"{'*' if v == best and v > 0 else ' '}{v}/{n}"
        print(f"  {d:<14s}  {fmt(va):>8s}  {fmt(vb):>8s}  {fmt(vc):>8s}")

    # Delta
    a_pct = totals["path_a"]["total"] / max_pts * 100
    b_pct = totals["path_b"]["total"] / max_pts * 100
    c_pct = totals["path_c"]["total"] / max_pts * 100
    best_path = "A (Raw NL)" if a_pct >= b_pct and a_pct >= c_pct else \
                "B (Bridge)" if b_pct >= a_pct and b_pct >= c_pct else "C (Native SAL)"
    print(f"\n  Best path: {best_path}")
    print(f"  B vs A delta: {b_pct - a_pct:+.1f}pp  (bridge value-add over raw NL)")
    print(f"  C vs A delta: {c_pct - a_pct:+.1f}pp  (native SAL value-add over raw NL)")
    print(f"{'='*78}\n")

    return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Layer 3 Semantic Roundtrip v2")
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--anthropic-model", default="claude-haiku-4-5-20251001")
    args = parser.parse_args()

    all_results = {}

    if args.anthropic_key:
        def call_claude(prompt, system):
            return call_anthropic(prompt, system, args.anthropic_key, args.anthropic_model)
        all_results["claude"] = run_test(call_claude, f"Claude ({args.anthropic_model})")

    if args.openai_key:
        def call_gpt(prompt, system):
            return call_openai(prompt, system, args.openai_key, args.openai_model)
        all_results["openai"] = run_test(call_gpt, f"OpenAI ({args.openai_model})")

    if not all_results:
        print("ERROR: No API keys. Use --anthropic-key and/or --openai-key.")
        return 1

    # Write report
    report_path = REPO_ROOT / "tests" / "layer3-roundtrip-results.json"
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
