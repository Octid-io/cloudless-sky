"""Z-station — Inference / Model operations."""
from ..request import ParsedRequest, FrameProposal, SlotValue
from .base import Station


class ZStation(Station):
    namespace = "Z"

    KEYWORD_MAP = {
        "batch inference":      "BATCH",
        "kv cache":             "CACHE",
        "capability query":     "CAPS",
        "agent confidence":     "CONF",
        "inference cost":       "COST",
        "context window":       "CTX",
        "context utilization":  "CTX",
        "run inference":        "INF",
        "invoke model":         "INF",
        "tokens":               "TOKENS",
        "token count":          "TOKENS",
        "sampling temperature": "TEMP",
        "top-p":                "TOPP",
        "top p":                "TOPP",
        "max tokens":           "MAX",
        "model response":       "RESP",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # LLM sampling parameter
        for sv in req.slot_values:
            if sv.key == "temperature" and req.verb_lemma in (None, "set", "configure"):
                out.append(FrameProposal(
                    namespace="Z", opcode="TEMP",
                    slot_values=(SlotValue(key="", value=sv.value, value_type="float"),),
                    confidence=0.6,
                    rationale="Z:TEMP for inference sampling temp",
                ))

        for phrase, op in sorted(self.KEYWORD_MAP.items(), key=lambda kv: -len(kv[0])):
            if phrase in raw_low:
                out.append(FrameProposal(
                    namespace="Z", opcode=op,
                    confidence=0.7,
                    is_query=req.is_query,
                    rationale=f"Z phrase '{phrase}'",
                ))
                break

        return out
