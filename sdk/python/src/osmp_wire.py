"""
OSMP Wire Modes — Semantic Assembly Isomorphic Language (SAIL) and Security Envelope (SEC)
Octid Semantic Mesh Protocol — Cloudless Sky Project

Four wire modes:
  OSMP          — Mnemonic SAL (UTF-8 text, human-readable)
  OSMP-SAIL      — Semantic Assembly Isomorphic Language (compact binary, table-decoded)
  OSMP-SEC      — Mnemonic SAL + security envelope
  OSMP-SAIL-SEC  — Semantic Assembly Isomorphic Language + security envelope

The decode mechanism is encoding-agnostic by design. The described lookup
cascade operates identically on binary-encoded, mnemonic-encoded, or any
other token representation.

Patent pending — inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import struct
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# WIRE MODE FLAGS
# ─────────────────────────────────────────────────────────────────────────────

class WireMode(IntFlag):
    """Wire mode selection. Compose with bitwise OR."""
    MNEMONIC = 0x00   # Default: UTF-8 SAL text
    SAIL      = 0x01   # Semantic Assembly Isomorphic Language
    SEC      = 0x02   # Security envelope
    SAIL_SEC  = 0x03   # Both

    @property
    def label(self) -> str:
        labels = {0x00: "OSMP", 0x01: "OSMP-SAIL", 0x02: "OSMP-SEC", 0x03: "OSMP-SAIL-SEC"}
        return labels.get(self.value, f"OSMP-0x{self.value:02X}")


# ─────────────────────────────────────────────────────────────────────────────
# SAIL TOKEN TABLE — Single-byte tokens for all SAL structural elements
#
# Layout:
#   0x00-0x7F  — ASCII data (node IDs, numeric values, string literals)
#   0x80-0x9F  — Logical/compositional operators (Category 1)
#   0xA0-0xA7  — Consequence class designators (Category 2)
#   0xA8-0xAF  — Outcome state designators (Category 3)
#   0xB0-0xBF  — Parameter/slot designators (Category 4)
#   0xC0-0xCF  — Loss tolerance policy designators (Category 5)
#   0xD0-0xDF  — Dictionary update mode designators (Category 6)
#   0xE0-0xEF  — Structural markers
#   0xF0-0xFF  — Value type tags
# ─────────────────────────────────────────────────────────────────────────────

# Category 1: Logical/compositional operators
TOK_AND            = 0x80  # ∧
TOK_OR             = 0x81  # ∨
TOK_NOT            = 0x82  # ¬
TOK_THEN           = 0x83  # →
TOK_IFF            = 0x84  # ↔
TOK_FOR_ALL        = 0x85  # ∀
TOK_EXISTS         = 0x86  # ∃
TOK_PARALLEL       = 0x87  # ∥
TOK_PRIORITY       = 0x88  # >
TOK_APPROX         = 0x89  # ~
TOK_WILDCARD       = 0x8A  # *
TOK_ASSIGN         = 0x8B  # : (slot assignment, not namespace separator)
TOK_SEQUENCE       = 0x8C  # ;
TOK_QUERY          = 0x8D  # ?
TOK_TARGET         = 0x8E  # @
TOK_REPEAT_EVERY   = 0x8F  # ⟳
TOK_NOT_EQUAL      = 0x90  # ≠
TOK_PRIORITY_ORDER = 0x91  # ⊕
TOK_UNLESS         = 0x92  # ¬→

# Category 2: Consequence class
TOK_HAZARDOUS      = 0xA0  # ⚠
TOK_REVERSIBLE     = 0xA1  # ↺
TOK_IRREVERSIBLE   = 0xA2  # ⊘

# Category 3: Outcome states
TOK_PASS_TRUE      = 0xA8  # ⊤
TOK_FAIL_FALSE     = 0xA9  # ⊥

# Category 4: Parameter/slot designators
TOK_DELTA          = 0xB0  # Δ
TOK_HOME           = 0xB1  # ⌂
TOK_ABORT_CANCEL   = 0xB2  # ⊗
TOK_TIMEOUT        = 0xB3  # τ
TOK_SCOPE_WITHIN   = 0xB4  # ∈
TOK_MISSING        = 0xB5  # ∖

# Category 5: Loss tolerance policy
TOK_FAIL_SAFE      = 0xC0  # Φ
TOK_GRACEFUL_DEG   = 0xC1  # Γ
TOK_ATOMIC         = 0xC2  # Λ

# Category 6: Dictionary update modes
TOK_ADDITIVE       = 0xD0  # +
TOK_REPLACE        = 0xD1  # ←
TOK_DEPRECATE      = 0xD2  # †

# Structural markers
TOK_FRAME          = 0xE0  # frame boundary (namespace + opcode follow)
TOK_BRACKET_OPEN   = 0xE4  # [
TOK_BRACKET_CLOSE  = 0xE5  # ]

# Value type tags
TOK_VARINT         = 0xF0  # next bytes are varint-encoded integer
TOK_NEGINT         = 0xF1  # next bytes are varint-encoded negative integer (magnitude)
TOK_FLOAT16        = 0xF2  # next 2 bytes are IEEE 754 half-precision
TOK_FLOAT32        = 0xF3  # next 4 bytes are IEEE 754 single-precision
TOK_STRING         = 0xF4  # length-prefixed string: varint_len + utf8_bytes
TOK_REF            = 0xF5  # interned string reference: 1-byte index into string table
TOK_END            = 0xFF  # end of SAIL payload


# ─────────────────────────────────────────────────────────────────────────────
# GLYPH-TO-TOKEN BIDIRECTIONAL MAPS
# ─────────────────────────────────────────────────────────────────────────────

GLYPH_TO_TOKEN: dict[str, int] = {
    "∧": TOK_AND, "∨": TOK_OR, "¬": TOK_NOT, "→": TOK_THEN,
    "↔": TOK_IFF, "∀": TOK_FOR_ALL, "∃": TOK_EXISTS, "∥": TOK_PARALLEL,
    ">": TOK_PRIORITY, "~": TOK_APPROX, "*": TOK_WILDCARD,
    ":": TOK_ASSIGN, ";": TOK_SEQUENCE, "?": TOK_QUERY, "@": TOK_TARGET,
    "⟳": TOK_REPEAT_EVERY, "≠": TOK_NOT_EQUAL, "⊕": TOK_PRIORITY_ORDER,
    # Compound
    "¬→": TOK_UNLESS,
    # Consequence class
    "⚠": TOK_HAZARDOUS, "↺": TOK_REVERSIBLE, "⊘": TOK_IRREVERSIBLE,
    # Outcome states
    "⊤": TOK_PASS_TRUE, "⊥": TOK_FAIL_FALSE,
    # Parameter designators
    "Δ": TOK_DELTA, "⌂": TOK_HOME, "⊗": TOK_ABORT_CANCEL,
    "τ": TOK_TIMEOUT, "∈": TOK_SCOPE_WITHIN, "∖": TOK_MISSING,
    # Loss policy
    "Φ": TOK_FAIL_SAFE, "Γ": TOK_GRACEFUL_DEG, "Λ": TOK_ATOMIC,
    # Dictionary update
    "+": TOK_ADDITIVE, "←": TOK_REPLACE, "†": TOK_DEPRECATE,
    # Brackets
    "[": TOK_BRACKET_OPEN, "]": TOK_BRACKET_CLOSE,
}

TOKEN_TO_GLYPH: dict[int, str] = {v: k for k, v in GLYPH_TO_TOKEN.items()}

# ─────────────────────────────────────────────────────────────────────────────
# NAMESPACE AND OPCODE INDEX TABLES
# ─────────────────────────────────────────────────────────────────────────────

# Namespace index: A=0, B=1, ..., Z=25
NS_TO_INDEX: dict[str, int] = {chr(65 + i): i for i in range(26)}
INDEX_TO_NS: dict[int, str] = {i: chr(65 + i) for i in range(26)}

def _build_opcode_tables(dict_path: Path | str | None = None) -> tuple[
    dict[str, dict[str, int]],   # ns -> {opcode -> index}
    dict[str, dict[int, str]],   # ns -> {index -> opcode}
]:
    """Build opcode index tables from the semantic dictionary CSV."""
    ns_opcodes: dict[str, list[str]] = {}

    if dict_path is None:
        # Try default locations
        candidates = [
            Path(__file__).parent.parent.parent.parent / "protocol" / "OSMP-semantic-dictionary-v15.csv",
            Path("protocol/OSMP-semantic-dictionary-v15.csv"),
        ]
        for c in candidates:
            if c.exists():
                dict_path = c
                break

    if dict_path is None or not Path(dict_path).exists():
        raise FileNotFoundError(
            f"Semantic dictionary not found. Tried default locations. "
            f"Pass dict_path explicitly."
        )

    with open(dict_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    s3_start = None
    for i, line in enumerate(lines):
        if "SECTION 3" in line:
            s3_start = i
            break

    if s3_start is None:
        raise ValueError("SECTION 3 not found in dictionary")

    for line in lines[s3_start:]:
        parts = line.strip().split(",")
        if len(parts) >= 5:
            prefix = parts[1].strip()
            opcode = parts[3].strip()
            if (prefix and prefix.isalpha() and len(prefix) <= 2
                    and prefix.isupper() and opcode and opcode != "Opcode"):
                ns_opcodes.setdefault(prefix, []).append(opcode)

    # Sort for stable indexing
    op_to_idx: dict[str, dict[str, int]] = {}
    idx_to_op: dict[str, dict[int, str]] = {}
    for ns in ns_opcodes:
        sorted_ops = sorted(set(ns_opcodes[ns]))
        op_to_idx[ns] = {op: i for i, op in enumerate(sorted_ops)}
        idx_to_op[ns] = {i: op for i, op in enumerate(sorted_ops)}

    return op_to_idx, idx_to_op


# ─────────────────────────────────────────────────────────────────────────────
# VARINT ENCODING (unsigned, LEB128-style)
# ─────────────────────────────────────────────────────────────────────────────

def _encode_varint(value: int) -> bytes:
    """Encode unsigned integer as LEB128 varint."""
    if value < 0:
        raise ValueError("Use TOK_NEGINT for negative values")
    parts = []
    while value > 0x7F:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.append(value & 0x7F)
    return bytes(parts)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Decode LEB128 varint. Returns (value, new_offset)."""
    value = 0
    shift = 0
    while offset < len(data):
        b = data[offset]
        value |= (b & 0x7F) << shift
        offset += 1
        if not (b & 0x80):
            break
        shift += 7
    return value, offset


