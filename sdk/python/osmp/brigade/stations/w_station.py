"""W-station — Weather / Atmospheric."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class WStation(Station):
    namespace = "W"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        # Word-boundary tokenization (prevents "wind" matching "window")
        tokens = set(raw_low.replace(",", " ").replace(".", " ").split())

        # Skip if "wind farm" / "wind generation" — those are X:WND (energy)
        if "wind farm" in raw_low or "wind generation" in raw_low:
            return out
        # Skip if "wind down" / "wind up" — idiom, not weather sensor
        if "wind down" in raw_low or "wind up" in raw_low:
            return out

        if "wind" in tokens:
            out.append(FrameProposal(
                namespace="W", opcode="WIND",
                target=self._pick_target(req),
                is_query=req.is_query or req.verb_lemma in (None, "report", "show", "get"),
                rationale="wind keyword",
            ))

        if "weather alert" in raw_low or (req.verb_lemma == "alert" and "wind" in raw_low):
            out.append(FrameProposal(
                namespace="W", opcode="ALERT",
                rationale="weather alert",
            ))

        return out

    def _pick_target(self, req):
        if req.is_broadcast and not req.targets:
            return "*"
        for t in req.targets:
            if t.source == "entity":
                return t.id
        if req.targets:
            return req.targets[0].id
        return None
