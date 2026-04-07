#!/usr/bin/env python3
"""
opcode_readability_test.py
==========================

Empirical test harness for OSMP opcode readability against LLM training
distributions. This is the tool that backs the Frequency-Aligned Lingua
Franca design principle: instead of relying on a single author's
intuition about what a model will guess for a given opcode, we actually
ask the models and aggregate their answers.

For each opcode in ASD_BASIS, the harness generates a minimal prompt
that gives only the namespace label as context, asks the model what the
opcode most likely stands for, and records the top-N guesses. Results
are compared to the current ASD meaning and classified as:

    AGREE      — model's first guess matches current ASD meaning
    IN_TOP3    — current ASD meaning is in model's top 3 but not first
    MISS       — model's top 3 does not include the current ASD meaning
                 (this is the rename candidate signal)
    BLANK      — model refused or gave an unparseable answer

Output is a CSV report that can be diffed across model families and
across dictionary revisions. The same harness that runs today against
Sonnet 4.6 should produce comparable results against Sonnet 5, GPT-5,
Gemini 3, etc. — that's the point of the frequency-aligned approach:
as long as the models train on roughly the same distribution, the
agreement numbers should stay stable or improve.

Usage
-----
::

    export ANTHROPIC_API_KEY=sk-ant-...
    python3 tools/opcode_readability_test.py --model claude-sonnet-4-6
    python3 tools/opcode_readability_test.py --namespace M --verbose
    python3 tools/opcode_readability_test.py --opcode E:OBS
    python3 tools/opcode_readability_test.py --flagged-only
    python3 tools/opcode_readability_test.py --output reports/readability-v14.csv

OpenAI support (when API key is added)::

    export OPENAI_API_KEY=sk-...
    python3 tools/opcode_readability_test.py --provider openai --model gpt-4o

The harness is deliberately provider-agnostic so the same invocation
works across vendors. A full multi-provider run produces an aggregated
agreement matrix that IS the empirical evidence for the canonical form
of each opcode.

Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import ASD_BASIS  # noqa: E402


# ── Namespace labels (provides the only context the model gets) ───────────

NAMESPACE_LABELS: dict[str, str] = {
    "A": "Agent Coordination",
    "B": "Building or Infrastructure",
    "C": "Compute or Resource Management",
    "D": "Data Transfer",
    "E": "Environment or Sensing",
    "F": "Food or Agriculture",
    "G": "Geospatial or Navigation",
    "H": "Health or Medical",
    "I": "Identity or Consent",
    "J": "Planning or Goals",
    "K": "Commerce or Finance",
    "L": "Logging or Audit",
    "M": "Movement or Evacuation",
    "N": "Network",
    "O": "Operational Context",
    "P": "Product or Parts",
    "Q": "Quality or Evaluation",
    "R": "Robotics or Peripherals",
    "S": "Security or Cryptography",
    "T": "Time",
    "U": "User Interaction",
    "V": "Vessel or Maritime",
    "W": "Weather",
    "X": "Electrical or Energy",
    "Y": "Memory or Knowledge",
    "Z": "LLM or Inference",
}


# ── Prompt generation ──────────────────────────────────────────────────────

PROMPT_TEMPLATE = """In a machine-readable protocol, you see the opcode `{ns}:{op}`.

The namespace `{ns}` is for "{ns_label}".

What does the opcode `{op}` most likely stand for in this context?

Give your top 3 guesses as a JSON array of short uppercase strings, most likely first. Do not include any other text, only the JSON array.

Example output: ["TEMPERATURE", "TEMPLATE", "TEMPO"]"""


def generate_prompt(ns: str, op: str) -> str:
    ns_label = NAMESPACE_LABELS.get(ns, "unknown")
    return PROMPT_TEMPLATE.format(ns=ns, op=op, ns_label=ns_label)


# ── Result classification ─────────────────────────────────────────────────

@dataclass
class OpcodeResult:
    namespace: str
    opcode: str
    current_meaning: str
    model_guesses: list[str] = field(default_factory=list)
    classification: str = ""  # AGREE | IN_TOP3 | MISS | BLANK
    first_guess_matches: bool = False
    rename_suggestion: str = ""
    error: str = ""

    @property
    def key(self) -> str:
        return f"{self.namespace}:{self.opcode}"


def normalize(s: str) -> str:
    """Normalize a string for comparison: uppercase, alphanumeric only."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def meaning_tokens(meaning: str) -> set[str]:
    """Break a meaning string into comparison tokens.

    E.g. 'heart_rate' -> {'HEART', 'RATE', 'HEARTRATE'}
         'wind_speed_and_direction' -> {'WIND', 'SPEED', 'AND',
                                         'DIRECTION', 'WINDSPEED',
                                         'WINDSPEEDANDDIRECTION'}
    """
    words = re.split(r"[_\s\-]+", meaning.upper())
    words = [w for w in words if w]
    tokens = set(words)
    if len(words) > 1:
        tokens.add("".join(words))
    return tokens


