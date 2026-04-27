"""M-station — Municipal / Routing. EVA, RTE."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class MStation(Station):
    namespace = "M"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        if req.verb_lemma == "evacuate" or "evacuation" in raw_low or "evacuate" in raw_low:
            out.append(FrameProposal(
                namespace="M", opcode="EVA",
                target="*" if req.is_broadcast else None,
                rationale="evacuate verb",
            ))

        if "route" in raw_low and ("emergency" in raw_low or "incident" in raw_low):
            out.append(FrameProposal(
                namespace="M", opcode="RTE",
                rationale="emergency route",
            ))

        return out
