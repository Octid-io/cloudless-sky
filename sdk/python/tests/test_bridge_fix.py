# Last run: 2026-04-24, 4 passed in 0.26s (pytest-9.0.3, Python 3.14.3).
#   tests/test_bridge_fix.py::test_t1_nl_annotation_roundtrip_ascii_unicode_byte_identical PASSED
#   tests/test_bridge_fix.py::test_t2_validator_parity_ascii_unicode_equivalent_issue_sets PASSED
#   tests/test_bridge_fix.py::test_t3_macro_chain_ascii_arrow_validates_against_asd PASSED
#   tests/test_bridge_fix.py::test_t4_unicode_corpus_byte_identical_to_golden PASSED
"""
Bridge-fix unit tests — T1..T4

Covers the 2026-04-24 bridge fix that added ASCII `->` as a frame-boundary
operator alongside the Unicode `→` in osmp/protocol.py and legacy src/osmp.py.

- T1: NL annotation round-trip. ASCII `->` and Unicode `→` produce byte-
      identical NL output; "then" appears in both.
- T2: Validator parity. validate_composition(...) on ASCII-arrow and
      Unicode-arrow forms produces equivalent issue sets (same rules, same
      severities, same frame identifiers).
- T3: Macro chain with ASCII arrow. Registering a MacroTemplate whose
      chain_template uses `->` validates against an ASD containing the
      referenced opcodes. Pre-fix, the chain was treated as one frame.
- T4: Regression on Unicode corpus. 10 Unicode-arrow SAL frames decode to
      byte-identical golden NL outputs, ensuring the ASCII-arrow addition
      did not regress Unicode handling.

Run:  pytest tests/test_bridge_fix.py -v
"""
from __future__ import annotations

import os
import sys

# Make the sdk/python source tree importable without install.
_SDK_PYTHON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SDK_PYTHON not in sys.path:
    sys.path.insert(0, _SDK_PYTHON)

from osmp.protocol import (
    AdaptiveSharedDictionary,
    MacroRegistry,
    MacroTemplate,
    SALDecoder,
    validate_composition,
)


# ---------------------------------------------------------------------------
# T1 — NL annotation round-trip
# ---------------------------------------------------------------------------

def test_t1_nl_annotation_roundtrip_ascii_unicode_byte_identical():
    """ASCII `->` and Unicode `→` must decode to byte-identical NL strings,
    both containing the operator word 'then'."""
    decoder = SALDecoder()
    ascii_out = decoder.decode_natural_language("H:HR>130->U:ALERT")
    unicode_out = decoder.decode_natural_language("H:HR>130\u2192U:ALERT")

    assert "then" in ascii_out, f"ASCII arrow output missing 'then': {ascii_out!r}"
    assert "then" in unicode_out, f"Unicode arrow output missing 'then': {unicode_out!r}"
    assert ascii_out == unicode_out, (
        f"ASCII-vs-Unicode divergence:\n  ascii={ascii_out!r}\n  uni  ={unicode_out!r}"
    )


# ---------------------------------------------------------------------------
# T2 — Validator parity
# ---------------------------------------------------------------------------

def _issue_key(issue):
    # Ignore .message text (may vary on arrow form); compare rule + severity + frame.
    return (issue.rule, issue.severity, issue.frame)


def test_t2_validator_parity_ascii_unicode_equivalent_issue_sets():
    """validate_composition on `A:BAR->B:QUX` and `A:BAR→B:QUX` must fire
    the same rules with the same severities on the same frames."""
    ascii_result = validate_composition("A:BAR->B:QUX")
    unicode_result = validate_composition("A:BAR\u2192B:QUX")

    ascii_keys = sorted(_issue_key(i) for i in ascii_result.issues)
    unicode_keys = sorted(_issue_key(i) for i in unicode_result.issues)
    assert ascii_keys == unicode_keys, (
        f"Issue-set divergence:\n  ascii={ascii_keys}\n  uni  ={unicode_keys}"
    )


