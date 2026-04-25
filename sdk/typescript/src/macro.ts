/**
 * OSMP Macro Registry — TypeScript port from sdk/python/osmp/protocol.py
 *
 * A pre-validated multi-step SAL instruction chain template carries an opcode
 * sequence with operator glyphs and {slot_name} placeholders. The MacroRegistry
 * stores templates, validates that referenced opcodes exist in the ASD, and
 * produces compact wire form (A:MACRO[id]:slot[val]) or expanded chain form
 * (the full chain with values substituted). Templates inherit a consequence
 * class from the most-severe R namespace frame in the chain.
 *
 * This file ports the Python implementation 1:1 to keep cross-SDK parity.
 * The compose-time macro priority check (a registered macro is preferred over
 * individual opcode composition) is wired in sal_composer.ts.
 *
 * Patent pending -- inventor Clay Holberg
 * License: Apache 2.0
 */

import { AdaptiveSharedDictionary } from "./asd.js";
import { FRAME_SPLIT_RE, FRAME_NS_OP_RE } from "./sal_patterns.js";

// ── Slot definition ─────────────────────────────────────────────────────────

/** A typed parameter slot in a macro chain template. */
export class SlotDefinition {
  constructor(
    public readonly name: string,
    public readonly slotType: string = "string", // string, uint, float, enum, bool
    public readonly namespace: string | null = null, // optional namespace hint for Layer 2 accessors
  ) {}
}

// ── Macro template ──────────────────────────────────────────────────────────

/**
 * A pre-validated multi-step SAL instruction chain template.
 *
 * The chain_template contains namespace-prefixed opcodes connected by glyph
 * operators, with {slot_name} placeholders at positions where the invoking
 * agent supplies context-specific values.
 */
export class MacroTemplate {
  constructor(
    public readonly macroId: string,
    public readonly chainTemplate: string,
    public readonly slots: ReadonlyArray<SlotDefinition>,
    public readonly description: string,
    public readonly consequenceClass: string | null = null,
    public readonly triggers: ReadonlyArray<string> = [],
  ) {}

  /** Return a copy with a different consequence class (used during registration when CC is computed). */
  withConsequenceClass(cc: string | null): MacroTemplate {
    return new MacroTemplate(
      this.macroId,
      this.chainTemplate,
      this.slots,
      this.description,
      cc,
      this.triggers,
    );
  }
}

// ── Consequence class severity ordering for inheritance ─────────────────────

const CC_SEVERITY: Readonly<Record<string, number>> = Object.freeze({
  "\u21BA": 1, // ↺ REVERSIBLE
  "\u26A0": 2, // ⚠ HAZARDOUS
  "\u2298": 3, // ⊘ IRREVERSIBLE
});

const CC_BY_SEVERITY: Readonly<Record<number, string>> = Object.freeze(
  Object.fromEntries(Object.entries(CC_SEVERITY).map(([g, s]) => [s, g])),
);

// Operators that should be filtered out when scanning frames for macro/CC analysis.
// Mirrors the Python filter list in protocol.py.
const OPERATOR_TOKENS: ReadonlySet<string> = new Set([
  "\u2192", // → THEN
  "\u2227", // ∧ AND
  "\u2228", // ∨ OR
  "\u2194", // ↔ IFF
  "\u2225", // ∥ PARALLEL
  ";",
  "->",
]);

// ── Macro Registry ──────────────────────────────────────────────────────────

interface MacroCorpusEntry {
  macro_id: string;
  chain_template: string;
  description?: string;
  triggers?: string[];
  slots?: Array<{
    name: string;
    slot_type?: string;
    namespace?: string | null;
  }>;
}

interface MacroCorpus {
  macros?: MacroCorpusEntry[];
}

/**
 * Registry of pre-validated SAL instruction chain templates.
 *
 * Macros are an ASD extension: stored alongside regular opcodes, queried
 * through the same lookup path, but with template expansion triggered when
 * A:MACRO is detected.
 */
export class MacroRegistry {
  readonly asd: AdaptiveSharedDictionary;
  private readonly _macros: Map<string, MacroTemplate>;

  constructor(asd: AdaptiveSharedDictionary | null = null) {
    this.asd = asd ?? new AdaptiveSharedDictionary();
    this._macros = new Map();
  }

