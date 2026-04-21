"""
eml.py — Universal Binary Operator Evaluator (UBOT public reference)
====================================================================

Reference implementation of the Universal Binary Operator for mathematical
instruction encoding. Patent pending.

Based on Odrzywołek (2026, arXiv:2603.21852):

    eml(x, y) = exp(x) − ln(y)

This module is the PUBLIC library-free evaluator. It uses only the Python
standard library (`math`, `struct`, `hashlib`). It does NOT depend on
torch, numpy, scipy, or any external numerical package. It is intended
for deployment on constrained edge devices (LoRa/BLE receivers, phones,
microcontrollers) where construction-time machinery is not present.

----------------------------------------------------------------------------
Dual-mode precision
----------------------------------------------------------------------------

    safe_exp(z):  exp(z) with z clamped to [-EXP_CLAMP, +EXP_CLAMP]
    safe_log(y):  log(|y|) with |y| floored at LOG_EPS

    EXP_CLAMP = 50.0
    LOG_EPS   = 1e-30

Two precision modes:

    "fast"      — fdlibm-derived (1-ULP accurate, ships publicly in this package)
    "precision" — crlibm-derived (correctly-rounded, audit-grade)
                  AVAILABLE UNDER COMMERCIAL LICENSE.

Precision mode (correctly-rounded, cross-device deterministic, audit-grade
for regulated industries — medical IEC 62304, aerospace DO-178C, nuclear
IEC 61513, audit-grade finance) is available under commercial license.
Contact ack@octid.io for evaluation.

Calling set_precision_mode("precision") without the commercial precision
pack installed raises PrecisionModeNotAvailable.

----------------------------------------------------------------------------
Attribution
----------------------------------------------------------------------------

Built on the universal binary operator eml(x, y) = exp(x) − ln(y)
introduced by Andrzej Odrzywołek (Jagiellonian University,
arXiv:2603.21852, March 2026). The operator itself is not claimed by
any patent; the present work claims the transmission, encoding, and
apparatus layer distinct from the operator. This release ships the
evaluator, tree data structure, three wire formats, and a pre-verified
corpus of base chains and arithmetic compounds.

----------------------------------------------------------------------------
Wire formats supported
----------------------------------------------------------------------------

1. Paper tree form (tag-byte-encoded):
   - 0x00 + <IEEE 754 float32, 4 bytes> = leaf with constant value
   - 0x01 = branch (followed by left subtree, then right subtree)
   - 0x02 = variable-x leaf (no payload)
   - 0x03 + <IEEE 754 double, 8 bytes> = leaf with constant value (extended)

2. Restricted chain form (bit-packed, single variable x):
   - Level 1: 1 bit per input × 2 inputs; 0=1, 1=x
   - Level k≥2: 2 bits per input × 2 inputs; 00=1, 01=x, 10=f_{k-1}
   - Optional 4-bit length header when self-describing

3. Wide multi-variable chain form (bit-packed, V variables):
   - Header byte: (V in high nibble) | (N in low nibble); supports V≤15, N≤15
   - Level k: 2·ceil(log2(V + k)) bits total
   - Operand encoding at level k:
     - 0              → constant 1
     - 1..V           → variables (x_1, x_2, ..., x_V)
     - V+1..V+k-1     → prior level outputs (f_1, ..., f_{k-1})

Patent pending | License: Apache 2.0
"""
from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field

# ── Fast-mode backend (always available) ──────────────────────────────────
from osmp.fdlibm import exp as _fdlibm_exp, log as _fdlibm_log

# ── Precision-mode backend (commercial precision pack — stub in public) ──
from osmp.crlibm import exp as _crlibm_exp, log as _crlibm_log, AVAILABLE as _CRLIBM_AVAILABLE
from osmp.crlibm import PrecisionModeNotAvailable


# Precision mode: "fast" (fdlibm, 1-ULP) or "precision" (crlibm, correctly-rounded).
# Default is "fast" — the right choice for practically all UBOT applications.
PRECISION_MODE: str = "fast"


