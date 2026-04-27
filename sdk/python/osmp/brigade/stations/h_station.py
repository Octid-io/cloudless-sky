"""H-station — Health / Clinical."""
from __future__ import annotations

from ..request import ParsedRequest, FrameProposal, SlotValue
from .base import Station


class HStation(Station):
    namespace = "H"

    PHRASE_TO_OPCODE = {
        "blood pressure":   "BP",
        "heart rate":       "HR",
        "oxygen level":     "SPO2",
        "oxygen saturation": "SPO2",
        "oxygen sat":       "SPO2",
        "oxygen drops":     "SPO2",
        "spo2":             "SPO2",
        "all vitals":       "VITALS",
        "vital signs":      "VITALS",
        "vitals check":     "VITALS",
        "body temperature": "TEMP",
        "body temp":        "TEMP",
        "patient pulse":    "HR",
        "patient temperature": "TEMP",
        "respiratory rate": "RR",
    }
    # High-confidence phrases that should win over generic E:TH/etc.
    HIGH_CONF_PHRASES = {"body temperature", "body temp", "patient temperature", "oxygen drops"}

    SINGLE_WORD = {
        "vitals": "VITALS",
        "pulse":  "HR",
        "bp":     "BP",
        "hr":     "HR",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        proposals: list[FrameProposal] = []
        raw_low = req.raw.lower()

        # ICD code parametric — patient diagnoses
        for sv in req.slot_values:
            if sv.value_type == "code" and sv.key == "icd":
                proposals.append(FrameProposal(
                    namespace="H", opcode="ICD",
                    slot_values=(SlotValue(key="", value=sv.value, value_type="code"),),
                    target=self._pick_target(req),
                    rationale=f"ICD code {sv.value}",
                ))

        # Article-tolerant phrase matching: also try with " the "/" a "/" an " removed
        # (catches "body the temperature" → "body temperature")
        raw_dearticled = " ".join(w for w in raw_low.split() if w not in ("the", "a", "an"))

        # Phrase matching (longest first)
        for phrase, op in sorted(self.PHRASE_TO_OPCODE.items(), key=lambda kv: -len(kv[0])):
            if phrase in raw_low or phrase in raw_dearticled:
                conf = 2.5 if phrase in self.HIGH_CONF_PHRASES else 1.0
                proposals.append(FrameProposal(
                    namespace="H", opcode=op,
                    target=self._pick_target(req),
                    confidence=conf,
                    is_query=req.is_query or req.verb_lemma in (None, "report", "show", "give", "check", "what"),
                    rationale=f"phrase '{phrase}' -> H:{op}",
                ))
                break  # take first phrase match

        # Single-word fallback
        if not any(p.opcode in ("BP", "HR", "VITALS", "SPO2", "TEMP", "RR") for p in proposals):
            for w in raw_low.split():
                clean = w.strip(",.!?;:'\"")
                if clean in self.SINGLE_WORD:
                    proposals.append(FrameProposal(
                        namespace="H", opcode=self.SINGLE_WORD[clean],
                        target=self._pick_target(req),
                        is_query=req.is_query,
                        rationale=f"single-word '{clean}' -> H:{self.SINGLE_WORD[clean]}",
                    ))
                    break

        # Casualty report
        if "casualty" in raw_low or "casrep" in raw_low:
            proposals.append(FrameProposal(
                namespace="H", opcode="CASREP",
                target=self._pick_target(req),
                rationale="casualty report",
            ))

        # Alert (clinical context — only if conditions or H-namespace already in play)
        if req.verb_lemma in ("alert", "warn", "notify") or "alert" in raw_low:
            # Only propose H:ALERT if the sensing namespace is also H (vitals chain)
            if any(p.namespace == "H" and p.opcode in ("BP", "HR", "SPO2", "TEMP", "VITALS")
                   for p in proposals):
                proposals.append(FrameProposal(
                    namespace="H", opcode="ALERT",
                    rationale="clinical alert (H sensing context)",
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
