/**
 * FNP Dictionary Basis Wire-Level Tests (ADR-004)
 *
 * Mirrors tests/test_fnp_basis.py. Verifies the wire-level FNP changes that
 * carry the Dictionary Basis Manifest through the capability handshake:
 * extended-form ADV layout, ACK match_status semantics, ESTABLISHED_SAIL /
 * ESTABLISHED_SAL_ONLY state grading, require_sail policy, degradation
 * event recording, and v1.0.2 backward compatibility.
 */

import { describe, it, expect } from "vitest";
import {
  AdaptiveSharedDictionary,
} from "../src/asd.js";
import {
  FNPSession,
  FNP_ADV_SIZE,
  FNP_ADV_EXT_FLAG,
  FNP_MSG_ADV,
  FNP_MSG_ADV_EXTENDED,
  FNP_MATCH_EXACT,
  FNP_MATCH_BASIS_MISMATCH,
  FNP_MATCH_BASIS_EXT_VS_BASE,
} from "../src/fnp.js";

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

// ─── ADV wire layout: base form ────────────────────────────────────────────

describe("FNP base-form ADV", () => {
  it("msg_type is 0x01", () => {
    const asd = new AdaptiveSharedDictionary();
    const s = new FNPSession(asd, "NODE_A");
    const adv = s.initiate();
    expect(adv[0]).toBe(FNP_MSG_ADV);
    expect(adv[0] & FNP_ADV_EXT_FLAG).toBe(0);
  });

  it("total size is 40 bytes", () => {
    const asd = new AdaptiveSharedDictionary();
    const s = new FNPSession(asd, "NODE_A");
    expect(s.initiate().length).toBe(40);
    expect(FNP_ADV_SIZE).toBe(40);
  });

  it("node_id field uses full 23 bytes in base form", () => {
    const asd = new AdaptiveSharedDictionary();
    const s = new FNPSession(asd, "NODE_LONG_NAME_22BYTES");
    const adv = s.initiate();
    const nodeIdField = new TextDecoder().decode(adv.slice(17, 40)).replace(/\0+$/, "");
    expect(nodeIdField).toBe("NODE_LONG_NAME_22BYTES");
  });

  it("base-form ADV parses with no basis fingerprint", () => {
    const asd = new AdaptiveSharedDictionary();
    const s = new FNPSession(asd, "NODE_A");
    const parsed = FNPSession.parseAdv(s.initiate());
    expect(parsed.isExtended).toBe(false);
    expect(parsed.basisFingerprint).toBeNull();
  });
});

// ─── ADV wire layout: extended form ────────────────────────────────────────

describe("FNP extended-form ADV", () => {
  it("msg_type is 0x81", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]);
    const s = new FNPSession(asd, "NODE_A", 1, undefined, { basisFingerprint: bfp });
    const adv = s.initiate();
    expect(adv[0]).toBe(FNP_MSG_ADV_EXTENDED);
    expect(adv[0] & FNP_ADV_EXT_FLAG).toBe(FNP_ADV_EXT_FLAG);
  });

  it("total size still 40 bytes (Option C field rebalance)", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array(8).fill(0xaa);
    const s = new FNPSession(asd, "NODE_A", 1, undefined, { basisFingerprint: bfp });
    expect(s.initiate().length).toBe(40);
  });

  it("basis_fingerprint sits at offset 32", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7]);
    const s = new FNPSession(asd, "NODE_A", 1, undefined, { basisFingerprint: bfp });
    const adv = s.initiate();
    expect(bytesEqual(adv.slice(32, 40), bfp)).toBe(true);
  });

  it("9-byte Meshtastic-style node_id fits the narrowed 15-byte field", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array(8).fill(0xaa);
    const s = new FNPSession(asd, "!2048ad45", 1, undefined, { basisFingerprint: bfp });
    const adv = s.initiate();
    const nodeIdField = new TextDecoder().decode(adv.slice(17, 32)).replace(/\0+$/, "");
    expect(nodeIdField).toBe("!2048ad45");
  });

  it("long node_id is truncated to 15 bytes without overwriting basis fingerprint", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array(8).fill(0xaa);
    const s = new FNPSession(asd, "NODE_LONG_NAME_22BYTES", 1, undefined, { basisFingerprint: bfp });
    const adv = s.initiate();
    expect(bytesEqual(adv.slice(32, 40), bfp)).toBe(true);
  });

  it("extended ADV round-trips through parseAdv", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array([0xde, 0xad, 0xbe, 0xef, 0xca, 0xfe, 0xba, 0xbe]);
    const s = new FNPSession(asd, "NODE_X", 1, undefined, { basisFingerprint: bfp });
    const adv = s.initiate();
    const parsed = FNPSession.parseAdv(adv);
    expect(parsed.isExtended).toBe(true);
    expect(parsed.basisFingerprint).not.toBeNull();
    expect(bytesEqual(parsed.basisFingerprint!, bfp)).toBe(true);
    expect(parsed.nodeId).toBe("NODE_X");
  });
});

