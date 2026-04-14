"""
Registered Macro Architecture Tests (Claims 37-39, 45)
======================================================

Tests for the MacroRegistry, MacroTemplate, and SlotDefinition classes
implementing the pre-validated SAL instruction chain template architecture.

Patent: OSMP-001-UTIL Claims 37-39, 45
License: Apache 2.0
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.protocol import (  # noqa: E402
    AdaptiveSharedDictionary,
    MacroRegistry,
    MacroTemplate,
    SlotDefinition,
)


# ── Registration and Lookup ──────────────────────────────────────────────


class TestMacroRegistration:
    """Claim 37: registering a pre-validated multi-step SAL instruction
    chain template as a single callable entry."""

    def test_register_and_lookup(self):
        reg = MacroRegistry()
        template = MacroTemplate(
            macro_id="TEST:SIMPLE",
            chain_template="H:HR[bpm:{bpm}]",
            slots=(SlotDefinition("bpm", "uint"),),
            description="Simple heart rate macro",
        )
        reg.register(template)
        result = reg.lookup("TEST:SIMPLE")
        assert result is not None
        assert result.macro_id == "TEST:SIMPLE"

    def test_lookup_nonexistent_returns_none(self):
        reg = MacroRegistry()
        assert reg.lookup("DOES:NOT:EXIST") is None

    def test_register_validates_opcodes_in_asd(self):
        reg = MacroRegistry()
        template = MacroTemplate(
            macro_id="BAD:OPCODE",
            chain_template="Z:NONEXISTENT[val:{v}]",
            slots=(SlotDefinition("v", "string"),),
            description="Uses a nonexistent opcode",
        )
        with pytest.raises(ValueError, match="not found in ASD"):
            reg.register(template)

    def test_register_validates_slot_placeholders(self):
        reg = MacroRegistry()
        template = MacroTemplate(
            macro_id="BAD:SLOTS",
            chain_template="H:HR[bpm:{bpm}]",
            slots=(
                SlotDefinition("bpm", "uint"),
                SlotDefinition("extra", "string"),  # no placeholder
            ),
            description="Extra slot with no placeholder",
        )
        with pytest.raises(ValueError, match="no matching placeholder"):
            reg.register(template)

    def test_register_validates_missing_slot_definition(self):
        reg = MacroRegistry()
        template = MacroTemplate(
            macro_id="BAD:MISSING",
            chain_template="H:HR[bpm:{bpm}]\u2227H:SPO2[o2:{spo2}]",
            slots=(SlotDefinition("bpm", "uint"),),  # missing spo2
            description="Missing slot definition",
        )
        with pytest.raises(ValueError, match="no matching SlotDefinition"):
            reg.register(template)

    def test_list_macros(self):
        reg = MacroRegistry()
        t1 = MacroTemplate("A:ONE", "A:ACK[m:{m}]",
                           (SlotDefinition("m", "string"),), "first")
        t2 = MacroTemplate("A:TWO", "A:NACK[m:{m}]",
                           (SlotDefinition("m", "string"),), "second")
        reg.register(t1)
        reg.register(t2)
        macros = reg.list_macros()
        assert len(macros) == 2
        ids = {m.macro_id for m in macros}
        assert ids == {"A:ONE", "A:TWO"}


# ── Expansion and Slot-Fill ──────────────────────────────────────────────


class TestMacroExpansion:
    """Claim 37: invoking the registered macro entry by dictionary lookup
    and slot-fill, producing the complete multi-step instruction chain."""

    def test_expand_simple(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:HR", "H:HR[bpm:{bpm}]",
            (SlotDefinition("bpm", "uint"),), "heart rate",
        ))
        result = reg.expand("TEST:HR", {"bpm": 72})
        assert result == "H:HR[bpm:72]"

    def test_expand_multi_slot_chain(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:ENV", "E:TH[t:{temp},h:{hum}]\u2227E:PU[p:{press}]",
            (SlotDefinition("temp", "float"),
             SlotDefinition("hum", "float"),
             SlotDefinition("press", "float")),
            "environment",
        ))
        result = reg.expand("TEST:ENV", {"temp": 22.5, "hum": 65.0, "press": 1013.25})
        assert result == "E:TH[t:22.5,h:65.0]\u2227E:PU[p:1013.25]"

    def test_expand_medevac_embodiment(self):
        """Spec Section 11 canonical embodiment."""
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "MEDEVAC",
            "H:ICD[{dx_code}]\u2192H:CASREP\u2227M:EVA@{target}",
            (SlotDefinition("dx_code", "string", namespace="H"),
             SlotDefinition("target", "string")),
            "Clinical MEDEVAC",
        ))
        result = reg.expand("MEDEVAC", {"dx_code": "J930", "target": "MED1"})
        assert result == "H:ICD[J930]\u2192H:CASREP\u2227M:EVA@MED1"

    def test_expand_missing_slot_raises(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:TWO", "H:HR[bpm:{bpm}]\u2227H:SPO2[o2:{spo2}]",
            (SlotDefinition("bpm", "uint"),
             SlotDefinition("spo2", "uint")),
            "two slots",
        ))
        with pytest.raises(ValueError, match="missing slot values"):
            reg.expand("TEST:TWO", {"bpm": 72})  # missing spo2

    def test_expand_nonexistent_macro_raises(self):
        reg = MacroRegistry()
        with pytest.raises(KeyError, match="Macro not found"):
            reg.expand("NOPE", {"x": 1})

    def test_no_composition_validation_on_expansion(self):
        """Claim 37: 'without applying the composition rules of claim 34
        to the chain structure.' Macro expansion does NOT run
        validate_composition on the expanded chain."""
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:CHAIN", "A:ACK\u2227A:NACK",
            (), "no slots",
        ))
        # This should succeed without composition validation
        result = reg.expand("TEST:CHAIN", {})
        assert result == "A:ACK\u2227A:NACK"


# ── Compact and Expanded Wire Format ────────────────────────────────────


class TestMacroWireFormat:
    """Claim 38: compact vs expanded transmission format."""

    def test_encode_compact(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:HR", "H:HR[bpm:{bpm}]",
            (SlotDefinition("bpm", "uint"),), "heart rate",
        ))
        result = reg.encode_compact("TEST:HR", {"bpm": 72})
        assert result == "A:MACRO[TEST:HR]:bpm[72]"

    def test_encode_expanded(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:HR", "H:HR[bpm:{bpm}]",
            (SlotDefinition("bpm", "uint"),), "heart rate",
        ))
        result = reg.encode_expanded("TEST:HR", {"bpm": 72})
        assert result == "H:HR[bpm:72]"

    def test_compact_preserves_slot_order(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:MULTI", "E:TH[t:{t}]\u2227E:PU[p:{p}]",
            (SlotDefinition("t", "float"), SlotDefinition("p", "float")),
            "multi",
        ))
        result = reg.encode_compact("TEST:MULTI", {"t": 22.5, "p": 1013.0})
        assert ":t[22.5]" in result
        assert ":p[1013.0]" in result
        # Slot order follows definition order
        assert result.index(":t[") < result.index(":p[")

    def test_encode_with_annotation(self):
        """Claim 39: expansion annotation for monitoring."""
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:ANN", "A:ACK[m:{m}]",
            (SlotDefinition("m", "string"),), "annotated",
        ))
        result = reg.encode_with_annotation("TEST:ANN", {"m": "hello"})
        assert "A:MACRO[TEST:ANN]" in result
        assert "_EXP[A:ACK[m:hello]]" in result


# ── Consequence Class Inheritance ────────────────────────────────────────


class TestConsequenceClassInheritance:
    """Claim 45: consequence class of the expanded chain is inherited
    by the compact macro invocation."""

    def test_no_r_namespace_no_cc(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:NOCC", "H:HR[bpm:{bpm}]",
            (SlotDefinition("bpm", "uint"),), "no R namespace",
        ))
        assert reg.inherited_consequence_class("TEST:NOCC") is None

    def test_reversible_inherited(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:REV", "R:MOV@BOT1\u21ba",
            (), "reversible R",
        ))
        assert reg.inherited_consequence_class("TEST:REV") == "\u21ba"

    def test_hazardous_inherited(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:HAZ", "I:\u00a7\u2192R:DRVE@UAV1\u26a0",
            (), "hazardous R",
        ))
        assert reg.inherited_consequence_class("TEST:HAZ") == "\u26a0"

    def test_highest_cc_wins(self):
        """Mixed chain: REVERSIBLE + HAZARDOUS = HAZARDOUS (highest)."""
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:MIX", "R:MOV@BOT1\u21ba\u2227I:\u00a7\u2192R:DPTH@UUV1\u26a0",
            (), "mixed CC",
        ))
        cc = reg.inherited_consequence_class("TEST:MIX")
        assert cc == "\u26a0"  # HAZARDOUS > REVERSIBLE

    def test_compact_carries_inherited_cc(self):
        reg = MacroRegistry()
        reg.register(MacroTemplate(
            "TEST:CCWIRE", "R:MOV@{target}\u21ba",
            (SlotDefinition("target", "string"),), "CC on wire",
        ))
        compact = reg.encode_compact("TEST:CCWIRE", {"target": "BOT1"})
        assert compact.endswith("\u21ba")


# ── Corpus Loading ───────────────────────────────────────────────────────


class TestCorpusLoading:
    """Loading macro definitions from a JSON corpus file."""

    CORPUS_PATH = REPO_ROOT / "mdr" / "meshtastic" / "meshtastic-macros.json"

    def test_load_meshtastic_corpus(self):
        reg = MacroRegistry()
        count = reg.load_corpus(self.CORPUS_PATH)
        assert count == 16

    def test_all_macros_registered(self):
        reg = MacroRegistry()
        reg.load_corpus(self.CORPUS_PATH)
        macros = reg.list_macros()
        ids = {m.macro_id for m in macros}
        expected = {
            "MESH:DEV", "MESH:ENV", "MESH:AQ", "MESH:PWR", "MESH:HLTH",
            "MESH:STAT", "MESH:POS", "MESH:NODE", "MESH:ACK", "MESH:ALRT",
            "MESH:TRACE", "MESH:WPT", "MESH:TALRT", "MESH:BATLO", "MESH:NOFF",
            "MEDEVAC",
        }
        assert ids == expected

    def test_mesh_dev_expands(self):
        reg = MacroRegistry()
        reg.load_corpus(self.CORPUS_PATH)
        result = reg.expand("MESH:DEV", {
            "battery_level": 87,
            "voltage": 3.72,
            "channel_util": 12.5,
            "air_util": 3.2,
            "uptime": 3600,
        })
        assert "X:STORE[bat:87]" in result
        assert "X:VOLT[v:3.72]" in result

    def test_mesh_hlth_expands(self):
        reg = MacroRegistry()
        reg.load_corpus(self.CORPUS_PATH)
        result = reg.expand("MESH:HLTH", {
            "heart_bpm": 72,
            "spO2": 98,
            "temperature": 36.6,
        })
        assert "H:HR[bpm:72]" in result
        assert "H:SPO2[o2:98]" in result

    def test_medevac_embodiment(self):
        """Spec Section 11 canonical embodiment from corpus."""
        reg = MacroRegistry()
        reg.load_corpus(self.CORPUS_PATH)
        result = reg.expand("MEDEVAC", {"dx_code": "J930", "target": "MED1"})
        assert result == "H:ICD[J930]\u2192H:CASREP\u2227M:EVA@MED1"

    def test_compact_vs_expanded_byte_savings(self):
        """Compact should be smaller than NL for non-trivial macros."""
        reg = MacroRegistry()
        reg.load_corpus(self.CORPUS_PATH)
        expanded = reg.expand("MESH:DEV", {
            "battery_level": 87, "voltage": 3.72,
            "channel_util": 12.5, "air_util": 3.2, "uptime": 3600,
        })
        nl = ("Report battery 87%, voltage 3.72V, channel utilization "
              "12.5%, TX airtime 3.2%, uptime 3600s")
        assert len(expanded.encode("utf-8")) < len(nl.encode("utf-8"))
