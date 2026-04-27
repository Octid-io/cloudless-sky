"""OSMP Brigade — the kitchen-style composer.

Mise en place: parser → ParsedRequest IR
Stations: per-namespace experts → FrameProposal
Orchestrator: head chef → final SAL
Expediter: validator (already in osmp.protocol)
"""
from .parser import parse
from .request import ParsedRequest, FrameProposal, Target, SlotValue, Condition
from .orchestrator import Orchestrator, ComposeResult

__all__ = ["parse", "ParsedRequest", "FrameProposal", "Target", "SlotValue",
           "Condition", "Orchestrator", "ComposeResult"]
