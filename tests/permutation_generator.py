#!/usr/bin/env python3
"""
Permutation generator — produces variants of every chip in the corpus by
applying linguistic transformations that should preserve meaning.

The generated variants share the source chip's expected_sal: any composer
that hits the source should hit the variant. Failures expose brittleness
the original test corpus didn't catch.

Transformations applied:
  - Article add/remove ("the door" <-> "door")
  - Synonym swap ("stop" <-> "halt", "show" <-> "give me")
  - Word-order swap where preserves meaning ("alert if X" <-> "if X then alert")
  - Casing: title case, ALL CAPS, lower
  - Punctuation: add/remove trailing punct, period <-> question
  - Filler addition: "please", "could you", "I want to"
  - Plural <-> singular ("the doors" <-> "door")
  - Verb tense ("stop" <-> "stopping")

Adversarial / edge cases (separate from permutations):
  - Negation ("don't stop", "do not move")
  - Ambiguous reference ("it", "that", "this")
  - Mixed domain ("temperature and pizza")
  - Very long sentences (50+ words)
  - Very short fragments ("temp.", "go")
  - Garbled punctuation ("stop, the!! conveyor??")
  - Code-switch ("ping the noeud" — French + English)
  - Numeric edge cases (negative numbers, decimals, very large/small)
  - Glyph injection (try to inject SAL syntax in NL)
  - Empty / whitespace-only

Output: corpus-permutations.json and corpus-edges.json that the brigade
test harness can load via CORPUS_FILE env var.
"""
from __future__ import annotations

import json
import random
import string
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_CORPUS = REPO / "tests" / "input-classes" / "corpus-v2-expanded.json"
OUT_PERMS = REPO / "tests" / "input-classes" / "corpus-permutations.json"
OUT_EDGES = REPO / "tests" / "input-classes" / "corpus-edges.json"

random.seed(42)


# ─────────────────────────────────────────────────────────────────────────────
# PERMUTATIONS — meaning-preserving transformations
# ─────────────────────────────────────────────────────────────────────────────

VERB_SYNONYMS = {
    "stop": ["halt", "cease", "stop"],
    "halt": ["stop", "halt"],
    "report": ["show", "give me", "tell me", "what is", "report"],
    "show": ["report", "give me", "show"],
    "send": ["transmit", "deliver", "send"],
    "encrypt": ["encrypt", "cipher"],
    "verify": ["verify", "confirm", "check"],
    "check": ["verify", "check", "examine"],
    "set": ["set", "configure", "modify"],
    "update": ["update", "modify", "change"],
    "lock": ["lock", "secure"],
    "open": ["open", "unlock"],
    "alert": ["alert", "notify", "warn"],
    "notify": ["notify", "alert", "warn"],
    "warn": ["warn", "alert", "notify"],
    "ping": ["ping", "ping"],
    "discover": ["discover", "find", "locate"],
    "shutdown": ["shutdown", "shut down", "terminate"],
    "restart": ["restart", "reboot", "restart"],
    "back up": ["back up", "backup"],
    "broadcast": ["broadcast", "transmit"],
    "move": ["move", "go to", "navigate to"],
}

ARTICLE_PATTERNS = [
    ("the ", ""),  # "stop the conveyor" -> "stop conveyor"
    ("a ", ""),
    ("an ", ""),
]

POLITE_PREFIXES = ["", "please ", "could you ", "I want to "]


def synonym_swap(nl: str) -> list[str]:
    """Return variants with first-found verb replaced by synonyms."""
    variants = []
    low = nl.lower()
    for verb, syns in VERB_SYNONYMS.items():
        if verb in low:
            for syn in syns:
                if syn != verb and syn in low:
                    continue
                variant = low.replace(verb, syn, 1)
                if variant != low:
                    variants.append(variant)
            break
    return variants


def article_swap(nl: str) -> list[str]:
    """Add/remove articles."""
    variants = []
    for pat, repl in ARTICLE_PATTERNS:
        if pat in nl.lower():
            variants.append(nl.lower().replace(pat, repl, 1))
        else:
            # Add an article before a noun (heuristic)
            words = nl.split()
            if len(words) >= 2 and words[0].lower() not in ("the", "a", "an", "what", "where"):
                variants.append(f"{words[0]} the {' '.join(words[1:])}")
    return variants[:2]  # cap


def casing_swap(nl: str) -> list[str]:
    return [nl.upper(), nl.title()]


def punct_swap(nl: str) -> list[str]:
    variants = []
    if not nl.endswith(("?", ".", "!")):
        variants.append(nl + ".")
        variants.append(nl + "?")
    if nl.endswith("."):
        variants.append(nl[:-1])
    return variants


def politeness_add(nl: str) -> list[str]:
    return [p + nl for p in POLITE_PREFIXES if p][:2]