SEMANTIC_JUDGMENT_PROMPT = """You are judging whether two phrases refer to the same concept.

Phrase A: "{guess}"
Phrase B: "{meaning}"

Do these refer to the same concept? Common examples:
- "EV" and "electric_vehicle" → YES (same concept, different form)
- "STAT" and "statistics" → YES
- "STAT" and "status" → YES (both are canonical abbreviations for "status" in different contexts, but STAT as an abbreviation is also used for both; consider the semantic overlap meaningful)
- "QUERY" and "queue" → NO (different concepts)
- "AUTHENTICATION" and "authorization" → NO (related but distinct concepts)
- "OBSERVATION" and "obstacle" → NO
- "TYPE" and "incident_type" → PARTIAL (TYPE alone is vague; incident_type is specific)

Answer with exactly one word: YES, NO, or PARTIAL."""


def classify(result: OpcodeResult,
             provider: Provider | None = None,
             model: str | None = None,
             use_semantic_judgment: bool = False) -> None:
    """Compare model_guesses to current_meaning and set classification.

    Two-pass logic:
      Pass 1 (string tokens): fast, free, catches obvious matches
      Pass 2 (semantic judgment): calls the model to disambiguate when
          the string-token match is ambiguous. Fixes false positives
          (e.g. "TYPE" matching "incident_type" on the TYPE token
          alone) and false negatives (e.g. "ELECTRIC_VEHICLE" vs "EV").

    The semantic pass is opt-in via use_semantic_judgment=True so a
    harness run without it is still valid but less precise.
    """
    if not result.model_guesses:
        result.classification = "BLANK"
        return

    current_tokens = meaning_tokens(result.current_meaning)

    def string_match(guess: str) -> bool:
        g_tokens = meaning_tokens(guess)
        return bool(g_tokens & current_tokens)

    def semantic_match(guess: str) -> str:
        """Returns 'YES', 'NO', 'PARTIAL', or 'ERROR'."""
        if provider is None or model is None:
            return "ERROR"
        prompt = SEMANTIC_JUDGMENT_PROMPT.format(
            guess=guess, meaning=result.current_meaning,
        )
        try:
            response = provider.query(prompt, model, max_tokens=10).strip().upper()
            # Extract first word
            word = re.split(r"\s+", response)[0] if response else ""
            if word in ("YES", "NO", "PARTIAL"):
                return word
            return "ERROR"
        except Exception:
            return "ERROR"

    def guess_matches(guess: str) -> bool:
        if string_match(guess):
            if not use_semantic_judgment:
                return True
            # Confirm with semantic pass to catch false positives
            # (like TYPE matching incident_type on a single token)
            sem = semantic_match(guess)
            if sem == "NO":
                return False  # String-token false positive
            return True  # YES or PARTIAL both count as match
        else:
            if not use_semantic_judgment:
                return False
            # Check if the string-token failure is a false negative
            # (like EV not matching electric_vehicle)
            sem = semantic_match(guess)
            if sem == "YES":
                return True  # String-token false negative recovered
            return False

    first_guess = result.model_guesses[0]
    if guess_matches(first_guess):
        result.classification = "AGREE"
        result.first_guess_matches = True
    elif any(guess_matches(g) for g in result.model_guesses[:3]):
        result.classification = "IN_TOP3"
        result.first_guess_matches = False
    else:
        result.classification = "MISS"
        result.first_guess_matches = False
        result.rename_suggestion = first_guess


# ── Provider abstraction ──────────────────────────────────────────────────

