"""J-station — Cognitive task / orchestration. HANDOFF, DECOMP."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class JStation(Station):
    namespace = "J"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        if "hand off" in raw_low or "handoff" in raw_low or req.verb_lemma == "handoff" or "hand this" in raw_low:
            target = None
            for t in req.targets:
                if t.source == "entity" or t.source == "preposition":
                    target = t.id
                    break
            out.append(FrameProposal(
                namespace="J", opcode="HANDOFF",
                target=target,
                rationale="handoff",
            ))

        return out
