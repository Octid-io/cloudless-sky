/**
 * Pangram module tests — TypeScript SDK.
 *
 * Verifies cross-SDK byte-identical SHA-256 with Python and Go via the
 * EXPECTED_PANGRAM_SHA256 constant shared across all three SDKs.
 */
import { describe, it, expect } from "vitest";
import { createHash } from "crypto";

import {
  EXPECTED_PANGRAM_SHA256,
  PANGRAM_ASD_VERSION,
  PANGRAM_BODY,
  PANGRAM_MACRO_ID,
  PANGRAM_SHA256,
  PANGRAM_SHA256_TRUNCATED_16,
  PANGRAM_UTF8_BYTES,
  emit,
  emitBytes,
  macroInvocation,
  metadata,
  verifyReceived,
} from "../src/pangram.js";

describe("Pangram canonical constants", () => {
  it("body is 185 UTF-8 bytes", () => {
    expect(PANGRAM_UTF8_BYTES).toBe(185);
  });

  it("computed SHA-256 matches registered fingerprint", () => {
    expect(PANGRAM_SHA256).toBe(EXPECTED_PANGRAM_SHA256);
    expect(PANGRAM_SHA256).toBe(
      "fcefe9363ab737be174829dd8c12f4ca365fefb3601464514dd2aa4e1e0332ba",
    );
  });

  it("truncated SHA-256 is first 16 hex chars", () => {
    expect(PANGRAM_SHA256_TRUNCATED_16).toBe(PANGRAM_SHA256.slice(0, 16));
    expect(PANGRAM_SHA256_TRUNCATED_16).toBe("fcefe9363ab737be");
  });

  it("macro ID is PANGRAM", () => {
    expect(PANGRAM_MACRO_ID).toBe("PANGRAM");
  });

  it("ASD version is pinned to v15.1", () => {
    expect(PANGRAM_ASD_VERSION).toBe("v15.1");
  });
});

describe("Pangram emit functions", () => {
  it("emit returns canonical body", () => {
    expect(emit()).toBe(PANGRAM_BODY);
  });

  it("emitBytes returns UTF-8 byte buffer", () => {
    const buf = emitBytes();
    expect(buf).toEqual(Buffer.from(PANGRAM_BODY, "utf-8"));
    expect(buf.length).toBe(185);
  });
});

describe("Pangram verifyReceived", () => {
  it("accepts canonical body as string", () => {
    expect(verifyReceived(PANGRAM_BODY)).toBe(true);
  });

  it("accepts canonical body as bytes", () => {
    expect(verifyReceived(Buffer.from(PANGRAM_BODY, "utf-8"))).toBe(true);
  });

  it("rejects modified body", () => {
    expect(verifyReceived(PANGRAM_BODY + "X")).toBe(false);
  });

  it("rejects single-bit-flip in first byte", () => {
    const buf = Buffer.from(PANGRAM_BODY, "utf-8");
    buf[0] = buf[0] ^ 1;
    expect(verifyReceived(buf)).toBe(false);
  });

  it("truncated comparison accepts canonical", () => {
    expect(verifyReceived(PANGRAM_BODY, { truncated: true })).toBe(true);
  });

  it("truncated comparison rejects modified", () => {
    expect(verifyReceived(PANGRAM_BODY + "X", { truncated: true })).toBe(false);
  });
});

describe("Pangram metadata + macro invocation", () => {
  it("macroInvocation returns A:MACRO[PANGRAM]", () => {
    expect(macroInvocation()).toBe("A:MACRO[PANGRAM]");
  });

  it("metadata covers all 9 namespaces", () => {
    const m = metadata();
    expect(m.namespacesCovered).toEqual(["A", "D", "G", "H", "I", "L", "N", "R", "T"]);
    expect(m.byteLengthUtf8).toBe(185);
    expect(m.sha256).toBe(EXPECTED_PANGRAM_SHA256);
  });
});

describe("Pangram cross-SDK parity", () => {
  it("SHA-256 is byte-identical to Python and Go EXPECTED_PANGRAM_SHA256 constant", () => {
    // The Python and Go SDKs hardcode the same EXPECTED_PANGRAM_SHA256 constant
    // and verify it at module load. Re-compute here to confirm independently.
    const h = createHash("sha256")
      .update(Buffer.from(PANGRAM_BODY, "utf-8"))
      .digest("hex");
    expect(h).toBe(EXPECTED_PANGRAM_SHA256);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Tier 2 — short-form pangram (LoRa floor)
// ─────────────────────────────────────────────────────────────────────────

import {
  EXPECTED_PANGRAM_TINY_SHA256,
  PANGRAM_TINY_BODY,
  PANGRAM_TINY_MACRO_ID,
  PANGRAM_TINY_SHA256,
  PANGRAM_TINY_UTF8_BYTES,
  ChannelTier,
  emitForTier,
  verifyForTier,
} from "../src/pangram.js";

describe("Pangram tier 2 (PANGRAM_TINY)", () => {
  it("fits LoRa floor (≤ 51 UTF-8 bytes)", () => {
    expect(PANGRAM_TINY_UTF8_BYTES).toBeLessThanOrEqual(51);
  });

  it("canonical SHA-256 matches expected", () => {
    expect(PANGRAM_TINY_SHA256).toBe(EXPECTED_PANGRAM_TINY_SHA256);
    expect(PANGRAM_TINY_SHA256).toBe(
      "91c807dbbf3693ca57fb9b10ca39a5092d69de63df19b019217460e5e9c04564",
    );
  });

  it("macro id is PANGRAM_TINY", () => {
    expect(PANGRAM_TINY_MACRO_ID).toBe("PANGRAM_TINY");
  });

  it("exercises cluster claim 4 minimum primitives", () => {
    expect(PANGRAM_TINY_BODY).toContain(":"); // frame structure
    expect(PANGRAM_TINY_BODY).toContain("@"); // target syntax
    expect(PANGRAM_TINY_BODY).toContain(">"); // threshold operator
    expect(PANGRAM_TINY_BODY).toContain(";"); // sequence operator
    expect(PANGRAM_TINY_BODY).toContain("∧"); // conjunction (∧)
    expect(/[⚠↺⊘]/.test(PANGRAM_TINY_BODY)).toBe(true); // some CC designator
  });
});

describe("Pangram tier-aware API", () => {
  it("emitForTier(STANDARD) returns full pangram body", () => {
    expect(emitForTier(ChannelTier.Standard)).toBe(PANGRAM_BODY);
  });

  it("emitForTier(LoraFloor) returns short-form pangram body", () => {
    expect(emitForTier(ChannelTier.LoraFloor)).toBe(PANGRAM_TINY_BODY);
  });

  it("verifyForTier accepts canonical per-tier", () => {
    expect(verifyForTier(PANGRAM_BODY, ChannelTier.Standard)).toBe(true);
    expect(verifyForTier(PANGRAM_TINY_BODY, ChannelTier.LoraFloor)).toBe(true);
  });

  it("verifyForTier rejects cross-tier mismatch", () => {
    expect(verifyForTier(PANGRAM_BODY, ChannelTier.LoraFloor)).toBe(false);
    expect(verifyForTier(PANGRAM_TINY_BODY, ChannelTier.Standard)).toBe(false);
  });

  it("verifyForTier truncated comparison per-tier", () => {
    expect(
      verifyForTier(PANGRAM_BODY, ChannelTier.Standard, { truncated: true }),
    ).toBe(true);
    expect(
      verifyForTier(PANGRAM_TINY_BODY, ChannelTier.LoraFloor, { truncated: true }),
    ).toBe(true);
  });
});
