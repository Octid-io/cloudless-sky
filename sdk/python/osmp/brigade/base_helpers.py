"""Helpers shared by stations — opcode-existence check, etc."""
from __future__ import annotations

from ..protocol import ASD_BASIS


def opcode_exists(namespace: str, opcode: str) -> bool:
    """Check whether namespace:opcode is in the active ASD.

    Stations should consult this before proposing — emitting SAL with an
    opcode that doesn't exist in the loaded dictionary will fail validation
    AND signals to the receiver an action it cannot dispatch.
    """
    return opcode in ASD_BASIS.get(namespace, {})


def all_opcodes(namespace: str) -> list[str]:
    """Return all opcodes in a namespace from the active ASD."""
    return list(ASD_BASIS.get(namespace, {}).keys())