def set_precision_mode(mode: str) -> None:
    """Set the evaluator precision mode.

    Modes:
        "fast"      — fdlibm-derived, 1-ULP accurate, ships publicly
        "precision" — crlibm-derived, correctly-rounded; requires commercial precision pack

    Raises:
        ValueError: if mode is neither "fast" nor "precision"
        PrecisionModeNotAvailable: if "precision" is requested and the
            commercial precision pack is not installed. Contact
            ack@octid.io for evaluation.
    """
    global PRECISION_MODE
    if mode not in ("fast", "precision"):
        raise ValueError(f"Unknown precision mode: {mode!r}; use 'fast' or 'precision'")
    if mode == "precision" and not _CRLIBM_AVAILABLE:
        raise PrecisionModeNotAvailable(
            "Precision mode requires the commercial precision pack. "
            "Contact ack@octid.io or see PATENTS.md for license inquiries."
        )
    PRECISION_MODE = mode


def get_precision_mode() -> str:
    return PRECISION_MODE


def precision_mode_available() -> bool:
    """Whether the commercial precision-mode backend is installed."""
    return _CRLIBM_AVAILABLE


def _active_exp(x: float) -> float:
    if PRECISION_MODE == "precision":
        return _crlibm_exp(x)
    return _fdlibm_exp(x)


def _active_log(y: float) -> float:
    if PRECISION_MODE == "precision":
        return _crlibm_log(y)
    return _fdlibm_log(y)


# =============================================================================
# CORE OPERATOR
# =============================================================================

EXP_CLAMP: float = 50.0
LOG_EPS: float = 1e-30


def safe_exp(x: float) -> float:
    """exp(x) with argument clamped to [-EXP_CLAMP, +EXP_CLAMP].

    Uses the current PRECISION_MODE. Byte-exact across Python/Go/TypeScript
    within the selected mode.
    """
    if x > EXP_CLAMP:
        return _active_exp(EXP_CLAMP)
    if x < -EXP_CLAMP:
        return _active_exp(-EXP_CLAMP)
    return _active_exp(x)


def safe_log(y: float) -> float:
    """log(|y|) with |y| floored at LOG_EPS. Uses current PRECISION_MODE."""
    mag = abs(y)
    if mag < LOG_EPS:
        mag = LOG_EPS
    return _active_log(mag)


def eml(x: float, y: float) -> float:
    """The universal binary operator: eml(x, y) = safe_exp(x) − safe_log(y)."""
    return safe_exp(x) - safe_log(y)


# =============================================================================
# PAPER TREE REPRESENTATION
# =============================================================================

# Sentinel NaN bit-pattern for the variable-x leaf (cannot collide with a float constant).
_X_SENTINEL: float = struct.unpack('<d', struct.pack('<Q', 0x7FF8000000000001))[0]


def _is_x_sentinel(v: float) -> bool:
    return struct.pack('<d', v) == struct.pack('<d', _X_SENTINEL)


@dataclass
class EMLNode:
    """A node in an EML expression tree.

    Grammar:  S -> constant | var_x | eml(S, S)

    Leaves hold a constant (or the X sentinel). Branches apply eml(left, right).
    """
    left: 'EMLNode | None' = None
    right: 'EMLNode | None' = None
    value: float = 1.0

    @property
    def is_leaf(self) -> bool:
        return self.left is None

    @property
    def depth(self) -> int:
        if self.is_leaf:
            return 0
        return 1 + max(self.left.depth, self.right.depth)

    @property
    def node_count(self) -> int:
        if self.is_leaf:
            return 1
        return 1 + self.left.node_count + self.right.node_count

    def evaluate(self, x: float = 0.0) -> float:
        if self.is_leaf:
            return x if _is_x_sentinel(self.value) else self.value
        return eml(self.left.evaluate(x), self.right.evaluate(x))


def leaf(value: float = 1.0) -> EMLNode:
    return EMLNode(value=value)


