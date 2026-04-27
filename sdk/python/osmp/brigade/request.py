"""
ParsedRequest IR — the mise en place of the brigade.

Set up once by the grammar parser; every station reads from this immutable
shared structure to produce its frame proposals. No station mutates it; no
station reaches into another station's pantry.

The IR is rich enough to fully describe any input the protocol can handle.
What's not in the IR cannot be composed — that's the design contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Condition:
    """A threshold/comparison gate ("if X above 130", "while Y below 65")."""
    operator: str   # ">", "<", ">=", "<=", "==", "!="
    value: str      # "130", "65", "1013.5"
    bound_to: str | None = None  # the sensor/opcode the condition gates ("E:TH", "H:HR")


@dataclass(frozen=True)
class SlotValue:
    """A typed parameter slot within a frame.

    Examples:
        SlotValue(key="threshold", value="30", value_type="uint")
        SlotValue(key="coordinates", value="35.7,-122.4", value_type="latlon")
        SlotValue(key="icd", value="J930", value_type="code")
        SlotValue(key="schedule", value="30s", value_type="duration")
    """
    key: str
    value: str
    value_type: str = "string"  # uint, float, code, duration, latlon, time, string


@dataclass(frozen=True)
class Target:
    """A target binding for the @ operator.

    Examples:
        Target(id="DRONE1", kind="drone", source="entity")
        Target(id="BRAVO", kind="node", source="entity")
        Target(id="*", kind="broadcast", source="implicit")
        Target(id="3", kind="gateway", source="entity")
    """
    id: str          # what goes after @
    kind: str        # the entity type ("drone", "node", "*", "patient")
    source: str      # how it was extracted ("entity", "preposition", "implicit")


@dataclass(frozen=True)
class ParsedRequest:
    """The mise en place — what the grammar parser produces for every NL input.

    Stations consume this. Orchestrator reads it. Validator confirms its
    derivatives. It is the single source of truth for what the input means
    structurally.
    """
    raw: str                                  # original NL, unchanged

    # Predicate-argument structure
    verb: str | None = None                   # head action ("move", "report", "stop")
    verb_lemma: str | None = None             # canonical form ("moved" → "move")
    direct_object: str | None = None          # the operand of the verb ("drone 1", "temperature", "payment")
    direct_object_kind: str | None = None     # entity-class of the object ("drone", "sensor", "transaction")

    # Bindings extracted from the input
    targets: tuple[Target, ...] = ()          # in priority order: entity > action+noun > preposition
    slot_values: tuple[SlotValue, ...] = ()   # parametric data extracted by type
    conditions: tuple[Condition, ...] = ()    # threshold/conditional gates

    # Modifiers
    schedule: str | None = None               # "30s", "2AM", "1h"
    authorization_required: bool = False      # presence of "only if X approves" / "requires sign-off"
    is_emergency: bool = False                # "emergency" / "immediate" / "right now"
    is_broadcast: bool = False                # "everyone" / "all nodes" / "broadcast"
    is_query: bool = False                    # "what is" / "?" / "report" verb
    is_passthrough_likely: bool = False       # input doesn't contain protocol-domain content
    is_negated: bool = False                  # contains negation marker — must not compose affirmative
    has_glyph_injection: bool = False         # user typed SAL syntax in NL — refuse to compose

    # Chain structure
    chain_segments: tuple["ParsedRequest", ...] = ()   # for "X then Y", "X and Y" — each segment as own ParsedRequest
    chain_operator: str | None = None         # ";" THEN, "∧" AND, "→" CONDITIONAL

    # Hints to stations (not authoritative — stations decide)
    namespace_hints: tuple[str, ...] = ()     # which namespaces are likely relevant
    domain_hint: str | None = None            # "medical", "uav", "device_control", etc.

    def has_chain(self) -> bool:
        return bool(self.chain_segments)

    def is_single_predicate(self) -> bool:
        return self.verb is not None and not self.has_chain()

    def __str__(self) -> str:
        parts = [f"raw={self.raw!r}"]
        if self.verb:
            parts.append(f"verb={self.verb!r}({self.verb_lemma!r})")
        if self.direct_object:
            parts.append(f"obj={self.direct_object!r}/{self.direct_object_kind}")
        if self.targets:
            parts.append(f"targets={[t.id for t in self.targets]}")
        if self.slot_values:
            parts.append(f"slots={[(s.key, s.value) for s in self.slot_values]}")
        if self.conditions:
            parts.append(f"cond={[(c.operator, c.value) for c in self.conditions]}")
        if self.schedule:
            parts.append(f"schedule={self.schedule!r}")
        if self.authorization_required:
            parts.append("AUTH")
        if self.is_emergency:
            parts.append("EMERGENCY")
        if self.is_broadcast:
            parts.append("BROADCAST")
        if self.is_query:
            parts.append("QUERY")
        if self.namespace_hints:
            parts.append(f"ns={self.namespace_hints}")
        if self.has_chain():
            parts.append(f"chain={len(self.chain_segments)} segs op={self.chain_operator}")
        return f"ParsedRequest({', '.join(parts)})"


@dataclass(frozen=True)
class FrameProposal:
    """What a station expert returns: a candidate SAL frame plus its confidence
    and what the orchestrator needs to know about it."""
    namespace: str           # "R", "E", "H", etc.
    opcode: str              # "STOP", "TH", "HR", etc.
    target: str | None = None
    slot_values: tuple[SlotValue, ...] = ()
    consequence_class: str | None = None   # ↻, ⚠, ⊘
    is_query: bool = False                 # adds ?
    confidence: float = 1.0                # 0.0 (uncertain) to 1.0 (definitive)
    rationale: str = ""                    # why this station proposed this frame

    def assemble(self) -> str:
        """Produce the canonical SAL frame string for this proposal."""
        s = f"{self.namespace}:{self.opcode}"
        if self.consequence_class:
            s += self.consequence_class
        if self.target:
            s += f"@{self.target}"
        if self.is_query:
            s += "?"
        if self.slot_values:
            # Single slot with no key: [value] (e.g., H:ICD[J930])
            # Multi-slot or keyed: [key:value, key:value]
            if len(self.slot_values) == 1 and self.slot_values[0].key in ("", "_"):
                s += f"[{self.slot_values[0].value}]"
            else:
                slots = ",".join(
                    f"{sv.key}:{sv.value}" if sv.key else sv.value
                    for sv in self.slot_values
                )
                s += f"[{slots}]"
        return s
