/**
 * Registered Macro Architecture Tests (TypeScript parity)
 * =======================================================
 *
 * Mirrors tests/tier1/test_macros.py 1:1 to lock cross-SDK byte-identical
 * behavior for the MacroRegistry, MacroTemplate, and SlotDefinition classes.
 *
 * Patent pending | License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import {
  AdaptiveSharedDictionary,
  MacroRegistry,
  MacroTemplate,
  SlotDefinition,
  SALComposer,
} from "../src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..", "..");
const CORPUS_PATH = resolve(REPO_ROOT, "mdr", "meshtastic", "meshtastic-macros.json");

// ── Registration and Lookup ────────────────────────────────────────────────

describe("MacroRegistration", () => {
  it("registers and looks up a macro", () => {
    const reg = new MacroRegistry();
    const template = new MacroTemplate(
      "TEST:SIMPLE",
      "H:HR[bpm:{bpm}]",
      [new SlotDefinition("bpm", "uint")],
      "Simple heart rate macro",
    );
    reg.register(template);
    const result = reg.lookup("TEST:SIMPLE");
    expect(result).not.toBeNull();
    expect(result!.macroId).toBe("TEST:SIMPLE");
  });

  it("returns null for nonexistent lookup", () => {
    const reg = new MacroRegistry();
    expect(reg.lookup("DOES:NOT:EXIST")).toBeNull();
  });

  it("validates opcodes against the ASD on register", () => {
    const reg = new MacroRegistry();
    const template = new MacroTemplate(
      "BAD:OPCODE",
      "Z:NONEXISTENT[val:{v}]",
      [new SlotDefinition("v", "string")],
      "Uses a nonexistent opcode",
    );
    expect(() => reg.register(template)).toThrow(/not found in ASD/);
  });

  it("rejects extra slot definitions with no placeholder", () => {
    const reg = new MacroRegistry();
    const template = new MacroTemplate(
      "BAD:SLOTS",
      "H:HR[bpm:{bpm}]",
      [
        new SlotDefinition("bpm", "uint"),
        new SlotDefinition("extra", "string"),
      ],
      "Extra slot with no placeholder",
    );
    expect(() => reg.register(template)).toThrow(/no matching placeholder/);
  });

  it("rejects placeholders with no matching SlotDefinition", () => {
    const reg = new MacroRegistry();
    const template = new MacroTemplate(
      "BAD:MISSING",
      "H:HR[bpm:{bpm}]\u2227H:SPO2[o2:{spo2}]",
      [new SlotDefinition("bpm", "uint")],
      "Missing slot definition",
    );
    expect(() => reg.register(template)).toThrow(/no matching SlotDefinition/);
  });

  it("lists all registered macros", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "A:ONE", "A:ACK[m:{m}]",
      [new SlotDefinition("m", "string")], "first",
    ));
    reg.register(new MacroTemplate(
      "A:TWO", "A:NACK[m:{m}]",
      [new SlotDefinition("m", "string")], "second",
    ));
    const macros = reg.listMacros();
    expect(macros.length).toBe(2);
    const ids = new Set(macros.map((m) => m.macroId));
    expect(ids).toEqual(new Set(["A:ONE", "A:TWO"]));
  });
});

// ── Expansion and Slot-Fill ───────────────────────────────────────────────

describe("MacroExpansion", () => {
  it("expands a simple single-slot macro", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:HR", "H:HR[bpm:{bpm}]",
      [new SlotDefinition("bpm", "uint")], "heart rate",
    ));
    expect(reg.expand("TEST:HR", { bpm: 72 })).toBe("H:HR[bpm:72]");
  });

  it("expands a multi-slot chain", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:ENV",
      "E:TH[t:{temp},h:{hum}]\u2227E:PU[p:{press}]",
      [
        new SlotDefinition("temp", "float"),
        new SlotDefinition("hum", "float"),
        new SlotDefinition("press", "float"),
      ],
      "environment",
    ));
    const result = reg.expand("TEST:ENV", { temp: 22.5, hum: 65.0, press: 1013.25 });
    // Slot type "float" forces TS to emit "65.0" (cross-SDK parity with Python str()).
    expect(result).toBe("E:TH[t:22.5,h:65.0]\u2227E:PU[p:1013.25]");
  });

  it("expands the MEDEVAC embodiment (Spec Section 11)", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "MEDEVAC",
      "H:ICD[{dx_code}]\u2192H:CASREP\u2227M:EVA@{target}",
      [
        new SlotDefinition("dx_code", "string", "H"),
        new SlotDefinition("target", "string"),
      ],
      "Clinical MEDEVAC",
    ));
    const result = reg.expand("MEDEVAC", { dx_code: "J930", target: "MED1" });
    expect(result).toBe("H:ICD[J930]\u2192H:CASREP\u2227M:EVA@MED1");
  });

  it("throws when required slot values are missing", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:TWO",
      "H:HR[bpm:{bpm}]\u2227H:SPO2[o2:{spo2}]",
      [new SlotDefinition("bpm", "uint"), new SlotDefinition("spo2", "uint")],
      "two slots",
    ));
    expect(() => reg.expand("TEST:TWO", { bpm: 72 })).toThrow(/missing slot values/);
  });

  it("throws when expanding a nonexistent macro", () => {
    const reg = new MacroRegistry();
    expect(() => reg.expand("NOPE", { x: 1 })).toThrow(/Macro not found/);
  });

  it("does NOT validate composition on expansion", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:CHAIN", "A:ACK\u2227A:NACK", [], "no slots",
    ));
    expect(reg.expand("TEST:CHAIN", {})).toBe("A:ACK\u2227A:NACK");
  });
});

// ── Compact and Expanded Wire Format ──────────────────────────────────────

describe("MacroWireFormat", () => {
  it("encodes compact form", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:HR", "H:HR[bpm:{bpm}]",
      [new SlotDefinition("bpm", "uint")], "heart rate",
    ));
    expect(reg.encodeCompact("TEST:HR", { bpm: 72 })).toBe("A:MACRO[TEST:HR]:bpm[72]");
  });

  it("encodes expanded form", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:HR", "H:HR[bpm:{bpm}]",
      [new SlotDefinition("bpm", "uint")], "heart rate",
    ));
    expect(reg.encodeExpanded("TEST:HR", { bpm: 72 })).toBe("H:HR[bpm:72]");
  });

  it("compact form preserves slot definition order", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:MULTI", "E:TH[t:{t}]\u2227E:PU[p:{p}]",
      [new SlotDefinition("t", "float"), new SlotDefinition("p", "float")],
      "multi",
    ));
    const result = reg.encodeCompact("TEST:MULTI", { t: 22.5, p: 1013.0 });
    expect(result.indexOf(":t[22.5]")).toBeGreaterThanOrEqual(0);
    expect(result.indexOf(":p[1013.0]")).toBeGreaterThanOrEqual(0);
    expect(result.indexOf(":t[")).toBeLessThan(result.indexOf(":p["));
  });

  it("encodes with expansion annotation", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:ANN", "A:ACK[m:{m}]",
      [new SlotDefinition("m", "string")], "annotated",
    ));
    const result = reg.encodeWithAnnotation("TEST:ANN", { m: "hello" });
    expect(result).toContain("A:MACRO[TEST:ANN]");
    expect(result).toContain("_EXP[A:ACK[m:hello]]");
  });
});

// ── Consequence Class Inheritance ─────────────────────────────────────────

describe("ConsequenceClassInheritance", () => {
  it("returns null when no R-namespace frames present", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:NOCC", "H:HR[bpm:{bpm}]",
      [new SlotDefinition("bpm", "uint")], "no R namespace",
    ));
    expect(reg.inheritedConsequenceClass("TEST:NOCC")).toBeNull();
  });

  it("inherits REVERSIBLE from a single R frame", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:REV", "R:MOV@BOT1\u21ba", [], "reversible R",
    ));
    expect(reg.inheritedConsequenceClass("TEST:REV")).toBe("\u21ba");
  });

  it("inherits HAZARDOUS from a single R frame with ⚠", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:HAZ", "I:\u00a7\u2192R:DRVE@UAV1\u26a0", [], "hazardous R",
    ));
    expect(reg.inheritedConsequenceClass("TEST:HAZ")).toBe("\u26a0");
  });

  it("returns the highest CC when mixed (HAZARDOUS > REVERSIBLE)", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:MIX",
      "R:MOV@BOT1\u21ba\u2227I:\u00a7\u2192R:DPTH@UUV1\u26a0",
      [], "mixed CC",
    ));
    expect(reg.inheritedConsequenceClass("TEST:MIX")).toBe("\u26a0");
  });

  it("compact form carries the inherited consequence class on the wire", () => {
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "TEST:CCWIRE", "R:MOV@{target}\u21ba",
      [new SlotDefinition("target", "string")], "CC on wire",
    ));
    const compact = reg.encodeCompact("TEST:CCWIRE", { target: "BOT1" });
    expect(compact.endsWith("\u21ba")).toBe(true);
  });
});

// ── Corpus Loading (Meshtastic) ────────────────────────────────────────────

describe("CorpusLoading", () => {
  function loadCorpus(): MacroRegistry {
    const reg = new MacroRegistry();
    const text = readFileSync(CORPUS_PATH, "utf-8");
    const corpus = JSON.parse(text);
    reg.loadCorpus(corpus);
    return reg;
  }

  it("loads the full Meshtastic corpus (16 macros)", () => {
    const reg = new MacroRegistry();
    const text = readFileSync(CORPUS_PATH, "utf-8");
    const corpus = JSON.parse(text);
    const count = reg.loadCorpus(corpus);
    expect(count).toBe(16);
  });

  it("registers every expected Meshtastic macro id", () => {
    const reg = loadCorpus();
    const ids = new Set(reg.listMacros().map((m) => m.macroId));
    const expected = new Set([
      "MESH:DEV", "MESH:ENV", "MESH:AQ", "MESH:PWR", "MESH:HLTH",
      "MESH:STAT", "MESH:POS", "MESH:NODE", "MESH:ACK", "MESH:ALRT",
      "MESH:TRACE", "MESH:WPT", "MESH:TALRT", "MESH:BATLO", "MESH:NOFF",
      "MEDEVAC",
    ]);
    expect(ids).toEqual(expected);
  });

  it("MESH:DEV expands with all five slots", () => {
    const reg = loadCorpus();
    const result = reg.expand("MESH:DEV", {
      battery_level: 87,
      voltage: 3.72,
      channel_util: 12.5,
      air_util: 3.2,
      uptime: 3600,
    });
    expect(result).toContain("X:STORE[bat:87]");
    expect(result).toContain("X:VOLT[v:3.72]");
  });

  it("MESH:HLTH expands with vitals slots", () => {
    const reg = loadCorpus();
    const result = reg.expand("MESH:HLTH", {
      heart_bpm: 72,
      spO2: 98,
      temperature: 36.6,
    });
    expect(result).toContain("H:HR[bpm:72]");
    expect(result).toContain("H:SPO2[o2:98]");
  });

  it("MEDEVAC matches Spec Section 11 byte-identical (cross-SDK lock)", () => {
    const reg = loadCorpus();
    const result = reg.expand("MEDEVAC", { dx_code: "J930", target: "MED1" });
    expect(result).toBe("H:ICD[J930]\u2192H:CASREP\u2227M:EVA@MED1");
  });

  it("compact form is smaller than the natural-language equivalent", () => {
    const reg = loadCorpus();
    const expanded = reg.expand("MESH:DEV", {
      battery_level: 87, voltage: 3.72, channel_util: 12.5,
      air_util: 3.2, uptime: 3600,
    });
    const nl = "Report battery 87%, voltage 3.72V, channel utilization 12.5%, TX airtime 3.2%, uptime 3600s";
    expect(new TextEncoder().encode(expanded).length).toBeLessThan(new TextEncoder().encode(nl).length);
  });
});

// ── Composer integration: macro priority + chain-split ────────────────────

describe("ComposerMacroPriority", () => {
  function loadComposerWithCorpus(): SALComposer {
    const reg = new MacroRegistry();
    const text = readFileSync(CORPUS_PATH, "utf-8");
    const corpus = JSON.parse(text);
    reg.loadCorpus(corpus);
    return new SALComposer(undefined, reg);
  }

  it("prefers a macro match over individual opcode composition", () => {
    const composer = loadComposerWithCorpus();
    // "battery" is a trigger on MESH:DEV
    const sal = composer.compose("report device status with battery details");
    expect(sal).toBe("A:MACRO[MESH:DEV]");
  });

  it("falls through when no macro trigger matches", () => {
    const composer = loadComposerWithCorpus();
    // "fire alarm" is a curated trigger (B:ALRM); not in any macro trigger list.
    const sal = composer.compose("fire alarm in building B");
    expect(sal).not.toBeNull();
    expect(sal!.startsWith("A:MACRO[")).toBe(false);
  });

  it("works without a macro registry (backward-compatible default)", () => {
    const composer = new SALComposer();
    expect(composer.macroRegistry).toBeNull();
    const sal = composer.compose("temp report from sensor");
    expect(sal).not.toBeNull();
  });

  it("can be attached after construction via setMacroRegistry", () => {
    const composer = new SALComposer();
    expect(composer.macroRegistry).toBeNull();
    const reg = new MacroRegistry();
    reg.register(new MacroTemplate(
      "FOO:BAR", "A:ACK[m:{m}]",
      [new SlotDefinition("m", "string")],
      "test", null, ["foo bar trigger"],
    ));
    composer.setMacroRegistry(reg);
    expect(composer.macroRegistry).toBe(reg);
    expect(composer.compose("please run the foo bar trigger now")).toBe("A:MACRO[FOO:BAR]");
  });
});

describe("ComposerChainSplit", () => {
  it("splits 'A, then B' into a SEQUENCE chain", () => {
    const composer = new SALComposer();
    const sal = composer.compose("encrypt the payload, then push to node BRAVO");
    // Both segments should compose; the join operator must be ; (SEQUENCE)
    expect(sal).not.toBeNull();
    expect(sal!.includes(";")).toBe(true);
  });

  it("splits 'A then B' (no comma) into a SEQUENCE chain", () => {
    const composer = new SALComposer();
    const sal = composer.compose("sign payload then push to node ALPHA");
    expect(sal).not.toBeNull();
    expect(sal!.includes(";")).toBe(true);
  });

  it("does not chain-split conditional sentences containing ' if '", () => {
    const composer = new SALComposer();
    // "if X then Y" must remain single-segment for condition extraction
    const sal = composer.compose("if temperature above 100 then alert operator");
    // Either composes as a conditional (→) or returns null; must NOT be a ; chain
    if (sal !== null) {
      expect(sal.includes(";")).toBe(false);
    }
  });

  it("aborts the chain and falls through when any segment fails", () => {
    const composer = new SALComposer();
    // Both segments are gibberish: chain-split returns null (segment fails),
    // and the full-string fallback also resolves nothing.
    const sal = composer.compose("xqzqzq frrrgg, then qqqq llwwww");
    expect(sal).toBeNull();
  });

  it("falls through to single-compose when chain-split's segment fails but the full string matches", () => {
    const composer = new SALComposer();
    // Chain-split sees ", then" — splits into ["encrypt the payload", "xqzqzq frrrgg"].
    // Second segment fails → chain-split returns null. Falls through to the full-string
    // path which still recognizes "encrypt" → S:ENC. Mirrors Python compose() behavior
    // at protocol.py lines 2566-2576.
    const sal = composer.compose("encrypt the payload, then xqzqzq frrrgg");
    expect(sal).not.toBeNull();
    expect(sal!.includes(";")).toBe(false); // not a chain — fell through to single
  });
});
