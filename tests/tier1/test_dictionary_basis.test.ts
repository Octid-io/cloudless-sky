/**
 * Dictionary Basis Manifest Tests (ADR-004 / Finding 41)
 *
 * Mirrors tests/test_dictionary_basis.py. The architectural property under
 * test: the SAIL intern table is a pure function of the Dictionary Basis.
 * Two codecs constructed from equal bases produce byte-identical intern
 * tables, byte-identical SAIL encodings, and successfully cross-decode each
 * other's payloads.
 */

import { describe, it, expect } from "vitest";
import { createHash } from "crypto";
import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import {
  CorpusEntry,
  DictionaryBasis,
  OSMPWireCodec,
  SAILCodec,
  WireMode,
} from "../src/osmp_wire.js";

const CANONICAL_SAMPLES = [
  "H:HR@NODE1>120→H:CASREP∧M:EVA@*",
  "H:ICD[R00.1]∧H:CPT[99213]",
  "K:PAY@RECV↔I:§→K:XFR[AMT]",
  "R:MOV@BOT1:WPT:WP1↺",
  "∃N:INET→A:DA@RELAY1",
  "J:GOAL∧Y:SEARCH∧Z:INF∧Q:GROUND",
  "H:HR<60→H:ALERT[BRADYCARDIA]∧H:ICD[R00.1]",
  "EQ@4A?TH:0",
  "MA@*!EVA",
];

describe("CorpusEntry validation", () => {
  it("rejects empty corpus_id via DictionaryBasis", () => {
    expect(() => new DictionaryBasis([
      { corpusId: "", corpusHash: Buffer.alloc(32) },
    ])).toThrow(/1-255/);
  });

  it("rejects oversized corpus_id (256 UTF-8 bytes)", () => {
    expect(() => new DictionaryBasis([
      { corpusId: "x".repeat(256), corpusHash: Buffer.alloc(32) },
    ])).toThrow(/1-255/);
  });

  it("rejects corpus_hash that is not exactly 32 bytes", () => {
    expect(() => new DictionaryBasis([
      { corpusId: "asd-v14", corpusHash: Buffer.alloc(16) },
    ])).toThrow(/32 bytes/);
    expect(() => new DictionaryBasis([
      { corpusId: "asd-v14", corpusHash: Buffer.alloc(64) },
    ])).toThrow(/32 bytes/);
  });

  it("counts UTF-8 bytes not characters", () => {
    // 'é' is 2 UTF-8 bytes; 128 of them is 256 bytes, exceeds the limit.
    expect(() => new DictionaryBasis([
      { corpusId: "é".repeat(128), corpusHash: Buffer.alloc(32) },
    ])).toThrow(/1-255/);
    // 127 of them is 254 bytes, within the limit.
    expect(() => new DictionaryBasis([
      { corpusId: "é".repeat(127), corpusHash: Buffer.alloc(32) },
    ])).not.toThrow();
  });
});

describe("DictionaryBasis construction and identity", () => {
  it("rejects empty basis", () => {
    expect(() => new DictionaryBasis([])).toThrow(/at least one/);
  });

  it("default basis is base-only and constructs", () => {
    const basis = DictionaryBasis.default();
    expect(basis.length).toBe(1);
    expect(basis.isBaseOnly()).toBe(true);
  });

  it("default basis is deterministic across constructions", () => {
    const b1 = DictionaryBasis.default();
    const b2 = DictionaryBasis.default();
    expect(b1.equals(b2)).toBe(true);
    expect(b1.fingerprint().equals(b2.fingerprint())).toBe(true);
    expect(b1.canonicalSerialization().equals(b2.canonicalSerialization())).toBe(true);
  });

  it("fingerprint is exactly 8 bytes", () => {
    const fp = DictionaryBasis.default().fingerprint();
    expect(Buffer.isBuffer(fp)).toBe(true);
    expect(fp.length).toBe(8);
  });

  it("fingerprint is first 8 bytes of SHA-256 over canonical serialization", () => {
    const basis = DictionaryBasis.default();
    const canonical = basis.canonicalSerialization();
    const expected = createHash("sha256").update(canonical).digest().subarray(0, 8);
    expect(basis.fingerprint().equals(expected)).toBe(true);
  });

  it("canonical serialization format: id_len || id || hash", () => {
    const h = Buffer.from(Array.from({ length: 32 }, (_, i) => i));
    const basis = new DictionaryBasis([{ corpusId: "asd-v14", corpusHash: h }]);
    const canonical = basis.canonicalSerialization();
    expect(canonical[0]).toBe("asd-v14".length);
    expect(canonical.subarray(1, 1 + "asd-v14".length).toString("utf-8")).toBe("asd-v14");
    expect(canonical.subarray(1 + "asd-v14".length).equals(h)).toBe(true);
    expect(canonical.length).toBe(1 + "asd-v14".length + 32);
  });

  it("two-entry basis serialization is concatenation", () => {
    const h1 = Buffer.alloc(32, 0x01);
    const h2 = Buffer.alloc(32, 0x02);
    const basis = new DictionaryBasis([
      { corpusId: "asd-v14", corpusHash: h1 },
      { corpusId: "mdr-icd10cm-fy2026", corpusHash: h2 },
    ]);
    const expectedLen = (1 + "asd-v14".length + 32) + (1 + "mdr-icd10cm-fy2026".length + 32);
    expect(basis.canonicalSerialization().length).toBe(expectedLen);
  });
});

