"""X-station — Energy / Storage / Battery / Grid."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class XStation(Station):
    namespace = "X"

    KEYWORD_MAP = {
        "demand response":     "DR",
        "ev charging":         "CHG",
        "charging state":      "CHG",
        "fault event":         "FAULT",
        "grid frequency":      "FREQ",
        "grid connection":     "GRD",
        "islanding":           "ISLND",
        "battery level":       "STORE",
        "battery status":      "STORE",
        "battery report":      "STORE",
        "voltage":             "VOLT",
        "wind generation":     "WND",
        "wind farm":           "WND",
        "production":          "PROD",
        "frequency":           "FREQ",
    }
    # High-confidence multi-word phrases that should win over generic alternatives
    HIGH_CONF_PHRASES = {"wind farm", "wind generation"}

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        # Article-tolerant matching ("wind the farm" → "wind farm")
        raw_dearticled = " ".join(w for w in raw_low.split() if w not in ("the", "a", "an"))
        for phrase, op in sorted(self.KEYWORD_MAP.items(), key=lambda kv: -len(kv[0])):
            if phrase in raw_low or phrase in raw_dearticled:
                conf = 2.5 if phrase in self.HIGH_CONF_PHRASES else 1.0
                out.append(FrameProposal(
                    namespace="X", opcode=op,
                    confidence=conf,
                    is_query=req.is_query or req.verb_lemma in (None, "report", "show", "check"),
                    rationale=f"X energy phrase '{phrase}'",
                ))
                break
        return out
