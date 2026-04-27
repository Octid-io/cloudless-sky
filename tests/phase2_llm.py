#!/usr/bin/env python3
"""
Phase 2 — LLM baseline matrix.

For each chip in the corpus, run through 4 conditions:

  A. RAW_RECEPTIVE   — show SAL string (no doctrine), ask "what action does this do?"
                       (measures whether SAL is self-evident as a language)
  B. COLD_DOCTRINE   — system prompt with grammar + ASD listing, single-shot compose
                       (the panel-discovery surface — known to cause refusal)
  C. DOCTRINE_FEWSHOT — system prompt + 10 vetted (NL,SAL) examples, single-shot compose
                       (priming with examples — "pangram-handshake" scaled down)
  D. TOOL_CASCADE    — system prompt + tool definitions for osmp_compose,
                       osmp_lookup, osmp_validate, osmp_emit, osmp_passthrough.
                       Multi-turn until tool_use stops. (mimics MCP cascade)

Models: claude-haiku-4-5, gpt-4o-mini.

Scoring uses the same verdict buckets as Phase 1:
  CORRECT, SAFE_PASSTHROUGH, REFUSED, INVALID, WRONG.

Output: tests/results/phase2-llm-{condition}-{model}.json + an aggregate
phase2-summary.json with per-condition × per-model stats.

Usage:
  python tests/phase2_llm.py --conditions A B C D --models haiku gpt
  python tests/phase2_llm.py --conditions B --models haiku  # quick run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import (
    SALComposer, validate_composition, AdaptiveSharedDictionary,
)

CORPUS_PATH = REPO_ROOT / "tests" / "input-classes" / "corpus.json"
RESULTS_DIR = REPO_ROOT / "tests" / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Load .env for API keys (direct assign — overrides empty env vars)
ENV_PATH = REPO_ROOT / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            if v:  # only set non-empty values
                os.environ[k] = v

# Pricing for cost estimation (Apr 2026, per 1M tokens)
PRICING = {
    "claude-haiku-4-5": {"in": 0.80, "out": 4.00},
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
}

OPCODE_RE = re.compile(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)')


# ─────────────────────────────────────────────────────────────────────────────
# CONDITION A — Raw SAL receptive (show SAL, ask meaning)
# ─────────────────────────────────────────────────────────────────────────────

RAW_RECEPTIVE_PROMPT = """Look at this string: {sal}

Without using any external knowledge or context, what action would a system take if it received this string?

Respond with ONE SHORT SENTENCE describing the action, OR "UNKNOWN" if you cannot determine."""


# ─────────────────────────────────────────────────────────────────────────────
# CONDITION B — Cold doctrine + ASD listing (panel-discovery prompt)
# ─────────────────────────────────────────────────────────────────────────────

def build_cold_doctrine() -> str:
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
- K:ORD = financial order, NOT food. A:SUM = summarize, NOT arithmetic.
- If SAL bytes >= NL bytes: NL_PASSTHROUGH

{opcode_count} opcodes:
{listing}

Compose SAL for the instruction. If no opcodes match, respond: NL_PASSTHROUGH
Respond with ONLY the SAL string on the first line. No explanation."""


# ─────────────────────────────────────────────────────────────────────────────
# CONDITION C — Doctrine + few-shot examples (priming)
# ─────────────────────────────────────────────────────────────────────────────

FEWSHOT_EXAMPLES = [
    ("report temperature", "E:TH"),
    ("report heading", "G:BEARING"),
    ("emergency stop", "R:ESTOP"),
    ("update config", "N:CFG"),
    ("blood pressure check", "H:BP"),
    ("fire alarm in building B", "B:ALRM@B"),
    ("alert when humidity above 80", "E:HU>80\u2192L:ALERT"),
    ("encrypt then send to BRAVO", "S:ENC;D:PUSH@BRAVO"),
    ("ping node 17", "A:PING@17"),
    ("tell me a joke", "NL_PASSTHROUGH"),
]


def build_fewshot_doctrine() -> str:
    cold = build_cold_doctrine()
    examples = "\n".join(f'NL: "{nl}"\nSAL: {sal}\n' for nl, sal in FEWSHOT_EXAMPLES)
    return cold + "\n\nEXAMPLES:\n\n" + examples + "\n\nNow compose SAL for the next instruction."


# ─────────────────────────────────────────────────────────────────────────────
# CONDITION D — Tool cascade (mimics MCP)
# ─────────────────────────────────────────────────────────────────────────────

