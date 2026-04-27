"""D-station — Data. PUSH, PULL, Q."""
from ..request import ParsedRequest, FrameProposal
from ..base_helpers import opcode_exists
from .base import Station


class DStation(Station):
    namespace = "D"

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # D:PUSH — send to TARGET
        if (req.verb_lemma in ("push", "send") and req.targets
            and opcode_exists("D", "PUSH")):
            for t in req.targets:
                if t.source in ("preposition", "entity"):
                    out.append(FrameProposal(
                        namespace="D", opcode="PUSH",
                        target=t.id,
                        rationale=f"send to {t.id}",
                    ))
                    break

        # D:Q — data query
        if (req.verb_lemma == "query" or "query" in raw_low) and opcode_exists("D", "Q"):
            out.append(FrameProposal(
                namespace="D", opcode="Q",
                rationale="data query",
            ))

        # D:DEL — delete (irreversible). Only propose if the opcode actually
        # exists in v15 ASD; otherwise the receiver can't act on it.
        # In current v15, D:DEL does NOT exist — D namespace has ABORT for
        # similar semantics. Until DEL is added, refuse to compose for "delete".
        if (req.verb_lemma == "delete" or "delete" in raw_low) and opcode_exists("D", "DEL"):
            out.append(FrameProposal(
                namespace="D", opcode="DEL",
                consequence_class="\u2298",
                confidence=2.0,
                rationale="delete",
            ))

        return out