def var_x() -> EMLNode:
    return EMLNode(value=_X_SENTINEL)


def node(left: EMLNode, right: EMLNode) -> EMLNode:
    return EMLNode(left=left, right=right)


ONE = leaf(1.0)


# =============================================================================
# PAPER TREE WIRE FORMAT
# =============================================================================

_TAG_LEAF_F32: int = 0x00
_TAG_BRANCH:   int = 0x01
_TAG_VAR_X:    int = 0x02
_TAG_LEAF_F64: int = 0x03


def encode_tree(tree: EMLNode, *, use_f64: bool = False) -> bytes:
    """Serialize an EML tree to the paper wire format."""
    buf = bytearray()
    _encode_node(tree, buf, use_f64)
    return bytes(buf)


def _encode_node(n: EMLNode, buf: bytearray, use_f64: bool) -> None:
    if n.is_leaf:
        if _is_x_sentinel(n.value):
            buf.append(_TAG_VAR_X)
        elif use_f64:
            buf.append(_TAG_LEAF_F64)
            buf.extend(struct.pack('<d', n.value))
        else:
            buf.append(_TAG_LEAF_F32)
            buf.extend(struct.pack('<f', n.value))
    else:
        buf.append(_TAG_BRANCH)
        _encode_node(n.left, buf, use_f64)
        _encode_node(n.right, buf, use_f64)


def decode_tree(data: bytes) -> EMLNode:
    node_result, offset = _decode_node(data, 0)
    if offset != len(data):
        raise ValueError(f"Trailing bytes after tree: {len(data) - offset}")
    return node_result


def _decode_node(data: bytes, offset: int) -> tuple[EMLNode, int]:
    if offset >= len(data):
        raise ValueError("Unexpected end of tree data")
    tag = data[offset]
    offset += 1
    if tag == _TAG_VAR_X:
        return var_x(), offset
    if tag == _TAG_LEAF_F32:
        v = struct.unpack('<f', data[offset:offset + 4])[0]
        return leaf(float(v)), offset + 4
    if tag == _TAG_LEAF_F64:
        v = struct.unpack('<d', data[offset:offset + 8])[0]
        return leaf(v), offset + 8
    if tag == _TAG_BRANCH:
        l, offset = _decode_node(data, offset)
        r, offset = _decode_node(data, offset)
        return node(l, r), offset
    raise ValueError(f"Invalid tree tag byte: 0x{tag:02x}")


# =============================================================================
# CHAIN REPRESENTATION
# =============================================================================

@dataclass
class ChainLevel:
    """A single chain level: two operands specified symbolically.

    Each operand is a string in a small language:
        "1"                     -> constant 1.0
        "x"                     -> variable x (single-variable)
        "x1", "x2", ...         -> variables by position (multi-variable)
        "f"                     -> f_{k-1} (restricted-chain shorthand)
        "f1", "f2", ...         -> f_k outputs (wide-chain explicit)
    """
    left: str
    right: str


@dataclass
class Chain:
    """A chain: ordered list of levels, + variable names, + grammar variant."""
    levels: list[ChainLevel]
    variables: list[str] = field(default_factory=lambda: ["x"])
    variant: str = "restricted"  # "restricted", "wide", or "wide_multivar"

    @property
    def n_levels(self) -> int:
        return len(self.levels)

    @property
    def n_variables(self) -> int:
        return len(self.variables)

    def evaluate(self, values) -> float:
        """Evaluate the chain.

        `values` may be:
            - a single float (when n_variables == 1)
            - a list/tuple of floats in positional order
            - a dict mapping variable-name -> float
        """
        var_map: dict[str, float] = {"1": 1.0}
        if isinstance(values, (int, float)):
            if self.n_variables != 1:
                raise ValueError(f"Scalar input but chain has {self.n_variables} variables")
            var_map[self.variables[0]] = float(values)
        elif isinstance(values, dict):
            for k, v in values.items():
                var_map[k] = float(v)
        else:
            values = list(values)
            if len(values) != self.n_variables:
                raise ValueError(f"Got {len(values)} values, expected {self.n_variables}")
            for nm, v in zip(self.variables, values):
                var_map[nm] = float(v)

        f: list[float] = []
        for k, lvl in enumerate(self.levels, start=1):
            a = _resolve_operand(lvl.left, var_map, f, k)
            b = _resolve_operand(lvl.right, var_map, f, k)
            f.append(eml(a, b))
        return f[-1] if f else 0.0