describe("Finding 41 silent-misdecode prevention", () => {
  it("equal basis -> equal fingerprint", () => {
    const h = Buffer.alloc(32, 0xab);
    const b1 = new DictionaryBasis([{ corpusId: "asd-v14", corpusHash: h }]);
    const b2 = new DictionaryBasis([{ corpusId: "asd-v14", corpusHash: h }]);
    expect(b1.fingerprint().equals(b2.fingerprint())).toBe(true);
  });

  it("different corpus_id -> different fingerprint", () => {
    const h = Buffer.alloc(32, 0xab);
    const b1 = new DictionaryBasis([{ corpusId: "asd-v14", corpusHash: h }]);
    const b2 = new DictionaryBasis([{ corpusId: "asd-v15", corpusHash: h }]);
    expect(b1.fingerprint().equals(b2.fingerprint())).toBe(false);
  });

  it("different corpus_hash -> different fingerprint", () => {
    const b1 = new DictionaryBasis([{ corpusId: "asd-v14", corpusHash: Buffer.alloc(32, 0x00) }]);
    const b2 = new DictionaryBasis([{ corpusId: "asd-v14", corpusHash: Buffer.alloc(32, 0x01) }]);
    expect(b1.fingerprint().equals(b2.fingerprint())).toBe(false);
  });

  it("order significance: same corpora different order -> different fingerprint", () => {
    const e1 = { corpusId: "asd-v14", corpusHash: Buffer.alloc(32, 0x01) };
    const e2 = { corpusId: "mdr-icd10cm", corpusHash: Buffer.alloc(32, 0x02) };
    const ascending = new DictionaryBasis([e1, e2]);
    const descending = new DictionaryBasis([e2, e1]);
    expect(ascending.fingerprint().equals(descending.fingerprint())).toBe(false);
  });
});

describe("SAILCodec basis-driven intern table determinism", () => {
  it("two default codecs have basis fingerprints that match", () => {
    const c1 = new SAILCodec();
    const c2 = new SAILCodec();
    expect(c1.basisFingerprint().equals(c2.basisFingerprint())).toBe(true);
  });

  it("codec with explicit default basis matches implicit", () => {
    const c1 = new SAILCodec();
    const c2 = new SAILCodec(undefined, DictionaryBasis.default());
    expect(c1.basisFingerprint().equals(c2.basisFingerprint())).toBe(true);
  });

  for (const sal of CANONICAL_SAMPLES) {
    it(`canonical round-trip under default basis: ${sal.slice(0, 30)}`, () => {
      const codec = new SAILCodec();
      const encoded = codec.encode(sal);
      const decoded = codec.decode(encoded);
      expect(decoded).toBe(sal);
    });
  }

  for (const sal of CANONICAL_SAMPLES) {
    it(`cross-codec byte-identical encoding: ${sal.slice(0, 30)}`, () => {
      const c1 = new SAILCodec();
      const c2 = new SAILCodec();
      const e1 = Buffer.from(c1.encode(sal));
      const e2 = Buffer.from(c2.encode(sal));
      expect(e1.equals(e2)).toBe(true);
    });
  }

  for (const sal of CANONICAL_SAMPLES) {
    it(`Finding 41 cross-codec round-trip: ${sal.slice(0, 30)}`, () => {
      const c1 = new SAILCodec();
      const c2 = new SAILCodec();
      const encodedByC1 = c1.encode(sal);
      const decodedByC2 = c2.decode(encodedByC1);
      expect(decodedByC2).toBe(sal);
    });
  }
});

describe("OSMPWireCodec exposes basis through unified interface", () => {
  it("wire codec basis is default base-only", () => {
    const wc = new OSMPWireCodec();
    expect(wc.basis.isBaseOnly()).toBe(true);
  });

  it("wire codec basis fingerprint matches standalone SAILCodec default", () => {
    const wc = new OSMPWireCodec();
    const sc = new SAILCodec();
    expect(wc.basisFingerprint().equals(sc.basisFingerprint())).toBe(true);
  });

  for (const sal of CANONICAL_SAMPLES) {
    it(`wire codec SAIL round-trip: ${sal.slice(0, 30)}`, () => {
      const wc = new OSMPWireCodec();
      const encoded = wc.encode(sal, WireMode.SAIL);
      const decoded = wc.decode(encoded, WireMode.SAIL);
      expect(decoded).toBe(sal);
    });
  }
});

describe("DictionaryBasis.fromPaths", () => {
  it("missing file raises", () => {
    expect(() => DictionaryBasis.fromPaths("/nonexistent/asd.csv")).toThrow(/not found/);
  });

  it("corpus_hash is SHA-256 of file bytes", () => {
    const tmp = join(tmpdir(), `osmp-test-${Date.now()}.csv`);
    const content = Buffer.from(
      "OSMP Semantic Dictionary v14\nSECTION 3\nNamespace,Prefix,...\nA,A,...,TEST,...\n",
      "utf-8",
    );
    writeFileSync(tmp, content);
    try {
      const expected = createHash("sha256").update(content).digest();
      const basis = DictionaryBasis.fromPaths(tmp);
      expect(basis.entries[0].corpusHash.equals(expected)).toBe(true);
    } finally {
      unlinkSync(tmp);
    }
  });
});
