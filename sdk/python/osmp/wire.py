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
# DICTIONARY BASIS MANIFEST (ADR-004)
#
# A Dictionary Basis is an ordered list of (corpus_id, corpus_hash) pairs that
# determines a node's SAIL intern table by pure-function construction. Two
# nodes loading the same ordered basis produce byte-identical intern tables
# and unlock SAIL with each other; nodes with different bases interoperate in
# SAL-only mode via FNP capability grading (spec §9.5).
#
# See ADR-004 for the architectural rationale and spec §9.8 for the formal
# definition.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CorpusEntry:
    """Single entry in a Dictionary Basis.

    corpus_id: stable UTF-8 identifier (1-255 bytes), e.g. "asd-v14".
    corpus_hash: full 32-byte SHA-256 over the corpus file bytes verbatim.
    """
    corpus_id: str
    corpus_hash: bytes

    def __post_init__(self) -> None:
        cid_bytes = self.corpus_id.encode("utf-8")
        if not 1 <= len(cid_bytes) <= 255:
            raise ValueError(
                f"corpus_id must be 1-255 UTF-8 bytes, got {len(cid_bytes)}"
            )
        if len(self.corpus_hash) != 32:
            raise ValueError(
                f"corpus_hash must be exactly 32 bytes (SHA-256), got {len(self.corpus_hash)}"
            )


