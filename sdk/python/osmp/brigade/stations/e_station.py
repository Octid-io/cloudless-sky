"""E-station — Environmental sensor. Read-only by default; bridge-allowed."""
from __future__ import annotations

from ..request import ParsedRequest, FrameProposal, SlotValue
from .base import Station


class EStation(Station):
    namespace = "E"

    # Sensor-name -> E:opcode
    SENSOR_TO_OPCODE = {
        "temperature":  "TH",
        "temp":         "TH",
        "humidity":     "HU",
        "pressure":     "PU",
        "pump":         "PU",   # pump pressure
        "barometric":   "PU",
        "gps":          "GPS",
        "coordinates":  "GPS",
        "air":          "EQ",   # air quality
        "vibration":    "VIB",
        "moisture":     "TH",   # default to TH (or W:WIND for wind moisture)
        "soil":         "TH",   # soil moisture sensors
    }

    # Multi-word sensor names
    PHRASE_TO_OPCODE = {
        "air quality":      "EQ",
        "soil moisture":    "TH",  # weak — could be specific soil sensor
        "temperature humidity": "EQ",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        proposals: list[FrameProposal] = []
        raw_low = req.raw.lower()

        # "read sensor X" with no specific sensor type → default to E:TH (env temp)
        # The receiver knows from context what sensor X measures.
        if (req.verb_lemma in ("read",) and req.direct_object_kind == "sensor"
            and not any(w in raw_low for w in ("temperature", "humidity", "pressure", "wind"))):
            target = self._pick_target(req)
            proposals.append(FrameProposal(
                namespace="E", opcode="TH",
                target=target,
                is_query=True,
                rationale="generic sensor read defaults to E:TH",
            ))

        # Phrase matches first (longer wins)
        for phrase, op in self.PHRASE_TO_OPCODE.items():
            if phrase in raw_low:
                proposals.append(FrameProposal(
                    namespace="E", opcode=op,
                    target=self._pick_target(req),
                    is_query=req.is_query or req.verb_lemma in (None, "report", "show", "get", "read"),
                    rationale=f"phrase '{phrase}' -> E:{op}",
                ))

        # Single-word sensor identification
        # Check direct object first, then any token
        candidates: list[tuple[str, str]] = []
        if req.direct_object:
            obj_words = req.direct_object.lower().split()
            for w in obj_words:
                if w in self.SENSOR_TO_OPCODE:
                    candidates.append((w, self.SENSOR_TO_OPCODE[w]))
        if not candidates:
            # Scan tokens
            for tok in raw_low.split():
                clean = tok.strip(",.!?;:'\"")
                if clean in self.SENSOR_TO_OPCODE:
                    candidates.append((clean, self.SENSOR_TO_OPCODE[clean]))

        for word, op in candidates:
            # Skip if already proposed (phrase match took priority)
            if any(p.opcode == op for p in proposals):
                continue
            # Pump pressure with numeric value: "increase pump pressure to 1013"
            slots: tuple[SlotValue, ...] = ()
            if op == "PU":
                for sv in req.slot_values:
                    if sv.value_type == "float" and sv.key in ("pressure", "pump"):
                        slots = (SlotValue(key="", value=sv.value, value_type="float"),)
                        break
                # Also check for "to N millibar" pattern
                import re as _re
                m = _re.search(r'to\s+(\d+\.?\d*)\s*(?:millibar|mbar|psi|kpa)?', raw_low)
                if m and not slots:
                    slots = (SlotValue(key="", value=m.group(1), value_type="float"),)
            proposals.append(FrameProposal(
                namespace="E", opcode=op,
                target=self._pick_target(req),
                slot_values=slots,
                is_query=req.is_query or (req.verb_lemma in (None, "report", "show", "get", "read", "what") and not slots),
                rationale=f"sensor '{word}' -> E:{op}",
            ))

        return proposals

    def _pick_target(self, req: ParsedRequest) -> str | None:
        if req.is_broadcast and not req.targets:
            return "*"
        for t in req.targets:
            if t.source == "entity":
                return t.id
        if req.targets:
            return req.targets[0].id
        return None
