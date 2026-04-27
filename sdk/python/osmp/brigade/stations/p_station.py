"""P-station — Procedure / Maintenance compliance. CODE, DEVICE, GUIDE, PART, STAT, STEP."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class PStation(Station):
    namespace = "P"

    KEYWORD_MAP = {
        "maintenance code":   "CODE",
        "compliance code":    "CODE",
        "device class":       "DEVICE",
        "procedure guide":    "GUIDE",
        "part reference":     "PART",
        "completion status":  "STAT",
        "step index":         "STEP",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        for phrase, op in sorted(self.KEYWORD_MAP.items(), key=lambda kv: -len(kv[0])):
            if phrase in raw_low:
                out.append(FrameProposal(
                    namespace="P", opcode=op,
                    rationale=f"procedure phrase '{phrase}'",
                ))
                break
        return out
