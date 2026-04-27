"""R-station — Robotic / Physical Agent. The busiest station.

Handles all actuation: stop, start, open, close, lock, move, return, peripherals.
Default consequence class is ↻ REVERSIBLE (R:ESTOP is the sole exception).
"""
from __future__ import annotations

from ..request import ParsedRequest, FrameProposal, SlotValue
from .base import Station


class RStation(Station):
    namespace = "R"

    # verb-lemma -> R:opcode mapping
    # Note: only opcodes that EXIST in v15 ASD are mapped here.
    # R:OPEN, R:LOCK, R:CLOSE, R:START don't exist in v15 — those map to R:STOP
    # (semantic equivalence) where reasonable, or fall through to passthrough.
    VERB_TO_OPCODE = {
        "stop":     "STOP",
        "halt":     "STOP",
        "cease":    "STOP",
        "block":    "STOP",
        "close":    "STOP",     # close valve = stop flow
        "lock":     "STOP",     # lock door = block (no R:LOCK in v15)
        "move":     "MOV",
        "go":       "MOV",      # "go to X" → R:MOV@X
        "navigate": "MOV",
        "fly":      "MOV",
        "return":   "RTH",
        "rtb":      "RTH",
        "rth":      "RTH",
    }

    # direct-object-kind -> R-peripheral opcode (when verb is wrapper-class
    # like "turn on", "activate", "enable")
    PERIPHERAL_OBJECT_TO_OPCODE = {
        "camera":     "CAM",
        "microphone": "MIC",
        "speaker":    "SPKR",
        "flashlight": "TORCH",
        "torch":      "TORCH",
        "haptic":     "HAPTIC",
        "vibration":  "VIBE",
        "wifi":       "WIFI",
        "bluetooth":  "BT",
        "gps":        "GPS",
        "screen":     "DISP",
        "display":    "DISP",
        "accelerometer": "ACCEL",
    }

    # Wrapper verbs that hand off to peripheral object lookup
    PERIPHERAL_VERBS = {"turn", "activate", "enable", "engage", "start"}

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        proposals: list[FrameProposal] = []

        # Emergency override: R:ESTOP (no glyph, broadcast implicit)
        if req.is_emergency and req.verb_lemma in (None, "stop", "halt", "cease", "block", "kill", "shutdown", "shut"):
            proposals.append(FrameProposal(
                namespace="R", opcode="ESTOP",
                rationale="emergency marker + stop verb (or no verb)",
            ))
            return proposals

        # Direct verb-to-opcode mapping (stop/start/open/close/lock/move/return)
        if req.verb_lemma in self.VERB_TO_OPCODE:
            opcode = self.VERB_TO_OPCODE[req.verb_lemma]
            target = self._pick_target(req)
            proposals.append(FrameProposal(
                namespace="R", opcode=opcode,
                target=target,
                slot_values=self._slots_for_opcode(opcode, req),
                consequence_class="\u21ba",  # ↻ REVERSIBLE (default for R)
                is_query=False,
                rationale=f"verb '{req.verb_lemma}' -> R:{opcode}",
            ))

        # Peripheral activation: "turn on the camera", "activate haptic"
        if req.verb_lemma in self.PERIPHERAL_VERBS and req.direct_object:
            obj_word = req.direct_object.lower().split()[-1]  # "the camera" -> "camera"
            if obj_word in self.PERIPHERAL_OBJECT_TO_OPCODE:
                opcode = self.PERIPHERAL_OBJECT_TO_OPCODE[obj_word]
                target = self._pick_target(req)
                proposals.append(FrameProposal(
                    namespace="R", opcode=opcode,
                    target=target,
                    consequence_class="\u21ba",
                    rationale=f"peripheral activation '{obj_word}' -> R:{opcode}",
                ))

        # Direct-object-only peripheral (no verb, e.g., "haptic feedback")
        if req.verb_lemma is None and req.direct_object_kind == "peripheral":
            obj_word = req.direct_object.lower().split()[-1]
            if obj_word in self.PERIPHERAL_OBJECT_TO_OPCODE:
                opcode = self.PERIPHERAL_OBJECT_TO_OPCODE[obj_word]
                proposals.append(FrameProposal(
                    namespace="R", opcode=opcode,
                    consequence_class="\u21ba",
                    rationale=f"nominal peripheral '{obj_word}' -> R:{opcode}",
                ))

        # Specific phrase patterns
        raw_low = req.raw.lower()
        if "haptic feedback" in raw_low or "vibrate" in raw_low and not proposals:
            proposals.append(FrameProposal(
                namespace="R", opcode="HAPTIC", consequence_class="\u21ba",
                rationale="haptic feedback phrase",
            ))

        # RTH from any "rtb" / "rth" / "return to base" / "return home" / "swarm RTB" pattern
        if not any(p.opcode == "RTH" for p in proposals):
            if "rtb" in raw_low or "rth" in raw_low or "return to base" in raw_low or "return home" in raw_low:
                proposals.append(FrameProposal(
                    namespace="R", opcode="RTH",
                    consequence_class="\u21ba",
                    confidence=2.0,
                    rationale="rtb/rth/return phrase",
                ))

        # FORM — swarm formation: "form swarm X with spacing N" OR "form column with spacing N"
        if req.verb_lemma == "form" and ("swarm" in raw_low or "formation" in raw_low
                                           or any(s in raw_low for s in ("wedge", "column", "line", "vee", "diamond", "echelon"))):
            slots = []
            # Extract formation type (wedge, line, vee, column)
            for shape in ("wedge", "line", "vee", "column", "diamond", "echelon"):
                if shape in raw_low:
                    slots.append(SlotValue(key="", value=shape, value_type="string"))
                    break
            # Extract spacing
            for sv in req.slot_values:
                if sv.key == "spacing":
                    slots.append(SlotValue(key="", value=sv.value, value_type="float"))
                    break
            proposals.append(FrameProposal(
                namespace="R", opcode="FORM",
                consequence_class="\u21ba",
                slot_values=tuple(slots),
                rationale="swarm formation",
            ))

        return proposals

    def _pick_target(self, req: ParsedRequest) -> str | None:
        """Pick the most appropriate target for an R-namespace action."""
        if req.is_broadcast and not req.targets:
            return "*"
        if req.targets:
            # Prefer entity-source targets
            for t in req.targets:
                if t.source == "entity":
                    return t.id
            for t in req.targets:
                if t.source == "action_verb":
                    return t.id
            return req.targets[0].id
        return None

    def _slots_for_opcode(self, opcode: str, req: ParsedRequest) -> tuple[SlotValue, ...]:
        """Return slot values relevant to this opcode."""
        if opcode == "MOV":
            # MOV takes coordinates as a slot value
            for sv in req.slot_values:
                if sv.value_type == "latlon":
                    return (SlotValue(key="", value=sv.value, value_type="latlon"),)
            # Or formation params
            for sv in req.slot_values:
                if sv.key in ("formation", "spacing"):
                    return (sv,)
        return ()
