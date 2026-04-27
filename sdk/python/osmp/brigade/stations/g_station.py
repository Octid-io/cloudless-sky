"""G-station — Geospatial / Navigation (POS, BEARING, GPS, alt)."""
from ..request import ParsedRequest, FrameProposal, SlotValue
from .base import Station


class GStation(Station):
    namespace = "G"

    POSITION_WORDS = {"position", "location", "place", "where", "spot", "altitude",
                      "elevation", "latlon", "lat", "lng", "long", "coords"}
    HEADING_WORDS = {"heading", "bearing", "direction", "course", "azimuth", "compass"}

    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        out = []
        raw_low = req.raw.lower()
        # Word-boundary tokenization (prevents "lat" matching "translate")
        tokens = set(raw_low.replace(",", " ").replace(".", " ").split())

        # POS — position read
        if any(w in tokens for w in self.POSITION_WORDS):
            target = self._pick_target(req)
            # Drone context — V:POS may be more appropriate (handled by V_station)
            # but emit G:POS as primary
            out.append(FrameProposal(
                namespace="G", opcode="POS",
                target="*" if req.is_broadcast and not target else target,
                is_query=req.is_query,
                rationale="position keyword",
            ))

        # BEARING — heading
        if any(w in tokens for w in self.HEADING_WORDS):
            # Skip if vehicle/marine context (V:HDG wins)
            target = self._pick_target(req)
            out.append(FrameProposal(
                namespace="G", opcode="BEARING",
                target=target,
                is_query=req.is_query,
                rationale="heading keyword",
            ))

        return out

    def _pick_target(self, req):
        if req.is_broadcast and not req.targets:
            return "*"
        for t in req.targets:
            if t.source == "entity":
                return t.id
        return None
