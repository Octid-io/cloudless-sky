#!/usr/bin/env python3
"""
Brigade vs MCP cascade — head-to-head measurement.

Runs the same corpus through:
  A. Brigade (deterministic, no LLM) — direct compose
  B. MCP cascade (Haiku + brigade tools as MCP-style functions)
     — each station + the brigade orchestrator exposed as tools to the LLM
  C. MCP cascade with single coarse osmp_compose tool (legacy MCP shape)

Compares CORRECT / WRONG / INVALID rates + cost/latency.
This validates whether fine-grained tools beat coarse compose tool.
"""
from __future__ import annotations

import argparse
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

from osmp.brigade import Orchestrator, parse
from osmp.brigade.stations import default_registry
from osmp.protocol import validate_composition, AdaptiveSharedDictionary

# Load .env
ENV = REPO / ".env"
if ENV.exists():
    for line in ENV.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            if v:
                os.environ[k] = v

OPCODE_RE = re.compile(r'([A-Z\u03a9]):([A-Z0-9\u00a7]+)')
RESULTS = REPO / "tests" / "results"


def opcodes_in(sal):
    return set(OPCODE_RE.findall(sal)) if sal else set()


def equivalent(emitted, expected_list):
    if not emitted:
        return False
    if emitted in expected_list:
        return True
    em = opcodes_in(emitted)
    if not em:
        return False
    return any(em == opcodes_in(e) for e in expected_list)


def classify(sal, expected, ev, nl):
    if ev == "SAFE_PASSTHROUGH":
        return "SAFE_PASSTHROUGH" if sal is None else "WRONG"
    if ev == "REFUSED_MALFORMED":
        return "REFUSED_MALFORMED" if sal is None else "WRONG"
    if sal is None:
        return "SAFE_PASSTHROUGH"
    v = validate_composition(sal, nl=nl)
    if not v.valid:
        return "INVALID"
    return "CORRECT" if equivalent(sal, expected) else "WRONG"


def run_brigade(inputs):
    """Path A: brigade direct."""
    orch = Orchestrator()
    results = []
    for chip in inputs:
        nl = chip["nl"]
        try:
            sal = orch.compose(nl)
        except Exception:
            sal = None
        verdict = classify(sal, chip.get("expected_sal", []),
                           chip.get("expected_verdict"), nl)
        results.append({"id": chip["id"], "nl": nl, "got": sal, "verdict": verdict})
    return results