# ---------------------------------------------------------------------------
# T3 — Macro chain with ASCII arrow
# ---------------------------------------------------------------------------

def test_t3_macro_chain_ascii_arrow_validates_against_asd():
    """A macro whose chain_template uses the ASCII arrow must validate
    successfully when the referenced opcodes exist in the ASD. Pre-fix,
    the whole string was parsed as one frame and failed lookup."""
    asd = AdaptiveSharedDictionary()
    # Add test opcodes A:BAR and B:QUX to the ASD for this macro.
    asd.apply_delta(
        "A", "BAR", "test opcode A:BAR",
        AdaptiveSharedDictionary.UpdateMode.ADDITIVE, "test",
    )
    asd.apply_delta(
        "B", "QUX", "test opcode B:QUX",
        AdaptiveSharedDictionary.UpdateMode.ADDITIVE, "test",
    )
    registry = MacroRegistry(asd)
    template = MacroTemplate(
        macro_id="TEST:MACRO",
        chain_template="A:BAR->B:QUX",
        slots=(),
        description="Test macro using ASCII arrow frame separator.",
    )
    # Pre-fix: "A:BAR->B:QUX" parsed as single frame "A:BAR->B:QUX", ASD lookup
    # for namespace "A" opcode "BAR->B:QUX" would fail → ValueError.
    # Post-fix: split into ["A:BAR", "B:QUX"] → both lookups succeed.
    registry.register(template)  # must not raise

    # Verify the template is registered.
    assert "TEST:MACRO" in registry._macros


# ---------------------------------------------------------------------------
# T4 — Regression on Unicode corpus
# ---------------------------------------------------------------------------

# Golden dict: Unicode-arrow SAL frames → expected NL decoder output.
# Captured 2026-04-24 against sdk/python/osmp/protocol.py (post-fix).
# If any of these fail byte-equal, the bridge fix regressed Unicode handling.
T4_GOLDEN = {
    "H:HR>130\u2192U:ALERT":
        "(clinical) [clinical] heart rate above 130 then [operator] urgent operator alert",
    "H:HR>130\u2227H:SPO2<90":
        "[clinical] heart rate above 130 and [clinical] oxygen saturation below 90",
    "H:HR>130\u2228H:SPO2<90":
        "[clinical] heart rate above 130 or [clinical] oxygen saturation below 90",
    "A:ACK\u2194U:CONFIRM":
        "(protocol) [protocol] positive acknowledgment iff [operator] request human confirmation",
    "H:VITALS\u2192U:ALERT":
        "(clinical) [clinical] composite vitals status then [operator] urgent operator alert",
    "H:SPO2<90\u2192U:ALERT":
        "(clinical) [clinical] oxygen saturation below 90 then [operator] urgent operator alert",
    "B:FIRE\u2192M:EVA":
        "(building) [building] FIRE then [emergency] evacuation",
    "W:WIND>60\u2192M:EVA":
        "(weather) [weather] wind speed and direction above 60 then [emergency] evacuation",
    "X:STORE<10\u2192U:ESCALATE":
        "(energy) [energy] storage state below 10 then [operator] escalate to human decision maker",
    "E:GPS\u2192U:ALERT":
        "(sensor) [sensor] gps coordinates then [operator] urgent operator alert",
}


def test_t4_unicode_corpus_byte_identical_to_golden():
    """Decode 10 Unicode-arrow SAL frames; each NL output must be byte-
    identical to the golden string. Catches regression in Unicode handling
    introduced by the ASCII-arrow frame-split fix."""
    decoder = SALDecoder()
    mismatches = []
    for sal, expected in T4_GOLDEN.items():
        actual = decoder.decode_natural_language(sal)
        if actual != expected:
            mismatches.append((sal, expected, actual))
    assert not mismatches, (
        "Unicode decoder regression(s):\n"
        + "\n".join(f"  {sal!r}\n    expected={exp!r}\n    actual  ={act!r}"
                    for sal, exp, act in mismatches)
    )
