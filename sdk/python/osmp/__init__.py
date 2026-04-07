"""
OSMP — Octid Semantic Mesh Protocol

Tier 1 API: Two functions. Zero setup.

    from osmp import encode, decode

    sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
    text = decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")

Tier 2 API: Direct access to ASD, encoder, decoder, validator, bridge.

    from osmp import AdaptiveSharedDictionary, SALEncoder, SALDecoder
    from osmp import SALBridge, FNPSession, ADPSession

Tier 3 API: Overflow Protocol (DAG fragmentation, wire codec, security envelope).

    from osmp import OverflowProtocol, DAGFragmenter, DAGReassembler
    from osmp import OSMPWireCodec, SecCodec, SAILCodec

Patent pending. Inventor: Clay Holberg. License: Apache 2.0.
"""

from __future__ import annotations

__version__ = "2.0.1"

# ─────────────────────────────────────────────────────────────────────────────
# TIER 1 — Lazy singleton, two functions
# ─────────────────────────────────────────────────────────────────────────────
# The protocol module is heavy (~3000 lines). We don't import it until the
# first call, and we cache the singleton instances.

_asd = None
_encoder = None
_decoder = None


def _init():
    """Initialize singleton ASD, encoder, and decoder on first use."""
    global _asd, _encoder, _decoder
    if _asd is not None:
        return
    from osmp.protocol import AdaptiveSharedDictionary, SALEncoder, SALDecoder
    _asd = AdaptiveSharedDictionary()
    _encoder = SALEncoder(_asd)
    _decoder = SALDecoder(_asd)


def encode(input_data) -> str:
    """Encode to SAL.

    Accepts:
        list[str]  -- opcode strings, joined with ; (sequence operator)
        str        -- if it looks like SAL (contains :), validates and returns as-is
                      if it looks like natural language, returns as NL_PASSTHROUGH

    Returns:
        SAL string ready for transmission.
    """
    _init()

    if isinstance(input_data, list):
        return _encoder.encode_sequence(input_data)

    if isinstance(input_data, str):
        if ":" in input_data and any(
            c in input_data for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ):
            return input_data
        return input_data

    raise TypeError(
        f"encode() accepts str or list[str], got {type(input_data).__name__}. "
        f"Example: encode(['H:HR@NODE1>120', 'H:CASREP', 'M:EVA@*'])"
    )


def decode(sal: str) -> str:
    """Decode SAL to natural language description.

    Accepts a SAL instruction string (single frame or ;-separated sequence).
    Returns the natural language expansion via ASD dictionary lookup. Zero
    inference. Chain handling is delegated to SALDecoder.decode_natural_language
    which natively handles ;-separated frames.
    """
    _init()
    return _decoder.decode_natural_language(sal)


def validate(sal: str, nl: str = "", dependency_rules=None):
    """Validate a composed SAL instruction against all eight composition rules.

    Returns a CompositionResult with .valid (bool) and .issues (list).
    """
    _init()
    from osmp.protocol import validate_composition
    return validate_composition(sal, nl, _asd, dependency_rules=dependency_rules)


def lookup(namespace_opcode: str) -> str | None:
    """Look up an opcode definition in the ASD.

    Accepts: "H:HR" (namespace:opcode form)
    Returns: definition string or None if not found.
    """
    _init()
    if ":" in namespace_opcode:
        ns, op = namespace_opcode.split(":", 1)
        return _asd.lookup(ns, op)
    return None


def byte_size(sal: str) -> int:
    """Return UTF-8 byte count of a SAL string."""
    return len(sal.encode("utf-8"))