def run_coarse_mcp(inputs):
    """Path C: legacy MCP cascade with one coarse osmp_compose tool only."""
    orch = Orchestrator()
    results = []
    total_cost = 0.0
    total_in = 0
    total_out = 0

    SYSTEM = """You compose SAL for OSMP. The brigade composer is reliable — TRUST IT.

MANDATORY WORKFLOW:
1. Call osmp_compose(text="<full user NL VERBATIM>"). Do not paraphrase the input.
2. The tool returns either a SAL string or null.
3. If SAL is non-null: IMMEDIATELY call osmp_emit(sal="<exact returned string>"). Do not validate first. Do not modify. Do not second-guess.
4. If SAL is null: call osmp_passthrough(reason="<brief reason>").

FORBIDDEN:
- Skipping osmp_compose
- Calling osmp_passthrough without first calling osmp_compose
- Modifying or "improving" the brigade's SAL
- Calling osmp_validate before emit (the brigade already validated)

If you get VALIDATION_FAILED feedback after emit (rare — brigade output should always validate), revise once based on the delta and re-emit. Otherwise passthrough.

EXAMPLE:
User: "Compose SAL for: stop the conveyor"
You: <call osmp_compose(text="stop the conveyor")>
Tool returns: {"sal": "R:STOP↺@CONVEYOR"}
You: <call osmp_emit(sal="R:STOP↺@CONVEYOR")>
[End cascade]

User: "Compose SAL for: tell me a joke"
You: <call osmp_compose(text="tell me a joke")>
Tool returns: {"sal": null}
You: <call osmp_passthrough(reason="conversational, no opcode coverage")>
[End cascade]

This is your ONLY job. Be mechanical."""
    TOOLS = [
        {"name": "osmp_compose", "description": "Run the deterministic brigade composer. Returns SAL or null.",
         "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
        {"name": "osmp_validate", "description": "Validate SAL is wire-grade. Returns {valid, issues}.",
         "input_schema": {"type": "object", "properties": {"sal": {"type": "string"}}, "required": ["sal"]}},
        {"name": "osmp_emit", "description": "Final SAL output. Cascade complete.",
         "input_schema": {"type": "object", "properties": {"sal": {"type": "string"}}, "required": ["sal"]}},
        {"name": "osmp_passthrough", "description": "NL passthrough with reason. Cascade complete.",
         "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
    ]

    for chip in inputs:
        nl = chip["nl"]
        messages = [{"role": "user", "content": f"Compose SAL for: {nl}"}]
        sal = None
        emit_attempts = 0
        max_emits = 2  # initial + 1 correction
        for turn in range(8):
            try:
                body = json.dumps({
                    "model": "claude-haiku-4-5", "max_tokens": 400,
                    "system": SYSTEM, "messages": messages, "tools": TOOLS,
                }).encode()
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages", data=body,
                    headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                             "anthropic-version": "2023-06-01", "content-type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read())
            except Exception as e:
                sal = None
                break

            usage = resp.get("usage", {})
            total_in += usage.get("input_tokens", 0)
            total_out += usage.get("output_tokens", 0)

            content = resp.get("content", [])
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if not tool_uses:
                break
            tu = tool_uses[0]
            name = tu.get("name")
            inp = tu.get("input", {})
            if name == "osmp_compose":
                r2 = orch.compose(inp.get("text", ""))
                tool_result = json.dumps({"sal": r2})
            elif name == "osmp_validate":
                v = validate_composition(inp.get("sal", ""), nl=nl)
                tool_result = json.dumps({"valid": v.valid,
                                           "issues": [i.message for i in v.issues]})
            elif name == "osmp_emit":
                candidate = inp.get("sal")
                # Validate before accepting emit (feedback loop)
                v = validate_composition(candidate, nl=nl)
                emit_attempts += 1
                if v.valid:
                    sal = candidate
                    break
                # Invalid emit — feed delta back if attempts remain
                if emit_attempts < max_emits:
                    delta_msg = (f"VALIDATION_FAILED for sal={candidate!r}. "
                                  f"Issues: {[i.message for i in v.issues]}. "
                                  f"Revise the SAL once and re-emit, or call passthrough.")
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": [{
                        "type": "tool_result", "tool_use_id": tu.get("id"),
                        "content": delta_msg, "is_error": True,
                    }]})
                    continue
                # Out of attempts — emit the (invalid) SAL anyway, classifier will mark it
                sal = candidate
                break
            elif name == "osmp_passthrough":
                sal = None
                break
            else:
                tool_result = json.dumps({"error": "unknown"})
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": tu.get("id"), "content": tool_result,
            }]})

        verdict = classify(sal, chip.get("expected_sal", []),
                           chip.get("expected_verdict"), nl)
        results.append({"id": chip["id"], "nl": nl, "got": sal, "verdict": verdict, "emit_attempts": emit_attempts})
        time.sleep(0.1)

    cost = (total_in * 0.80 + total_out * 4.0) / 1_000_000
    return results, cost


