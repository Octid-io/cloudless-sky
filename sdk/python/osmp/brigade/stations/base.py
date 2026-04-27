"""Station base class + registry. Stations are pure functions of ParsedRequest."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..request import ParsedRequest, FrameProposal


class Station(ABC):
    """A namespace expert. Pure: input ParsedRequest, output FrameProposals."""

    namespace: str = ""  # subclass sets

    @abstractmethod
    def propose(self, req: ParsedRequest) -> list[FrameProposal]:
        """Examine the request and return zero or more candidate frames in
        this station's namespace. Returns [] if the request doesn't fit."""
        raise NotImplementedError

    def applies(self, req: ParsedRequest) -> bool:
        """Quick check: should this station bother examining this request?"""
        return self.namespace in req.namespace_hints


class BrigadeRegistry:
    """Holds the brigade of stations. Dispatches a parsed request to each."""

    def __init__(self):
        self._stations: dict[str, Station] = {}

    def register(self, station: Station) -> None:
        self._stations[station.namespace] = station

    def all_stations(self) -> list[Station]:
        return list(self._stations.values())

    def get(self, namespace: str) -> Station | None:
        return self._stations.get(namespace)

    def propose_all(self, req: ParsedRequest) -> dict[str, list[FrameProposal]]:
        """Run every station on the request; return their proposals keyed by namespace."""
        results: dict[str, list[FrameProposal]] = {}
        for ns, station in self._stations.items():
            try:
                props = station.propose(req)
            except Exception:
                props = []
            if props:
                results[ns] = props
        return results
