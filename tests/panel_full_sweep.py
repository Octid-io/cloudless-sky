#!/usr/bin/env python3
"""
Full Dictionary Sweep — All 350 opcodes, 3 composition paths.

For each opcode in ASD_BASIS:
  1. Generate an NL prompt from the definition
  2. Path A: Deterministic (osmp_compose tool)
  3. Path B: LLM direct (model writes SAL with doctrine)
  4. Path C: Combined (tool first, LLM fallback if tool returns NONE)

Output: per-opcode coverage map showing which paths resolve each opcode.

Usage:
  python tests/panel_full_sweep.py --anthropic-key KEY --openai-key KEY [--gemini-key KEY]
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
        "model": model, "temperature": 0, "max_tokens": 200,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()


def call_anthropic(prompt: str, system: str, api_key: str, model: str = "claude-haiku-4-5-20251001") -> str:
    import urllib.request
    body = json.dumps({
        "model": model, "max_tokens": 200, "system": system,
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
        "generationConfig": {"temperature": 0, "maxOutputTokens": 200},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── Doctrine ─────────────────────────────────────────────────────────────────

def build_doctrine() -> str:
    asd = AdaptiveSharedDictionary()
    ns_lines = []
    for ns, ops in sorted(asd._data.items()):
        entries = [f"{op}={defn.replace('_',' ')}" for op, defn in sorted(ops.items())]
        ns_lines.append(f"  {ns}: {', '.join(entries)}")
    listing = "\n".join(ns_lines)
    count = sum(len(ops) for ops in asd._data.values())
    return f"""SAL encodes agent instructions. GRAMMAR: NS:OPCODE[@TARGET][OPERATOR ...]
OPERATORS: → THEN  ∧ AND  ; SEQUENCE
R namespace needs consequence class (⚠↺⊘) except ESTOP. ⚠/⊘ need I:§→.
If no opcode matches: NL_PASSTHROUGH. If SAL >= NL bytes: NL_PASSTHROUGH.
{count} opcodes:
{listing}

