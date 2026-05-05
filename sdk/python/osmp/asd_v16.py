"""
v16 NAMESPACE STRUCTURE — 33 active namespaces

  - 20 cleanly-converged 3c primaries
  - 9 refactored splits across 4 v15 letters: C/D/K/Q
  - 3 v15 namespaces locked at 2c form: I→ID, V→VT, X→EP
  - 1 sovereign extension: Ω

v15 single-letter forms are PRESERVED as deprecated siblings.
The AdaptiveSharedDictionary loads BOTH v15 letters AND v16 primaries
into _data so wire-format lookups resolve under either form.

Cross-SDK byte-identical with TypeScript ASD_BASIS_V16 and Go ASDBasisV16.
"""

from __future__ import annotations

from typing import Optional

from .protocol import ASD_BASIS


# Maps each v15 single-letter namespace to its v16 primary (single-element
# list for direct mapping) or split set (multi-element list for the four
# split letters C/D/K/Q).
ASD_V15_TO_V16: dict[str, list[str]] = {
    "A": ["AGT"],
    "B": ["BLD"],
    "C": ["CMP", "RES"],
    "D": ["DAT", "QRY", "XFR"],
    "E": ["ENV"],
    "F": ["FED"],
    "G": ["GEO"],
    "H": ["HLT"],
    "I": ["ID"],
    "J": ["CES"],
    "K": ["FIN", "TXN"],
    "L": ["LOG"],
    "M": ["MUN"],
    "N": ["NET"],
    "O": ["OPE"],
    "P": ["PRO"],
    "Q": ["QLT", "EVL", "GND"],
    "R": ["ROB"],
    "S": ["SEC"],
    "T": ["TIM"],
    "U": ["USR"],
    "V": ["VT"],
    "W": ["WEA"],
    "X": ["EP"],
    "Y": ["MEM"],
    "Z": ["INF"],
    "Ω": ["Ω"],
}


# Bridge composer disambiguation for split letters.
# Maps v15_letter -> opcode -> v16_primary. Opcodes outside these sets fall
# to NL_PASSTHROUGH at the composer.
#
# The Q namespace additionally defaults unmatched opcodes to QLT — that
# fallback is applied in _build_asd_basis_v16() below.
BRIDGE_SPLIT_DISAMBIGUATION: dict[str, dict[str, str]] = {
    "C": {
        # C -> CMP: process / compute lifecycle
        "ALLOC": "CMP",
        "FREE":  "CMP",
        "KILL":  "CMP",
        "CHKPT": "CMP",
        "MIGRT": "CMP",
        "PAUSE": "CMP",
        "PRTY":  "CMP",
        "RESUME":"CMP",
        "RSTRT": "CMP",
        "SCALE": "CMP",
        "SPAWN": "CMP",
        # C -> RES: resource constraints / status
        "QUOTA": "RES",
        "LIMIT": "RES",
        "STAT":  "RES",
    },
    "D": {
        # D -> DAT: data records / storage encoding
        "DEL":    "DAT",
        "LOG":    "DAT",
        "PACK":   "DAT",
        "UNPACK": "DAT",
        # D -> QRY: query / search
        "Q": "QRY",
        # D -> XFR: transfer lifecycle
        "CHUNK":  "XFR",
        "PUSH":   "XFR",
        "PULL":   "XFR",
        "FEED":   "XFR",
        "ABORT":  "XFR",
        "CSUM":   "XFR",
        # Same opcode name resolves differently by namespace context
        # (D:RESUME -> XFR; C:RESUME -> CMP).
        "RESUME": "XFR",
        "RTN":    "XFR",
        "STAT":   "XFR",
        "XFER":   "XFR",
    },
    "K": {
        # K -> FIN: financial instrument / asset class
        "DIG": "FIN",
        # K -> TXN: transaction
        "TRD": "TXN",
        "PAY": "TXN",
        "XFR": "TXN",
        "ORD": "TXN",
    },
    "Q": {
        # Q -> EVL: evaluation / metrics
        "SCORE":  "EVL",
        "BENCH":  "EVL",
        # Q -> GND: groundedness / citation
        "CITE":   "GND",
        "GROUND": "GND",
        # All other Q opcodes fall to QLT per default rule (applied below).
    },
}


