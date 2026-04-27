"""C-station — Compute / Resource Management."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class CStation(Station):
    namespace = "C"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        # KILL — terminate process / shutdown
        if req.verb_lemma in ("kill", "shutdown", "shut", "terminate"):
            out.append(FrameProposal(
                namespace="C", opcode="KILL",
                target=self._pick_target(req),
                rationale=f"verb '{req.verb_lemma}' -> C:KILL",
            ))
        # RSTRT — restart, reboot
        if req.verb_lemma in ("restart", "reboot"):
            out.append(FrameProposal(
                namespace="C", opcode="RSTRT",
                target=self._pick_target(req),
                rationale=f"verb '{req.verb_lemma}' -> C:RSTRT",
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
