"""O-station — Operational Context / Environment. Bandwidth, channel, mode, posture, link, mesh, etc."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class OStation(Station):
    namespace = "O"

    KEYWORD_MAP = {
        "bandwidth":     "BW",
        "authority":     "LVL",
        "channel":       "CHAN",
        "concept of operations": "CONOPS",
        "constraint":    "CONSTRAINT",
        "deescalation":  "DESC",
        "emcon":         "EMCON",
        "escalation":    "ESCL",
        "fallback":      "FALLBACK",
        "floor":         "FLOOR",
        "incident action plan": "IAP",
        "latency":       "LATENCY",
        "link quality":  "LINK",
        "mesh":          "MESH",
        "operational mode": "MODE",
        "posture":       "POSTURE",
        "signal strength": "LINK",
        "conspicuity":   "CONSPIC",
        "autonomy level": "AUTOLEV",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        for phrase, op in sorted(self.KEYWORD_MAP.items(), key=lambda kv: -len(kv[0])):
            if phrase in raw_low:
                out.append(FrameProposal(
                    namespace="O", opcode=op,
                    is_query=req.is_query,
                    rationale=f"O-context phrase '{phrase}'",
                ))
                break
        return out
