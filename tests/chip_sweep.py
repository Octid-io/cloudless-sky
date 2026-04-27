#!/usr/bin/env python3
"""
Local chip sweep — runs an arbitrary list of NL chips through the Python
SDK composer (Tier 1 only — no LLM, no Worker, no api.octid.io). Prints
per-chip SAL output + byte deltas + verdict, then a summary.

Use this for tight composer iteration: edit protocol.py, run this, see
which chips pass/fail. No deploy required.

Usage:
  python tests/chip_sweep.py
  python tests/chip_sweep.py "report location" "report heading"
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from osmp.protocol import SALComposer

DEFAULT_CHIPS = [
    # ── Original demo chips ─────────────────────────────────────────────
    "update config",
    "report temperature",
    "fire alarm in building B",
    "back up the database tonight at 2am",
    "increase pump pressure to 1013 millibar",
    "alert me when the temperature drops below 65",
    "encrypt this payload then send it to the central server",
    "send my heart rate",
    # ── Position / Geo ──────────────────────────────────────────────────
    "report location",
    "report heading",
    "report position",
    "report bearing",
    "report altitude",
    "what is my position",
    "where am I",
    "show coordinates",
    # ── Status / Health ─────────────────────────────────────────────────
    "cpu usage",
    "memory usage",
    "disk space",
    "battery level",
    "signal strength",
    "link quality",
    "node status",
    "network status",
    # ── Sensors ─────────────────────────────────────────────────────────
    "humidity reading",
    "wind speed",
    "soil moisture",
    "air quality",
    "vibration sensor",
    # ── Actuation ───────────────────────────────────────────────────────
    "turn off the light",
    "lock the door",
    "open the valve",
    "start the pump",
    "stop the conveyor",
    "emergency stop",
    "return to base",
    # ── Auth / Crypto ───────────────────────────────────────────────────
    "verify identity",
    "sign the payload",
    "generate keypair",
    "hash this file",
    # ── Data ────────────────────────────────────────────────────────────
    "query the last hour",
    "delete the row",
    "fetch from cache",
    "push to node 17",
    # ── Config / Service ────────────────────────────────────────────────
    "restart the service",
    "reboot the gateway",
    "shutdown",
    "rotate keys",
    # ── Vehicle / Fleet ─────────────────────────────────────────────────
    "vehicle position",
    "fleet status",
    "vessel heading",
    # ── Vitals ──────────────────────────────────────────────────────────
    "blood pressure check",
    "oxygen level",
    "vitals check",
    # ── Multi-step chains ───────────────────────────────────────────────
    "snapshot then upload",
    "verify then sign",
    # ── Conditional ─────────────────────────────────────────────────────
    "alert when humidity above 80",
    "trigger when pressure below 1000",
    # ── Out-of-scope (expected passthrough) ─────────────────────────────
    "order me a pepperoni pizza",
    "tell me a joke",
    "what's the weather like",
    # ── Vocab gaps (expected passthrough until extension) ───────────────
    "silence all alarms in zone 4",
    "mute the speaker",
    # ── Typos / fuzzy ───────────────────────────────────────────────────
    "report loca",
    "log uptime",
]

# Tag chips by expected outcome so the harness can score honestly.
EXPECTED_PASSTHROUGH = {
    "order me a pepperoni pizza",
    "tell me a joke",
    "what's the weather like",
    "silence all alarms in zone 4",  # vocab gap until R:SPKR extends
    "mute the speaker",              # vocab gap until R:SPKR extends
    "report loca",                    # typo, Tier 2 cascade handles
}


def utf8(s: str) -> int:
    return len(s.encode("utf-8"))


def main(argv: list[str]) -> int:
    chips = argv[1:] if len(argv) > 1 else DEFAULT_CHIPS
    composer = SALComposer()

    print("=" * 90)
    print(f"CHIP SWEEP — Python SDK composer (Tier 1 only, no LLM)")
    print("=" * 90)
    print(f"{'NL':<55}{'SAL':<25}{'NLB':>4} {'SALB':>5} {'D':>5}")
    print("-" * 90)

    pass_count = 0
    fail_count = 0
    bael_violations = 0

    for nl in chips:
        try:
            sal = composer.compose(nl)
        except Exception as e:
            sal = f"ERR:{type(e).__name__}"
        nl_b = utf8(nl)
        sal_b = utf8(sal) if sal else 0
        delta = sal_b - nl_b if sal else 0

        if not sal:
            verdict = "[NO COMPOSE]"
            fail_count += 1
        elif sal_b >= nl_b:
            verdict = "[BAEL VIOLATION]"
            bael_violations += 1
        else:
            verdict = "[OK]"
            pass_count += 1

        sal_display = sal if sal else "(null)"
        print(
            f"{nl[:54]:<55}{sal_display[:24]:<25}{nl_b:>4} {sal_b:>5} {delta:>+5}  {verdict}"
        )

    print("-" * 90)
    total = len(chips)
    print(f"PASS: {pass_count}/{total}   BAEL_FLOOR: {bael_violations}/{total}   NO_COMPOSE: {fail_count}/{total}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
