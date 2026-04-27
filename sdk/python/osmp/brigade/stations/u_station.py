"""U-station — User / Human Interaction. Notify, approve, alert."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class UStation(Station):
    namespace = "U"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # APPROVE — when explicit "X approves Y" pattern (not just "approval" mentioned).
        # Also requires the input to have an ACTION verb that's gated by the approval.
        # Standalone "with approval" without a composable action shouldn't emit U:APPROVE.
        ACTION_VERBS = {"pay", "process", "transfer", "delete", "send", "execute",
                        "shutdown", "kill", "stop", "move", "fire", "deploy", "start"}
        has_gated_action = req.verb_lemma in ACTION_VERBS or any(
            v in raw_low for v in ACTION_VERBS
        )
        if (("approve" in raw_low or "approval" in raw_low) and has_gated_action):
            out.append(FrameProposal(
                namespace="U", opcode="APPROVE",
                confidence=0.5,  # weak — only used as gating chain; primary action wins
                rationale="approval pattern with action verb",
            ))

        # NOTIFY — generic notification
        if req.verb_lemma == "notify" or "notify" in raw_low:
            out.append(FrameProposal(
                namespace="U", opcode="NOTIFY",
                rationale="notify verb",
            ))

        # ALERT — operator alert (when no clinical context)
        if req.verb_lemma in ("alert", "warn") and "H" not in req.namespace_hints:
            out.append(FrameProposal(
                namespace="U", opcode="ALERT",
                rationale="operator alert (non-clinical)",
            ))

        return out
