"""L-station — Logging / Compliance. ALERT, AUDIT, SEND."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class LStation(Station):
    namespace = "L"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # L:ALERT — generic alert (compliance)
        # Only propose if no domain-specific alert namespace fires (orchestrator handles that)
        if req.verb_lemma in ("alert", "warn", "trigger"):
            out.append(FrameProposal(
                namespace="L", opcode="ALERT",
                confidence=0.5,  # lower confidence — defer to H:/U:/W:ALERT in context
                rationale="generic alert (compliance default)",
            ))

        # L:SEND not in v15 ASD — fall through to passthrough for "broadcast"/"rebroadcast"
        # unless something else fires (G:POS@* for "broadcast position", etc.)

        return out