// ─── State machine: ESTABLISHED_SAIL vs ESTABLISHED_SAL_ONLY ───────────────

describe("FNP state machine capability grading", () => {
  function makePair(
    fpA: Uint8Array | null,
    fpB: Uint8Array | null,
    requireSailA = false,
  ): [FNPSession, FNPSession] {
    const asd = new AdaptiveSharedDictionary();
    const a = new FNPSession(asd, "NODE_A", 1, undefined, {
      basisFingerprint: fpA ?? undefined,
      requireSail: requireSailA,
    });
    const b = new FNPSession(asd, "NODE_B", 1, undefined, {
      basisFingerprint: fpB ?? undefined,
    });
    return [a, b];
  }

  it("both base form lands in ESTABLISHED_SAIL", () => {
    const [a, b] = makePair(null, null);
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("ESTABLISHED_SAIL");
    expect(b.state).toBe("ESTABLISHED_SAIL");
    expect(a.matchStatus).toBe(FNP_MATCH_EXACT);
    expect(a.isSailCapable).toBe(true);
    expect(b.isSailCapable).toBe(true);
  });

  it("matching extended basis lands in ESTABLISHED_SAIL", () => {
    const bfp = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const [a, b] = makePair(bfp, bfp);
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("ESTABLISHED_SAIL");
    expect(b.state).toBe("ESTABLISHED_SAIL");
    expect(a.matchStatus).toBe(FNP_MATCH_EXACT);
  });

  it("mismatched extended basis lands in ESTABLISHED_SAL_ONLY", () => {
    const [a, b] = makePair(new Uint8Array(8).fill(0x01), new Uint8Array(8).fill(0x02));
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("ESTABLISHED_SAL_ONLY");
    expect(b.state).toBe("ESTABLISHED_SAL_ONLY");
    expect(a.matchStatus).toBe(FNP_MATCH_BASIS_MISMATCH);
    expect(b.matchStatus).toBe(FNP_MATCH_BASIS_MISMATCH);
    expect(a.isSailCapable).toBe(false);
    expect(b.isSailCapable).toBe(false);
  });

  it("extended initiator vs base responder lands in SAL_ONLY with EXT_VS_BASE", () => {
    const [a, b] = makePair(new Uint8Array(8).fill(0xab), null);
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("ESTABLISHED_SAL_ONLY");
    expect(b.state).toBe("ESTABLISHED_SAL_ONLY");
    expect(a.matchStatus).toBe(FNP_MATCH_BASIS_EXT_VS_BASE);
    expect(b.matchStatus).toBe(FNP_MATCH_BASIS_EXT_VS_BASE);
  });

  it("base initiator vs extended responder lands in SAL_ONLY with EXT_VS_BASE", () => {
    const [a, b] = makePair(null, new Uint8Array(8).fill(0xab));
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("ESTABLISHED_SAL_ONLY");
    expect(b.state).toBe("ESTABLISHED_SAL_ONLY");
    expect(a.matchStatus).toBe(FNP_MATCH_BASIS_EXT_VS_BASE);
    expect(b.matchStatus).toBe(FNP_MATCH_BASIS_EXT_VS_BASE);
  });
});

// ─── require_sail policy ───────────────────────────────────────────────────

