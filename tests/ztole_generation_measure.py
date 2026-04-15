#!/usr/bin/env python3
"""
ZTOLE 3rd Mode: Generation Measurement

Measures whether frontier models consistently resolve NL phrases to the
correct OSMP opcode. The same cross-vendor panel methodology as ZTOLE
recognition measurement, applied in the generation direction.

Input:  Candidate NL phrases with expected (namespace, opcode) mappings
Output: Per-phrase panel agreement score. Phrases with >= 3/4 panel
        agreement graduate into the generation index.

Usage:
  python tests/ztole_generation_measure.py --anthropic-key KEY --openai-key KEY [--gemini-key KEY]
  python tests/ztole_generation_measure.py --generate-candidates  # list candidates only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import ASD_BASIS, AdaptiveSharedDictionary

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
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()


def call_anthropic(prompt: str, system: str, api_key: str, model: str = "claude-haiku-4-5-20251001") -> str:
    import urllib.request
    body = json.dumps({
        "model": model, "max_tokens": 150, "system": system,
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
    # Gemini v1beta API with system instruction
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": 0, "maxOutputTokens": 100},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        # Try v1 endpoint if v1beta fails
        url2 = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
        req2 = urllib.request.Request(url2, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req2, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── ZTOLE Generation Probe ──────────────────────────────────────────────────

def build_probe_system() -> str:
    """Build probe prompt with the full ASD listing.

    This is dictionary-aware generation measurement: given the ASD,
    does the panel agree on which opcode maps to the NL phrase?
    """
    asd = AdaptiveSharedDictionary()
    ns_lines = []
    for ns, ops in sorted(asd._data.items()):
        entries = [f"{op}={defn.replace('_',' ')}" for op, defn in sorted(ops.items())]
        ns_lines.append(f"  {ns}: {', '.join(entries)}")
    listing = "\n".join(ns_lines)

    return f"""You are mapping natural language phrases to OSMP protocol opcodes.
Here is the complete OSMP dictionary:

{listing}

