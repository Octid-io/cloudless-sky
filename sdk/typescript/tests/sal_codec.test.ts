/**
 * SAL Encoder / Decoder / Validator Tests (Finding 37)
 * ====================================================
 *
 * Lock-in tests for the SAL encode/decode/validate path. Canonical
 * frames and expected behaviors mirror the Python tier1 test suite.
 *
 * Patent pending | License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import { OSMPEncoder } from "../src/encoder.js";
import { OSMPDecoder } from "../src/decoder.js";
import { validateComposition } from "../src/validate.js";

describe("OSMPEncoder", () => {
  const enc = new OSMPEncoder();

  it("encodes a simple H:HR frame", () => {
    expect(enc.encodeFrame("H", "HR")).toBe("H:HR");
  });

  it("encodes a frame with target", () => {
    expect(enc.encodeFrame("H", "HR", "NODE1")).toBe("H:HR@NODE1");
  });

  it("encodes a frame with target and slot", () => {
    expect(enc.encodeFrame("H", "HR", "NODE1", undefined, { ALERT: "120" }))
      .toBe("H:HR@NODE1:ALERT:120");
  });

  it("R namespace requires consequence class", () => {
    expect(() => enc.encodeFrame("R", "MOV", "DRONE1")).toThrow(
      /R namespace requires consequence class/,
    );
  });

  it("R frame with HAZARDOUS consequence class encodes", () => {
    const out = enc.encodeFrame("R", "MOV", "DRONE1", undefined, undefined, "⚠");
    expect(out).toBe("R:MOV@DRONE1⚠");
  });

  it("encodes broadcast", () => {
    expect(enc.encodeBroadcast("M", "EVA")).toBe("M:EVA@*");
  });

  it("encodes sequence", () => {
    const out = enc.encodeSequence(["A:PING", "A:PONG"]);
    expect(out).toBe("A:PING;A:PONG");
  });

  it("encodes compound with THEN operator", () => {
    expect(enc.encodeCompound("H:CASREP", "→", "M:EVA@MEDEVAC"))
      .toBe("H:CASREP→M:EVA@MEDEVAC");
  });

  it("rejects unknown compound operator", () => {
    expect(() => enc.encodeCompound("A", "?", "B")).not.toThrow();
    // ? IS in GLYPH_OPERATORS, so it doesn't throw. Testing with a
    // truly unknown operator:
    expect(() => enc.encodeCompound("A", "%", "B")).toThrow(
      /Unknown operator/,
    );
  });
});

describe("OSMPDecoder", () => {
  const dec = new OSMPDecoder();

  it("decodes a simple frame", () => {
    const result = dec.decodeFrame("H:HR");
    expect(result.namespace).toBe("H");
    expect(result.opcode).toBe("HR");
    expect(result.opcodeMeaning).toBe("heart_rate");
  });

  it("decodes a frame with target", () => {
    const result = dec.decodeFrame("H:HR@NODE1");
    expect(result.namespace).toBe("H");
    expect(result.opcode).toBe("HR");
    expect(result.target).toBe("NODE1");
  });

  it("decodes a frame with consequence class", () => {
    const result = dec.decodeFrame("R:MOV@DRONE1⚠");
    expect(result.namespace).toBe("R");
    expect(result.opcode).toBe("MOV");
    expect(result.target).toBe("DRONE1");
    expect(result.consequenceClass).toBe("⚠");
    expect(result.consequenceClassName).toBe("HAZARDOUS");
  });

  it("decodes a frame with slots", () => {
    const result = dec.decodeFrame("H:HR@NODE1:ALERT:120");
    expect(result.target).toBe("NODE1");
    expect(result.slots).toEqual({ ALERT: "120" });
  });

  it("returns null meaning for unknown opcode", () => {
    const result = dec.decodeFrame("H:NOTREAL");
    expect(result.opcodeMeaning).toBe(null);
  });
});

describe("Encode/decode round trip", () => {
  const enc = new OSMPEncoder();
  const dec = new OSMPDecoder();

  it("round trips simple frame", () => {
    const sal = enc.encodeFrame("H", "HR");
    const result = dec.decodeFrame(sal);
    expect(result.namespace).toBe("H");
    expect(result.opcode).toBe("HR");
  });

  it("round trips R frame with consequence class", () => {
    const sal = enc.encodeFrame("R", "MOV", "DRONE1", undefined, undefined, "⚠");
    const result = dec.decodeFrame(sal);
    expect(result.namespace).toBe("R");
    expect(result.opcode).toBe("MOV");
    expect(result.target).toBe("DRONE1");
    expect(result.consequenceClass).toBe("⚠");
  });
});

describe("validateComposition", () => {
  it("accepts a valid simple frame", () => {
    const result = validateComposition("H:HR", "heart rate");
    expect(result.errors.length).toBe(0);
  });

  it("rejects slash operator", () => {
    const result = validateComposition("H:HR/M:EVA", "heart rate / evacuate");
    expect(result.errors.some(e => e.rule === "SLASH_OPERATOR")).toBe(true);
  });

  it("rejects namespace as target", () => {
    const result = validateComposition("H:CASREP@H:ICD", "");
    expect(result.errors.some(e => e.rule === "NAMESPACE_AS_TARGET")).toBe(true);
  });

  it("rejects hallucinated opcode", () => {
    const result = validateComposition("H:NOTAREALOPCODE", "");
    expect(result.errors.some(e => e.rule === "HALLUCINATED_OPCODE")).toBe(true);
  });

  it("accepts R frame with consequence class and I:§ precondition", () => {
    const result = validateComposition("I:§→R:MOV@DRONE1⚠", "human gate then move drone");
    // Should be valid: HAZARDOUS preceded by I:§
    expect(result.errors.length).toBe(0);
  });

  it("rejects R HAZARDOUS frame without I:§ precondition", () => {
    const result = validateComposition("R:MOV@DRONE1⚠", "move drone hazardous");
    // ⚠ requires I:§ precondition
    expect(result.errors.some(e => e.rule === "AUTHORIZATION_OMISSION")).toBe(true);
  });
});