describe("FNP require_sail policy", () => {
  it("refuses basis-mismatched sessions locally", () => {
    const asd = new AdaptiveSharedDictionary();
    const a = new FNPSession(asd, "NODE_A", 1, undefined, {
      basisFingerprint: new Uint8Array(8).fill(0x01),
      requireSail: true,
    });
    const b = new FNPSession(asd, "NODE_B", 1, undefined, {
      basisFingerprint: new Uint8Array(8).fill(0x02),
    });
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("IDLE");
    expect(a.degradationEvent).not.toBeNull();
    expect(a.degradationEvent!.reason).toContain("require_sail");
    // Responder without policy still establishes normally.
    expect(b.state).toBe("ESTABLISHED_SAL_ONLY");
  });

  it("does not affect matching basis sessions", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array(8).fill(0x42);
    const a = new FNPSession(asd, "NODE_A", 1, undefined, {
      basisFingerprint: bfp, requireSail: true,
    });
    const b = new FNPSession(asd, "NODE_B", 1, undefined, { basisFingerprint: bfp });
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("ESTABLISHED_SAIL");
    expect(a.degradationEvent).toBeNull();
  });

  it("does not affect base-form-only pairs", () => {
    const asd = new AdaptiveSharedDictionary();
    const a = new FNPSession(asd, "NODE_A", 1, undefined, { requireSail: true });
    const b = new FNPSession(asd, "NODE_B");
    const ack = b.receive(a.initiate());
    a.receive(ack!);
    expect(a.state).toBe("ESTABLISHED_SAIL");
    expect(a.degradationEvent).toBeNull();
  });
});

// ─── Degradation event recording ───────────────────────────────────────────

describe("FNP degradation event recording", () => {
  it("responder records event when remote basis differs from expected", () => {
    const asd = new AdaptiveSharedDictionary();
    const local = new Uint8Array(8).fill(0xaa);
    const remote = new Uint8Array(8).fill(0xbb);
    const a = new FNPSession(asd, "NODE_A", 1, undefined, { basisFingerprint: remote });
    const b = new FNPSession(asd, "NODE_B", 1, undefined, {
      basisFingerprint: local,
      expectedBasisFingerprint: local,
    });
    b.receive(a.initiate());
    expect(b.state).toBe("ESTABLISHED_SAL_ONLY");
    expect(b.degradationEvent).not.toBeNull();
    expect(b.degradationEvent!.remote_basis_fingerprint).toBe(Buffer.from(remote).toString("hex"));
    expect(b.degradationEvent!.expected_basis_fingerprint).toBe(Buffer.from(local).toString("hex"));
  });

  it("no event when no expectation set", () => {
    const asd = new AdaptiveSharedDictionary();
    const a = new FNPSession(asd, "NODE_A", 1, undefined, { basisFingerprint: new Uint8Array(8).fill(0xaa) });
    const b = new FNPSession(asd, "NODE_B", 1, undefined, { basisFingerprint: new Uint8Array(8).fill(0xbb) });
    b.receive(a.initiate());
    expect(b.degradationEvent).toBeNull();
  });

  it("no event when basis matches expected", () => {
    const asd = new AdaptiveSharedDictionary();
    const bfp = new Uint8Array(8).fill(0x42);
    const a = new FNPSession(asd, "NODE_A", 1, undefined, { basisFingerprint: bfp });
    const b = new FNPSession(asd, "NODE_B", 1, undefined, {
      basisFingerprint: bfp,
      expectedBasisFingerprint: bfp,
    });
    b.receive(a.initiate());
    expect(b.state).toBe("ESTABLISHED_SAIL");
    expect(b.degradationEvent).toBeNull();
  });
});

// ─── v1.0.2 backward compatibility ─────────────────────────────────────────

describe("FNP v1.0.2 backward compatibility", () => {
  it("extended ADV stays at FNP_ADV_SIZE bytes (no fragmentation)", () => {
    const asd = new AdaptiveSharedDictionary();
    const s = new FNPSession(asd, "NODE", 1, undefined, {
      basisFingerprint: new Uint8Array(8),
    });
    expect(s.initiate().length).toBe(FNP_ADV_SIZE);
  });

  it("base ADV is byte-compatible with v1.0.2 layout", () => {
    const asd = new AdaptiveSharedDictionary();
    const s = new FNPSession(asd, "NODE_A");
    const adv = s.initiate();
    expect(adv[0]).toBe(0x01);
    expect(adv.slice(2, 10).length).toBe(8);    // fingerprint
    expect(adv.slice(10, 12).length).toBe(2);   // asd_version
    expect(adv.slice(12, 16).length).toBe(4);   // namespace_bitmap
    expect(adv.slice(17, 40).length).toBe(23);  // node_id field
  });

  it("two base-form nodes negotiate normally", () => {
    const asd = new AdaptiveSharedDictionary();
    const a = new FNPSession(asd, "NODE_A");
    const b = new FNPSession(asd, "NODE_B");
    const adv = a.initiate();
    const ack = b.receive(adv);
    a.receive(ack!);
    expect(adv.length).toBe(40);
    expect(ack!.length).toBe(38);
    expect(a.state).toBe("ESTABLISHED_SAIL");
    expect(b.state).toBe("ESTABLISHED_SAIL");
  });
});