def make_bridge(node_id: str, **kwargs):
    """Create a SALBridge instance for boundary translation.

    OSMP spreads by contact, not installation.

        from osmp import make_bridge
        b = make_bridge("MY_NODE")
        b.register_peer("GPT_AGENT")
        out = b.send("H:HR@NODE1>120", "GPT_AGENT")

    Equivalent to: ``SALBridge("MY_NODE")`` after ``from osmp import SALBridge``.
    The factory form is provided for symmetry with the other Tier 1 helpers.
    """
    return SALBridge(node_id, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2 / TIER 3 — Re-exports
# ─────────────────────────────────────────────────────────────────────────────
# Mirrors the TypeScript SDK index.ts re-export pattern. Anything used by
# tests/test_composition_fidelity.py, tests/test_sec.py, tests/test_tokenomics.py
# or downstream consumers should be importable from the top-level package.

from osmp.protocol import (
    # ASD basis dictionary (raw data)
    ASD_BASIS,

    # Glyph operators and consequence class table
    GLYPH_OPERATORS,
    CONSEQUENCE_CLASSES,

    # Utilities
    utf8_bytes,

    # BAEL — Bandwidth-Agnostic Efficiency Layer
    BAELMode,
    BAELEncoder,

    # ASD — Adaptive Shared Dictionary
    AdaptiveSharedDictionary,
    ASD_FLOOR_VERSION,

    # FNP — Frame Negotiation Protocol
    FNPSession,
    FNP_MSG_NACK,
    FNP_MATCH_FINGERPRINT,
    FNP_CAP_UNCONSTRAINED,
    FNP_CAP_BYTES,
    FNP_ADV_SIZE,
    FNP_ACK_SIZE,
    FNP_PROTOCOL_VERSION,

    # ADP — Adaptive Dictionary Protocol
    ADPDeltaOp,
    ADPDelta,
    PendingInstruction,
    ADPSession,
    ADP_PRIORITY_MISSION,
    ADP_PRIORITY_MICRO,
    ADP_PRIORITY_DELTA,
    ADP_PRIORITY_TRICKLE,
    asd_version_pack,
    asd_version_unpack,
    asd_version_str,
    asd_version_parse,
    asd_version_is_breaking,

    # SAL Encoder
    SALEncoder,

    # Validator and dependency rules
    DependencyRule,
    load_mdr_dependency_rules,
    CompositionIssue,
    CompositionResult,
    validate_composition,

    # SAL Decoder
    DecodedInstruction,
    SALDecoder,

    # Tier 3 — Overflow Protocol and DAG fragmentation
    LossPolicy,
    Fragment,
    OverflowProtocol,
    DAGNode,
    DAGFragmenter,
    DAGReassembler,
    FRAGMENT_HEADER_BYTES,
    LORA_FLOOR_BYTES,
    FLAG_TERMINAL,
    FLAG_CRITICAL,
    FLAG_EXTENDED_DEP,

    # D:PACK/BLK two-tier compressor
    TwoTierCompressor,
    BlockCompressor,
    DBLK_MAGIC,
)

from osmp.bridge import (
    SALBridge,
    AcquisitionMetrics,
    BridgeEvent,
    BridgeInbound,
    DEFAULT_ACQUISITION_THRESHOLD,
    DEFAULT_REGRESSION_THRESHOLD,
)

from osmp.wire import (
    WireMode,
    SAILCodec,
    SecEnvelope,
    SecCodec,
    OSMPWireCodec,
    NODE_ID_LONG,
    SEC_VERSION_1,
)


__all__ = [
    # Tier 1
    "encode", "decode", "validate", "lookup", "byte_size", "make_bridge",
    "__version__",

    # Raw ASD data + glyph tables
    "ASD_BASIS", "GLYPH_OPERATORS", "CONSEQUENCE_CLASSES", "utf8_bytes",

    # BAEL
    "BAELMode", "BAELEncoder",

    # ASD
    "AdaptiveSharedDictionary", "ASD_FLOOR_VERSION",

    # FNP
    "FNPSession", "FNP_MSG_NACK", "FNP_MATCH_FINGERPRINT",
    "FNP_CAP_UNCONSTRAINED", "FNP_CAP_BYTES",
    "FNP_ADV_SIZE", "FNP_ACK_SIZE", "FNP_PROTOCOL_VERSION",

    # ADP
    "ADPDeltaOp", "ADPDelta", "PendingInstruction", "ADPSession",
    "ADP_PRIORITY_MISSION", "ADP_PRIORITY_MICRO",
    "ADP_PRIORITY_DELTA", "ADP_PRIORITY_TRICKLE",
    "asd_version_pack", "asd_version_unpack", "asd_version_str",
    "asd_version_parse", "asd_version_is_breaking",

    # Encoder
    "SALEncoder",

    # Validator
    "DependencyRule", "load_mdr_dependency_rules",
    "CompositionIssue", "CompositionResult", "validate_composition",

    # Decoder
    "DecodedInstruction", "SALDecoder",

    # Tier 3 — Overflow
    "LossPolicy", "Fragment", "OverflowProtocol",
    "DAGNode", "DAGFragmenter", "DAGReassembler",
    "FRAGMENT_HEADER_BYTES", "LORA_FLOOR_BYTES",
    "FLAG_TERMINAL", "FLAG_CRITICAL", "FLAG_EXTENDED_DEP",

    # D:PACK/BLK
    "TwoTierCompressor", "BlockCompressor", "DBLK_MAGIC",

    # Bridge
    "SALBridge", "AcquisitionMetrics", "BridgeEvent", "BridgeInbound",
    "DEFAULT_ACQUISITION_THRESHOLD", "DEFAULT_REGRESSION_THRESHOLD",

    # Wire
    "WireMode", "SAILCodec", "SecEnvelope", "SecCodec", "OSMPWireCodec",
    "NODE_ID_LONG", "SEC_VERSION_1",
]