def _resolve_operand(op, var_map, f, k):
    if op == "1":
        return 1.0
    if op == "f":
        if k < 2:
            raise ValueError("'f' operand referenced at L1 (no prior level)")
        return f[k - 2]
    if op.startswith("f") and op[1:].isdigit():
        idx = int(op[1:])
        if idx < 1 or idx >= k:
            raise ValueError(f"'f{idx}' out of range at level {k}")
        return f[idx - 1]
    if op in var_map:
        return var_map[op]
    raise ValueError(f"Unknown operand code: {op!r}")


# =============================================================================
# RESTRICTED-CHAIN WIRE FORMAT
# =============================================================================

_R_L1_BITS_PER_INPUT = 1
_R_L1_CODE = {"1": 0, "x": 1}
_R_LK_BITS_PER_INPUT = 2
_R_LK_CODE = {"1": 0b00, "x": 0b01, "f": 0b10}


def encode_chain_restricted(chain: Chain, *, self_describing: bool = True) -> bytes:
    """Bit-pack a restricted chain to bytes."""
    if chain.variant != "restricted":
        raise ValueError(f"Not a restricted chain: {chain.variant!r}")
    if chain.n_variables != 1:
        raise ValueError("Restricted chain must be single-variable")
    var_name = chain.variables[0]

    bits: list[int] = []
    if self_describing:
        if chain.n_levels > 15:
            raise ValueError(f"Self-describing restricted format supports N≤15 (got {chain.n_levels})")
        for i in range(3, -1, -1):
            bits.append((chain.n_levels >> i) & 1)

    for k, lvl in enumerate(chain.levels, start=1):
        bits_per_input = _R_L1_BITS_PER_INPUT if k == 1 else _R_LK_BITS_PER_INPUT
        codebook = _R_L1_CODE if k == 1 else _R_LK_CODE
        for operand in (lvl.left, lvl.right):
            op = operand if operand != var_name else "x"
            if op not in codebook:
                raise ValueError(f"Operand {operand!r} not encodable in restricted chain at L{k}")
            code = codebook[op]
            for i in range(bits_per_input - 1, -1, -1):
                bits.append((code >> i) & 1)

    return _pack_bits(bits)


def decode_chain_restricted(data: bytes, *, self_describing: bool = True,
                            n_levels: int | None = None,
                            variable_name: str = "x") -> Chain:
    """Decode a restricted-chain wire payload to a Chain."""
    bits = _unpack_bits(data)
    offset = 0
    if self_describing:
        if n_levels is not None:
            raise ValueError("Cannot pass n_levels with self_describing=True")
        if len(bits) < 4:
            raise ValueError("Truncated self-describing header")
        n_levels = 0
        for i in range(4):
            n_levels = (n_levels << 1) | bits[offset]
            offset += 1
    if n_levels is None:
        raise ValueError("n_levels required when self_describing=False")

    _R_L1_DECODE = {v: k for k, v in _R_L1_CODE.items()}
    _R_LK_DECODE = {v: k for k, v in _R_LK_CODE.items()}

    levels: list[ChainLevel] = []
    for k in range(1, n_levels + 1):
        bits_per_input = _R_L1_BITS_PER_INPUT if k == 1 else _R_LK_BITS_PER_INPUT
        decoder = _R_L1_DECODE if k == 1 else _R_LK_DECODE
        ops: list[str] = []
        for _ in range(2):
            if offset + bits_per_input > len(bits):
                raise ValueError(f"Truncated payload at level {k}")
            code = 0
            for i in range(bits_per_input):
                code = (code << 1) | bits[offset]
                offset += 1
            if code not in decoder:
                raise ValueError(f"Reserved operand code {code:0{bits_per_input}b} at L{k}")
            op = decoder[code]
            ops.append(variable_name if op == "x" else op)
        levels.append(ChainLevel(left=ops[0], right=ops[1]))

    return Chain(levels=levels, variables=[variable_name], variant="restricted")


