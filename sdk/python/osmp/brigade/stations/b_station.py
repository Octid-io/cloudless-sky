"""B-station — Building / Construction. Alarms, sprinklers, areas."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class BStation(Station):
    namespace = "B"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        if "fire alarm" in raw_low or "alarm" in raw_low and "building" in raw_low:
            target = self._pick_target(req)
            out.append(FrameProposal(
                namespace="B", opcode="ALRM",
                target=target,
                rationale="building fire alarm",
            ))
        return out

    def _pick_target(self, req):
        for t in req.targets:
            if t.kind == "building":
                return t.id
        # building-letter: "building B" -> @B
        import re as _re
        m = _re.search(r'\bbuilding\s+(\w+)', req.raw, _re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return None
