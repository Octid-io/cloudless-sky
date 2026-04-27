"""I-station — Identity / Authorization. I:§ is the auth precondition glyph."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class IStation(Station):
    namespace = "I"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # I:§ is NOT proposed as a standalone frame. It's a precondition glyph
        # the orchestrator prepends to the action frame when authorization_required
        # is set. Proposing it here causes the orchestrator to pick it as the
        # primary frame and emit "I:§→I:§" (double-prepended).

        # I:ID — identity verification (high confidence — overrides S:VFY)
        if (req.verb_lemma in ("authenticate",)
            or "verify identity" in raw_low or "verify the identity" in raw_low
            or "identity check" in raw_low or "who is" in raw_low
            or "check identity" in raw_low or "confirm identity" in raw_low
            or ("identity" in raw_low and req.verb_lemma == "verify")):
            out.append(FrameProposal(
                namespace="I", opcode="ID",
                target=self._pick_target(req),
                is_query=req.is_query,
                confidence=2.0,  # explicit override of S:VFY
                rationale="identity verification (overrides S:VFY)",
            ))

        return out

    def _pick_target(self, req):
        for t in req.targets:
            if t.source == "entity":
                return t.id
        return None