# =============================================================================
# WIDE MULTI-VARIABLE CHAIN WIRE FORMAT
# =============================================================================

def _bits_per_input_at_level(V: int, k: int) -> int:
    options = V + k
    b = 0
    while (1 << b) < options:
        b += 1
    return max(b, 1)


def encode_chain_wide(chain: Chain) -> bytes:
    """Bit-pack a wide (multi-variable) chain to bytes."""
    if chain.variant not in ("wide", "wide_multivar"):
        raise ValueError(f"Not a wide chain: {chain.variant!r}")
    V = chain.n_variables
    N = chain.n_levels
    if V < 1 or V > 255 or N < 1 or N > 255:
        raise ValueError(f"V={V}, N={N} out of supported range (1..255)")

    var_index: dict[str, int] = {v: i for i, v in enumerate(chain.variables, start=1)}

    bits: list[int] = []
    if V <= 15 and N <= 15:
        header = (V << 4) | N
        _push_byte(bits, header)
    else:
        _push_byte(bits, 0xFF)
        _push_byte(bits, N)
        _push_byte(bits, V)

    for k, lvl in enumerate(chain.levels, start=1):
        bpi = _bits_per_input_at_level(V, k)
        for operand in (lvl.left, lvl.right):
            idx = _wide_operand_index(operand, var_index, V, k)
            for i in range(bpi - 1, -1, -1):
                bits.append((idx >> i) & 1)

    return _pack_bits(bits)


def _wide_operand_index(op, var_index, V, k):
    if op == "1":
        return 0
    if op in var_index:
        return var_index[op]
    if op == "f":
        if k < 2:
            raise ValueError("'f' operand at L1")
        return V + (k - 1)
    if op.startswith("f") and op[1:].isdigit():
        fi = int(op[1:])
        if fi < 1 or fi >= k:
            raise ValueError(f"f{fi} out of range at L{k}")
        return V + fi
    raise ValueError(f"Unknown operand {op!r}")


def decode_chain_wide(data: bytes, *, variables: list[str] | None = None) -> Chain:
    bits = _unpack_bits(data)
    offset = 0
    header = 0
    for _ in range(8):
        header = (header << 1) | bits[offset]
        offset += 1
    if header == 0xFF:
        N = 0
        for _ in range(8):
            N = (N << 1) | bits[offset]; offset += 1
        V = 0
        for _ in range(8):
            V = (V << 1) | bits[offset]; offset += 1
    else:
        V = (header >> 4) & 0x0F
        N = header & 0x0F

    if variables is None:
        variables = [f"x{i}" for i in range(1, V + 1)]
    elif len(variables) != V:
        raise ValueError(f"Got {len(variables)} variable names, header says V={V}")

    idx_to_var: dict[int, str] = {i: v for i, v in enumerate(variables, start=1)}

    levels: list[ChainLevel] = []
    for k in range(1, N + 1):
        bpi = _bits_per_input_at_level(V, k)
        ops: list[str] = []
        for _ in range(2):
            if offset + bpi > len(bits):
                raise ValueError(f"Truncated payload at level {k}")
            idx = 0
            for i in range(bpi):
                idx = (idx << 1) | bits[offset]; offset += 1
            if idx == 0:
                ops.append("1")
            elif idx <= V:
                ops.append(idx_to_var[idx])
            elif idx < V + k:
                ops.append(f"f{idx - V}")
            else:
                raise ValueError(f"Operand index {idx} out of range at L{k} (V={V})")
        levels.append(ChainLevel(left=ops[0], right=ops[1]))

    return Chain(levels=levels, variables=variables, variant="wide_multivar")