def _build_asd_basis_v16() -> dict[str, dict[str, str]]:
    """Construct the v16-keyed ASD basis from ASD_BASIS via the v15->v16
    sibling map and the split disambiguation rules.

    For non-split letters, the entire opcode dict is migrated to the v16
    primary key (a copy, not a shared reference, so subsequent runtime
    mutations to one don't leak into the other).

    For split letters (C/D/K/Q), opcodes are partitioned into v16 split
    namespaces per BRIDGE_SPLIT_DISAMBIGUATION. Opcodes not in any split's
    rule set remain in ASD_BASIS under the v15 letter (deprecated sibling
    path) and are NOT mirrored to any v16 primary — wire-format senders
    using the v16 primary form for those opcodes will miss; senders using
    the v15 letter form continue to resolve.

    The Q namespace applies a default-to-QLT rule for unmapped opcodes.
    """
    v16: dict[str, dict[str, str]] = {}
    for v15_letter, targets in ASD_V15_TO_V16.items():
        if v15_letter not in ASD_BASIS:
            continue
        opcodes = ASD_BASIS[v15_letter]
        if len(targets) == 1:
            # Single mapping (or sovereign Ω): copy entire opcode dict.
            v16[targets[0]] = dict(opcodes)
        else:
            # Split letter: partition opcodes per disambiguation table.
            disambiguation = BRIDGE_SPLIT_DISAMBIGUATION.get(v15_letter, {})
            for split in targets:
                v16.setdefault(split, {})
            for op, defn in opcodes.items():
                v16_target = disambiguation.get(op)
                if v16_target is None:
                    # Orphan opcode: stays v15-only.
                    # Q applies default-to-QLT below; other splits do not.
                    continue
                v16[v16_target][op] = defn
    # Apply Q's default-to-QLT fallback.
    if "Q" in ASD_BASIS:
        q_disamb = BRIDGE_SPLIT_DISAMBIGUATION.get("Q", {})
        v16.setdefault("QLT", {})
        for op, defn in ASD_BASIS["Q"].items():
            if op not in q_disamb:
                v16["QLT"][op] = defn
    return v16


# v16-keyed ASD basis built at module load. Cross-SDK byte-identical with
# TypeScript ASD_BASIS_V16 and Go ASDBasisV16.
ASD_BASIS_V16: dict[str, dict[str, str]] = _build_asd_basis_v16()


def disambiguate_to_v16(namespace: str, opcode: str) -> Optional[str]:
    """Resolve a (namespace, opcode) pair to its v16 primary namespace.

    Use cases:
      - Composer wire-format conversion (v15 letter input -> v16 primary emit).
      - Bridge composer routing for the four split letters.
      - Migration tooling that canonicalizes legacy v15 traffic.

    Returns:
      - The v16 primary namespace string for known mappings (e.g.,
        ("A", "ACK") -> "AGT"; ("C", "ALLOC") -> "CMP"; ("D", "STAT") -> "XFR").
      - The input namespace itself if it is already a v16 primary.
      - None if the namespace is unknown or the opcode is an orphan under
        a split letter that has no rule for it.

    The Q namespace's default-to-QLT rule for unmapped opcodes is applied here.

    Cross-SDK byte-identical with TypeScript disambiguateToV16 and Go
    DisambiguateToV16.
    """
    # Already a v16 primary? Pass through.
    if namespace in ASD_BASIS_V16:
        return namespace
    targets = ASD_V15_TO_V16.get(namespace)
    if targets is None:
        return None
    if len(targets) == 1:
        return targets[0]
    disambiguation = BRIDGE_SPLIT_DISAMBIGUATION.get(namespace, {})
    if opcode in disambiguation:
        return disambiguation[opcode]
    # Q applies default-to-QLT for unmapped opcodes.
    if namespace == "Q":
        return "QLT"
    # Other split letters (C, D, K) without a rule: orphan — no v16 home.
    return None


__all__ = [
    "ASD_V15_TO_V16",
    "BRIDGE_SPLIT_DISAMBIGUATION",
    "ASD_BASIS_V16",
    "disambiguate_to_v16",
]
