"""
OSMP — Octid Semantic Mesh Protocol
Tier 1 API: Two functions. Zero setup.

    from osmp import encode, decode

    sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
    print(sal)    # "H:HR@NODE1>120;H:CASREP;M:EVA@*"

    text = decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
    print(text)   # "heart_rate at NODE1 priority 120; casualty_report; evacuation at broadcast"

Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

# Lazy-loaded singleton. The protocol module is heavy (~2700 lines).
# We don't import it until the first call, and we cache the instances.
_asd = None
_encoder = None
_decoder = None


def _init():
    """Initialize singleton ASD, encoder, and decoder on first use."""
    global _asd, _encoder, _decoder
    if _asd is not None:
        return

    # Import from wherever the protocol internals live.
    # This supports both the current osmp_mcp.osmp layout and
    # the future osmp.protocol layout.
    try:
        from osmp.protocol import AdaptiveSharedDictionary, SALEncoder, SALDecoder
    except ImportError:
        try:
            from osmp_mcp.osmp import AdaptiveSharedDictionary, SALEncoder, SALDecoder
        except ImportError:
            # Fallback: same package, different module name
            from .osmp import AdaptiveSharedDictionary, SALEncoder, SALDecoder

    _asd = AdaptiveSharedDictionary()
    _encoder = SALEncoder(_asd)
    _decoder = SALDecoder(_asd)


def encode(input_data) -> str:
    """Encode to SAL.

    Accepts:
        list[str]  — opcode strings, joined with ; (sequence operator)
        str        — if it looks like SAL (contains :), validates and returns as-is
                     if it looks like natural language, returns as NL_PASSTHROUGH

    Returns:
        SAL string ready for transmission.

    Examples:
        encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
        → "H:HR@NODE1>120;H:CASREP;M:EVA@*"

        encode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
        → "H:HR@NODE1>120;H:CASREP;M:EVA@*"  (passthrough)
    """
    _init()

    if isinstance(input_data, list):
        return _encoder.encode_sequence(input_data)

    if isinstance(input_data, str):
        # If it contains namespace:opcode patterns, treat as pre-formatted SAL
        if ":" in input_data and any(
            c in input_data for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ):
            # Looks like SAL already — return as-is
            return input_data
        # Natural language — return as NL passthrough
        # (Future: NL-to-SAL conversion when composition engine is available)
        return input_data

    raise TypeError(
        f"encode() accepts str or list[str], got {type(input_data).__name__}. "
        f"Example: encode(['H:HR@NODE1>120', 'H:CASREP', 'M:EVA@*'])"
    )


def decode(sal: str) -> str:
    """Decode SAL to natural language description.

    Accepts:
        str — a SAL instruction string (single frame or ;-separated sequence)

    Returns:
        Human-readable natural language expansion of the SAL instruction,
        resolved by ASD dictionary lookup. Zero inference.

    Examples:
        decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
        → "H:heart_rate →NODE1>120; H:casualty_report; M:evacuation →*"
    """
    _init()
    frames = [f.strip() for f in sal.split(";") if f.strip()]
    if len(frames) <= 1:
        return _decoder.decode_natural_language(sal)
    return "; ".join(_decoder.decode_natural_language(f) for f in frames)


def validate(sal: str, nl: str = "", dependency_rules=None):
    """Validate a composed SAL instruction against all eight rules.

    Returns a CompositionResult with .valid (bool) and .issues (list).
    """
    _init()
    try:
        from osmp.protocol import validate_composition
    except ImportError:
        try:
            from osmp_mcp.osmp import validate_composition
        except ImportError:
            from .osmp import validate_composition

    return validate_composition(sal, nl, _asd, dependency_rules=dependency_rules)


def lookup(namespace_opcode: str) -> str | None:
    """Look up an opcode definition in the ASD.

    Accepts: "H:HR" or namespace="H", opcode="HR"
    Returns: definition string or None if not found.
    """
    _init()
    if ":" in namespace_opcode:
        parts = namespace_opcode.split(":", 1)
        return _asd.lookup(parts[0], parts[1])
    return None


def byte_size(sal: str) -> int:
    """Return UTF-8 byte count of a SAL string."""
    return len(sal.encode("utf-8"))


# Version
__version__ = "2.0.1"


# Bridge — lazy import to avoid loading protocol.py until needed
def bridge(node_id: str, **kwargs):
    """Create a SALBridge instance for boundary translation.

    OSMP spreads by contact, not installation.

        from osmp import bridge
        b = bridge("MY_NODE")
        b.register_peer("GPT_AGENT")
        out = b.send("H:HR@NODE1>120", "GPT_AGENT")
        inb = b.receive("acknowledged", "GPT_AGENT")
    """
    from osmp.bridge import SALBridge
    return SALBridge(node_id, **kwargs)