Given a phrase, find the BEST matching namespace:opcode from the dictionary above.
Respond with ONLY the namespace:opcode pair. Format: "NS:OPCODE" (e.g., "H:HR").
If NO opcode in the dictionary matches the phrase's core meaning, respond "NONE".
Read the DEFINITIONS, not just the mnemonics. K:ORD = financial order entry, not food.
One line only. No explanation."""


PROBE_SYSTEM: str = ""  # built at runtime


@dataclass
class ProbeResult:
    phrase: str
    expected_ns: str
    expected_op: str
    responses: dict[str, str]  # model_name -> response
    agreements: int  # how many models got the right answer
    panel_size: int


# ── Candidate Generation ────────────────────────────────────────────────────

# Tier 1: Auto-generated from ASD definitions (synonym expansion)
# Each definition generates the phrase + common English variants
SYNONYM_SEEDS: dict[str, list[str]] = {
    # Format: "NS:OP": ["synonym1", "synonym2", ...]
    # These are candidate NL phrases that SHOULD map to the given opcode
    # but are NOT in the current generation index (definition text only)

    # From composition failures (CF-003, CF-021, CF-023, CF-027)
    "S:KEYGEN": ["generate key", "generate a key pair", "key generation", "create keys", "make a keypair"],
    "S:SIGN": ["sign the payload", "digital signature", "cryptographically sign"],
    "D:PUSH": ["send data", "push data", "transmit to node", "send to node"],
    "R:ESTOP": ["emergency stop", "stop everything", "halt immediately", "e-stop"],
    "M:EVA": ["evacuate", "evacuation", "medevac", "clear the area"],
    "J:HANDOFF": ["hand off", "handoff", "transfer task", "pass the task"],
    "I:ID": ["verify identity", "identity check", "identify the patient", "authenticate"],

    # Common synonyms not in definitions
    "H:HR": ["heart rate", "heartbeat", "pulse", "cardiac rate", "bpm"],
    "H:BP": ["blood pressure", "bp reading", "systolic", "diastolic"],
    "H:TEMP": ["body temperature", "patient temperature", "fever check", "core temp"],
    "H:SPO2": ["oxygen saturation", "spo2", "pulse ox", "blood oxygen"],
    "H:CASREP": ["casualty report", "injury report", "patient report"],
    "H:ICD": ["diagnosis code", "icd code", "icd-10", "diagnostic code"],
    "E:TH": ["sensor temperature", "ambient reading", "environmental temperature", "temp and humidity"],
    "E:HU": ["humidity", "moisture level", "relative humidity"],
    "E:GPS": ["gps coordinates", "location coordinates", "gps position", "lat long"],
    "W:WIND": ["wind speed", "wind direction", "wind conditions", "wind data"],
    "W:VIS": ["visibility", "visibility report", "visual range"],
    "W:TEMP": ["weather temperature", "outside temperature", "ambient temperature"],
    "W:METAR": ["metar", "aviation weather", "airfield weather"],
    "R:MOV": ["move robot", "move to", "navigate to", "go to waypoint", "drive to"],
    "R:ZONE": ["safety zone", "exclusion zone", "keep-out area", "restricted area"],
    "S:ENC": ["encrypt", "encrypt data", "encryption", "cipher"],
    "S:DEC": ["decrypt", "decryption", "decipher"],
    "S:VFY": ["verify signature", "signature verification", "check signature"],
    "K:PAY": ["payment", "process payment", "pay", "execute payment"],
    "Z:TEMP": ["model temperature", "sampling temperature", "inference temperature"],
    "Z:INF": ["run inference", "invoke model", "generate response", "call the model"],
    "Z:TOKENS": ["token count", "token usage", "how many tokens"],
    "X:WND": ["wind generation", "wind farm", "wind energy", "wind turbine output"],
    "X:SOLAR": ["solar generation", "solar output", "solar panel", "photovoltaic"],
    "B:ALRM": ["building alarm", "fire alarm", "building fire", "alarm in the building"],
    "T:SCHED": ["schedule", "schedule event", "book a time", "set a time"],
    "T:WIN": ["time window", "maintenance window", "scheduling window"],
    "L:AUDIT": ["audit log", "audit trail", "log audit", "compliance log"],
    "L:REPORT": ["compliance report", "audit report", "generate report"],
    "D:LOG": ["log entry", "write log", "log data"],
    "A:SUM": ["summarize", "condense", "create summary", "tldr"],
    "U:ALERT": ["alert operator", "notify user", "urgent alert", "send alert"],

    # NL_PASSTHROUGH candidates (should return NONE)
    "NONE": ["order tacos", "book a flight", "send an email", "post to instagram",
             "what is 2+2", "hey how are you", "who painted the mona lisa",
             "calculate the total cost", "acknowledge the receipt"],
}


def generate_candidates() -> list[dict]:
    """Generate the full candidate set for ZTOLE generation measurement."""
    candidates = []
    for opcode_key, phrases in SYNONYM_SEEDS.items():
        if opcode_key == "NONE":
            for phrase in phrases:
                candidates.append({
                    "phrase": phrase,
                    "expected_ns": "NONE",
                    "expected_op": "NONE",
                    "source": "passthrough_validation",
                })
        else:
            ns, op = opcode_key.split(":")
            for phrase in phrases:
                candidates.append({
                    "phrase": phrase,
                    "expected_ns": ns,
                    "expected_op": op,
                    "source": "synonym_seed",
                })
    return candidates


# ── Measurement ──────────────────────────────────────────────────────────────

def parse_opcode_response(text: str) -> tuple[str, str]:
    """Parse model response into (namespace, opcode) or ("NONE", "NONE")."""
    text = text.strip().upper()
    if "NONE" in text or "NO MATCH" in text or "N/A" in text:
        return ("NONE", "NONE")
    m = re.match(r'^([A-Z\u03a9]):([A-Z0-9\u00a7]+)', text)
    if m:
        return (m.group(1), m.group(2))
    return ("PARSE_ERROR", text[:20])


def run_measurement(panel: dict[str, callable], candidates: list[dict]) -> list[ProbeResult]:
    """Run the ZTOLE generation measurement across the panel."""
    results = []
    panel_size = len(panel)
    probe_system = build_probe_system()

    print(f"\n{'='*78}")
    print(f"ZTOLE 3rd MODE — GENERATION MEASUREMENT (dictionary-aware)")
    print(f"{'='*78}")
    print(f"Panel: {', '.join(panel.keys())} ({panel_size} models)")
    print(f"Candidates: {len(candidates)} phrases")
    print(f"Graduation threshold: {max(2, panel_size * 3 // 4)}/{panel_size} agreement")
    print(f"{'='*78}\n")

    for i, cand in enumerate(candidates):
        phrase = cand["phrase"]
        expected_ns = cand["expected_ns"]
        expected_op = cand["expected_op"]

        responses = {}
        correct_count = 0

        for model_name, call_fn in panel.items():
            try:
                raw = call_fn(f'What OSMP opcode matches: "{phrase}"', probe_system)
                resp_ns, resp_op = parse_opcode_response(raw)
                responses[model_name] = f"{resp_ns}:{resp_op}"
                if resp_ns == expected_ns and resp_op == expected_op:
                    correct_count += 1
                elif expected_ns == "NONE" and resp_ns == "NONE":
                    correct_count += 1
            except Exception as e:
                responses[model_name] = f"ERROR:{str(e)[:30]}"
            time.sleep(0.2)

        result = ProbeResult(
            phrase=phrase,
            expected_ns=expected_ns,
            expected_op=expected_op,
            responses=responses,
            agreements=correct_count,
            panel_size=panel_size,
        )
        results.append(result)

        # Print progress
        threshold = max(2, panel_size * 3 // 4)
        icon = "+" if correct_count >= threshold else "~" if correct_count >= 2 else "X"
        expected = f"{expected_ns}:{expected_op}" if expected_ns != "NONE" else "NONE"
        resp_summary = "  ".join(f"{k}={v}" for k, v in responses.items())
        print(f"  [{icon}] {correct_count}/{panel_size}  {expected:10s}  \"{phrase}\"")
        if correct_count < threshold:
            print(f"         {resp_summary}")

        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(candidates)} measured ...")

    return results


def report(results: list[ProbeResult]) -> dict:
    """Generate summary report from measurement results."""
    if not results:
        return {}

    panel_size = results[0].panel_size
    threshold = max(2, panel_size * 3 // 4)

    graduated = [r for r in results if r.agreements >= threshold]
    borderline = [r for r in results if 1 <= r.agreements < threshold]
    failed = [r for r in results if r.agreements == 0]

    # Separate passthrough candidates
    pt_results = [r for r in results if r.expected_ns == "NONE"]
    opcode_results = [r for r in results if r.expected_ns != "NONE"]

    pt_graduated = [r for r in pt_results if r.agreements >= threshold]
    op_graduated = [r for r in opcode_results if r.agreements >= threshold]

    print(f"\n{'='*78}")
    print(f"ZTOLE GENERATION MEASUREMENT — RESULTS")
    print(f"{'='*78}")
    print(f"Panel size: {panel_size}  Graduation threshold: {threshold}/{panel_size}")
    print(f"Total candidates: {len(results)}")
    print(f"  Opcode candidates: {len(opcode_results)}  (graduated: {len(op_graduated)})")
    print(f"  Passthrough candidates: {len(pt_results)}  (graduated: {len(pt_graduated)})")
    print(f"\nGRADUATED TRIGGERS ({len(graduated)} total):")
    for r in graduated:
        expected = f"{r.expected_ns}:{r.expected_op}" if r.expected_ns != "NONE" else "NONE"
        print(f"  {r.agreements}/{r.panel_size}  {expected:10s}  \"{r.phrase}\"")

    if borderline:
        print(f"\nBORDERLINE (below threshold, {len(borderline)}):")
        for r in borderline:
            expected = f"{r.expected_ns}:{r.expected_op}" if r.expected_ns != "NONE" else "NONE"
            resps = "  ".join(f"{k}={v}" for k, v in r.responses.items())
            print(f"  {r.agreements}/{r.panel_size}  {expected:10s}  \"{r.phrase}\"  [{resps}]")

    if failed:
        print(f"\nFAILED (0 agreement, {len(failed)}):")
        for r in failed:
            expected = f"{r.expected_ns}:{r.expected_op}" if r.expected_ns != "NONE" else "NONE"
            resps = "  ".join(f"{k}={v}" for k, v in r.responses.items())
            print(f"  {r.agreements}/{r.panel_size}  {expected:10s}  \"{r.phrase}\"  [{resps}]")

    graduation_rate = len(graduated) / len(results) * 100 if results else 0
    print(f"\nGraduation rate: {len(graduated)}/{len(results)} ({graduation_rate:.1f}%)")
    print(f"{'='*78}\n")

    return {
        "panel_size": panel_size,
        "threshold": threshold,
        "total_candidates": len(results),
        "graduated": len(graduated),
        "borderline": len(borderline),
        "failed": len(failed),
        "graduation_rate_pct": round(graduation_rate, 1),
        "graduated_triggers": [
            {"phrase": r.phrase, "ns": r.expected_ns, "op": r.expected_op,
             "agreements": r.agreements, "responses": r.responses}
            for r in graduated
        ],
        "borderline_triggers": [
            {"phrase": r.phrase, "ns": r.expected_ns, "op": r.expected_op,
             "agreements": r.agreements, "responses": r.responses}
            for r in borderline
        ],
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ZTOLE Generation Measurement")
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"))
    parser.add_argument("--generate-candidates", action="store_true", help="Print candidates and exit")
    parser.add_argument("--anthropic-model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--gemini-model", default="gemini-2.0-flash")
    args = parser.parse_args()

    candidates = generate_candidates()

    if args.generate_candidates:
        for c in candidates:
            expected = f"{c['expected_ns']}:{c['expected_op']}" if c['expected_ns'] != "NONE" else "NONE"
            print(f"  {expected:10s}  \"{c['phrase']}\"")
        print(f"\nTotal: {len(candidates)} candidates")
        return 0

    # Build panel — hi/lo pairs per vendor for diversity
    panel = {}
    if args.anthropic_key:
        panel["claude-hi"] = lambda p, s, k=args.anthropic_key: call_anthropic(p, s, k, "claude-sonnet-4-5-20241022")
        panel["claude-lo"] = lambda p, s, k=args.anthropic_key: call_anthropic(p, s, k, "claude-haiku-4-5-20251001")
    if args.openai_key:
        panel["gpt-hi"] = lambda p, s, k=args.openai_key: call_openai(p, s, k, "gpt-5")
        panel["gpt-lo"] = lambda p, s, k=args.openai_key: call_openai(p, s, k, "gpt-4o-mini")
    if args.gemini_key:
        panel["gemini"] = lambda p, s, k=args.gemini_key: call_gemini(p, s, k, "gemini-2.0-flash")

    if len(panel) < 2:
        print("ERROR: ZTOLE requires at least 2 panel models. Provide 2+ API keys.")
        return 1

    results = run_measurement(panel, candidates)
    report_data = report(results)

    report_path = REPO_ROOT / "tests" / "ztole-generation-results.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
