/**
 * sal_patterns Tests (Finding 37, locks in Findings 13/29/30)
 * ===========================================================
 *
 * The shared regex building blocks in src/sal_patterns.ts are the
 * cross-SDK consistent fix for Findings 13 (bridge frame detection),
 * 29 (regulatory dependency parsing), and 30 (validator regex
 * factoring). These tests pin the behavior so future edits can't
 * silently break I:§ handling, Tier 2 namespaces, or single-letter
 * opcodes.
 *
 * Patent pending | License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import {
  NS_PATTERN,
  OPCODE_PATTERN,
  FRAME_SPLIT_RE,
  NS_TARGET_RE,
  FRAME_NS_OP_RE,
  PREREQ_RE,
  CHAIN_FRAME_RE,
  SAL_FRAME_RE_BRIDGE,
} from "../src/sal_patterns.js";

describe("Building block constants", () => {
  it("NS_PATTERN matches 1 or 2 uppercase letters", () => {
    const re = new RegExp(`^${NS_PATTERN}$`);
    expect(re.test("A")).toBe(true);
    expect(re.test("AB")).toBe(true);
    expect(re.test("ABC")).toBe(false); // 3 chars
    expect(re.test("a")).toBe(false);   // lowercase
  });

  it("OPCODE_PATTERN accepts § (human authorization marker)", () => {
    const re = new RegExp(`^${OPCODE_PATTERN}$`);
    expect(re.test("§")).toBe(true);
    expect(re.test("HR")).toBe(true);
    expect(re.test("HRRATE")).toBe(true);
  });

  it("OPCODE_PATTERN accepts single-letter opcodes", () => {
    const re = new RegExp(`^${OPCODE_PATTERN}$`);
    expect(re.test("Q")).toBe(true);
    expect(re.test("W")).toBe(true);
  });
});

describe("FRAME_SPLIT_RE — Finding 14", () => {
  it("splits on chain operators preserving them", () => {
    const parts = "H:CASREP→M:EVA@MEDEVAC".split(FRAME_SPLIT_RE);
    expect(parts).toContain("H:CASREP");
    expect(parts).toContain("→");
    expect(parts).toContain("M:EVA@MEDEVAC");
  });

  it("splits on semicolon sequence operator", () => {
    const parts = "A:PING;A:PONG".split(FRAME_SPLIT_RE);
    expect(parts).toContain("A:PING");
    expect(parts).toContain("A:PONG");
  });

  it("splits on AND operator", () => {
    const parts = "H:HR∧H:BP".split(FRAME_SPLIT_RE);
    expect(parts).toContain("H:HR");
    expect(parts).toContain("H:BP");
  });
});

describe("NS_TARGET_RE — Rule 2 violation detection", () => {
  it("matches @namespace:opcode pattern", () => {
    const re = new RegExp(NS_TARGET_RE.source, "g");
    const matches = [...("H:CASREP@H:ICD".matchAll(re))];
    expect(matches.length).toBe(1);
    expect(matches[0][1]).toBe("H");
    expect(matches[0][2]).toBe("ICD");
  });

  it("does not match valid @target", () => {
    const re = new RegExp(NS_TARGET_RE.source, "g");
    const matches = [...("H:HR@NODE1".matchAll(re))];
    expect(matches.length).toBe(0);
  });
});

describe("FRAME_NS_OP_RE — frame parser", () => {
  it("matches namespace:opcode at start of frame", () => {
    const m = "H:HR".match(FRAME_NS_OP_RE);
    expect(m).not.toBeNull();
    expect(m![1]).toBe("H");
    expect(m![2]).toBe("HR");
  });

  it("accepts I:§", () => {
    const m = "I:§".match(FRAME_NS_OP_RE);
    expect(m).not.toBeNull();
    expect(m![1]).toBe("I");
    expect(m![2]).toBe("§");
  });

  it("accepts Tier 2 namespace AB:CD", () => {
    const m = "AB:CD".match(FRAME_NS_OP_RE);
    expect(m).not.toBeNull();
    expect(m![1]).toBe("AB");
    expect(m![2]).toBe("CD");
  });
});

describe("CHAIN_FRAME_RE — Finding 14 chain decoding", () => {
  it("matches frame with bracket slot value", () => {
    // CHAIN_FRAME_RE has the /g flag so we use matchAll to get capture groups
    const re = new RegExp(CHAIN_FRAME_RE.source, "g");
    const matches = [...("H:ICD[J930]".matchAll(re))];
    expect(matches.length).toBeGreaterThan(0);
    expect(matches[0][1]).toBe("H");
    expect(matches[0][2]).toBe("ICD");
    expect(matches[0][3]).toBe("J930");
  });

  it("accepts I:§ in chain context", () => {
    const re = new RegExp(CHAIN_FRAME_RE.source, "g");
    const matches = [...("I:§".matchAll(re))];
    expect(matches.length).toBeGreaterThan(0);
    expect(matches[0][1]).toBe("I");
    expect(matches[0][2]).toBe("§");
  });
});

describe("SAL_FRAME_RE_BRIDGE — Finding 13 bridge frame detection", () => {
  it("detects I:§ in natural language", () => {
    const re = new RegExp(SAL_FRAME_RE_BRIDGE.source, "g");
    const matches = [...("operator should authorize via I:§ before R:MOV".matchAll(re))];
    const tuples = matches.map(m => [m[1], m[2]]);
    expect(tuples).toContainEqual(["I", "§"]);
    expect(tuples).toContainEqual(["R", "MOV"]);
  });

  it("detects Tier 2 namespace AB:CD", () => {
    const re = new RegExp(SAL_FRAME_RE_BRIDGE.source, "g");
    const matches = [...("the AB:CD frame is valid".matchAll(re))];
    expect(matches.length).toBe(1);
    expect(matches[0][1]).toBe("AB");
    expect(matches[0][2]).toBe("CD");
  });

  it("detects single-letter opcode", () => {
    const re = new RegExp(SAL_FRAME_RE_BRIDGE.source, "g");
    const matches = [...("send Z:Q to the model".matchAll(re))];
    expect(matches.length).toBe(1);
    expect(matches[0][1]).toBe("Z");
    expect(matches[0][2]).toBe("Q");
  });

  it("does not truncate long opcode names", () => {
    const re = new RegExp(SAL_FRAME_RE_BRIDGE.source, "g");
    const matches = [...("send H:HRRATE now".matchAll(re))];
    expect(matches.length).toBe(1);
    expect(matches[0][2]).toBe("HRRATE");
  });

  it("rejects lowercase as not SAL", () => {
    const re = new RegExp(SAL_FRAME_RE_BRIDGE.source, "g");
    const matches = [...("a:hr is not valid".matchAll(re))];
    expect(matches.length).toBe(0);
  });

  it("does not match SAL-shaped substring inside word", () => {
    const re = new RegExp(SAL_FRAME_RE_BRIDGE.source, "g");
    // Word boundary requires preceding non-word char or start of string
    const matches = [...("noticedH:HR".matchAll(re))];
    expect(matches.length).toBe(0);
  });

  it("matches with space restoring word boundary", () => {
    const re = new RegExp(SAL_FRAME_RE_BRIDGE.source, "g");
    const matches = [...("noticed H:HR".matchAll(re))];
    expect(matches.length).toBe(1);
  });
});

// ── Marker test for Findings 13, 29, 30 ────────────────────────────────────

describe("Cross-SDK shared regex marker", () => {
  it("Findings 13/29/30 — sal_patterns shared building blocks", () => {
    // The shared NS_PATTERN + OPCODE_PATTERN constants are imported
    // by validate.ts, regulatory_dependency.ts, and bridge.ts so
    // there's a single source of truth across the TS SDK that mirrors
    // the Python and Go SDKs. If this test fails, the cross-SDK
    // consistency for I:§ handling is broken.
    expect(NS_PATTERN).toBe("[A-Z]{1,2}");
    expect(OPCODE_PATTERN).toBe("[A-Z§][A-Z0-9§]*");

    // I:§ must work in all three regex consumers
    expect("I:§".match(FRAME_NS_OP_RE)).not.toBeNull();
    expect([..."I:§".matchAll(new RegExp(CHAIN_FRAME_RE.source, "g"))].length).toBeGreaterThan(0);
    expect(SAL_FRAME_RE_BRIDGE.test("authorize via I:§")).toBe(true);
  });
});