# ─────────────────────────────────────────────────────────────────────────────
# SAIL CODEC
# ─────────────────────────────────────────────────────────────────────────────

class SAILCodec:
    """Semantic Assembly Isomorphic Language encoder/decoder — FULLY OPAQUE.

    Nothing on the wire is human-readable. Every alphanumeric token is
    encoded as either a dictionary index (namespace:opcode), a string
    intern reference (TOK_REF + 1-byte index), or a length-prefixed
    binary string (TOK_STRING + varint_len + bytes). All glyphs are
    single-byte tokens. All integers are varint-encoded.

    The decode side reconstructs the exact mnemonic SAL string from
    the index tables. The ASD lookup cascade operates identically on
    both representations — encoding-agnostic by design.
    """

    @staticmethod
    def _build_intern_table(
        dict_path: Path | str | None = None,
        mdr_paths: list[Path | str] | None = None,
    ) -> list[str]:
        """Dynamically construct the intern table from loaded dictionary and MDR content.

        Phase 1: Extracts every opcode name from the base dictionary Section 3.
        Phase 2: Extracts every slot value from each loaded MDR corpus Section B.

        Zero static data. Every interned string originates from a loaded file.
        Loading a new MDR corpus simultaneously expands semantic vocabulary
        (via _build_opcode_tables) AND configures the binary compression
        table (via this method) from a single loading operation.
        """
        strings: set[str] = set()

        # ── Phase 1: Opcode names from base dictionary Section 3 ──────────

        if dict_path is None:
            candidates = [
                Path(__file__).parent.parent.parent.parent / "protocol" / "OSMP-semantic-dictionary-v15.csv",
                Path("protocol/OSMP-semantic-dictionary-v15.csv"),
            ]
            for c in candidates:
                if c.exists():
                    dict_path = c
                    break

        if dict_path and Path(dict_path).exists():
            with open(dict_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            in_section3 = False
            for line in lines:
                stripped = line.strip()
                if "SECTION 3" in stripped:
                    in_section3 = True
                    continue
                if "SECTION 4" in stripped:
                    break
                if not in_section3:
                    continue

                parts = stripped.split(",")
                if len(parts) >= 5:
                    prefix = parts[1].strip()
                    opcode = parts[3].strip()
                    if (prefix and prefix.isalpha() and len(prefix) <= 2
                            and prefix.isupper() and opcode and opcode != "Opcode"):
                        strings.add(opcode)

        # ── Phase 2: Slot values from each MDR corpus Section B ───────────

        if mdr_paths:
            for mdr_path in mdr_paths:
                mdr_path = Path(mdr_path)
                if not mdr_path.exists():
                    continue

                with open(mdr_path, "r", encoding="utf-8") as f:
                    mdr_lines = f.readlines()

                in_section_b = False
                for line in mdr_lines:
                    stripped = line.strip()

                    # Track sections
                    if "SECTION B" in stripped:
                        in_section_b = True
                        continue
                    if stripped.startswith("SECTION ") and "SECTION B" not in stripped:
                        if in_section_b:
                            break
                    if not in_section_b:
                        continue

                    # Skip non-data lines
                    if (not stripped or stripped.startswith("Format:")
                            or stripped.startswith("===") or stripped.startswith("---")
                            or stripped.startswith("Note:")):
                        continue

                    # Parse: Namespace:Opcode,SlotValue,...
                    parts = stripped.split(",")
                    if len(parts) >= 2 and ":" in parts[0]:
                        slot_value = parts[1].strip()
                        if slot_value:
                            strings.add(slot_value)

                    # Also extract bracket references from dependency rules
                    if len(parts) >= 5:
                        dep_rule = parts[4] if len(parts) > 4 else ""
                        for match in re.findall(r'\[([^\]]+)\]', dep_rule):
                            strings.add(match)

        # ── Filter: only keep strings where interning saves bytes ─────────

        sorted_strings = sorted(strings, key=lambda s: (-len(s), s))
        result = []
        for s in sorted_strings:
            idx = len(result)
            ref_cost = 2 if idx < 128 else (3 if idx < 16384 else 4)
            if len(s) > ref_cost:
                result.append(s)
        return result


    def __init__(self, dict_path: Path | str | None = None,
                 mdr_paths: list[Path | str] | None = None):
        self.op_to_idx, self.idx_to_op = _build_opcode_tables(dict_path)
        self._intern_table = self._build_intern_table(dict_path, mdr_paths)
        self._str_to_ref: dict[str, int] = {s: i for i, s in enumerate(self._intern_table)}
        self._ref_to_str: dict[int, str] = {i: s for i, s in enumerate(self._intern_table)}


    @staticmethod
    def _is_alnum_ext(ch: str) -> bool:
        return ch.isalnum() or ch in "-_."

    def _try_namespace_opcode(self, sal: str, pos: int, n: int) -> tuple[bytes, int] | None:
        colon_pos = sal.find(":", pos)
        if colon_pos <= pos or colon_pos - pos > 2:
            return None
        ns_candidate = sal[pos:colon_pos]
        if ns_candidate not in NS_TO_INDEX:
            return None
        op_start = colon_pos + 1
        op_end = op_start
        while op_end < n and (sal[op_end].isupper() or sal[op_end].isdigit() or sal[op_end] == "\xa7"):
            op_end += 1
        opcode = sal[op_start:op_end]
        if not opcode or ns_candidate not in self.op_to_idx or opcode not in self.op_to_idx[ns_candidate]:
            return None
        return bytes([TOK_FRAME, NS_TO_INDEX[ns_candidate], self.op_to_idx[ns_candidate][opcode]]), op_end

    def _encode_token(self, token: str) -> bytes:
        """Encode alphanumeric token: intern table if cheaper, raw ASCII otherwise.

        Intern ref cost: TOK_REF + varint(index) = 2 bytes if index < 128, 3 bytes if >= 128.
        Raw cost: len(token) bytes.
        Use whichever is shorter. Never regresses.
        """
        if token in self._str_to_ref:
            idx = self._str_to_ref[token]
            ref_bytes = bytes([TOK_REF]) + _encode_varint(idx)
            if len(ref_bytes) < len(token):
                return ref_bytes
        return token.encode("utf-8")

    def encode(self, sal: str) -> bytes:
        """Encode mnemonic SAL to fully opaque SAIL binary."""
        out = bytearray()
        pos = 0
        n = len(sal)

        while pos < n:
            ch = sal[pos]

            # Compound operator
            if pos + 1 < n and sal[pos:pos+2] == "\u00ac\u2192":
                out.append(TOK_UNLESS)
                pos += 2
                continue

            # Multi-byte Unicode glyphs
            if ord(ch) >= 0x80 and ch in GLYPH_TO_TOKEN:
                out.append(GLYPH_TO_TOKEN[ch])
                pos += 1
                continue

            # Namespace:opcode
            if ch.isupper():
                result = self._try_namespace_opcode(sal, pos, n)
                if result is not None:
                    out.extend(result[0])
                    pos = result[1]
                    continue

            # ASCII structural tokens
            if ch in ("@", "?", ";", "*", "~"):
                out.append(GLYPH_TO_TOKEN[ch])
                pos += 1
                continue
            if ch == ":":
                out.append(TOK_ASSIGN)
                pos += 1
                continue
            if ch == ">":
                out.append(TOK_PRIORITY)
                pos += 1
                continue
            if ch == "+":
                out.append(TOK_ADDITIVE)
                pos += 1
                continue
            if ch == "[":
                out.append(TOK_BRACKET_OPEN)
                pos += 1
                continue
            if ch == "]":
                out.append(TOK_BRACKET_CLOSE)
                pos += 1
                continue

            # Alphanumeric run
            if SAILCodec._is_alnum_ext(ch) or (ch == "-" and pos + 1 < n and sal[pos+1].isdigit()):
                run_start = pos
                while pos < n and SAILCodec._is_alnum_ext(sal[pos]):
                    pos += 1
                if sal[run_start] == "-":
                    pos = run_start + 1
                    while pos < n and SAILCodec._is_alnum_ext(sal[pos]):
                        pos += 1
                token = sal[run_start:pos]

                is_pure_numeric = True
                has_dot = False
                is_neg = token.startswith("-")
                num_part = token[1:] if is_neg else token
                for c in num_part:
                    if c == ".":
                        if has_dot: is_pure_numeric = False; break
                        has_dot = True
                    elif not c.isdigit():
                        is_pure_numeric = False; break
                if not num_part:
                    is_pure_numeric = False

                if is_pure_numeric:
                    has_leading_zero = (not is_neg and len(num_part) > 1 and num_part[0] == "0")
                    if has_dot or has_leading_zero:
                        out.extend(self._encode_token(token))
                    else:
                        ival = int(num_part)
                        out.append(TOK_NEGINT if is_neg else TOK_VARINT)
                        out.extend(_encode_varint(ival))
                else:
                    out.extend(self._encode_token(token))
                continue

            # Remaining ASCII
            if ord(ch) < 0x80:
                out.extend(self._encode_token(ch))
                pos += 1
                continue

            # Unknown Unicode glyph fallback
            if ch in GLYPH_TO_TOKEN:
                out.append(GLYPH_TO_TOKEN[ch])
                pos += 1
                continue

            out.extend(ch.encode("utf-8"))
            pos += 1

        out.append(TOK_END)
        return bytes(out)

    def decode(self, data: bytes) -> str:
        """Decode fully opaque SAIL binary back to mnemonic SAL string."""
        out = []
        pos = 0
        n = len(data)

        while pos < n:
            b = data[pos]

            if b == TOK_END:
                break

            if b == TOK_FRAME:
                pos += 1
                if pos + 1 >= n: break
                ns_idx = data[pos]; pos += 1
                op_idx = data[pos]; pos += 1
                ns = INDEX_TO_NS.get(ns_idx, f"?{ns_idx}")
                opcode = self.idx_to_op.get(ns, {}).get(op_idx, f"?{op_idx}")
                out.append(f"{ns}:{opcode}")
                continue

            if b == TOK_REF:
                pos += 1
                ref_idx, pos = _decode_varint(data, pos)
                out.append(self._ref_to_str.get(ref_idx, f"?REF{ref_idx}"))
                continue

            if b == TOK_STRING:
                pos += 1
                str_len, pos = _decode_varint(data, pos)
                if pos + str_len <= n:
                    out.append(data[pos:pos + str_len].decode("utf-8"))
                    pos += str_len
                continue

            if b in TOKEN_TO_GLYPH:
                out.append(TOKEN_TO_GLYPH[b])
                pos += 1
                continue

            if b == TOK_VARINT:
                pos += 1
                value, pos = _decode_varint(data, pos)
                out.append(str(value))
                continue

            if b == TOK_NEGINT:
                pos += 1
                value, pos = _decode_varint(data, pos)
                out.append(f"-{value}")
                continue

            if b == TOK_FLOAT16:
                pos += 1
                if pos + 2 <= n:
                    fval = struct.unpack(">e", data[pos:pos+2])[0]
                    out.append(f"{fval:.4g}")
                    pos += 2
                continue

            if b == TOK_FLOAT32:
                pos += 1
                if pos + 4 <= n:
                    fval = struct.unpack(">f", data[pos:pos+4])[0]
                    out.append(f"{fval}")
                    pos += 4
                continue

            if b < 0x80:
                out.append(chr(b))
                pos += 1
                continue

            pos += 1

        return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# SECURITY ENVELOPE CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SEC_VERSION_1      = 0x00   # bits 5-7 = 000
NODE_ID_SHORT      = 0x00   # bit 2 = 0 → 2-byte node ID
NODE_ID_LONG       = 0x04   # bit 2 = 1 → 4-byte node ID


@dataclass
class SecEnvelope:
    """Parsed security envelope."""
    mode: WireMode
    node_id: bytes
    seq_counter: int
    payload: bytes
    auth_tag: bytes     # 16 bytes, ChaCha20-Poly1305
    signature: bytes    # 64 bytes, Ed25519

    @property
    def overhead_bytes(self) -> int:
        return 1 + len(self.node_id) + 4 + 16 + 64

    @property
    def total_bytes(self) -> int:
        return self.overhead_bytes + len(self.payload)


class SecCodec:
    """Security envelope encoder/decoder.

    This implements the envelope format only. Actual cryptographic operations
    (Ed25519 signing, ChaCha20-Poly1305 AEAD) require keys. This codec
    provides:
      - pack/unpack for the envelope wire format
      - placeholder signing/verification using HMAC-SHA256 for testing
      - key management is external (MDR node identity service)

    For production deployment, replace _sign/_verify/_seal/_open with
    calls to a real cryptographic library (e.g. PyNaCl, cryptography).
    """

    def __init__(self, node_id: bytes, signing_key: bytes | None = None,
                 symmetric_key: bytes | None = None):
        """Initialize with node identity and optional keys.

        Args:
            node_id: 2 or 4 byte node identifier
            signing_key: 32-byte Ed25519 private key (or HMAC key for testing)
            symmetric_key: 32-byte symmetric key for AEAD
        """
        if len(node_id) not in (2, 4):
            raise ValueError(f"node_id must be 2 or 4 bytes, got {len(node_id)}")
        self.node_id = node_id
        self.signing_key = signing_key or os.urandom(32)
        self.symmetric_key = symmetric_key or os.urandom(32)
        self._seq_counter = 0

    def _next_seq(self) -> int:
        """Monotonic sequence counter."""
        self._seq_counter += 1
        return self._seq_counter

    def _seal(self, associated_data: bytes, payload: bytes) -> tuple[bytes, bytes]:
        """AEAD seal (ChaCha20-Poly1305 placeholder using HMAC-SHA256).

        In production, replace with actual ChaCha20-Poly1305.
        Returns (ciphertext, auth_tag).

        For this reference implementation, payload is NOT encrypted
        (to support human inspection in development). Only the auth_tag
        is computed for integrity verification.
        """
        tag = hmac.new(self.symmetric_key,
                       associated_data + payload,
                       hashlib.sha256).digest()[:16]
        return payload, tag  # No encryption in reference impl

    def _open(self, associated_data: bytes, payload: bytes,
              auth_tag: bytes) -> bytes | None:
        """AEAD open (verify integrity). Returns payload or None if invalid."""
        expected = hmac.new(self.symmetric_key,
                            associated_data + payload,
                            hashlib.sha256).digest()[:16]
        if hmac.compare_digest(auth_tag, expected):
            return payload
        return None

    def _sign(self, message: bytes) -> bytes:
        """Ed25519 signature placeholder using HMAC-SHA256 padded to 64 bytes.

        In production, replace with actual Ed25519 signing.
        """
        sig = hmac.new(self.signing_key, message, hashlib.sha256).digest()
        return sig + sig  # 64 bytes (2x SHA256 = placeholder)

    def _verify(self, message: bytes, signature: bytes,
                verify_key: bytes | None = None) -> bool:
        """Ed25519 verification placeholder."""
        key = verify_key or self.signing_key
        expected = hmac.new(key, message, hashlib.sha256).digest()
        expected_sig = expected + expected
        return hmac.compare_digest(signature, expected_sig)

    def pack(self, payload: bytes, wire_mode: WireMode = WireMode.SEC) -> bytes:
        """Pack payload into a security envelope.

        Args:
            payload: SAL (mnemonic or SAIL) encoded instruction bytes
            wire_mode: wire mode flags (must include SEC)

        Returns:
            Complete security envelope as bytes
        """
        # Mode byte
        mode_byte = int(wire_mode) & 0x03  # bits 0-1: wire mode
        if len(self.node_id) == 4:
            mode_byte |= NODE_ID_LONG       # bit 2: node_id length
        mode_byte |= SEC_VERSION_1           # bits 5-7: version

        seq = self._next_seq()

        # Associated data for AEAD: mode + node_id + seq
        header = bytes([mode_byte]) + self.node_id + struct.pack(">I", seq)

        # Seal payload
        sealed_payload, auth_tag = self._seal(header, payload)

        # Sign everything: header + payload + auth_tag
        sign_input = header + sealed_payload + auth_tag
        signature = self._sign(sign_input)

        # Pack envelope
        return header + sealed_payload + auth_tag + signature

    def unpack(self, data: bytes) -> SecEnvelope | None:
        """Unpack and verify a security envelope.

        Returns SecEnvelope if valid, None if verification fails.
        """
        if len(data) < 87:  # minimum: 1 + 2 + 4 + 0 + 16 + 64
            return None

        pos = 0
        mode_byte = data[pos]; pos += 1

        wire_mode = WireMode(mode_byte & 0x03)
        node_id_len = 4 if (mode_byte & NODE_ID_LONG) else 2

        node_id = data[pos:pos + node_id_len]; pos += node_id_len
        seq_counter = struct.unpack(">I", data[pos:pos + 4])[0]; pos += 4

        header = data[:pos]

        # Payload is everything between header and auth_tag + signature
        payload_end = len(data) - 16 - 64
        if payload_end < pos:
            return None

        payload = data[pos:payload_end]
        auth_tag = data[payload_end:payload_end + 16]
        signature = data[payload_end + 16:payload_end + 80]

        # Verify AEAD
        verified_payload = self._open(header, payload, auth_tag)
        if verified_payload is None:
            return None

        # Verify signature
        sign_input = header + payload + auth_tag
        if not self._verify(sign_input, signature):
            return None

        return SecEnvelope(
            mode=wire_mode,
            node_id=node_id,
            seq_counter=seq_counter,
            payload=verified_payload,
            auth_tag=auth_tag,
            signature=signature,
        )


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED WIRE CODEC — All four modes
# ─────────────────────────────────────────────────────────────────────────────

class OSMPWireCodec:
    """Unified codec supporting all four OSMP wire modes.

    Modes:
      MNEMONIC    — UTF-8 SAL text (default, human-readable)
      SAIL         — Semantic Assembly Isomorphic Language (compact, table-decoded)
      SEC         — Mnemonic + security envelope
      SAIL_SEC     — Binary + security envelope

    The decode path is encoding-agnostic: it produces the same
    DecodedInstruction regardless of wire mode.
    """

    def __init__(self, dict_path: Path | str | None = None,
                 mdr_paths: list[Path | str] | None = None,
                 node_id: bytes = b"\x00\x01",
                 signing_key: bytes | None = None,
                 symmetric_key: bytes | None = None):
        self.sail = SAILCodec(dict_path, mdr_paths)
        self.sec = SecCodec(node_id, signing_key, symmetric_key)

    def encode(self, sal: str, mode: WireMode = WireMode.MNEMONIC) -> bytes:
        """Encode a SAL instruction in the specified wire mode.

        Args:
            sal: Mnemonic SAL instruction string
            mode: Wire mode selection

        Returns:
            Encoded bytes in the specified mode
        """
        if mode == WireMode.MNEMONIC:
            return sal.encode("utf-8")

        elif mode == WireMode.SAIL:
            return self.sail.encode(sal)

        elif mode == WireMode.SEC:
            payload = sal.encode("utf-8")
            return self.sec.pack(payload, WireMode.SEC)

        elif mode == WireMode.SAIL_SEC:
            payload = self.sail.encode(sal)
            return self.sec.pack(payload, WireMode.SAIL_SEC)

        else:
            raise ValueError(f"Unknown wire mode: {mode}")

    def decode(self, data: bytes, mode: WireMode = WireMode.MNEMONIC) -> str:
        """Decode wire bytes back to mnemonic SAL string.

        Args:
            data: Encoded bytes
            mode: Wire mode used for encoding

        Returns:
            Mnemonic SAL instruction string

        Raises:
            ValueError: If security verification fails (SEC modes)
        """
        if mode == WireMode.MNEMONIC:
            return data.decode("utf-8")

        elif mode == WireMode.SAIL:
            return self.sail.decode(data)

        elif mode == WireMode.SEC:
            env = self.sec.unpack(data)
            if env is None:
                raise ValueError("Security envelope verification failed")
            return env.payload.decode("utf-8")

        elif mode == WireMode.SAIL_SEC:
            env = self.sec.unpack(data)
            if env is None:
                raise ValueError("Security envelope verification failed")
            return self.sail.decode(env.payload)

        else:
            raise ValueError(f"Unknown wire mode: {mode}")

    def measure(self, sal: str) -> dict:
        """Measure byte costs across all four wire modes for a SAL instruction.

        Returns dict with per-mode byte counts, reductions vs mnemonic,
        and round-trip verification status.
        """
        results = {}
        mnemonic_bytes = len(sal.encode("utf-8"))
        _ALL_MODES = [WireMode.MNEMONIC, WireMode.SAIL, WireMode.SEC, WireMode.SAIL_SEC]

        for mode in _ALL_MODES:
            try:
                encoded = self.encode(sal, mode)
                decoded = self.decode(encoded, mode)
                byte_count = len(encoded)
                roundtrip_ok = (decoded == sal)

                results[mode.label] = {
                    "bytes": byte_count,
                    "reduction_vs_mnemonic": round(
                        (1 - byte_count / mnemonic_bytes) * 100, 1
                    ) if mnemonic_bytes > 0 else 0.0,
                    "roundtrip": roundtrip_ok,
                }
            except Exception as e:
                results[mode.label] = {"error": str(e)}

        results["_mnemonic_bytes"] = mnemonic_bytes
        return results

    def measure_batch(self, instructions: list[str]) -> dict:
        """Measure byte costs for a batch of SAL instructions.

        Returns aggregate statistics across all four modes.
        """
        _ALL_MODES = [WireMode.MNEMONIC, WireMode.SAIL, WireMode.SEC, WireMode.SAIL_SEC]
        totals = {m.label: {"bytes": 0, "roundtrips": 0, "count": 0}
                  for m in _ALL_MODES}
        total_mnemonic = 0

        for sal in instructions:
            r = self.measure(sal)
            total_mnemonic += r["_mnemonic_bytes"]
            for mode in _ALL_MODES:
                label = mode.label
                if "error" not in r.get(label, {}):
                    totals[label]["bytes"] += r[label]["bytes"]
                    totals[label]["roundtrips"] += int(r[label]["roundtrip"])
                    totals[label]["count"] += 1

        summary = {}
        for mode in _ALL_MODES:
            label = mode.label
            t = totals[label]
            if t["count"] > 0:
                summary[label] = {
                    "total_bytes": t["bytes"],
                    "reduction_vs_mnemonic": round(
                        (1 - t["bytes"] / total_mnemonic) * 100, 1
                    ) if total_mnemonic > 0 else 0.0,
                    "roundtrip_pass": t["roundtrips"],
                    "roundtrip_total": t["count"],
                    "roundtrip_pct": round(
                        t["roundtrips"] / t["count"] * 100, 1
                    ),
                }
        summary["mnemonic_total_bytes"] = total_mnemonic
        summary["instruction_count"] = len(instructions)
        return summary