  /**
   * Register a macro template.
   *
   * Validates that every opcode in the chain exists in the ASD and that
   * all slot placeholders have matching SlotDefinitions. Computes the
   * inherited consequence class from the chain.
   */
  register(template: MacroTemplate): void {
    // Strip slot placeholders before opcode validation
    const chain = template.chainTemplate;
    const clean = chain.replace(/\{[^}]+\}/g, "X");

    // Split into frames using the canonical splitter
    const parts = clean.split(FRAME_SPLIT_RE);
    const frames = parts
      .map((p) => p.trim())
      .filter((p) => p.length > 0 && !OPERATOR_TOKENS.has(p));

    for (const frame of frames) {
      const m = FRAME_NS_OP_RE.exec(frame);
      if (m) {
        const ns = m[1];
        const op = m[2];
        if (this.asd.lookup(ns, op) === null) {
          throw new Error(
            `Macro ${template.macroId}: opcode ${ns}:${op} not found in ASD`,
          );
        }
      }
    }

    // Validate slot placeholders have matching definitions
    const placeholderMatches = template.chainTemplate.matchAll(/\{(\w+)\}/g);
    const placeholders = new Set<string>();
    for (const pm of placeholderMatches) placeholders.add(pm[1]);

    const definedSlots = new Set(template.slots.map((s) => s.name));

    const missing = [...placeholders].filter((p) => !definedSlots.has(p));
    if (missing.length > 0) {
      throw new Error(
        `Macro ${template.macroId}: slot placeholders ${JSON.stringify(missing)} ` +
          `have no matching SlotDefinition`,
      );
    }

    const extra = [...definedSlots].filter((s) => !placeholders.has(s));
    if (extra.length > 0) {
      throw new Error(
        `Macro ${template.macroId}: SlotDefinitions ${JSON.stringify(extra)} ` +
          `have no matching placeholder in chain template`,
      );
    }

    // Compute inherited consequence class from R frames
    const cc = this._computeInheritedCc(clean);

    // Store with computed CC if not explicitly set
    let toStore = template;
    if (template.consequenceClass === null && cc !== null) {
      toStore = template.withConsequenceClass(cc);
    }