def _pack_bits(bits: list[int]) -> bytes:
    n = (len(bits) + 7) // 8
    out = bytearray(n)
    for i, b in enumerate(bits):
        if b:
            out[i // 8] |= (1 << (7 - (i % 8)))
    return bytes(out)


def _unpack_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _push_byte(bits: list[int], byte: int) -> None:
    for i in range(7, -1, -1):
        bits.append((byte >> i) & 1)


# =============================================================================
# BASE TREE DERIVATIONS
# =============================================================================

def tree_exp_x() -> EMLNode:
    """exp(x) = eml(x, 1). Depth 1."""
    return node(var_x(), ONE)


def tree_ln_x() -> EMLNode:
    """ln(x) = eml(1, eml(eml(1, x), 1)). Depth 3."""
    inner = node(ONE, var_x())
    mid = node(inner, ONE)
    return node(ONE, mid)


def tree_identity() -> EMLNode:
    """x = eml(ln(x), 1). Depth 4."""
    return node(tree_ln_x(), ONE)


def tree_zero() -> EMLNode:
    """0 via eml(1, eml(eml(1,1),1)) = e - ln(exp(e)) = 0."""
    inner = node(ONE, ONE)
    mid = node(inner, ONE)
    return node(ONE, mid)


def tree_exp_exp_x() -> EMLNode:
    """exp(exp(x)) = eml(eml(x,1),1). Depth 2."""
    return node(node(var_x(), ONE), ONE)


# =============================================================================
# BASE CORPUS — 16 pre-verified restricted-chain structures
# =============================================================================

BASE_CHAIN_STRUCTURES: dict[str, list[tuple[str, str]]] = {
    "exp(x)":             [("x", "1")],
    "ln(x)":              [("1", "x"), ("f", "1"), ("1", "f")],
    "identity":           [("1", "x"), ("f", "1"), ("1", "f"), ("f", "1")],
    "zero":               [("1", "1"), ("f", "1"), ("1", "f")],
    "exp(x)-ln(x)":       [("x", "x")],
    "exp(x)-x":           [("x", "1"), ("x", "f")],
    "e-x":                [("x", "1"), ("1", "f")],
    "exp(exp(x))":        [("x", "1"), ("f", "1")],
    "e-exp(x)":           [("x", "1"), ("f", "1"), ("1", "f")],
    "1-ln(x)":            [("1", "1"), ("f", "1"), ("1", "f"), ("f", "x")],
    "e/x":                [("1", "1"), ("f", "1"), ("1", "f"), ("f", "x"), ("f", "1")],
    "exp(x)-1":           [("1", "1"), ("x", "f")],
    "exp(x)-e":           [("1", "1"), ("f", "1"), ("x", "f")],
    "e^e/x":              [("1", "x"), ("f", "1")],
    "ln(ln(x))":          [("1", "x"), ("f", "1"), ("1", "f"),
                           ("1", "f"), ("f", "1"), ("1", "f")],
    "exp(exp(exp(x)))":   [("x", "1"), ("f", "1"), ("f", "1")],
}


def chain_from_pairs(pairs: list[tuple[str, str]], variable: str = "x") -> Chain:
    levels = [ChainLevel(left=a, right=b) for a, b in pairs]
    return Chain(levels=levels, variables=[variable], variant="restricted")


def get_base_chain(name: str) -> Chain:
    if name not in BASE_CHAIN_STRUCTURES:
        raise KeyError(f"Unknown base corpus entry: {name!r}")
    return chain_from_pairs(BASE_CHAIN_STRUCTURES[name])


# =============================================================================
# ARITHMETIC COMPOUNDS — wide multi-variable chains
# =============================================================================

COMPOUND_NEG_Y: list[tuple[str, str]] = [
    ("1", "1"), ("f1", "1"), ("1", "f2"),
    ("1", "f3"), ("f4", "1"), ("1", "f5"),
    ("y", "1"), ("f6", "f7"),
]

COMPOUND_X_PLUS_Y: list[tuple[str, str]] = [
    ("1", "1"), ("f1", "1"), ("1", "f2"),
    ("1", "f3"), ("f4", "1"), ("1", "f5"),
    ("y", "1"), ("f6", "f7"),
    ("1", "x"), ("f9", "1"), ("1", "f10"),
    ("f8", "1"),
    ("f11", "f12"),
]

COMPOUND_X_TIMES_Y: list[tuple[str, str]] = [
    ("1", "1"), ("f1", "1"), ("1", "f2"),
    ("1", "x"), ("f4", "1"), ("1", "f5"),
    ("1", "y"), ("f7", "1"), ("1", "f8"),
    ("1", "f3"), ("f10", "1"), ("1", "f11"),
    ("f12", "y"),
    ("1", "f6"), ("f14", "1"), ("1", "f15"),
    ("f13", "1"),
    ("f16", "f17"),
    ("f18", "1"),
]

COMPOUND_LINEAR_CALIBRATION: list[tuple[str, str]] = [
    ("1", "1"), ("f1", "1"), ("1", "f2"),
    ("1", "a"), ("f4", "1"), ("1", "f5"),
    ("1", "x"), ("f7", "1"), ("1", "f8"),
    ("1", "f3"), ("f10", "1"), ("1", "f11"),
    ("f12", "x"),
    ("1", "f6"), ("f14", "1"), ("1", "f15"),
    ("f13", "1"),
    ("f16", "f17"),
    ("f18", "1"),
    ("b", "1"),
    ("f12", "f20"),
    ("1", "f19"), ("f22", "1"), ("1", "f23"),
    ("f21", "1"),
    ("f24", "f25"),
]


def compound_neg_y() -> Chain:
    return Chain(
        levels=[ChainLevel(a, b) for a, b in COMPOUND_NEG_Y],
        variables=["y"], variant="wide_multivar",
    )


def compound_x_plus_y() -> Chain:
    return Chain(
        levels=[ChainLevel(a, b) for a, b in COMPOUND_X_PLUS_Y],
        variables=["x", "y"], variant="wide_multivar",
    )


def compound_x_times_y() -> Chain:
    return Chain(
        levels=[ChainLevel(a, b) for a, b in COMPOUND_X_TIMES_Y],
        variables=["x", "y"], variant="wide_multivar",
    )


def compound_linear_calibration() -> Chain:
    return Chain(
        levels=[ChainLevel(a, b) for a, b in COMPOUND_LINEAR_CALIBRATION],
        variables=["a", "x", "b"], variant="wide_multivar",
    )


# =============================================================================
# DETERMINISM FINGERPRINT
# =============================================================================

CANONICAL_INPUTS: list[float] = [
    0.5, 1.0, 1.5, 2.0, math.e, math.pi, 3.0, 5.0, 7.0, 10.0,
]


def evaluate_base_corpus_at_canonical() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for name in BASE_CHAIN_STRUCTURES:
        chain = get_base_chain(name)
        out[name] = [chain.evaluate(x) for x in CANONICAL_INPUTS]
    return out


def evaluate_compound_at_canonical() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    out["neg_y"] = [compound_neg_y().evaluate([y]) for y in CANONICAL_INPUTS]
    pairs = [(x, y) for x in CANONICAL_INPUTS for y in CANONICAL_INPUTS]
    out["x_plus_y"] = [compound_x_plus_y().evaluate([x, y]) for x, y in pairs]
    out["x_times_y"] = [compound_x_times_y().evaluate([x, y]) for x, y in pairs]
    triples = [(a, x, b)
               for a in [0.5, 1.0, math.pi]
               for x in [1.0, math.e]
               for b in [0.5, 1.0, math.e]]
    out["linear_calibration"] = [
        compound_linear_calibration().evaluate([a, x, b]) for a, x, b in triples
    ]
    return out


def corpus_fingerprint() -> str:
    """SHA-256 over IEEE 754 double byte-representation of corpus outputs.

    Cross-device and cross-language determinism check: two compliant
    implementations MUST produce the same fingerprint when they evaluate
    the same corpus at the same canonical inputs under the same mode.
    """
    h = hashlib.sha256()
    base = evaluate_base_corpus_at_canonical()
    for name in BASE_CHAIN_STRUCTURES:
        h.update(name.encode("utf-8"))
        h.update(b":")
        for y in base[name]:
            h.update(struct.pack("<d", y))
    compound = evaluate_compound_at_canonical()
    for name in ("neg_y", "x_plus_y", "x_times_y", "linear_calibration"):
        h.update(name.encode("utf-8"))
        h.update(b":")
        for y in compound[name]:
            h.update(struct.pack("<d", y))
    return h.hexdigest()


# =============================================================================
# CLI / SELF-TEST
# =============================================================================

def _self_test() -> None:
    print("eml.py evaluator — self-test")
    print("=" * 60)
    print(f"EXP_CLAMP = {EXP_CLAMP}")
    print(f"LOG_EPS   = {LOG_EPS}")
    print(f"Precision mode available: {precision_mode_available()}")
    print()

    print("Base corpus (restricted chain):")
    base = evaluate_base_corpus_at_canonical()
    for name in BASE_CHAIN_STRUCTURES:
        chain = get_base_chain(name)
        sample = base[name][0]
        print(f"  {name:25s}  L={chain.n_levels:2d}  @x=0.5 -> {sample!r}")
    print()

    print("Arithmetic compounds (wide multi-variable chain):")
    print(f"  neg_y(2.0)                        -> {compound_neg_y().evaluate([2.0])!r}  (target -2.0)")
    print(f"  x_plus_y(2.0, 3.0)                -> {compound_x_plus_y().evaluate([2.0, 3.0])!r}  (target 5.0)")
    print(f"  x_times_y(2.0, 3.0)               -> {compound_x_times_y().evaluate([2.0, 3.0])!r}  (target 6.0)")
    print(f"  linear_calibration(2.0, 3.0, 1.0) -> {compound_linear_calibration().evaluate([2.0, 3.0, 1.0])!r}  (target 7.0)")
    print()

    tree = tree_ln_x()
    enc = encode_tree(tree)
    dec = decode_tree(enc)
    print(f"Tree wire format round-trip:")
    print(f"  ln(x) tree: {len(enc)} bytes, decoded@x=e -> {dec.evaluate(math.e)!r}  (target 1.0)")

    ch = get_base_chain("ln(x)")
    enc_r = encode_chain_restricted(ch, self_describing=True)
    dec_r = decode_chain_restricted(enc_r, self_describing=True)
    print(f"  ln(x) restricted chain: {len(enc_r)} bytes, decoded@x=e -> {dec_r.evaluate(math.e)!r}  (target 1.0)")

    ch_wide = compound_neg_y()
    enc_w = encode_chain_wide(ch_wide)
    dec_w = decode_chain_wide(enc_w, variables=["y"])
    print(f"  neg_y wide chain: {len(enc_w)} bytes, decoded@y=2.0 -> {dec_w.evaluate([2.0])!r}  (target -2.0)")
    print()

    print("Corpus determinism fingerprints (SHA-256):")
    set_precision_mode("fast")
    print(f"  fast      mode (fdlibm, 1-ULP):    {corpus_fingerprint()}")
    if precision_mode_available():
        set_precision_mode("precision")
        print(f"  precision mode (crlibm, 0-ULP):    {corpus_fingerprint()}")
        set_precision_mode("fast")
    else:
        print(f"  precision mode: available under commercial license")
        print(f"    (contact ack@octid.io or see PATENTS.md)")


if __name__ == "__main__":
    _self_test()
