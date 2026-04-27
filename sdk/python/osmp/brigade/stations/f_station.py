"""F-station — Flow control. AV (authorization), PRCD (proceed), QRY, WAIT."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class FStation(Station):
    namespace = "F"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        if "flow authorization" in raw_low or "authorization to proceed" in raw_low:
            out.append(FrameProposal(namespace="F", opcode="AV", rationale="flow auth"))
        if "proceed" in raw_low and req.verb_lemma in (None, "may", "request"):
            out.append(FrameProposal(namespace="F", opcode="PRCD", rationale="proceed protocol"))
        if "wait" in raw_low or "pause" in raw_low:
            out.append(FrameProposal(namespace="F", opcode="WAIT", confidence=2.5, rationale="wait/pause"))
        return out
