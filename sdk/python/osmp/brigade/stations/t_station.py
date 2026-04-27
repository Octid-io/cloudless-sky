"""T-station — Time / Scheduling."""
from ..request import ParsedRequest, FrameProposal, SlotValue
from .base import Station


class TStation(Station):
    namespace = "T"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # T:EXP — expiration
        if req.verb_lemma in ("expire",) or "expire" in raw_low or "ttl" in raw_low:
            slot = ()
            for sv in req.slot_values:
                if sv.value_type == "duration":
                    slot = (SlotValue(key="", value=sv.value, value_type="duration"),)
                    break
            out.append(FrameProposal(
                namespace="T", opcode="EXP",
                slot_values=slot,
                rationale="expire verb + duration",
            ))

        # T:SCHED — schedule. Only fired when there's a duration slot AND another action
        # The orchestrator decides whether to chain T:SCHED→action.
        for sv in req.slot_values:
            if sv.value_type == "duration" and "every" in raw_low:
                out.append(FrameProposal(
                    namespace="T", opcode="SCHED",
                    slot_values=(SlotValue(key="", value=sv.value, value_type="duration"),),
                    rationale="schedule with every-N pattern",
                ))
                break

        # T:WIN — maintenance window
        if "maintenance window" in raw_low or "window" in raw_low and req.verb_lemma == "schedule":
            out.append(FrameProposal(
                namespace="T", opcode="WIN",
                rationale="maintenance window",
            ))

        return out
