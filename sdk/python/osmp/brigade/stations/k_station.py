"""K-station — Commerce / Financial."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class KStation(Station):
    namespace = "K"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        if req.verb_lemma == "pay" or "payment" in raw_low or "transfer" in raw_low:
            out.append(FrameProposal(
                namespace="K", opcode="PAY",
                confidence=2.0 if "payment" in raw_low else 1.0,
                rationale="payment intent",
            ))
        if "order" in raw_low and "financial" in raw_low:
            out.append(FrameProposal(namespace="K", opcode="ORD", rationale="financial order"))
        return out
