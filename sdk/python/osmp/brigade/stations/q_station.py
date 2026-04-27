"""Q-station — Quality / Evaluation / Grounding."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class QStation(Station):
    namespace = "Q"

    KEYWORD_MAP = {
        "analysis":             "ANL",
        "benchmark":            "BENCH",
        "cite":                 "CITE",
        "citation":             "CITE",
        "confidence interval":  "CONF",
        "correction":           "CORRECT",
        "critique":             "CRIT",
        "evaluate":             "EVAL",
        "evaluation":           "EVAL",
        "feedback":             "FB",
        "ground truth":         "GT",
        "report quality":       "RPRT",
        "structured report":    "RPRT",
        "review":               "REVIEW",
        "verify quality":       "VERIFY",
        "revise":               "REVISE",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        for phrase, op in sorted(self.KEYWORD_MAP.items(), key=lambda kv: -len(kv[0])):
            if phrase in raw_low:
                out.append(FrameProposal(
                    namespace="Q", opcode=op,
                    confidence=0.6,  # low — Q is meta, often not the primary intent
                    is_query=req.is_query,
                    rationale=f"Q phrase '{phrase}'",
                ))
                break
        return out
