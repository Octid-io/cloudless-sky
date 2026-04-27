"""A-station — Agentic / OSMP-Native (PING, SUM, etc.)."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class AStation(Station):
    namespace = "A"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        if req.verb_lemma == "ping":
            out.append(FrameProposal(
                namespace="A", opcode="PING",
                target=self._pick_target(req),
                rationale="ping verb",
            ))

        if req.verb_lemma == "summarize" or "summarize" in raw_low:
            # Slot value is the rest of the input
            out.append(FrameProposal(
                namespace="A", opcode="SUM",
                rationale="summarize verb",
            ))

        return out

    def _pick_target(self, req):
        if req.is_broadcast and not req.targets:
            return "*"
        for t in req.targets:
            if t.source == "entity":
                return t.id
        if req.targets:
            return req.targets[0].id
        return None