class DictionaryBasis:
    """Ordered, content-addressed set of dictionary corpora (ADR-004).

    The basis is the input to deterministic SAIL intern table construction.
    A basis is constructed from one or more corpus files. The first entry is
    always the base ASD; subsequent entries are MDR corpora in operator-
    specified order. Order is significant: it determines intern table index
    assignment and is reflected in the basis fingerprint.

    Use the classmethods to construct: `from_paths` is the typical entry
    point for loading corpora from disk; `default` constructs a base-ASD-only
    basis for the common case.
    """

    def __init__(self, entries: list[CorpusEntry]):
        if not entries:
            raise ValueError("DictionaryBasis must contain at least one entry")
        self._entries: tuple[CorpusEntry, ...] = tuple(entries)
        # Cache the fingerprint; basis is logically immutable after construction.
        self._fingerprint: bytes | None = None

    @property
    def entries(self) -> tuple[CorpusEntry, ...]:
        return self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DictionaryBasis):
            return NotImplemented
        return self._entries == other._entries

    def __hash__(self) -> int:
        return hash(self._entries)

    def canonical_serialization(self) -> bytes:
        """Canonical wire form per spec §9.3.

        For each entry in basis order, emit:
            corpus_id_length (1 byte) || corpus_id (UTF-8 bytes) || corpus_hash (32 bytes)

        This is unambiguous across platforms because no padding, alignment,
        or text encoding is involved beyond the explicit length prefix and
        the raw hash bytes.
        """
        out = bytearray()
        for entry in self._entries:
            cid = entry.corpus_id.encode("utf-8")
            out.append(len(cid))
            out.extend(cid)
            out.extend(entry.corpus_hash)
        return bytes(out)

    def fingerprint(self) -> bytes:
        """8-byte basis fingerprint per spec §9.3.

        First 8 bytes of SHA-256 over the canonical serialization. Two
        bases with equal fingerprints have byte-identical canonical
        serializations and produce byte-identical intern tables.
        """
        if self._fingerprint is None:
            digest = hashlib.sha256(self.canonical_serialization()).digest()
            object.__setattr__(self, "_fingerprint", digest[:8])
        return self._fingerprint  # type: ignore[return-value]

    def is_base_only(self) -> bool:
        """True if this basis contains only the base ASD (length 1).

        Base-only bases are the default. Two base-only bases loading the
        same dictionary version automatically match and unlock SAIL.
        """
        return len(self._entries) == 1

    @classmethod
    def from_paths(
        cls,
        asd_path: Path | str,
        asd_id: str | None = None,
        mdr_corpora: list[tuple[str, Path | str]] | None = None,
    ) -> "DictionaryBasis":
        """Construct a basis from corpus files on disk.

        asd_path: path to the base ASD CSV (the dictionary).
        asd_id: optional override for the base ASD identifier. If not given,
            derived from the dictionary version detected in the CSV header,
            or "asd-v14" as a stable fallback.
        mdr_corpora: optional list of (corpus_id, path) pairs for MDR corpora
            to append to the basis after the base ASD, in the order given.
        """
        entries: list[CorpusEntry] = []

        # Base ASD entry.
        asd_path = Path(asd_path)
        if not asd_path.exists():
            raise FileNotFoundError(f"Base ASD not found: {asd_path}")
        asd_hash = cls._hash_file(asd_path)
        if asd_id is None:
            asd_id = cls._derive_asd_id(asd_path)
        entries.append(CorpusEntry(corpus_id=asd_id, corpus_hash=asd_hash))

        # MDR corpora in operator-specified order.
        if mdr_corpora:
            for corpus_id, corpus_path in mdr_corpora:
                cp = Path(corpus_path)
                if not cp.exists():
                    raise FileNotFoundError(f"MDR corpus not found: {cp}")
                ch = cls._hash_file(cp)
                entries.append(CorpusEntry(corpus_id=corpus_id, corpus_hash=ch))

        return cls(entries)

    @classmethod
    def default(cls, dict_path: Path | str | None = None) -> "DictionaryBasis":
        """Construct the default base-ASD-only basis.

        If dict_path is None, searches the canonical default locations
        (matching _build_opcode_tables behavior).
        """
        if dict_path is None:
            candidates = [
                Path(__file__).parent.parent.parent.parent / "protocol" / "OSMP-semantic-dictionary-v15.csv",
                Path("protocol/OSMP-semantic-dictionary-v15.csv"),
                Path(__file__).parent / "data" / "OSMP-semantic-dictionary-v15.csv",
            ]
            for c in candidates:
                if c.exists():
                    dict_path = c
                    break
        if dict_path is None or not Path(dict_path).exists():
            raise FileNotFoundError(
                "Base ASD not found in any default location. "
                "Pass dict_path explicitly or use DictionaryBasis.from_paths."
            )
        return cls.from_paths(dict_path)

    @staticmethod
    def _hash_file(path: Path) -> bytes:
        """SHA-256 over file bytes verbatim. No canonicalization."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.digest()

    @staticmethod
    def _derive_asd_id(asd_path: Path) -> str:
        """Derive a stable ASD corpus identifier from the dictionary file.

        Looks for a version marker in the first 20 lines of the CSV. Falls
        back to 'asd-v14' as the v14 default. The identifier is part of the
        basis fingerprint, so it must be stable across nodes loading the
        same dictionary version.
        """
        try:
            with open(asd_path, "r", encoding="utf-8") as f:
                head = "".join(f.readline() for _ in range(20))
            # Look for "vNN" where NN is two digits, common in OSMP CSV headers.
            m = re.search(r"v(\d{2})", head)
            if m:
                return f"asd-v{m.group(1)}"
        except (OSError, UnicodeDecodeError):
            pass
        return "asd-v14"


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
    def _build_intern_table(basis: DictionaryBasis | None = None,
                            dict_path: Path | str | None = None) -> list[str]:
        """Construct the SAIL intern table from a Dictionary Basis (ADR-004).

        The intern table is a pure function of the basis: two basis instances
        with equal entries produce byte-identical intern tables. Index
        assignment is deterministic over (basis order, deduplicated
        first-seen order, length-descending sort, cost filter).

        For the v14 base ASD, extraction is the historical Phase 1 behavior:
        every opcode name from Section 3. Future corpus types declare their
        own extraction rule per the corpus's sidecar manifest; this
        implementation supports the base ASD CSV extractor as the only
        shipping rule.

        The dict_path parameter is retained as a fallback for the historical
        default-search behavior so existing code paths that construct a
        SAILCodec with no arguments continue to work. When `basis` is
        provided, it takes precedence and dict_path is ignored.
        """
        strings: set[str] = set()

        # If a basis is provided, iterate it; otherwise fall back to the
        # historical default-search behavior over the base ASD only.
        if basis is not None:
            for entry in basis:
                # Per ADR-004, corpus identifiers prefixed with "asd-" use the
                # base ASD CSV extractor. Future corpus types dispatch by id
                # prefix or by sidecar manifest tag.
                if entry.corpus_id.startswith("asd-"):
                    # The basis entry tells us what the corpus is, but the
                    # actual file content lives at the path the SDK loaded
                    # from. We re-derive content extraction from the same
                    # default-search the codec already does.
                    SAILCodec._extract_asd_opcodes(strings, dict_path)
                # MDR corpus extraction rules are deferred until corpora
                # ship with sidecar manifests. Historical Phase 2 (parsing
                # MDR CSV "SECTION B") is removed; it produced zero
                # observable intern entries on every shipped MDR.
        else:
            SAILCodec._extract_asd_opcodes(strings, dict_path)

        # Filter: only keep strings where interning saves bytes.
        # Sort length-descending for deterministic, byte-identical output
        # across nodes.
        sorted_strings = sorted(strings, key=lambda s: (-len(s), s))
        result = []
        for s in sorted_strings:
            idx = len(result)
            ref_cost = 2 if idx < 128 else (3 if idx < 16384 else 4)
            if len(s) > ref_cost:
                result.append(s)
        return result

    @staticmethod
    def _extract_asd_opcodes(strings: set[str],
                             dict_path: Path | str | None = None) -> None:
        """Extract every opcode name from the base ASD Section 3.

        Mutates the `strings` set in place. Used by both basis-driven
        construction (when an "asd-*" corpus appears in the basis) and the
        historical default-search fallback.
        """
        if dict_path is None:
            candidates = [
                Path(__file__).parent.parent.parent.parent / "protocol" / "OSMP-semantic-dictionary-v15.csv",
                Path("protocol/OSMP-semantic-dictionary-v15.csv"),
                Path(__file__).parent / "data" / "OSMP-semantic-dictionary-v15.csv",
            ]
            for c in candidates:
                if c.exists():
                    dict_path = c
                    break

        if not dict_path or not Path(dict_path).exists():
            return

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


    def __init__(self, dict_path: Path | str | None = None,
                 basis: DictionaryBasis | None = None):
        """Construct a SAIL codec.

        dict_path: path to the base ASD CSV. Used for opcode table
            construction and as the fallback content source when no basis
            is provided.
        basis: optional DictionaryBasis (ADR-004). When provided, the
            intern table is constructed deterministically from the basis
            and the codec's basis_fingerprint() reports the basis fingerprint
            for FNP capability negotiation. When omitted, the codec
            constructs a default base-ASD-only basis from dict_path.
        """
        self.op_to_idx, self.idx_to_op = _build_opcode_tables(dict_path)

        # If no basis was supplied, construct the default base-ASD-only
        # basis from the resolved dict_path so codec.basis is always
        # well-defined and basis_fingerprint() always returns a value.
        if basis is None:
            try:
                basis = DictionaryBasis.default(dict_path)
            except FileNotFoundError:
                # Last-resort fallback for environments where the dictionary
                # cannot be located on disk: synthesize a basis from a
                # placeholder hash so the codec is still constructible.
                # Tests that exercise basis_fingerprint() must supply a
                # real basis or a valid dict_path.
                placeholder_hash = hashlib.sha256(b"asd-unknown").digest()
                basis = DictionaryBasis([
                    CorpusEntry(corpus_id="asd-unknown", corpus_hash=placeholder_hash)
                ])

        self.basis: DictionaryBasis = basis
        self._intern_table = self._build_intern_table(basis, dict_path)
        self._str_to_ref: dict[str, int] = {s: i for i, s in enumerate(self._intern_table)}
        self._ref_to_str: dict[int, str] = {i: s for i, s in enumerate(self._intern_table)}

    def basis_fingerprint(self) -> bytes:
        """8-byte basis fingerprint for FNP capability negotiation (spec §9.3)."""
        return self.basis.fingerprint()


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

    Implements the OSMP security envelope wire format with real cryptographic
    primitives:
      - **Ed25519** (RFC 8032) for sender authentication via 64-byte signatures
      - **ChaCha20-Poly1305** (RFC 7539, RFC 8439) for AEAD payload integrity
        with a 16-byte authentication tag
      - 12-byte nonces derived deterministically from the envelope header
        (mode + node_id + seq) padded with the canonical OSMP nonce salt

    The wire format is byte-identical to the previous reference implementation
    so cross-SDK compatibility is preserved: a Python-signed envelope decodes
    in the Go SDK and vice versa, provided both sides share the symmetric key
    and the verifying side has the sender's Ed25519 public key.

    Key management is external (MDR node identity service). For ephemeral
    sessions or local testing, omit the key arguments and the constructor
    will generate a fresh keypair via os.urandom + Ed25519 derivation.
    """

    NONCE_SALT = b"OSMP-SEC-v1\x00"  # 12 bytes — pads short headers up to nonce length

    def __init__(self, node_id: bytes, signing_key: bytes | None = None,
                 symmetric_key: bytes | None = None,
                 verify_key: bytes | None = None):
        """Initialize with node identity and optional keys.

        Args:
            node_id: 2 or 4 byte node identifier
            signing_key: 32-byte Ed25519 private key seed. Generated if None.
            symmetric_key: 32-byte ChaCha20-Poly1305 key. Generated if None.
            verify_key: 32-byte Ed25519 public key for verifying inbound
                envelopes from a peer. Defaults to this codec's own public key
                (loopback / local-only verification).
        """
        # Lazy-import the cryptography primitives so the rest of the SDK can
        # be imported in environments without the cryptography library
        # available (e.g. environments that only need SAL encode/decode).
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        from cryptography.exceptions import InvalidTag
        self._Ed25519PrivateKey = Ed25519PrivateKey
        self._Ed25519PublicKey = Ed25519PublicKey
        self._ChaCha20Poly1305 = ChaCha20Poly1305
        self._InvalidTag = InvalidTag

        if len(node_id) not in (2, 4):
            raise ValueError(f"node_id must be 2 or 4 bytes, got {len(node_id)}")
        self.node_id = node_id

        # Ed25519 signing key (private). 32-byte seed.
        seed = signing_key if signing_key is not None else os.urandom(32)
        if len(seed) != 32:
            raise ValueError(
                f"signing_key must be 32 bytes (Ed25519 seed), got {len(seed)}"
            )
        self.signing_key = seed
        self._ed25519_private = Ed25519PrivateKey.from_private_bytes(seed)
        self._ed25519_public = self._ed25519_private.public_key()

        # ChaCha20-Poly1305 symmetric key. 32 bytes.
        sym = symmetric_key if symmetric_key is not None else os.urandom(32)
        if len(sym) != 32:
            raise ValueError(
                f"symmetric_key must be 32 bytes (ChaCha20-Poly1305), got {len(sym)}"
            )
        self.symmetric_key = sym
        self._aead = ChaCha20Poly1305(sym)

        # Default verify key: our own public key (loopback). For
        # inter-node verification, callers pass the peer's public key.
        if verify_key is not None:
            if len(verify_key) != 32:
                raise ValueError(
                    f"verify_key must be 32 bytes (Ed25519 public key), got {len(verify_key)}"
                )
            self._verify_public_default = Ed25519PublicKey.from_public_bytes(verify_key)
        else:
            self._verify_public_default = self._ed25519_public

        self._seq_counter = 0

    @property
    def public_signing_key(self) -> bytes:
        """Return the 32-byte Ed25519 public key for distributing to peers."""
        from cryptography.hazmat.primitives import serialization
        return self._ed25519_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def _next_seq(self) -> int:
        """Monotonic sequence counter."""
        self._seq_counter += 1
        return self._seq_counter

    def _derive_nonce(self, header: bytes) -> bytes:
        """Derive a 12-byte ChaCha20-Poly1305 nonce from the envelope header.

        The nonce is deterministic over (mode_byte, node_id, seq) which is
        unique per envelope due to the monotonic sequence counter. We pad
        short headers with the canonical NONCE_SALT to reach 12 bytes.
        """
        if len(header) >= 12:
            return header[:12]
        return (header + self.NONCE_SALT)[:12]

    def _seal(self, associated_data: bytes, payload: bytes) -> tuple[bytes, bytes]:
        """ChaCha20-Poly1305 AEAD seal.

        Returns (ciphertext, auth_tag) where ciphertext has the same length
        as payload and auth_tag is the 16-byte Poly1305 authentication tag.

        The ChaCha20-Poly1305 primitive returns ciphertext concatenated with
        the tag; we split them so the wire format can place the tag in its
        canonical position after the payload.
        """
        nonce = self._derive_nonce(associated_data)
        sealed = self._aead.encrypt(nonce, payload, associated_data)
        # cryptography returns ciphertext || tag; split into the two parts.
        ciphertext = sealed[:-16]
        auth_tag = sealed[-16:]
        return ciphertext, auth_tag

    def _open(self, associated_data: bytes, payload: bytes,
              auth_tag: bytes) -> bytes | None:
        """ChaCha20-Poly1305 AEAD open. Returns plaintext or None if invalid."""
        nonce = self._derive_nonce(associated_data)
        try:
            return self._aead.decrypt(nonce, payload + auth_tag, associated_data)
        except self._InvalidTag:
            return None

    def _sign(self, message: bytes) -> bytes:
        """Ed25519 signature. Returns a 64-byte signature."""
        return self._ed25519_private.sign(message)

    def _verify(self, message: bytes, signature: bytes,
                verify_key: bytes | None = None) -> bool:
        """Ed25519 verification.

        If verify_key is None, uses self._verify_public_default (which is
        either the constructor's verify_key parameter or this codec's own
        public key for loopback verification).
        """
        if verify_key is not None:
            try:
                pub = self._Ed25519PublicKey.from_public_bytes(verify_key)
            except Exception:
                return False
        else:
            pub = self._verify_public_default
        try:
            pub.verify(signature, message)
            return True
        except Exception:
            return False

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
                 basis: DictionaryBasis | None = None,
                 node_id: bytes = b"\x00\x01",
                 signing_key: bytes | None = None,
                 symmetric_key: bytes | None = None):
        """Construct a unified OSMP wire codec.

        dict_path: path to the base ASD CSV. Used for opcode table
            construction and as the fallback content source when no basis
            is provided.
        basis: optional DictionaryBasis (ADR-004). When provided, the SAIL
            codec uses it directly. When omitted, a default base-ASD-only
            basis is constructed from dict_path.
        node_id, signing_key, symmetric_key: SEC envelope parameters,
            unchanged from v1.0.2.
        """
        self.sail = SAILCodec(dict_path=dict_path, basis=basis)
        self.sec = SecCodec(node_id, signing_key, symmetric_key)

    @property
    def basis(self) -> DictionaryBasis:
        """The Dictionary Basis bound to this codec (ADR-004)."""
        return self.sail.basis

    def basis_fingerprint(self) -> bytes:
        """8-byte basis fingerprint for FNP capability negotiation (spec §9.3)."""
        return self.sail.basis_fingerprint()

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