def run_brigade_tools_mcp(inputs):
    """Path B: MCP cascade with FINE-GRAINED brigade tools (parser + per-namespace stations + assembly).

    Each station becomes a tool. The LLM orchestrates: calls parser, sees IR,
    calls relevant stations, picks proposals, validates, emits. This is the
    'harness for all LLMs' shape.
    """
    orch = Orchestrator()
    asd = AdaptiveSharedDictionary()
    results = []
    total_in = 0
    total_out = 0

    SYSTEM = """You are an OSMP brigade composer. You have access to fine-grained tools:
- brigade_parse: parse NL → ParsedRequest IR (returns verb, dobj, targets, slots, conditions, namespace_hints, etc.)
- station_propose: ask a specific namespace station for FrameProposals given a parsed request
- assemble_frame: build a SAL frame from {namespace, opcode, target, slots, glyph}
- compose_chain: join frames with operator (∧/→/;)
- validate_sal: check if a SAL string is wire-grade
- emit / passthrough: terminate

Workflow: parse → identify relevant namespaces → ask their stations → pick best proposals → assemble → validate → emit.

Bar: never emit invalid SAL or SAL that decodes to wrong action. Passthrough is preferred to wrong."""

    TOOLS = [
        {"name": "brigade_parse",
         "description": "Parse NL into a structured request (verb, direct_object, targets, slots, conditions, namespace_hints).",
         "input_schema": {"type": "object", "properties": {"nl": {"type": "string"}}, "required": ["nl"]}},
        {"name": "station_propose",
         "description": "Get FrameProposals from a specific namespace station (A-Z + Ω). Returns list of {opcode, target, slots, glyph, confidence, rationale}.",
         "input_schema": {"type": "object", "properties": {
             "namespace": {"type": "string", "description": "Single uppercase letter."},
             "nl": {"type": "string", "description": "The NL input (re-parsed by the station)."},
         }, "required": ["namespace", "nl"]}},
        {"name": "validate_sal",
         "description": "Check SAL is wire-grade.",
         "input_schema": {"type": "object", "properties": {
             "sal": {"type": "string"}, "nl": {"type": "string"},
         }, "required": ["sal"]}},
        {"name": "emit",
         "description": "Emit final SAL. Cascade ends.",
         "input_schema": {"type": "object", "properties": {"sal": {"type": "string"}}, "required": ["sal"]}},
        {"name": "passthrough",
         "description": "Refuse to compose; reason required. Cascade ends.",
         "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
    ]

    registry = orch.registry

    for chip in inputs:
        nl = chip["nl"]
        messages = [{"role": "user", "content": f"Compose SAL for: {nl}"}]
        sal = None
        for turn in range(8):
            try:
                body = json.dumps({
                    "model": "claude-haiku-4-5", "max_tokens": 600,
                    "system": SYSTEM, "messages": messages, "tools": TOOLS,
                }).encode()
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages", data=body,
                    headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                             "anthropic-version": "2023-06-01", "content-type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read())
            except Exception:
                sal = None
                break

            usage = resp.get("usage", {})
            total_in += usage.get("input_tokens", 0)
            total_out += usage.get("output_tokens", 0)

            content = resp.get("content", [])
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if not tool_uses:
                break
            tu = tool_uses[0]
            name = tu.get("name")
            inp = tu.get("input", {})

            if name == "brigade_parse":
                pr = parse(inp.get("nl", ""))
                tool_result = json.dumps({
                    "verb": pr.verb, "verb_lemma": pr.verb_lemma,
                    "direct_object": pr.direct_object,
                    "direct_object_kind": pr.direct_object_kind,
                    "targets": [{"id": t.id, "kind": t.kind, "source": t.source} for t in pr.targets],
                    "slot_values": [{"key": s.key, "value": s.value, "type": s.value_type} for s in pr.slot_values],
                    "conditions": [{"op": c.operator, "value": c.value} for c in pr.conditions],
                    "namespace_hints": list(pr.namespace_hints),
                    "domain_hint": pr.domain_hint,
                    "is_emergency": pr.is_emergency,
                    "is_broadcast": pr.is_broadcast,
                    "is_query": pr.is_query,
                    "schedule": pr.schedule,
                    "authorization_required": pr.authorization_required,
                })
            elif name == "station_propose":
                ns = inp.get("namespace", "")
                station = registry.get(ns)
                if not station:
                    tool_result = json.dumps({"proposals": [], "error": f"no station for {ns}"})
                else:
                    pr = parse(inp.get("nl", ""))
                    props = station.propose(pr)
                    tool_result = json.dumps({"proposals": [{
                        "opcode": p.opcode, "target": p.target,
                        "slots": [{"key": s.key, "value": s.value} for s in p.slot_values],
                        "glyph": p.consequence_class, "is_query": p.is_query,
                        "confidence": p.confidence, "assembled": p.assemble(),
                        "rationale": p.rationale,
                    } for p in props]})
            elif name == "validate_sal":
                v = validate_composition(inp.get("sal", ""), nl=inp.get("nl", nl))
                tool_result = json.dumps({"valid": v.valid, "issues": [i.message for i in v.issues]})
            elif name == "emit":
                sal = inp.get("sal")
                break
            elif name == "passthrough":
                sal = None
                break
            else:
                tool_result = json.dumps({"error": f"unknown tool {name}"})

            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": tu.get("id"), "content": tool_result,
            }]})

        verdict = classify(sal, chip.get("expected_sal", []),
                           chip.get("expected_verdict"), nl)
        results.append({"id": chip["id"], "nl": nl, "got": sal, "verdict": verdict})
        time.sleep(0.1)

    cost = (total_in * 0.80 + total_out * 4.0) / 1_000_000
    return results, cost