class Provider:
    """Base class for LLM providers."""
    name: str = "base"

    def query(self, prompt: str, model: str, max_tokens: int = 200) -> str:
        raise NotImplementedError

    def parse_json_array(self, response: str) -> list[str]:
        """Extract the first JSON array of strings from a response.

        Tolerates leading/trailing text, code fences, and minor format
        deviations. Returns an empty list on unrecoverable parse errors.
        """
        # Strip code fences if present
        text = re.sub(r"```(?:json)?\s*|\s*```", "", response).strip()
        # Find the first '[' ... ']' span
        match = re.search(r"\[[^\[\]]*\]", text)
        if not match:
            return []
        try:
            arr = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        if not isinstance(arr, list):
            return []
        return [str(x).strip() for x in arr if str(x).strip()]


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self) -> None:
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "anthropic package not installed. pip install anthropic"
            ) from e
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable not set"
            )
        self._client = anthropic.Anthropic(api_key=api_key)

    def query(self, prompt: str, model: str, max_tokens: int = 200) -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate text blocks (there's usually just one)
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts)


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self) -> None:
        try:
            import openai  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "openai package not installed. pip install openai"
            ) from e
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable not set"
            )
        self._client = openai.OpenAI(api_key=api_key)

    def query(self, prompt: str, model: str, max_tokens: int = 200) -> str:
        response = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


PROVIDERS: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


# ── Harness execution ─────────────────────────────────────────────────────

def collect_opcodes(
    filter_namespace: str | None = None,
    filter_opcode: str | None = None,
    flagged_only: bool = False,
) -> list[tuple[str, str, str]]:
    """Gather (namespace, opcode, meaning) tuples from ASD_BASIS."""

    # Opcodes flagged by the first-pass static analysis. When
    # --flagged-only is passed, only these are tested (faster, cheaper
    # than running the full 342).
    FLAGGED = {
        # CONFLICT-level
        "E:OBS", "M:MA", "M:IT", "F:PRO", "F:W", "B:L", "B:X",
        "N:PR", "N:S", "D:Q", "F:Q", "N:Q", "M:A", "O:AUTH",
        "D:RT", "O:TYPE",
        # MATCH-level that might need verification
        "M:RT", "H:HR", "H:BP", "H:RR", "H:TEMP", "G:POS", "V:POS",
        "C:STAT", "D:STAT", "P:STAT", "R:STAT", "Z:TEMP", "W:WIND",
        "X:GRID", "L:SEV", "O:MODE", "X:GEN", "Y:PROMOTE",
        # RELATED-level
        "B:BA", "B:BS", "G:DR", "X:DR", "X:EV", "X:WIND", "Y:STAT",
        "A:AUTH", "G:CONF", "R:DISP", "R:FORM", "O:ESC", "Q:CRIT",
        "Y:PAGE", "Z:CAP", "Q:CONF", "Z:CONF",
    }

    opcodes: list[tuple[str, str, str]] = []
    for ns in sorted(ASD_BASIS.keys()):
        if filter_namespace and ns != filter_namespace:
            continue
        for op, meaning in sorted(ASD_BASIS[ns].items()):
            key = f"{ns}:{op}"
            if filter_opcode and key != filter_opcode:
                continue
            if flagged_only and key not in FLAGGED:
                continue
            opcodes.append((ns, op, meaning))
    return opcodes


def run_harness(
    provider: Provider,
    model: str,
    opcodes: list[tuple[str, str, str]],
    delay_seconds: float = 0.3,
    verbose: bool = False,
    use_semantic_judgment: bool = False,
) -> list[OpcodeResult]:
    results: list[OpcodeResult] = []
    total = len(opcodes)
    for i, (ns, op, meaning) in enumerate(opcodes, start=1):
        result = OpcodeResult(namespace=ns, opcode=op, current_meaning=meaning)
        prompt = generate_prompt(ns, op)

        try:
            response = provider.query(prompt, model)
            guesses = provider.parse_json_array(response)
            result.model_guesses = guesses
        except Exception as e:
            result.error = str(e)[:200]

        classify(
            result,
            provider=provider if use_semantic_judgment else None,
            model=model if use_semantic_judgment else None,
            use_semantic_judgment=use_semantic_judgment,
        )
        results.append(result)

        if verbose:
            marker = {
                "AGREE": "  ",
                "IN_TOP3": "~ ",
                "MISS": "!!",
                "BLANK": "??",
            }.get(result.classification, "  ")
            guesses_str = ", ".join(result.model_guesses[:3]) or "(none)"
            print(
                f"  [{i:3}/{total}] {marker} {result.key:12} "
                f"[{meaning[:40]:40}] -> {guesses_str}",
                file=sys.stderr,
            )

        # Rate limit politeness
        if i < total and delay_seconds > 0:
            time.sleep(delay_seconds)

    return results


# ── Report generation ─────────────────────────────────────────────────────

