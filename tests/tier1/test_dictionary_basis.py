"""
Dictionary Basis Manifest Tests (ADR-004 / Finding 41)
======================================================

These tests verify the basis-parameterized SAIL intern table architecture
defined in ADR-004 and formalized in spec §3.6, §9.3, and §9.8. The test
suite Finding 41 identified as missing.

The architectural property under test: the SAIL intern table is a pure
function of the Dictionary Basis. Two codecs constructed from equal bases
produce byte-identical intern tables, byte-identical SAIL encodings of any
SAL instruction, and successfully cross-decode each other's payloads. Two
codecs constructed from unequal bases produce different basis fingerprints
and (in deployment) would route through SAL-only mode via FNP capability
grading.

These tests do not exercise FNP wire-level state transitions; those are
covered by the FNP test suite. The focus here is the determinism guarantee
of the basis manifest itself and the protection against the silent
misdecode failure mode logged in Finding 41.

Patent pending — inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

# Make the SDK importable from the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk" / "python"))

from osmp.wire import (  # noqa: E402
    CorpusEntry,
    DictionaryBasis,
    OSMPWireCodec,
    SAILCodec,
    WireMode,
)


# ─── Canonical SAL instructions used as round-trip probes ──────────────────

CANONICAL_SAMPLES = [
    "H:HR@NODE1>120→H:CASREP∧M:EVA@*",
    "H:ICD[R00.1]∧H:CPT[99213]",
    "K:PAY@RECV↔I:§→K:XFR[AMT]",
    "R:MOV@BOT1:WPT:WP1↺",
    "∃N:INET→A:DA@RELAY1",
    "J:GOAL∧Y:SEARCH∧Z:INF∧Q:GROUND",
    "H:HR<60→H:ALERT[BRADYCARDIA]∧H:ICD[R00.1]",
    "EQ@4A?TH:0",
    "MA@*!EVA",
]


# ─── CorpusEntry validation ────────────────────────────────────────────────

class TestCorpusEntry:
    def test_valid_entry_constructs(self):
        entry = CorpusEntry(corpus_id="asd-v15", corpus_hash=b"\x00" * 32)
        assert entry.corpus_id == "asd-v15"
        assert entry.corpus_hash == b"\x00" * 32

    def test_corpus_hash_must_be_32_bytes(self):
        with pytest.raises(ValueError, match="32 bytes"):
            CorpusEntry(corpus_id="asd-v15", corpus_hash=b"\x00" * 16)
        with pytest.raises(ValueError, match="32 bytes"):
            CorpusEntry(corpus_id="asd-v15", corpus_hash=b"\x00" * 64)

    def test_corpus_id_must_be_1_to_255_bytes(self):
        with pytest.raises(ValueError, match="1-255"):
            CorpusEntry(corpus_id="", corpus_hash=b"\x00" * 32)
        with pytest.raises(ValueError, match="1-255"):
            CorpusEntry(corpus_id="x" * 256, corpus_hash=b"\x00" * 32)

    def test_corpus_id_utf8_byte_length_not_character_length(self):
        # 'é' is 2 UTF-8 bytes; 128 of them is 256 bytes, exceeds the limit.
        with pytest.raises(ValueError, match="1-255"):
            CorpusEntry(corpus_id="é" * 128, corpus_hash=b"\x00" * 32)
        # 127 of them is 254 bytes, within the limit.
        entry = CorpusEntry(corpus_id="é" * 127, corpus_hash=b"\x00" * 32)
        assert len(entry.corpus_id.encode("utf-8")) == 254

    def test_entry_is_frozen(self):
        entry = CorpusEntry(corpus_id="asd-v15", corpus_hash=b"\x00" * 32)
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.corpus_id = "asd-v16"  # type: ignore[misc]


# ─── DictionaryBasis construction and identity ─────────────────────────────

class TestDictionaryBasisConstruction:
    def test_empty_basis_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            DictionaryBasis([])

    def test_default_basis_constructs(self):
        basis = DictionaryBasis.default()
        assert len(basis) == 1
        assert basis.is_base_only()

    def test_default_basis_is_deterministic(self):
        b1 = DictionaryBasis.default()
        b2 = DictionaryBasis.default()
        assert b1 == b2
        assert b1.fingerprint() == b2.fingerprint()
        assert b1.canonical_serialization() == b2.canonical_serialization()

    def test_fingerprint_is_8_bytes(self):
        basis = DictionaryBasis.default()
        fp = basis.fingerprint()
        assert isinstance(fp, bytes)
        assert len(fp) == 8

    def test_fingerprint_is_first_8_bytes_of_sha256(self):
        # The canonical serialization is the input to SHA-256; the basis
        # fingerprint is the first 8 bytes of the digest. This test pins
        # that contract because the spec depends on it for cross-SDK
        # interop.
        basis = DictionaryBasis.default()
        canonical = basis.canonical_serialization()
        expected = hashlib.sha256(canonical).digest()[:8]
        assert basis.fingerprint() == expected

    def test_canonical_serialization_format(self):
        # Single entry with known values.
        h = bytes(range(32))
        basis = DictionaryBasis([CorpusEntry(corpus_id="asd-v15", corpus_hash=h)])
        canonical = basis.canonical_serialization()
        # Format: id_len (1B) || id (UTF-8) || hash (32B)
        assert canonical[0] == len("asd-v15")
        assert canonical[1:1 + len("asd-v15")] == b"asd-v15"
        assert canonical[1 + len("asd-v15"):] == h
        assert len(canonical) == 1 + len("asd-v15") + 32

    def test_two_entry_basis_serialization_is_concatenation(self):
        h1 = b"\x01" * 32
        h2 = b"\x02" * 32
        basis = DictionaryBasis([
            CorpusEntry(corpus_id="asd-v15", corpus_hash=h1),
            CorpusEntry(corpus_id="mdr-icd10cm-fy2026", corpus_hash=h2),
        ])
        canonical = basis.canonical_serialization()
        # Each entry contributes 1 + len(id) + 32 bytes.
        expected_len = (1 + len("asd-v15") + 32) + (1 + len("mdr-icd10cm-fy2026") + 32)
        assert len(canonical) == expected_len


# ─── The Finding 41 silent-misdecode prevention property ───────────────────

class TestBasisFingerprintDeterminism:
    """The architectural property that Finding 41 was logging.

    Two nodes with equal basis fingerprints MUST produce byte-identical
    intern tables. Two nodes with unequal basis fingerprints MUST produce
    different basis fingerprints (which in deployment routes through
    SAL-only mode via FNP).
    """

    def test_equal_basis_equal_fingerprint(self):
        h = b"\xab" * 32
        b1 = DictionaryBasis([CorpusEntry(corpus_id="asd-v15", corpus_hash=h)])
        b2 = DictionaryBasis([CorpusEntry(corpus_id="asd-v15", corpus_hash=h)])
        assert b1.fingerprint() == b2.fingerprint()

    def test_different_corpus_id_different_fingerprint(self):
        h = b"\xab" * 32
        b1 = DictionaryBasis([CorpusEntry(corpus_id="asd-v15", corpus_hash=h)])
        b2 = DictionaryBasis([CorpusEntry(corpus_id="asd-v16", corpus_hash=h)])
        assert b1.fingerprint() != b2.fingerprint()

    def test_different_corpus_hash_different_fingerprint(self):
        b1 = DictionaryBasis([CorpusEntry(corpus_id="asd-v15", corpus_hash=b"\x00" * 32)])
        b2 = DictionaryBasis([CorpusEntry(corpus_id="asd-v15", corpus_hash=b"\x01" * 32)])
        assert b1.fingerprint() != b2.fingerprint()

    def test_order_significance(self):
        """Different ordering of the same corpora produces different fingerprints.

        ADR-004 makes order significant in the basis because intern table
        index assignment depends on iteration order. This test pins the
        contract.
        """
        h1 = b"\x01" * 32
        h2 = b"\x02" * 32
        e1 = CorpusEntry(corpus_id="asd-v15", corpus_hash=h1)
        e2 = CorpusEntry(corpus_id="mdr-icd10cm", corpus_hash=h2)
        b_ascending = DictionaryBasis([e1, e2])
        b_descending = DictionaryBasis([e2, e1])
        assert b_ascending.fingerprint() != b_descending.fingerprint()


# ─── SAILCodec basis-driven intern table determinism ───────────────────────

class TestSAILCodecBasisDeterminism:
    def test_two_default_codecs_byte_identical_intern_tables(self):
        c1 = SAILCodec()
        c2 = SAILCodec()
        assert c1._intern_table == c2._intern_table
        assert c1.basis_fingerprint() == c2.basis_fingerprint()

    def test_codec_with_explicit_default_basis_matches_implicit(self):
        c_implicit = SAILCodec()
        c_explicit = SAILCodec(basis=DictionaryBasis.default())
        assert c_implicit._intern_table == c_explicit._intern_table
        assert c_implicit.basis_fingerprint() == c_explicit.basis_fingerprint()

    @pytest.mark.parametrize("sal", CANONICAL_SAMPLES)
    def test_canonical_round_trip_under_default_basis(self, sal):
        codec = SAILCodec()
        encoded = codec.encode(sal)
        decoded = codec.decode(encoded)
        assert decoded == sal

    @pytest.mark.parametrize("sal", CANONICAL_SAMPLES)
    def test_cross_codec_byte_identical_encoding(self, sal):
        c1 = SAILCodec()
        c2 = SAILCodec()
        e1 = c1.encode(sal)
        e2 = c2.encode(sal)
        assert e1 == e2, f"Encoding diverged for {sal!r}"

    @pytest.mark.parametrize("sal", CANONICAL_SAMPLES)
    def test_cross_codec_round_trip(self, sal):
        """The Finding 41 smoking-gun: codec A encodes, codec B decodes.

        Both codecs use the default basis. Under ADR-004, this MUST
        succeed because basis fingerprints are equal and therefore
        intern tables are byte-identical.
        """
        c1 = SAILCodec()
        c2 = SAILCodec()
        encoded_by_c1 = c1.encode(sal)
        decoded_by_c2 = c2.decode(encoded_by_c1)
        assert decoded_by_c2 == sal


# ─── OSMPWireCodec exposes the basis through the unified interface ─────────

class TestOSMPWireCodecBasis:
    def test_wire_codec_basis_is_default(self):
        wc = OSMPWireCodec()
        assert wc.basis.is_base_only()

    def test_wire_codec_basis_fingerprint_matches_sail(self):
        wc = OSMPWireCodec()
        assert wc.basis_fingerprint() == wc.sail.basis_fingerprint()

    def test_wire_codec_basis_fingerprint_matches_standalone_sail(self):
        wc = OSMPWireCodec()
        sc = SAILCodec()
        assert wc.basis_fingerprint() == sc.basis_fingerprint()

    @pytest.mark.parametrize("sal", CANONICAL_SAMPLES)
    def test_wire_codec_sail_round_trip(self, sal):
        wc = OSMPWireCodec()
        encoded = wc.encode(sal, WireMode.SAIL)
        decoded = wc.decode(encoded, WireMode.SAIL)
        assert decoded == sal


# ─── The classmethod path for constructing a basis from disk ───────────────

class TestBasisFromPaths:
    def test_from_paths_with_default_dictionary(self):
        # Locate the canonical dictionary the same way the codec does.
        candidates = [
            REPO_ROOT / "protocol" / "OSMP-semantic-dictionary-v15.csv",
            REPO_ROOT / "sdk" / "python" / "osmp" / "data" / "OSMP-semantic-dictionary-v15.csv",
        ]
        asd_path = next((c for c in candidates if c.exists()), None)
        if asd_path is None:
            pytest.skip("Base ASD CSV not found in canonical locations")
        basis = DictionaryBasis.from_paths(asd_path)
        assert len(basis) == 1
        assert basis.is_base_only()
        assert basis.entries[0].corpus_id.startswith("asd-")
        assert len(basis.entries[0].corpus_hash) == 32

    def test_from_paths_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            DictionaryBasis.from_paths("/nonexistent/path/to/asd.csv")

    def test_corpus_hash_is_sha256_of_file_bytes(self):
        # Construct a temporary file, hash it manually, verify the basis
        # entry carries the same hash.
        import tempfile
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            content = b"OSMP Semantic Dictionary v15\nSECTION 3\nNamespace,Prefix,...\nA,A,...,TEST,...\n"
            f.write(content)
            tmp_path = Path(f.name)
        try:
            expected = hashlib.sha256(content).digest()
            basis = DictionaryBasis.from_paths(tmp_path)
            assert basis.entries[0].corpus_hash == expected
        finally:
            tmp_path.unlink()