def summarize(name, results, cost=0.0):
    n = len(results)
    bucket = Counter(r["verdict"] for r in results)
    correct = bucket.get("CORRECT", 0)
    wrong = bucket.get("WRONG", 0)
    invalid = bucket.get("INVALID", 0)
    safe = bucket.get("CORRECT", 0) + bucket.get("SAFE_PASSTHROUGH", 0) + bucket.get("REFUSED_MALFORMED", 0)
    print(f"\n{name}:")
    print(f"  CORRECT: {correct}/{n} ({100*correct/n:.1f}%)")
    print(f"  WRONG: {wrong}/{n} ({100*wrong/n:.1f}%)")
    print(f"  INVALID: {invalid}/{n} ({100*invalid/n:.1f}%)")
    print(f"  SAFE total: {safe}/{n} ({100*safe/n:.1f}%)")
    if cost > 0:
        print(f"  Cost: ${cost:.4f}")
    return {"name": name, "verdicts": dict(bucket), "cost": cost, "n": n}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="corpus.json")
    parser.add_argument("--limit", type=int, default=0, help="Limit chips for cost control (0=all)")
    parser.add_argument("--paths", nargs="+", default=["A", "B", "C"], choices=["A", "B", "C"])
    args = parser.parse_args()

    corpus = json.load(open(REPO / "tests" / "input-classes" / args.corpus, encoding="utf-8"))
    inputs = corpus["inputs"]
    if args.limit > 0:
        inputs = inputs[:args.limit]

    print(f"Running {len(inputs)} inputs from {args.corpus}")
    summary = {}
    if "A" in args.paths:
        results = run_brigade(inputs)
        summary["A_brigade"] = summarize("A. Brigade (deterministic)", results)
        with open(RESULTS / "phase2-brigade-vs-mcp-A.json", "w", encoding="utf-8") as f:
            json.dump({"name": "brigade", "results": results}, f, indent=2, ensure_ascii=False)

    if "B" in args.paths:
        print("\n... running B (LLM + fine-grained brigade tools) — slow, costs money ...")
        results, cost = run_brigade_tools_mcp(inputs)
        summary["B_llm_brigade_tools"] = summarize("B. LLM + brigade tools", results, cost)
        with open(RESULTS / "phase2-brigade-vs-mcp-B.json", "w", encoding="utf-8") as f:
            json.dump({"name": "llm_brigade_tools", "results": results, "cost": cost}, f, indent=2, ensure_ascii=False)

    if "C" in args.paths:
        print("\n... running C (LLM + coarse osmp_compose tool only) — slow, costs money ...")
        results, cost = run_coarse_mcp(inputs)
        summary["C_llm_coarse"] = summarize("C. LLM + coarse osmp_compose only", results, cost)
        with open(RESULTS / "phase2-brigade-vs-mcp-C.json", "w", encoding="utf-8") as f:
            json.dump({"name": "llm_coarse", "results": results, "cost": cost}, f, indent=2, ensure_ascii=False)

    with open(RESULTS / "phase2-brigade-vs-mcp-summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nSummary saved to tests/results/phase2-brigade-vs-mcp-summary.json")


if __name__ == "__main__":
    main()
