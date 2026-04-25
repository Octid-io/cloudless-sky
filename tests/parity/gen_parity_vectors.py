"""
Cross-SDK Parity Vector Generator
==================================

Runs a fixed list of natural-language inputs through the Python SAL composer
(with the Meshtastic macro corpus attached) and writes the resulting
{nl, sal} pairs to parity_vectors.json. The TS and Go test suites read the
same JSON and assert byte-identical SAL output.

Python is the reference implementation. Any divergence in TS or Go means a
parity bug in the downstream SDK (cross-SDK contract is byte-identical SAL
for every input across all three composers).

Usage:
    python tests/parity/gen_parity_vectors.py

Patent pending. Inventor: Clay Holberg. License: Apache 2.0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp import SALComposer, MacroRegistry  # noqa: E402

CORPUS_PATH = REPO_ROOT / "mdr" / "meshtastic" / "meshtastic-macros.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "parity_vectors.json"

# ── Curated parity inputs ──────────────────────────────────────────────────
# The list intentionally exercises every code path that diverged between
# Python (post-2.3.3) and TS/Go (frozen at the April-16 snapshot before
# this 2.4 port). Categories: site chips, macro priority, chain-split,
# single-segment composition, NL passthrough.

INPUTS: list[tuple[str, str]] = [
    # ── Site chips (the four phrases the live encoder demos) ──────────────
    ("chip", "report battery level"),
    ("chip", "report temperature"),
    ("chip", "sync clock"),
    ("chip", "update config"),

    # ── Macro priority triggers (Meshtastic corpus) ───────────────────────
    ("macro", "report device status with battery details"),
    ("macro", "give me the air quality readings"),
    ("macro", "what is my position right now"),
    ("macro", "casualty evacuation needed at the LZ"),
    ("macro", "send the mesh stats over"),
    ("macro", "vitals report from sensor 3"),

    # ── Chain-split (SEQUENCE / AND chains via NL separators) ─────────────
    ("chain", "encrypt the payload, then push to node BRAVO"),
    ("chain", "sign payload then push to node ALPHA"),
    ("chain", "verify identity, and then run inference"),
    ("chain", "store to memory, then sync clock"),

    # ── Single-segment composition (curated triggers / opcode keywords) ───
    ("single", "fire alarm in building B"),
    ("single", "emergency route now to the staging point"),
    ("single", "data query needed for the audit"),
    ("single", "robot status update from BOT1"),
    ("single", "alert me if heart rate exceeds 130"),

    # ── NL passthrough (no opcode resolution; expect None) ────────────────
    ("passthrough", "Order me some tacos"),
    ("passthrough", "Hey, how is it going?"),
    ("passthrough", "What is 247 times 83?"),
    ("passthrough", "Book me a flight to Denver"),
    ("passthrough", "Post this photo to Instagram"),
]


def main() -> int:
    registry = MacroRegistry()
    count = registry.load_corpus(CORPUS_PATH)
    composer = SALComposer(macro_registry=registry)

    vectors = []
    for category, nl in INPUTS:
        sal = composer.compose(nl)  # None on passthrough; str otherwise
        vectors.append({
            "category": category,
            "nl": nl,
            "sal": sal,  # null in JSON when None
        })

    payload = {
        "spec_version": "2.4.0-parity-1",
        "reference_sdk": "python",
        "macro_corpus": "mdr/meshtastic/meshtastic-macros.json",
        "macros_loaded": count,
        "vectors": vectors,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Wrote {len(vectors)} vectors to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
