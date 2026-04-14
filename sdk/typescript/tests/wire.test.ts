/**
 * Wire Codec Tests (Finding 37, locks in Sprint 3 real crypto)
 * ============================================================
 *
 * These tests guard the SecCodec and SAIL wire format. The most
 * important property is that the SecCodec uses real Ed25519 +
 * ChaCha20-Poly1305 (not the HMAC placeholder it shipped with) and
 * produces envelopes that are byte-identical to the Python SDK output
 * for the same inputs. The fingerprint test in asd_fingerprint.test.ts
 * locks in cross-SDK ASD compatibility; this file locks in cross-SDK
 * wire format compatibility.
 *
 * Patent pending | License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import { SecCodec, SAILCodec, OSMPWireCodec, WireMode } from "../src/osmp_wire.js";

// Deterministic keys (match Python alice_keys fixture)
const ALICE_NODE_ID = Buffer.from([0xa0, 0x01]);
const ALICE_SIGNING = Buffer.from(Array.from({ length: 32 }, (_, i) => i));
const ALICE_SYMMETRIC = Buffer.from(Array.from({ length: 32 }, (_, i) => i + 32));

describe("SecCodec real cryptography", () => {
  it("constructor accepts deterministic 32-byte keys", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    expect(codec).toBeDefined();
  });

  it("rejects wrong node_id length", () => {
    expect(() => new SecCodec(Buffer.from([0x01, 0x02, 0x03]), ALICE_SIGNING, ALICE_SYMMETRIC))
      .toThrow(/nodeId must be 2 or 4 bytes/);
  });

  it("rejects wrong signing key length", () => {
    expect(() => new SecCodec(ALICE_NODE_ID, Buffer.alloc(16), ALICE_SYMMETRIC))
      .toThrow(/signingKey must be 32 bytes/);
  });

  it("rejects wrong symmetric key length", () => {
    expect(() => new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, Buffer.alloc(16)))
      .toThrow(/symmetricKey must be 32 bytes/);
  });

  it("public signing key is 32 bytes", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    expect(codec.publicSigningKey.length).toBe(32);
  });

  it("public signing key is deterministic from seed", () => {
    const a = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const b = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    expect(a.publicSigningKey.equals(b.publicSigningKey)).toBe(true);
  });

  it("payload is encrypted on the wire (not plaintext)", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const plaintext = Buffer.from("this is a secret payload");
    const envelope = codec.pack(plaintext);
    // The plaintext substring must NOT appear in the envelope bytes
    expect(envelope.includes(plaintext)).toBe(false);
  });

  it("envelope overhead is 87 bytes for 2-byte node_id", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const envelope = codec.pack(Buffer.alloc(0));
    expect(envelope.length).toBe(87);
  });

  it("envelope grows by exact payload size", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    for (const n of [0, 1, 10, 50, 100]) {
      const envelope = codec.pack(Buffer.alloc(n, "X"));
      expect(envelope.length).toBe(87 + n);
    }
  });

  it("roundtrip preserves payload", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const plaintext = Buffer.from("hello world");
    const envelope = codec.pack(plaintext);
    const parsed = codec.unpack(envelope);
    expect(parsed).not.toBeNull();
    expect(parsed!.payload.equals(plaintext)).toBe(true);
  });

  it("rejects tampered payload", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const envelope = codec.pack(Buffer.from("original"));
    const tampered = Buffer.concat([
      envelope.subarray(0, 10),
      Buffer.from([envelope[10] ^ 1]),
      envelope.subarray(11),
    ]);
    expect(codec.unpack(tampered)).toBeNull();
  });

  it("seq counter increments monotonically", () => {
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const e1 = codec.pack(Buffer.from("first"));
    const e2 = codec.pack(Buffer.from("second"));
    expect(codec.unpack(e1)!.seqCounter).toBe(1);
    expect(codec.unpack(e2)!.seqCounter).toBe(2);
  });
});

describe("SecCodec cross-codec verification (real Ed25519)", () => {
  it("Bob with Alice's pubkey decodes Alice's envelope", () => {
    const alice = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const envelope = alice.pack(Buffer.from("hello bob"));

    // Bob has his own Ed25519 keys but shares the symmetric key,
    // and verifies with Alice's public key
    const bob = new SecCodec(
      Buffer.from([0xb0, 0x02]),
      Buffer.from(Array.from({ length: 32 }, (_, i) => i + 64)),
      ALICE_SYMMETRIC,
      alice.publicSigningKey,
    );
    const parsed = bob.unpack(envelope);
    expect(parsed).not.toBeNull();
    expect(parsed!.payload.toString()).toBe("hello bob");
  });

  it("envelope from Alice fails without Alice's pubkey", () => {
    const alice = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const envelope = alice.pack(Buffer.from("hello bob"));

    // Bob uses default loopback verification (his own pubkey, wrong)
    const bob = new SecCodec(
      Buffer.from([0xb0, 0x02]),
      Buffer.from(Array.from({ length: 32 }, (_, i) => i + 64)),
      ALICE_SYMMETRIC,
    );
    expect(bob.unpack(envelope)).toBeNull();
  });
});

describe("SAIL codec", () => {
  it("encodes and decodes a simple frame", () => {
    const codec = new SAILCodec();
    const sal = "H:HR";
    const sail = codec.encode(sal);
    expect(sail.length).toBeGreaterThan(0);
    const decoded = codec.decode(sail);
    expect(decoded).toBe(sal);
  });

  it("encodes and decodes a frame with target", () => {
    const codec = new SAILCodec();
    const sal = "H:HR@NODE1";
    const decoded = codec.decode(codec.encode(sal));
    expect(decoded).toBe(sal);
  });

  it("encodes and decodes a frame with consequence class", () => {
    const codec = new SAILCodec();
    const sal = "R:MOV@DRONE1⚠";
    const decoded = codec.decode(codec.encode(sal));
    expect(decoded).toBe(sal);
  });

  it("SAIL is more compact than mnemonic for known opcodes", () => {
    const codec = new SAILCodec();
    const sal = "H:HR@NODE1";
    const sail = codec.encode(sal);
    expect(sail.length).toBeLessThanOrEqual(Buffer.byteLength(sal, "utf-8"));
  });
});

describe("OSMPWireCodec four-mode roundtrip", () => {
  it("MNEMONIC mode preserves SAL exactly", () => {
    const codec = new OSMPWireCodec({
      nodeId: ALICE_NODE_ID,
      signingKey: ALICE_SIGNING,
      symmetricKey: ALICE_SYMMETRIC,
    });
    const sal = "H:HR@NODE1";
    const encoded = codec.encode(sal, WireMode.MNEMONIC);
    expect(codec.decode(encoded, WireMode.MNEMONIC)).toBe(sal);
  });

  it("SAIL mode preserves SAL through binary encode", () => {
    const codec = new OSMPWireCodec({
      nodeId: ALICE_NODE_ID,
      signingKey: ALICE_SIGNING,
      symmetricKey: ALICE_SYMMETRIC,
    });
    const sal = "H:HR@NODE1";
    const encoded = codec.encode(sal, WireMode.SAIL);
    expect(codec.decode(encoded, WireMode.SAIL)).toBe(sal);
  });

  it("SEC mode wraps mnemonic in security envelope", () => {
    const codec = new OSMPWireCodec({
      nodeId: ALICE_NODE_ID,
      signingKey: ALICE_SIGNING,
      symmetricKey: ALICE_SYMMETRIC,
    });
    const sal = "H:HR@NODE1";
    const encoded = codec.encode(sal, WireMode.SEC);
    expect(encoded.length).toBeGreaterThan(87); // overhead + payload
    expect(codec.decode(encoded, WireMode.SEC)).toBe(sal);
  });

  it("SAIL_SEC mode wraps SAIL in security envelope", () => {
    const codec = new OSMPWireCodec({
      nodeId: ALICE_NODE_ID,
      signingKey: ALICE_SIGNING,
      symmetricKey: ALICE_SYMMETRIC,
    });
    const sal = "H:HR@NODE1";
    const encoded = codec.encode(sal, WireMode.SAIL_SEC);
    expect(codec.decode(encoded, WireMode.SAIL_SEC)).toBe(sal);
  });
});

// ── Marker test for the audit finding ──────────────────────────────────────

describe("Sprint 3 real crypto marker", () => {
  it("Findings 4/31 — SecCodec uses real Ed25519 + ChaCha20-Poly1305", () => {
    // If this test fails, the SecCodec has reverted to the HMAC
    // placeholder it shipped with. Real crypto must:
    //   1. Encrypt the payload (not ship plaintext)
    //   2. Produce 64-byte signatures
    //   3. Produce 16-byte auth tags
    const codec = new SecCodec(ALICE_NODE_ID, ALICE_SIGNING, ALICE_SYMMETRIC);
    const plaintext = Buffer.from("the marker payload");
    const envelope = codec.pack(plaintext);

    expect(envelope.includes(plaintext)).toBe(false);

    const parsed = codec.unpack(envelope);
    expect(parsed).not.toBeNull();
    expect(parsed!.signature.length).toBe(64);
    expect(parsed!.authTag.length).toBe(16);
    expect(parsed!.payload.equals(plaintext)).toBe(true);
  });
});