Compose SAL. Respond ONLY: the SAL string, or NL_PASSTHROUGH. No explanation."""


# ── NL Prompt Generation ─────────────────────────────────────────────────────

def generate_nl_prompt(ns: str, op: str, defn: str) -> str:
    """Generate a natural language instruction that should resolve to this opcode."""
    readable = defn.replace("_", " ")
    # Context-appropriate framing by namespace
    frames = {
        "H": f"The patient needs a {readable} check.",
        "E": f"Read the {readable} from the sensor.",
        "W": f"What is the current {readable}?",
        "R": f"Command the robot to perform {readable}.",
        "S": f"Perform {readable} on the payload.",
        "D": f"Execute a {readable} operation.",
        "K": f"Process the {readable} transaction.",
        "M": f"Issue a {readable} for the area.",
        "B": f"Check the {readable} in the building.",
        "J": f"The agent should {readable}.",
        "Z": f"Configure {readable} for the model.",
        "U": f"Send {readable} to the operator.",
        "I": f"Perform {readable} verification.",
        "G": f"Query the {readable} data.",
        "T": f"Set up the {readable}.",
        "L": f"Record a {readable}.",
        "X": f"Report the {readable} status.",
        "N": f"Query the {readable} of the network node.",
        "O": f"Set the {readable} for this operation.",
        "P": f"Execute {readable} procedure.",
        "Q": f"Perform {readable} on the output.",
        "V": f"Report the {readable} for the vessel.",
        "Y": f"Execute {readable} in the memory system.",
        "A": f"Send {readable} to the protocol layer.",
    }
    return frames.get(ns, f"Execute {readable}.")


def parse_sal(text: str) -> str | None:
    text = text.strip()
    if "NL_PASSTHROUGH" in text.upper() or text.upper().startswith("NONE"):
        return None
    for line in text.split("\n"):
        line = line.strip()
        if re.match(r'^[A-Z\u03a9]:[\w\u00a7]', line):
            return line
    m = re.search(r'\[SAL:\s*(.+?)\]', text)
    if m:
        return m.group(1).strip()
    return None


def check_opcode_in_sal(sal: str, ns: str, op: str) -> bool:
    """Check if the expected NS:OP appears in the composed SAL."""
    if not sal:
        return False
    pattern = rf'\b{re.escape(ns)}:{re.escape(op)}\b'
    return bool(re.search(pattern, sal))


# ── Sweep ────────────────────────────────────────────────────────────────────

def run_sweep(models: dict[str, callable]):
    composer = SALComposer()
    doctrine = build_doctrine()

    # Build opcode list
    opcodes = []
    for ns, ops in sorted(ASD_BASIS.items()):
        for op, defn in sorted(ops.items()):
            opcodes.append((ns, op, defn))

    print(f"\n{'='*78}")
    print(f"cross-model panel FULL DICTIONARY SWEEP — {len(opcodes)} opcodes, 3 paths")
    print(f"{'='*78}")
    print(f"Models: {', '.join(models.keys())}")
    print(f"Path A: Deterministic (osmp_compose)")
    print(f"Path B: LLM direct (best model writes SAL)")
    print(f"Path C: Combined (tool first, LLM fallback)")
    print(f"{'='*78}\n")

    results = []
    a_hits = 0
    b_hits = 0
    c_hits = 0

    for i, (ns, op, defn) in enumerate(opcodes):
        nl = generate_nl_prompt(ns, op, defn)

        # Path A: Deterministic
        tool_sal = composer.compose(nl)
        a_ok = check_opcode_in_sal(tool_sal, ns, op)
        if a_ok:
            a_hits += 1

        # Path B: LLM direct (try each model, take first success)
        llm_sal = None
        llm_model = None
        for model_name, call_fn in models.items():
            try:
                raw = call_fn(f"Compose SAL:\n{nl}", doctrine)
                candidate = parse_sal(raw)
                if candidate and check_opcode_in_sal(candidate, ns, op):
                    llm_sal = candidate
                    llm_model = model_name
                    break
                elif candidate and llm_sal is None:
                    llm_sal = candidate  # keep first attempt even if wrong
                    llm_model = model_name
            except Exception:
                pass
            time.sleep(0.2)

        b_ok = check_opcode_in_sal(llm_sal, ns, op)
        if b_ok:
            b_hits += 1

        # Path C: Combined (tool first, LLM fallback)
        c_ok = a_ok or b_ok
        if c_ok:
            c_hits += 1

        row = {
            "ns": ns, "op": op, "defn": defn, "nl": nl,
            "tool_sal": tool_sal, "tool_hit": a_ok,
            "llm_sal": llm_sal, "llm_model": llm_model, "llm_hit": b_ok,
            "combined_hit": c_ok,
        }
        results.append(row)

        # Print progress
        icon = "+" if c_ok else ("A" if a_ok else ("B" if b_ok else "X"))
        print(f"  [{icon}] {ns}:{op:8s}  A:{'Y' if a_ok else 'N'}  B:{'Y' if b_ok else 'N'}  C:{'Y' if c_ok else 'N'}  {defn[:35]}")

        if (i + 1) % 50 == 0:
            print(f"  ... {i+1}/{len(opcodes)} ({a_hits}A/{b_hits}B/{c_hits}C) ...")

    # ── Summary ──────────────────────────────────────────────────────
    n = len(opcodes)
    print(f"\n{'='*78}")
    print(f"FULL SWEEP RESULTS — {n} opcodes")
    print(f"{'='*78}")
    print(f"  Path A (Deterministic tool):  {a_hits}/{n} ({a_hits/n*100:.1f}%)")
    print(f"  Path B (LLM direct):          {b_hits}/{n} ({b_hits/n*100:.1f}%)")
    print(f"  Path C (Combined):            {c_hits}/{n} ({c_hits/n*100:.1f}%)")
    print(f"  LLM adds over tool:           {c_hits - a_hits} opcodes")
    print(f"  Tool-only (LLM missed):       {a_hits - (c_hits - (c_hits - a_hits))} opcodes")

    # Gap analysis — opcodes neither path covers
    gaps = [r for r in results if not r["combined_hit"]]
    if gaps:
        print(f"\n  GAPS ({len(gaps)} opcodes not covered by any path):")
        for r in gaps[:20]:
            print(f"    {r['ns']}:{r['op']:8s}  {r['defn'][:40]}")
        if len(gaps) > 20:
            print(f"    ... and {len(gaps)-20} more")

    # LLM-only hits (tool missed, model caught)
    llm_only = [r for r in results if r["llm_hit"] and not r["tool_hit"]]
    if llm_only:
        print(f"\n  LLM-ONLY ({len(llm_only)} — model caught, tool missed):")
        for r in llm_only[:20]:
            print(f"    {r['ns']}:{r['op']:8s}  model={r['llm_model']}  sal={r['llm_sal'][:40] if r['llm_sal'] else 'None'}")

    print(f"{'='*78}\n")

    # Write report
    report_path = REPO_ROOT / "tests" / "panel-full-sweep-results.json"
    with open(report_path, "w") as f:
        json.dump({
            "total_opcodes": n,
            "tool_hits": a_hits, "tool_pct": round(a_hits/n*100, 1),
            "llm_hits": b_hits, "llm_pct": round(b_hits/n*100, 1),
            "combined_hits": c_hits, "combined_pct": round(c_hits/n*100, 1),
            "gaps": len(gaps),
            "llm_only_count": len(llm_only),
            "per_opcode": results,
        }, f, indent=2, ensure_ascii=False, default=str)
    print(f"Report: {report_path}")
    return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Full Dictionary Sweep")
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"))
    args = parser.parse_args()

    models = {}
    if args.anthropic_key:
        models["claude-haiku"] = lambda p, s, k=args.anthropic_key: call_anthropic(p, s, k, "claude-haiku-4-5-20251001")
    if args.openai_key:
        models["gpt-4o-mini"] = lambda p, s, k=args.openai_key: call_openai(p, s, k, "gpt-4o-mini")
    if args.gemini_key:
        models["gemini-flash"] = lambda p, s, k=args.gemini_key: call_gemini(p, s, k, "gemini-2.0-flash")

    if not models:
        print("ERROR: Need at least 1 API key.")
        return 1

    run_sweep(models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