    this._macros.set(toStore.macroId, toStore);
  }

  /** Look up a registered macro by ID. */
  lookup(macroId: string): MacroTemplate | null {
    return this._macros.get(macroId) ?? null;
  }

  /**
   * Format a slot value to match Python's `str(value)` output exactly.
   *
   * Cross-SDK parity is the contract. JavaScript collapses 1013.0 to "1013"
   * and bool true to lowercase "true"; Python's `str()` preserves "1013.0"
   * (when the value was authored as a float) and emits "True"/"False".
   * The slot type carried on `SlotDefinition` is the canonical signal we
   * use to disambiguate, since JS has no float/int type distinction.
   *
   * Mirrors the implicit `str()` calls in Python's expand/encode_compact
   * paths (protocol.py lines 2978, 2996).
   */
  private _formatSlotValue(slotType: string, value: string | number | boolean): string {
    if (slotType === "float" && typeof value === "number" && Number.isInteger(value)) {
      return `${value}.0`;
    }
    if (slotType === "bool" && typeof value === "boolean") {
      return value ? "True" : "False";
    }
    return String(value);
  }

  /**
   * Expand a macro with slot values.
   *
   * Returns the fully expanded SAL chain with all placeholders substituted.
   * This is the "slot-fill" operation the patent describes.
   */
  expand(macroId: string, slotValues: Record<string, string | number | boolean>): string {
    const template = this._macros.get(macroId);
    if (template === undefined) {
      throw new Error(`Macro not found: ${macroId}`);
    }

    // Verify all required slots are provided
    const required = new Set(template.slots.map((s) => s.name));
    const provided = new Set(Object.keys(slotValues));
    const missing = [...required].filter((s) => !provided.has(s));
    if (missing.length > 0) {
      throw new Error(
        `Macro ${macroId}: missing slot values: ${JSON.stringify(missing)}`,
      );
    }

    const slotTypeByName = new Map(template.slots.map((s) => [s.name, s.slotType]));

    // Substitute placeholders
    let result = template.chainTemplate;
    for (const [name, value] of Object.entries(slotValues)) {
      const slotType = slotTypeByName.get(name) ?? "string";
      const formatted = this._formatSlotValue(slotType, value);
      // Use split/join to avoid regex-escaping each name
      result = result.split(`{${name}}`).join(formatted);
    }
    return result;
  }

  /**
   * Encode a macro invocation in compact wire format.
   *
   * Compact format: A:MACRO[macro_id]:slot1[val1]:slot2[val2]...
   * Used when both nodes share the macro definition.
   */
  encodeCompact(
    macroId: string,
    slotValues: Record<string, string | number | boolean>,
  ): string {
    const template = this._macros.get(macroId);
    if (template === undefined) {
      throw new Error(`Macro not found: ${macroId}`);
    }

    const parts: string[] = [`A:MACRO[${macroId}]`];
    for (const slotDef of template.slots) {
      if (slotDef.name in slotValues) {
        const formatted = this._formatSlotValue(slotDef.slotType, slotValues[slotDef.name]);
        parts.push(`:${slotDef.name}[${formatted}]`);
      }
    }

    let result = parts.join("");

    // Append inherited consequence class if present
    if (template.consequenceClass) {
      result += template.consequenceClass;
    }

    return result;
  }

  /**
   * Encode a macro invocation in expanded wire format.
   *
   * Expanded format: the full chain with values substituted.
   * Used when the receiving node doesn't have the macro definition.
   */
  encodeExpanded(
    macroId: string,
    slotValues: Record<string, string | number | boolean>,
  ): string {
    return this.expand(macroId, slotValues);
  }

  /**
   * Encode compact form with expansion annotation.
   *
   * The _EXP slot carries the fully expanded chain for monitoring.
   * Non-authoritative: receiver always expands from local ASD.
   * Included at unconstrained bandwidth, omitted at constrained.
   */
  encodeWithAnnotation(
    macroId: string,
    slotValues: Record<string, string | number | boolean>,
  ): string {
    const compact = this.encodeCompact(macroId, slotValues);
    const expanded = this.expand(macroId, slotValues);
    // Insert _EXP before any trailing consequence class
    const lastChar = compact[compact.length - 1];
    if (lastChar === "\u21BA" || lastChar === "\u26A0" || lastChar === "\u2298") {
      const cc = lastChar;
      const base = compact.slice(0, -1);
      return `${base}:_EXP[${expanded}]${cc}`;
    }
    return `${compact}:_EXP[${expanded}]`;
  }

  /**
   * Get the inherited consequence class for a macro.
   *
   * Scans the chain template for R namespace instructions and returns
   * the highest severity consequence class found.
   * IRREVERSIBLE > HAZARDOUS > REVERSIBLE > null
   */
  inheritedConsequenceClass(macroId: string): string | null {
    const template = this._macros.get(macroId);
    if (template === undefined) return null;
    return template.consequenceClass;
  }

  /** Compute the highest consequence class from a chain's R frames. */
  private _computeInheritedCc(cleanChain: string): string | null {
    let maxSeverity = 0;
    const parts = cleanChain.split(FRAME_SPLIT_RE);
    for (const rawPart of parts) {
      const part = rawPart.trim();
      if (!part || OPERATOR_TOKENS.has(part)) continue;
      const m = FRAME_NS_OP_RE.exec(part);
      if (m && m[1] === "R") {
        for (const [glyph, severity] of Object.entries(CC_SEVERITY)) {
          if (part.includes(glyph)) {
            if (severity > maxSeverity) maxSeverity = severity;
          }
        }
      }
    }
    return CC_BY_SEVERITY[maxSeverity] ?? null;
  }

  /** List all registered macros. */
  listMacros(): MacroTemplate[] {
    return [...this._macros.values()];
  }

  /**
   * Load macro definitions from a JSON corpus object.
   *
   * Returns the count of macros successfully loaded.
   * The corpus shape mirrors the Python loader: { macros: [...] }.
   */
  loadCorpus(corpus: MacroCorpus): number {
    let count = 0;
    for (const entry of corpus.macros ?? []) {
      const slots: SlotDefinition[] = (entry.slots ?? []).map(
        (s) => new SlotDefinition(s.name, s.slot_type ?? "string", s.namespace ?? null),
      );
      const template = new MacroTemplate(
        entry.macro_id,
        entry.chain_template,
        slots,
        entry.description ?? "",
        null,
        entry.triggers ?? [],
      );
      this.register(template);
      count += 1;
    }
    return count;
  }
}