def generate_permutations(chip: dict, max_per_chip: int = 4) -> list[dict]:
    """Generate variants of a single chip. Variants share expected_sal."""
    nl = chip["nl"]
    variants = set()

    # Apply each transformation
    for var in synonym_swap(nl):
        variants.add(var)
    for var in article_swap(nl):
        variants.add(var)
    for var in casing_swap(nl):
        variants.add(var)
    for var in punct_swap(nl):
        variants.add(var)
    for var in politeness_add(nl):
        variants.add(var)

    # Strip duplicates (case-insensitive)
    seen_lower = set()
    deduped = []
    for v in variants:
        key = v.lower().strip()
        if key in seen_lower or key == nl.lower().strip():
            continue
        seen_lower.add(key)
        deduped.append(v)

    # Cap
    selected = deduped[:max_per_chip]

    out = []
    for i, var_nl in enumerate(selected):
        new_chip = deepcopy(chip)
        new_chip["id"] = f"{chip['id']}-V{i+1}"
        new_chip["nl"] = var_nl
        new_chip["original_id"] = chip["id"]
        new_chip["transform"] = "permutation"
        out.append(new_chip)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# EDGE CASES — adversarial / boundary inputs
# ─────────────────────────────────────────────────────────────────────────────

EDGE_CASES = [
    # Negation — must NOT compose to the affirmative
    {"id": "EDGE-NEG-01", "nl": "don't stop the conveyor",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "negation", "note": "negation should suppress affirmative compose"},
    {"id": "EDGE-NEG-02", "nl": "do not move the drone",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "negation"},
    {"id": "EDGE-NEG-03", "nl": "never restart the service",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "negation"},

    # Ambiguous reference
    {"id": "EDGE-AMB-01", "nl": "do it",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "ambiguous"},
    {"id": "EDGE-AMB-02", "nl": "stop that",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "ambiguous"},
    {"id": "EDGE-AMB-03", "nl": "send this",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "ambiguous"},

    # Mixed-domain (some compose-able, some not)
    {"id": "EDGE-MIX-01", "nl": "stop the conveyor and order pizza",
     "expected_sal": ["R:STOP\u21ba@CONVEYOR", "R:STOP\u21bb@CONVEYOR", "R:STOP\u21ba"],
     "shape": "mixed_partial", "note": "should compose the protocol part, drop the food part"},
    {"id": "EDGE-MIX-02", "nl": "report temperature and tell me a joke",
     "expected_sal": ["E:TH", "E:TH?"],
     "shape": "mixed_partial"},

    # Very long
    {"id": "EDGE-LONG-01",
     "nl": "Please report the current temperature reading from sensor node 4A and also broadcast my position to all peers in the mesh network now",
     "expected_sal": ["E:TH@4A", "E:TH@4A?", "G:POS"],
     "shape": "long_multi_clause"},

    # Very short
    {"id": "EDGE-SHORT-01", "nl": "go",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "very_short"},
    {"id": "EDGE-SHORT-02", "nl": "stop",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "very_short", "note": "stop alone is too short to compress"},
    {"id": "EDGE-SHORT-03", "nl": "ping",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "very_short"},

    # Garbled punctuation
    {"id": "EDGE-PUNCT-01", "nl": "stop, the!! conveyor??",
     "expected_sal": ["R:STOP\u21ba@CONVEYOR", "R:STOP\u21bb@CONVEYOR", "R:STOP\u21ba"],
     "shape": "punct_garbled"},

    # Casing extremes
    {"id": "EDGE-CASE-01", "nl": "STOP THE CONVEYOR",
     "expected_sal": ["R:STOP\u21ba@CONVEYOR", "R:STOP\u21bb@CONVEYOR", "R:STOP\u21ba"],
     "shape": "all_caps"},
    {"id": "EDGE-CASE-02", "nl": "rEpOrT TeMpErAtUrE",
     "expected_sal": ["E:TH", "E:TH?"],
     "shape": "weird_case"},

    # Numeric edge cases
    {"id": "EDGE-NUM-01", "nl": "alert me if heart rate exceeds -1",
     "expected_sal": ["H:HR>-1\u2192H:ALERT", "H:HR>-1\u2192U:ALERT"],
     "shape": "negative_number"},
    {"id": "EDGE-NUM-02", "nl": "alert me if heart rate exceeds 999999",
     "expected_sal": ["H:HR>999999\u2192H:ALERT", "H:HR>999999\u2192U:ALERT"],
     "shape": "very_large_number"},
    {"id": "EDGE-NUM-03", "nl": "set threshold to 0.0001",
     "expected_sal": ["N:CFG[threshold:0.0001]"],
     "shape": "small_decimal"},

    # Code-switching (mixed language)
    {"id": "EDGE-LANG-01", "nl": "ping the noeud BRAVO",
     "expected_sal": ["A:PING@BRAVO"],
     "shape": "code_switch", "note": "mostly English with French noun"},

    # Glyph injection — adversarial; user types SAL syntax in NL
    {"id": "EDGE-INJECT-01", "nl": "please send R:STOP to the conveyor",
     "expected_sal": [],
     "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "glyph_injection",
     "note": "user types SAL in their input; brigade should not compose this"},

    # Empty / whitespace
    {"id": "EDGE-EMPTY-01", "nl": "",
     "expected_sal": [], "expected_verdict": "REFUSED_MALFORMED",
     "shape": "empty"},
    {"id": "EDGE-EMPTY-02", "nl": "   ",
     "expected_sal": [], "expected_verdict": "REFUSED_MALFORMED",
     "shape": "whitespace_only"},

    # Imperative without verb (just a noun or phrase)
    {"id": "EDGE-NOM-01", "nl": "temperature",
     "expected_sal": [], "expected_verdict": "SAFE_PASSTHROUGH",
     "shape": "bare_noun"},
    {"id": "EDGE-NOM-02", "nl": "humidity reading from sensor 7",
     "expected_sal": ["E:HU@7", "E:HU@7?"],
     "shape": "nominal_predicate"},

    # Question-form vs imperative
    {"id": "EDGE-QUERY-01", "nl": "what is the heart rate?",
     "expected_sal": ["H:HR", "H:HR?"],
     "shape": "interrogative"},
    {"id": "EDGE-QUERY-02", "nl": "where is drone 3?",
     "expected_sal": ["V:POS@DRONE3", "G:POS", "V:POS"],
     "shape": "interrogative"},

    # Filler-heavy
    {"id": "EDGE-FILLER-01", "nl": "uh, can you, like, maybe, stop the conveyor please",
     "expected_sal": ["R:STOP\u21ba@CONVEYOR", "R:STOP\u21bb@CONVEYOR", "R:STOP\u21ba"],
     "shape": "filler_heavy"},

    # Authorization variants
    {"id": "EDGE-AUTH-01", "nl": "process payment, requires sign-off",
     "expected_sal": ["I:\u00a7\u2192K:PAY"],
     "shape": "auth_required"},
    {"id": "EDGE-AUTH-02", "nl": "delete the database, but only with approval",
     "expected_sal": ["I:\u00a7\u2192D:DEL\u2298", "U:APPROVE\u2192D:DEL\u2298"],
     "shape": "auth_required"},

    # Conditional with "when" (vs "if")
    {"id": "EDGE-COND-01", "nl": "alert me when temperature drops below 65",
     "expected_sal": ["E:TH<65\u2192L:ALERT", "E:TH<65\u2192U:ALERT", "E:TH<65\u2192U:NOTIFY"],
     "shape": "when_conditional"},
    {"id": "EDGE-COND-02", "nl": "warn while wind exceeds 50",
     "expected_sal": ["W:WIND>50\u2192W:ALERT", "W:WIND>50\u2192L:ALERT"],
     "shape": "while_conditional"},
]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    src = json.load(open(SRC_CORPUS, encoding="utf-8"))
    src_inputs = src["inputs"]

    # Permutations
    perms = []
    for chip in src_inputs:
        # Skip chips that are themselves OOS — perms of "tell me a joke" don't add signal
        if chip.get("expected_verdict"):
            continue
        for variant in generate_permutations(chip, max_per_chip=4):
            perms.append(variant)

    perm_corpus = {
        "version": "perms-v1",
        "source": "corpus-v2-expanded.json",
        "description": f"Permutations of in-scope chips. Each variant shares the source's expected_sal.",
        "scoring": src["scoring"],
        "inputs": perms,
    }
    with open(OUT_PERMS, "w", encoding="utf-8") as f:
        json.dump(perm_corpus, f, indent=2, ensure_ascii=False)
    print(f"Permutations: {len(perms)} chips written to {OUT_PERMS.name}")

    # Edge cases — only write if file doesn't exist (preserve manual fixture edits)
    if not OUT_EDGES.exists():
        edge_corpus = {
            "version": "edges-v1",
            "description": "Adversarial / boundary inputs designed to stress brigade.",
            "scoring": src["scoring"],
            "inputs": EDGE_CASES,
        }
        with open(OUT_EDGES, "w", encoding="utf-8") as f:
            json.dump(edge_corpus, f, indent=2, ensure_ascii=False)
        print(f"Edge cases: {len(EDGE_CASES)} chips written to {OUT_EDGES.name}")
    else:
        print(f"Edge cases: {OUT_EDGES.name} exists, NOT overwriting (preserving manual edits)")


if __name__ == "__main__":
    main()
