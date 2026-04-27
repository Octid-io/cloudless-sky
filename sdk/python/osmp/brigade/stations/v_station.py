"""V-station — Vehicle / Transport Fleet."""
from ..request import ParsedRequest, FrameProposal
from .base import Station


class VStation(Station):
    namespace = "V"

    VEHICLE_CONTEXT = {"vehicle", "vessel", "ship", "boat", "fleet", "ais", "drone", "uav"}

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()

        # V:CSPOS removed — not in v15 ASD active set. Use V:POS for control station context.

        in_vehicle_ctx = any(w in raw_low for w in self.VEHICLE_CONTEXT)

        if not in_vehicle_ctx:
            return out

        # V:HDG — vehicle heading
        if "heading" in raw_low or "bearing" in raw_low or "course" in raw_low:
            out.append(FrameProposal(
                namespace="V", opcode="HDG",
                target=self._pick_target(req),
                is_query=req.is_query,
                rationale="vehicle heading context",
            ))

        # V:POS — vehicle position (when explicitly vehicle/drone context)
        if "position" in raw_low or "location" in raw_low or "where" in raw_low:
            out.append(FrameProposal(
                namespace="V", opcode="POS",
                target=self._pick_target(req),
                is_query=req.is_query,
                rationale="vehicle position context",
            ))

        # V:FLEET — fleet status
        if "fleet" in raw_low:
            if "status" in raw_low or req.is_query:
                out.append(FrameProposal(
                    namespace="V", opcode="FLEET",
                    is_query=True,
                    rationale="fleet status",
                ))

        # V:AIS — AIS position report (high confidence — overrides V:POS for "AIS" inputs)
        if "ais" in raw_low.split() or " ais " in f" {raw_low} ":
            out.append(FrameProposal(
                namespace="V", opcode="AIS",
                target=self._pick_target(req),
                confidence=2.5,
                rationale="AIS keyword (overrides V:POS)",
            ))

        # (V:CSPOS handled at top regardless of vehicle context)

        return out

    def _pick_target(self, req):
        if req.is_broadcast and not req.targets:
            return "*"
        for t in req.targets:
            if t.source == "entity":
                return t.id
        return None
