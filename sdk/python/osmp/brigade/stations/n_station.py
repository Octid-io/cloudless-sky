"""N-station — Network / Routing. Status, config, backup, query/discover, relay."""
from __future__ import annotations

from ..request import ParsedRequest, FrameProposal, SlotValue
from .base import Station


class NStation(Station):
    namespace = "N"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        proposals: list[FrameProposal] = []
        raw_low = req.raw.lower()

        # CFG — config update or set/modify/change/adjust
        if (req.verb_lemma in ("set", "configure", "update", "modify", "change", "adjust")
            or "config" in raw_low or "configuration" in raw_low or "settings" in raw_low):
            slots = ()
            for sv in req.slot_values:
                if sv.value_type == "float" and sv.key not in ("at_time",):
                    slots = (sv,)
                    break
            proposals.append(FrameProposal(
                namespace="N", opcode="CFG",
                slot_values=slots,
                target=self._pick_target(req),
                rationale="config verb or config keyword",
            ))

        # BK — backup
        if (req.verb_lemma in ("back", "backup") or "back up" in raw_low):
            target = None
            # Time anchor as target: "at 2am"
            for sv in req.slot_values:
                if sv.value_type == "time":
                    target = sv.value
                    break
            proposals.append(FrameProposal(
                namespace="N", opcode="BK",
                target=target,
                rationale="backup verb",
            ))

        # STS — status query
        if ("status" in raw_low or "uptime" in raw_low or "alive" in raw_low or "online" in raw_low):
            target = self._pick_target(req)
            proposals.append(FrameProposal(
                namespace="N", opcode="STS",
                target=target,
                is_query=req.is_query or True,
                rationale="status keyword",
            ))

        # Q — query/discover
        if req.verb_lemma == "discover" or "discover" in raw_low:
            proposals.append(FrameProposal(
                namespace="N", opcode="Q",
                target="*" if (req.is_broadcast or "peers" in raw_low or "all" in raw_low) else None,
                rationale="discover verb",
            ))

        # RLY — relay
        if "relay" in raw_low and req.verb_lemma in (None, "find", "what", "where", "show", "report", "get"):
            proposals.append(FrameProposal(
                namespace="N", opcode="RLY",
                is_query=True,
                rationale="relay query",
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
