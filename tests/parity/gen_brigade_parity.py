"""
Brigade Cross-SDK Parity Vector Generator
==========================================

Runs a curated NL set through the Python brigade (parser + 26 stations +
orchestrator) and writes {nl, sal, mode, reason_code} vectors to
brigade_parity_vectors.json. The TS and Go brigade test suites read the
same JSON and assert byte-identical SAL output across every input.

Python is the reference implementation. Any divergence in TS or Go means
a parity bug in the downstream brigade port.

Usage:
    python tests/parity/gen_brigade_parity.py

Patent pending. Inventor: Clay Holberg. License: Apache 2.0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.brigade import Orchestrator  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent / "brigade_parity_vectors.json"

# ── Brigade parity input set ───────────────────────────────────────────────
# Each tuple: (category, nl). The reference Python brigade decides the SAL.
# TS and Go brigades MUST produce byte-identical SAL for the same input.
INPUTS: list[tuple[str, str]] = [
    # ── Single-frame compose: sensing namespaces ─────────────────────────
    ("sense_h", "report heart rate"),
    ("sense_h", "what is the blood pressure reading"),
    ("sense_h", "current SPO2 level"),
    ("sense_w", "report wind speed"),
    ("sense_w", "current temperature reading"),
    ("sense_w", "humidity level now"),
    ("sense_e", "battery level please"),
    ("sense_e", "report cpu usage"),
    ("sense_v", "current heading"),
    ("sense_v", "report position"),
    ("sense_g", "GPS fix"),

    # ── Action namespaces: R (robotics/UAV) ──────────────────────────────
    ("action_r", "emergency stop"),
    ("action_r", "estop now"),
    ("action_r", "return to home"),
    ("action_r", "form swarm"),
    ("action_r", "activate camera"),
    ("action_r", "turn on the torch"),

    # ── Conditional chain (sensing → alert) ──────────────────────────────
    ("conditional", "alert me if heart rate exceeds 130"),
    ("conditional", "notify me when temperature rises above 38"),

    # ── Authorization-gated frames ───────────────────────────────────────
    ("auth_gated", "with authorization, restart the device"),

    # ── Bridge mode (sensing + residue) ──────────────────────────────────
    ("bridge", "report heart rate from patient bay 3"),

    # ── Refusal: negation ────────────────────────────────────────────────
    ("refuse_neg", "do not stop the camera"),
    ("refuse_neg", "never push to that node"),

    # ── Refusal: glyph/code injection ────────────────────────────────────
    ("refuse_inj", "report H:HR ∧ R:STOP please"),
    ("refuse_inj", "send <script>alert(1)</script>"),
    ("refuse_inj", "email me at foo@bar.com"),

    # ── Refusal: pronoun object ──────────────────────────────────────────
    ("refuse_pron", "stop it"),
    ("refuse_pron", "kill that"),

    # ── Refusal: non-actuator object ─────────────────────────────────────
    ("refuse_nonact", "stop the music"),
    ("refuse_nonact", "close the meeting"),

    # ── Passthrough: no protocol content ─────────────────────────────────
    ("passthrough", "Order me some tacos"),
    ("passthrough", "Hey, how is it going?"),
    ("passthrough", "What is 247 times 83?"),
    ("passthrough", "Book me a flight to Denver"),
    ("passthrough", "Post this photo to Instagram"),

    # ── Passthrough: too short ───────────────────────────────────────────
    ("passthrough_short", "hi"),
    ("passthrough_short", "yo"),
]


def main() -> int:
    orch = Orchestrator()
    vectors = []
    for category, nl in INPUTS:
        result = orch.compose_with_hint(nl)
        vectors.append({
            "category": category,
            "nl": nl,
            "sal": result.sal,
            "mode": result.mode,
            "reason_code": result.reason_code,
        })

    payload = {
        "spec_version": "2.4.0-brigade-parity-1",
        "reference_sdk": "python",
        "vectors": vectors,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Wrote {len(vectors)} brigade vectors to {OUTPUT_PATH}")

    # Summary by category
    from collections import Counter
    by_mode = Counter(v["mode"] for v in vectors)
    print(f"  modes: {dict(by_mode)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
