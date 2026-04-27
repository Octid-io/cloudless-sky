"""Y-station — Memory / Storage. STORE, FETCH, FORGET, INDEX, COMMIT, EMBED."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class YStation(Station):
    namespace = "Y"

    VERB_TO_OPCODE = {
        "store":    "STORE",
        "save":     "STORE",
        "remember": "STORE",
        "fetch":    "FETCH",
        "recall":   "FETCH",
        "forget":   "FORGET",
        "index":    "INDEX",
        "commit":   "COMMIT",
        "embed":    "EMBED",
        "clear":    "CLEAR",
    }

    KEYWORD_MAP = {
        "page out memory":     "PAGEOUT",
        "store to memory":     "STORE",
        "save to memory":      "STORE",
        "embedding":           "EMBED",
        "memory tier":         "CLEAR",
    }

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # Verb-driven (only when memory context is clear)
        if "memory" in raw_low or "store" in raw_low.split() or "fetch" in raw_low.split() or req.verb_lemma in ("forget", "store"):
            if req.verb_lemma in self.VERB_TO_OPCODE:
                out.append(FrameProposal(
                    namespace="Y", opcode=self.VERB_TO_OPCODE[req.verb_lemma],
                    confidence=1.5,
                    rationale=f"memory verb '{req.verb_lemma}'",
                ))

        # Phrase matches
        for phrase, op in sorted(self.KEYWORD_MAP.items(), key=lambda kv: -len(kv[0])):
            if phrase in raw_low:
                out.append(FrameProposal(
                    namespace="Y", opcode=op,
                    confidence=0.7,
                    rationale=f"Y phrase '{phrase}'",
                ))
                break

        return out