def write_csv_report(results: list[OpcodeResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "namespace", "opcode", "current_meaning",
            "classification", "first_guess",
            "guess_1", "guess_2", "guess_3",
            "rename_suggestion", "error",
        ])
        for r in results:
            writer.writerow([
                r.namespace, r.opcode, r.current_meaning,
                r.classification,
                r.model_guesses[0] if r.model_guesses else "",
                r.model_guesses[0] if len(r.model_guesses) > 0 else "",
                r.model_guesses[1] if len(r.model_guesses) > 1 else "",
                r.model_guesses[2] if len(r.model_guesses) > 2 else "",
                r.rename_suggestion,
                r.error,
            ])


def print_summary(results: list[OpcodeResult]) -> None:
    total = len(results)
    counts = {"AGREE": 0, "IN_TOP3": 0, "MISS": 0, "BLANK": 0}
    for r in results:
        counts[r.classification] = counts.get(r.classification, 0) + 1

    print()
    print("=" * 72)
    print(f"Readability results: {total} opcodes tested")
    print("=" * 72)
    for cat in ("AGREE", "IN_TOP3", "MISS", "BLANK"):
        n = counts[cat]
        pct = 100.0 * n / total if total else 0
        print(f"  {cat:8} {n:4}  ({pct:5.1f}%)")
    print()

    misses = [r for r in results if r.classification == "MISS"]
    if misses:
        print(f"MISS details ({len(misses)} rename candidates):")
        print()
        for r in misses:
            guesses = " | ".join(r.model_guesses[:3])
            print(f"  {r.key:12} [{r.current_meaning[:40]}]")
            print(f"    Model guessed: {guesses}")
            if r.rename_suggestion:
                print(f"    Rename to:     {r.rename_suggestion}")
            print()


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Empirical opcode readability test against LLM training distributions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--provider", choices=list(PROVIDERS.keys()), default="anthropic",
        help="LLM provider (default: anthropic)",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-6",
        help="Model identifier (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--namespace", default=None,
        help="Test only opcodes in a specific namespace (e.g. 'M')",
    )
    parser.add_argument(
        "--opcode", default=None,
        help="Test only a specific opcode (e.g. 'E:OBS')",
    )
    parser.add_argument(
        "--flagged-only", action="store_true",
        help="Test only the ~50 opcodes flagged by the static analysis",
    )
    parser.add_argument(
        "--output", type=Path,
        default=REPO_ROOT / "reports" / "opcode-readability.csv",
        help="CSV report output path",
    )
    parser.add_argument(
        "--delay", type=float, default=0.3,
        help="Delay between API calls in seconds (default: 0.3)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print per-opcode progress to stderr",
    )
    parser.add_argument(
        "--semantic-judgment", action="store_true",
        help="Use a second model pass to judge whether each guess "
             "semantically matches the current ASD meaning. Fixes false "
             "positives (TYPE matching incident_type on one token) and "
             "false negatives (ELECTRIC_VEHICLE vs EV) at the cost of "
             "~2x API calls. Recommended for canonical reports.",
    )
    args = parser.parse_args()

    # Dry-run mode: if provider can't initialize (no API key), still
    # allow --opcode or --namespace to print the prompt so the user can
    # verify the harness logic without spending tokens.
    provider_class = PROVIDERS[args.provider]
    try:
        provider = provider_class()
    except RuntimeError as e:
        print(f"Provider init failed: {e}", file=sys.stderr)
        print(
            "Dry-run mode: printing prompts that WOULD be sent.",
            file=sys.stderr,
        )
        opcodes = collect_opcodes(
            filter_namespace=args.namespace,
            filter_opcode=args.opcode,
            flagged_only=args.flagged_only,
        )
        for ns, op, meaning in opcodes[:5]:
            print(f"\n--- {ns}:{op} ({meaning}) ---")
            print(generate_prompt(ns, op))
        if len(opcodes) > 5:
            print(f"\n... and {len(opcodes) - 5} more opcodes")
        return 2

    opcodes = collect_opcodes(
        filter_namespace=args.namespace,
        filter_opcode=args.opcode,
        flagged_only=args.flagged_only,
    )
    if not opcodes:
        print("No opcodes matched filters", file=sys.stderr)
        return 1

    print(
        f"Running readability harness: {len(opcodes)} opcodes, "
        f"provider={args.provider}, model={args.model}",
        file=sys.stderr,
    )

    results = run_harness(
        provider, args.model, opcodes,
        delay_seconds=args.delay, verbose=args.verbose,
        use_semantic_judgment=args.semantic_judgment,
    )

    write_csv_report(results, args.output)
    print_summary(results)
    print(f"Full CSV report: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