CASCADE_SYSTEM = """You compose SAL (Semantic Assembly Language) for OSMP, a deterministic agentic instruction protocol.

Your tools:
- osmp_compose(text): Run the deterministic SDK composer. Returns SAL or null.
- osmp_lookup(keyword OR namespace): Search the ASD. Returns matching opcodes.
- osmp_validate(sal): Validate composed SAL. Returns {valid, issues}.
- osmp_emit(sal): Final SAL output. Cascade ends.
- osmp_passthrough(reason): Final NL passthrough with reason. Cascade ends.

GRAMMAR: [NS:]OPCODE[@TARGET][OPERATOR INSTRUCTION]
OPERATORS: \u2192 THEN, \u2227 AND, ; SEQUENCE
R namespace requires consequence glyph (\u26a0, \u21bb, \u2298) except R:ESTOP.

PROTOCOL: Try osmp_compose FIRST. If null, decompose intent with osmp_lookup, then osmp_emit. If no opcode covers the action, osmp_passthrough.

ITERATION BUDGET: 5 turns. Use efficiently."""

CASCADE_TOOLS = [
    {
        "name": "osmp_compose",
        "description": "Run the deterministic SDK composer on natural-language input. Returns SAL or null.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "osmp_lookup",
        "description": "Search the ASD by namespace letter and/or keyword.",
        "input_schema": {"type": "object", "properties": {
            "namespace": {"type": "string", "description": "Single uppercase letter A-Z (optional)"},
            "keyword": {"type": "string", "description": "Search term (optional)"},
        }, "required": []},
    },
    {
        "name": "osmp_validate",
        "description": "Validate composed SAL against grammar and doctrine rules.",
        "input_schema": {"type": "object", "properties": {"sal": {"type": "string"}}, "required": ["sal"]},
    },
    {
        "name": "osmp_emit",
        "description": "Emit the final SAL output. Terminates the cascade.",
        "input_schema": {"type": "object", "properties": {"sal": {"type": "string"}}, "required": ["sal"]},
    },
    {
        "name": "osmp_passthrough",
        "description": "Final NL passthrough with brief explanation. Terminates the cascade.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# API CLIENTS (anthropic + openai with retry/backoff)
# ─────────────────────────────────────────────────────────────────────────────

def call_anthropic(system: str, messages: list, model: str = "claude-haiku-4-5",
                   tools: list | None = None, max_tokens: int = 400) -> dict:
    body = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(2 ** attempt * 5)
                continue
            raise


def call_openai(system: str, user: str, model: str = "gpt-4o-mini",
                tools: list | None = None, max_tokens: int = 400) -> dict:
    body = {
        "model": model, "max_tokens": max_tokens, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    # Note: tools converted to OpenAI function-call format if present
    if tools:
        body["tools"] = [{"type": "function", "function": t} for t in tools]
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(2 ** attempt * 5)
                continue
            raise


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE EXTRACTION + SCORING
# ─────────────────────────────────────────────────────────────────────────────

def extract_anthropic_text(response: dict) -> str:
    """Extract first text block from Anthropic response."""
    content = response.get("content", [])
    for block in content:
        if block.get("type") == "text":
            return block.get("text", "")
    return ""


def extract_openai_text(response: dict) -> str:
    return response["choices"][0]["message"].get("content", "") or ""


def parse_sal_from_response(text: str) -> str | None:
    """Extract a SAL string from a model response. Returns None if PASSTHROUGH or unparseable."""
    text = text.strip()
    if not text:
        return None
    # First non-empty line
    first_line = text.splitlines()[0].strip()
    if not first_line:
        return None
    # Detect explicit passthrough marker
    if first_line.upper() in ("NL_PASSTHROUGH", "NL", "PASSTHROUGH", "NONE", "UNKNOWN"):
        return None
    if "NL_PASSTHROUGH" in first_line.upper():
        return None
    # Otherwise treat as SAL
    return first_line


def opcodes_in(sal: str | None) -> set[tuple[str, str]]:
    if not sal:
        return set()
    return set(OPCODE_RE.findall(sal))


def equivalent_sal(emitted: str, expected_list: list[str]) -> bool:
    if not emitted:
        return False
    if emitted in expected_list:
        return True
    emitted_ops = opcodes_in(emitted)
    if not emitted_ops:
        return False
    for exp in expected_list:
        if emitted_ops == opcodes_in(exp):
            return True
    return False


def classify(emitted_sal: str | None, expected_sal: list[str],
             expected_verdict: str | None, nl: str, refused: bool = False) -> str:
    if refused:
        return "REFUSED"
    if expected_verdict == "SAFE_PASSTHROUGH":
        return "SAFE_PASSTHROUGH" if emitted_sal is None else "WRONG"
    if expected_verdict == "REFUSED_MALFORMED":
        return "REFUSED_MALFORMED" if emitted_sal is None else "WRONG"
    if emitted_sal is None:
        return "SAFE_PASSTHROUGH"
    val = validate_composition(emitted_sal, nl=nl)
    if not val.valid:
        return "INVALID"
    return "CORRECT" if equivalent_sal(emitted_sal, expected_sal) else "WRONG"


# ─────────────────────────────────────────────────────────────────────────────
# CONDITION RUNNERS
# ─────────────────────────────────────────────────────────────────────────────

def run_cond_A(model: str, sal_strings: list[str]) -> list[dict]:
    """Raw receptive: show SAL, ask meaning. Doesn't use chip corpus directly —
    uses the EXPECTED SAL strings from in-scope chips."""
    results = []
    for sal in sal_strings:
        if not sal:
            continue
        prompt = RAW_RECEPTIVE_PROMPT.format(sal=sal)
        try:
            if model == "haiku":
                resp = call_anthropic("", [{"role": "user", "content": prompt}], "claude-haiku-4-5")
                text = extract_anthropic_text(resp)
                usage = resp.get("usage", {})
            else:
                resp = call_openai("", prompt, "gpt-4o-mini")
                text = extract_openai_text(resp)
                usage = resp.get("usage", {})
            results.append({"sal": sal, "response": text[:300], "usage": usage})
        except Exception as e:
            results.append({"sal": sal, "response": f"ERR:{e}", "usage": {}})
        time.sleep(0.1)  # gentle rate limit
    return results


def run_cond_B_or_C(model: str, system_prompt: str, inputs: list[dict],
                    cond_label: str) -> list[dict]:
    results = []
    for chip in inputs:
        nl = chip["nl"]
        try:
            if model == "haiku":
                resp = call_anthropic(system_prompt, [{"role": "user", "content": nl}], "claude-haiku-4-5")
                text = extract_anthropic_text(resp)
                usage = resp.get("usage", {})
            else:
                resp = call_openai(system_prompt, nl, "gpt-4o-mini")
                text = extract_openai_text(resp)
                usage = resp.get("usage", {})
            sal = parse_sal_from_response(text)
            refused = (text.strip() == "")
            verdict = classify(sal, chip.get("expected_sal", []),
                               chip.get("expected_verdict"), nl, refused)
        except Exception as e:
            text = f"ERR:{e}"
            sal = None
            verdict = "INVALID"
            usage = {}
        results.append({
            "id": chip["id"], "domain": chip["domain"], "nl": nl,
            "expected": chip.get("expected_sal", []),
            "expected_verdict": chip.get("expected_verdict"),
            "got": sal, "raw_response": text[:200],
            "verdict": verdict, "usage": usage,
        })
        time.sleep(0.1)
    return results


def run_cond_D(model: str, inputs: list[dict]) -> list[dict]:
    """Tool cascade — multi-turn with osmp_compose, osmp_lookup, etc.

    Anthropic supports tools natively. OpenAI uses function-calling.
    For brevity, this implementation only runs Anthropic; OpenAI tool support
    requires a different message protocol.
    """
    if model != "haiku":
        return [{"id": chip["id"], "skipped": "OpenAI tool format different — only haiku for cascade", "verdict": "SKIPPED"} for chip in inputs]

    composer = SALComposer()
    results = []

    for chip in inputs:
        nl = chip["nl"]
        messages = [{"role": "user", "content": f"Compose SAL for: {nl}"}]
        verdict = "REFUSED"
        emitted_sal = None
        turns = 0
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        for turn in range(5):
            try:
                resp = call_anthropic(CASCADE_SYSTEM, messages, "claude-haiku-4-5",
                                       tools=CASCADE_TOOLS, max_tokens=600)
            except Exception as e:
                emitted_sal = None
                verdict = "INVALID"
                break

            turns += 1
            usage = resp.get("usage", {})
            total_usage["input_tokens"] += usage.get("input_tokens", 0)
            total_usage["output_tokens"] += usage.get("output_tokens", 0)

            content = resp.get("content", [])
            stop_reason = resp.get("stop_reason")

            # Look for tool_use blocks
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            text_blocks = [b.get("text", "") for b in content if b.get("type") == "text"]

            if not tool_uses:
                # No tool — attempt to parse SAL from text
                emitted_sal = parse_sal_from_response("\n".join(text_blocks))
                if emitted_sal:
                    verdict = classify(emitted_sal, chip.get("expected_sal", []),
                                       chip.get("expected_verdict"), nl)
                else:
                    verdict = classify(None, chip.get("expected_sal", []),
                                       chip.get("expected_verdict"), nl)
                break

            # Process the first tool_use
            tu = tool_uses[0]
            tool_name = tu.get("name")
            tool_input = tu.get("input", {})

            tool_result = ""
            if tool_name == "osmp_compose":
                r = composer.compose(tool_input.get("text", ""))
                tool_result = json.dumps({"sal": r})
            elif tool_name == "osmp_lookup":
                hits = []
                if tool_input.get("keyword"):
                    hits = composer.lookup_by_keyword(tool_input["keyword"])[:5]
                if tool_input.get("namespace"):
                    ns = tool_input["namespace"]
                    asd_lookup = composer.asd._data.get(ns, {})
                    hits.extend([(ns, op, defn) for op, defn in list(asd_lookup.items())[:10]])
                tool_result = json.dumps({"matches": [{"ns": ns, "op": op, "defn": defn} for ns, op, defn in hits[:8]]})
            elif tool_name == "osmp_validate":
                v = validate_composition(tool_input.get("sal", ""), nl=nl)
                tool_result = json.dumps({"valid": v.valid, "issues": [i.message for i in v.issues]})
            elif tool_name == "osmp_emit":
                emitted_sal = tool_input.get("sal")
                verdict = classify(emitted_sal, chip.get("expected_sal", []),
                                   chip.get("expected_verdict"), nl)
                break
            elif tool_name == "osmp_passthrough":
                emitted_sal = None
                verdict = classify(None, chip.get("expected_sal", []),
                                   chip.get("expected_verdict"), nl)
                break
            else:
                tool_result = json.dumps({"error": f"unknown tool {tool_name}"})

            # Append assistant + tool_result for next turn
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": tu.get("id"),
                "content": tool_result,
            }]})
        else:
            # Iter budget exhausted
            verdict = "REFUSED"

        results.append({
            "id": chip["id"], "domain": chip["domain"], "nl": nl,
            "expected": chip.get("expected_sal", []),
            "expected_verdict": chip.get("expected_verdict"),
            "got": emitted_sal, "verdict": verdict,
            "turns": turns, "usage": total_usage,
        })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def estimate_cost(usage_list: list[dict], model_name: str) -> float:
    rate = PRICING.get(model_name, {"in": 1.0, "out": 5.0})
    total_in = sum(u.get("input_tokens", u.get("prompt_tokens", 0)) for u in usage_list)
    total_out = sum(u.get("output_tokens", u.get("completion_tokens", 0)) for u in usage_list)
    return (total_in * rate["in"] + total_out * rate["out"]) / 1_000_000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conditions", nargs="+", default=["A", "B", "C", "D"],
                        choices=["A", "B", "C", "D"])
    parser.add_argument("--models", nargs="+", default=["haiku", "gpt"],
                        choices=["haiku", "gpt"])
    args = parser.parse_args()

    with open(CORPUS_PATH, encoding="utf-8") as f:
        corpus = json.load(f)
    inputs = corpus["inputs"]

    summary = {"conditions": {}}
    total_cost = 0.0

    for cond in args.conditions:
        for model in args.models:
            label = f"{cond}-{model}"
            print(f"\n=== Running condition {cond} on {model} ===")

            if cond == "A":
                # Raw receptive — pull a sample of expected SALs
                sals = []
                for chip in inputs:
                    if chip.get("expected_sal"):
                        sals.append(chip["expected_sal"][0])
                results = run_cond_A(model, sals[:30])  # cap at 30 to limit cost
            elif cond == "B":
                results = run_cond_B_or_C(model, build_cold_doctrine(), inputs, label)
            elif cond == "C":
                results = run_cond_B_or_C(model, build_fewshot_doctrine(), inputs, label)
            elif cond == "D":
                results = run_cond_D(model, inputs)
            else:
                continue

            # Aggregate
            verdicts = Counter(r.get("verdict", "UNKNOWN") for r in results)
            usages = [r.get("usage", {}) for r in results]
            mname = "claude-haiku-4-5" if model == "haiku" else "gpt-4o-mini"
            cost = estimate_cost(usages, mname)
            total_cost += cost

            print(f"  results: {len(results)} measurements")
            print(f"  verdicts: {dict(verdicts)}")
            print(f"  cost: ${cost:.4f}")

            out_path = RESULTS_DIR / f"phase2-{label}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({
                    "condition": cond, "model": model,
                    "verdicts": dict(verdicts),
                    "cost_usd": round(cost, 4),
                    "results": results,
                }, f, indent=2, ensure_ascii=False)
            summary["conditions"][label] = {
                "verdicts": dict(verdicts),
                "cost_usd": round(cost, 4),
                "n": len(results),
            }

    summary["total_cost_usd"] = round(total_cost, 4)
    with open(RESULTS_DIR / "phase2-summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== TOTAL COST: ${total_cost:.4f} ===")
    print(f"Summary: {RESULTS_DIR}/phase2-summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
