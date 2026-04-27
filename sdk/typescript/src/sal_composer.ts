/**
 * SALComposer — Deterministic NL-to-SAL composition pipeline.
 *
 * The composer NEVER generates SAL text via inference. It decomposes
 * NL into intent, looks up opcodes in the ASD, assembles using grammar
 * rules, and validates the result.
 *
 * Patent pending | License: Apache 2.0
 */

import { ASD_BASIS } from "./glyphs.js";
import { AdaptiveSharedDictionary } from "./asd.js";
import { validateComposition } from "./validate.js";
import type { MacroRegistry } from "./macro.js";
import { Orchestrator as BrigadeOrchestrator } from "./brigade/index.js";

// ── Types ────────────────────────────────────────────────────────────────────

export interface ComposedIntent {
  actions: string[];
  conditions: string[];
  targets: string[];
  parameters: Record<string, string>;
  raw: string;
}

// ── Chain separators ────────────────────────────────────────────────────────
//
// Each separator pattern in NL maps to the SAL operator that joins composed
// segments. Order matters: longer/more-specific patterns first. Mirrors the
// Python `_CHAIN_SEPARATORS` constant in protocol.py (lines 2495-2505).

const CHAIN_SEPARATORS: ReadonlyArray<readonly [RegExp, string]> = [
  [/,\s+then\s+/i, ";"],
  [/,\s+and\s+then\s+/i, ";"],
  [/\s+then\s+/i, ";"],
  [/\s+next\s+/i, ";"],
  [/,\s+and\s+/i, "\u2227"],
];

// ── Constants ────────────────────────────────────────────────────────────────

const CONDITION_MAP: Record<string, string> = {
  above: ">", over: ">", exceeds: ">", "greater than": ">",
  "more than": ">", "higher than": ">",
  below: "<", under: "<", "less than": "<", "lower than": "<",
  equals: "=", "equal to": "=", is: "=",
  not: "\u00ac",
};

const SENSING_NS = new Set(["E", "H", "W", "G", "X", "S", "D", "Z"]);
const ACTION_NS = new Set(["U", "M", "R", "B", "J", "A", "K"]);

const SKIP_WORDS = new Set([
  "the", "and", "for", "from", "with", "that", "this", "when",
  "then", "turn", "get", "set", "put", "make", "give", "take",
  "show", "tell", "let", "use", "try", "see", "ask",
  "how", "what", "where", "who", "why", "can", "will", "has",
  "have", "does", "did", "are", "was", "been", "being", "many",
  "much", "some", "any", "all", "each", "every", "other",
  "about", "into", "over", "after", "before", "between",
  "but", "only", "just", "also", "too", "very", "really",
  "it", "its", "it's", "me", "my", "your", "our", "their",
  "him", "her", "his", "them", "going", "goes", "went",
  "you", "need", "want", "know", "like", "think", "would",
  "post", "photo", "caption", "book", "order", "send",
  // Generic referent nouns — objects of actions, not actions themselves
  "payload", "data", "message", "request", "response", "content",
  "file", "item", "value", "result", "thing",
]);

const TARGET_FALSE_POSITIVES = new Set([
  "THE", "A", "AN", "THIS", "THAT", "MY", "YOUR",
  "IT", "THEM", "HIM", "HER", "ME", "EVERYTHING",
  "TEMPERATURE", "IS", "SOME", "ALL",
]);

// ── Curated Triggers ─────────────────────────────────────────────────────────

const CURATED_TRIGGERS: Record<string, [string, string]> = {
  "flow authorization": ["F", "AV"],
  "authorization proceed": ["F", "AV"],
  "emergency route": ["M", "RTE"],
  "municipal route": ["M", "RTE"],
  "incident route": ["M", "RTE"],
  "network status": ["N", "STS"],
  "node status": ["N", "STS"],
  "vessel heading": ["V", "HDG"],
  "ship heading": ["V", "HDG"],
  "maritime heading": ["V", "HDG"],
  "restart process": ["C", "RSTRT"],
  "restart service": ["C", "RSTRT"],
  "data query": ["D", "Q"],
  "query data": ["D", "Q"],
  "audit query": ["L", "QUERY"],
  "query audit": ["L", "QUERY"],
  "robot heading": ["R", "HDNG"],
  "vehicle heading": ["R", "HDNG"],
  "robot status": ["R", "STAT"],
  "device status": ["R", "STAT"],
  "robot waypoint": ["R", "WPT"],
  "attest payload": ["S", "ATST"],
  "attestation": ["S", "ATST"],
  "page out memory": ["Y", "PAGEOUT"],
  "store to memory": ["Y", "STORE"],
  "save to memory": ["Y", "STORE"],
  "generate key": ["S", "KEYGEN"],
  "generate keys": ["S", "KEYGEN"],
  "key pair": ["S", "KEYGEN"],
  "create keypair": ["S", "KEYGEN"],
  "sign payload": ["S", "SIGN"],
  "digital signature": ["S", "SIGN"],
  "push to node": ["D", "PUSH"],
  "send to node": ["D", "PUSH"],
  "transfer task": ["J", "HANDOFF"],
  "hand off": ["J", "HANDOFF"],
  "task handoff": ["J", "HANDOFF"],
  "verify identity": ["I", "ID"],
  "identity check": ["I", "ID"],
  "run inference": ["Z", "INF"],
  "invoke model": ["Z", "INF"],
  "building fire": ["B", "ALRM"],
  "fire alarm": ["B", "ALRM"],
  // Operational abbreviations (mesh radio shorthand)
  "temp report": ["E", "TH"],
  "temp check": ["E", "TH"],
  "battery level": ["X", "STORE"],
  "battery status": ["X", "STORE"],
  "battery report": ["X", "STORE"],
  "signal strength": ["O", "LINK"],
  "link quality": ["O", "LINK"],
  "gps fix": ["E", "GPS"],
  "position report": ["G", "POS"],
  "node info": ["N", "STS"],
  "mesh status": ["O", "MESH"],
  "air quality": ["E", "EQ"],
  "wind speed": ["W", "WIND"],
  "heart rate check": ["H", "HR"],
  "blood pressure check": ["H", "BP"],
  "vitals check": ["H", "VITALS"],
  "oxygen level": ["H", "SPO2"],
};

// ── SALComposer ──────────────────────────────────────────────────────────────

export class SALComposer {
  private _asd: AdaptiveSharedDictionary;
  private _macroRegistry: MacroRegistry | null;
  private _keywordIndex: Map<string, [string, string][]> = new Map();
  private _phraseIndex: Map<string, [string, string]> = new Map();
  private _phrasesByLength: string[] = [];

  constructor(asd?: AdaptiveSharedDictionary, macroRegistry?: MacroRegistry | null) {
    this._asd = asd ?? new AdaptiveSharedDictionary();
    this._macroRegistry = macroRegistry ?? null;
    this._buildKeywordIndex();
    this._buildPhraseIndex();
  }

  /** Optional accessor for the registered macro registry (parity with Python self.macro_registry). */
  get macroRegistry(): MacroRegistry | null {
    return this._macroRegistry;
  }

  /** Attach or replace the macro registry after construction. */
  setMacroRegistry(registry: MacroRegistry | null): void {
    this._macroRegistry = registry;
  }

  private _buildKeywordIndex(): void {
    for (const [ns, ops] of Object.entries(ASD_BASIS)) {
      for (const [op, defn] of Object.entries(ops)) {
        const words = defn.toLowerCase().replace(/_/g, " ").split(/\s+/);
        for (const word of words) {
          if (word.length > 2) {
            if (!this._keywordIndex.has(word)) {
              this._keywordIndex.set(word, []);
            }
            this._keywordIndex.get(word)!.push([ns, op]);
          }
        }
      }
    }
  }

  private _buildPhraseIndex(): void {
    // Auto-generate from definitions
    for (const [ns, ops] of Object.entries(ASD_BASIS)) {
      for (const [op, defn] of Object.entries(ops)) {
        const phrase = defn.toLowerCase().replace(/_/g, " ");
        if (phrase.includes(" ")) {
          this._phraseIndex.set(phrase, [ns, op]);
        }
      }
    }
    // Curated triggers
    for (const [phrase, nsOp] of Object.entries(CURATED_TRIGGERS)) {
      this._phraseIndex.set(phrase, nsOp);
    }
    // Sort longest-first
    this._phrasesByLength = [...this._phraseIndex.keys()].sort(
      (a, b) => b.length - a.length
    );
  }

  lookupByKeyword(keyword: string): [string, string, string][] {
    const kw = keyword.toLowerCase().trim();
    const results: [string, string, string][] = [];
    const seen = new Set<string>();

    // Direct opcode match
    for (const [ns, ops] of Object.entries(ASD_BASIS)) {
      for (const [op, defn] of Object.entries(ops)) {
        if (kw === op.toLowerCase()) {
          const key = `${ns}:${op}`;
          if (!seen.has(key)) { results.push([ns, op, defn]); seen.add(key); }
        }
      }
    }
    // Keyword index match
    for (const [ns, op] of this._keywordIndex.get(kw) ?? []) {
      const key = `${ns}:${op}`;
      if (!seen.has(key)) {
        const defn = this._asd.lookup(ns, op) ?? "";
        results.push([ns, op, defn]);
        seen.add(key);
      }
    }
    // Fuzzy substring
    if (results.length === 0) {
      for (const [ns, ops] of Object.entries(ASD_BASIS)) {
        for (const [op, defn] of Object.entries(ops)) {
          if (defn.toLowerCase().includes(kw)) {
            results.push([ns, op, defn]);
          }
        }
      }
    }
    return results;
  }

  extractIntentKeywords(nlText: string): ComposedIntent {
    const raw = nlText.trim();
    const rawLower = raw.toLowerCase();
    const words = rawLower.replace(/[.,!?;:'"()\[\]{}]/g, "").split(/\s+/).filter(Boolean);
    const actions: string[] = [];
    const conditions: string[] = [];
    const targets: string[] = [];
    const parameters: Record<string, string> = {};

    // Numeric conditions
    const condRe = /(above|over|below|under|exceeds?|greater than|less than|higher than|lower than)\s+(\d+\.?\d*)/gi;
    let m: RegExpExecArray | null;
    while ((m = condRe.exec(raw)) !== null) {
      const salOp = CONDITION_MAP[m[1].toLowerCase()] ?? ">";
      conditions.push(`${salOp}${m[2]}`);
    }

    // Parametric values
    const paramRe = /(?:temperature|top.?p|top.?k|max.?tokens?)\s+(\d+\.?\d*)/gi;
    while ((m = paramRe.exec(raw)) !== null) {
      parameters[m[0].split(/\s/)[0].toLowerCase()] = m[1];
    }

    // ICD codes
    const icdRe = /(?:code|icd|diagnosis|icd-10)\s+([A-Z]\d{2}\.?\d*)/gi;
    while ((m = icdRe.exec(raw)) !== null) {
      parameters["icd"] = m[1].replace(".", "");
    }

    // Targets
    const targetRe = /(?<!\w)(?:on|at|to|@)\s+(\w+)/gi;
    while ((m = targetRe.exec(raw)) !== null) {
      targets.push(m[1].toUpperCase());
    }

    // Phase 1: Phrase matching (longest first)
    const matchedSpans: [number, number][] = [];
    for (const phrase of this._phrasesByLength) {
      const re = new RegExp(`(?<!\\w)${phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?!\\w)`, "i");
      const pm = re.exec(rawLower);
      if (pm) {
        const idx = pm.index;
        const end = idx + pm[0].length;
        const overlaps = matchedSpans.some(([s, e]) => !(end <= s || idx >= e));
        if (!overlaps) {
          matchedSpans.push([idx, end]);
          actions.push(phrase);
        }
      }
    }

    // Build consumed word positions
    const consumed = new Set<number>();
    for (const [spanStart, spanEnd] of matchedSpans) {
      let pos = 0;
      for (let i = 0; i < words.length; i++) {
        const wIdx = rawLower.indexOf(words[i], pos);
        if (wIdx >= spanStart && wIdx + words[i].length <= spanEnd) {
          consumed.add(i);
        }
        pos = wIdx + words[i].length;
      }
    }

    // Build set of all 2-char opcode names for short-word matching
    const shortOpcodes = new Set<string>();
    for (const [, ops] of Object.entries(ASD_BASIS)) {
      for (const op of Object.keys(ops)) {
        if (op.length <= 2) shortOpcodes.add(op.toLowerCase());
      }
    }

    // Phase 2: Single-word keyword fallback
    for (let i = 0; i < words.length; i++) {
      if (consumed.has(i)) continue;
      const word = words[i];
      // Allow short words (2 chars) if they're exact opcode names
      if (word.length === 2 && !shortOpcodes.has(word)) continue;
      if (word.length < 2) continue;
      if (SKIP_WORDS.has(word)) continue;
      if (word.length > 2 || shortOpcodes.has(word)) {
        if (this.lookupByKeyword(word).length > 0) {
          actions.push(word);
        }
      }
    }

    return { actions, conditions, targets, parameters, raw };
  }

  /**
   * Compose valid SAL from natural language.
   *
   * First tries chain-split: if the NL contains sequential separators
   * ("then", "next", ", and"), split into segments and compose each.
   * This produces proper ; (SEQUENCE) or ∧ (AND) chains instead of
   * flat keyword-matched SAL.
   *
   * Falls back to single-segment composition if no chain detected.
   *
   * Mirrors Python `compose` at protocol.py lines 2553-2576.
   */
  compose(nlText: string, intent?: ComposedIntent): string | null {
    if (!intent) {
      // Step 1: Macro priority — pre-validated chain templates win over both
      // brigade and legacy paths. A macro encodes the intent of a whole
      // multi-opcode chain in a single A:MACRO[id] frame; we must not let a
      // station propose a partial single-frame match in its place. Mirrors
      // Python protocol.py compose() and Go composer.go.
      if (this.macroRegistry) {
        const nlLow = nlText.toLowerCase();
        for (const macro of this.macroRegistry.listMacros()) {
          for (const trigger of macro.triggers) {
            if (nlLow.includes(trigger.toLowerCase())) {
              return `A:MACRO[${macro.macroId}]`;
            }
          }
        }
      }

      // Step 2: Brigade composer (parser → IR → 26 stations → orchestrator).
      // Brigade returning null means "no station resolved confidently" — the
      // legacy keyword stacker may still find something, so fall through.
      try {
        if (!SALComposer._brigadeSingleton) {
          SALComposer._brigadeSingleton = new BrigadeOrchestrator();
        }
        const brigadeSal = SALComposer._brigadeSingleton.compose(nlText);
        if (brigadeSal !== null) return brigadeSal;
      } catch {
        // Any brigade error → fall through, never break compose.
      }

      // Step 3: Legacy chain-split (preserved for inputs the brigade returns
      // null for — e.g., novel chain shapes).
      const chainSal = this._tryChainSplit(nlText);
      if (chainSal !== null) {
        const result = validateComposition(chainSal, nlText);
        if (result.valid) return chainSal;
        // Chain validation failed → fall through to single-compose
      }
    }
    return this._composeImpl(nlText, intent);
  }

  private static _brigadeSingleton: BrigadeOrchestrator | null = null;

  /**
   * Single-segment composition entry. Used by chain-split for each
   * segment so the recursion stops at one level.
   */
  private _composeSingle(nlText: string): string | null {
    return this._composeImpl(nlText);
  }

  /**
   * Try to split NL into chain segments and compose each independently.
   *
   * Returns a composed SAL chain (using ; or ∧) or null if the NL
   * doesn't contain chain separators OR if any segment fails to compose.
   *
   * Mirrors Python `_try_chain_split` at protocol.py lines 2507-2546.
   */
  private _tryChainSplit(nlText: string): string | null {
    const nlLower = nlText.toLowerCase();
    if (nlLower.includes(" if ") || nlLower.startsWith("if ")) {
      return null; // conditional chains handled by existing logic
    }

    for (const [pattern, operator] of CHAIN_SEPARATORS) {
      const splitter = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g");
      const rawSegments = nlText.split(splitter);
      if (rawSegments.length < 2) continue;

      const segments = rawSegments
        .map((s) => s.trim().replace(/[.,;]+$/, ""))
        .filter((s) => s.length > 0);
      if (segments.length < 2) continue;

      const composedSegments: string[] = [];
      for (const seg of segments) {
        if (new TextEncoder().encode(seg).length < 4) return null;
        const segSal = this._composeSingle(seg);
        if (segSal === null) return null; // any segment fails → whole chain fails
        composedSegments.push(segSal);
      }
      if (composedSegments.length >= 2) {
        return composedSegments.join(operator);
      }
      return null;
    }

    return null;
  }

  /**
   * Core composition logic. Mirrors Python `_compose_impl` at protocol.py
   * lines 2578-2812. The macro priority check is the first step after the
   * BAEL byte pre-check (lines 2595-2602).
   */
  private _composeImpl(nlText: string, intent?: ComposedIntent): string | null {
    if (!intent) intent = this.extractIntentKeywords(nlText);

    // BAEL byte pre-check
    if (new TextEncoder().encode(nlText).length < 6) return null;

    // Step 1: Macro priority check (composition priority hierarchy)
    if (this._macroRegistry) {
      const rawLower = intent.raw.toLowerCase();
      for (const macro of this._macroRegistry.listMacros()) {
        for (const trigger of macro.triggers) {
          if (trigger && rawLower.includes(trigger.toLowerCase())) {
            return `A:MACRO[${macro.macroId}]`;
          }
        }
      }
    }

    // Step 2: ASD lookup
    let resolved: [string, string][] = [];
    let hasPhraseMatch = false;
    for (const action of intent.actions) {
      if (this._phraseIndex.has(action)) {
        const [ns, op] = this._phraseIndex.get(action)!;
        if (!resolved.some(([n, o]) => n === ns && o === op)) {
          resolved.push([ns, op]);
        }
        hasPhraseMatch = true;
        continue;
      }
      const matches = this.lookupByKeyword(action);
      if (matches.length > 0) {
        const [ns, op] = matches[0];
        if (!resolved.some(([n, o]) => n === ns && o === op)) {
          resolved.push([ns, op]);
        }
      }
    }

    // Parameter-driven injection
    if (intent.parameters["icd"] && !resolved.some(([n, o]) => n === "H" && o === "ICD")) {
      resolved.unshift(["H", "ICD"]);
    }
    if (intent.parameters["temperature"] && !resolved.some(([n, o]) => n === "Z" && o === "TEMP")) {
      resolved.push(["Z", "TEMP"]);
    }
    if (intent.parameters["top-p"] && !resolved.some(([n, o]) => n === "Z" && o === "TOPP")) {
      resolved.push(["Z", "TOPP"]);
    }

    if (resolved.length === 0) return null;

    // Confidence gate
    if (!hasPhraseMatch && intent.conditions.length === 0) {
      const isStrong = (ns: string, op: string): boolean => {
        const defn = ASD_BASIS[ns]?.[op] ?? "";
        const defnClean = defn.toLowerCase().replace(/_/g, " ");
        for (const action of intent.actions) {
          if (action.toUpperCase() === op) return true;
          if (action.toLowerCase() === defnClean && action.length >= 4) return true;
          // Action is a prefix of a definition word (e.g., "temp" starts "temperature")
          for (const dw of defnClean.split(/\s+/)) {
            if (action.length >= 4 && dw.startsWith(action.toLowerCase()) && dw.length >= action.length + 2) return true;
          }
          if (op.length >= 3 && action.toUpperCase().startsWith(op) && action.length >= op.length + 3) return true;
        }
        return false;
      };

      const defnMatchesContext = (ns: string, op: string): boolean => {
        const defn = ASD_BASIS[ns]?.[op] ?? "";
        const defnWords = defn.toLowerCase().replace(/_/g, " ").split(/\s+/);
        if (defnWords.length <= 1) return true;
        const nlLower = nlText.toLowerCase();
        const qualifiers = defnWords.filter(w => w.length > 3);
        let exactMatches = 0;
        let prefixMatches = 0;
        for (const qw of qualifiers) {
          if (nlLower.includes(qw)) {
            exactMatches++;
          } else {
            for (const nlWord of nlLower.split(/\s+/)) {
              if (nlWord.length >= 4 && qw.startsWith(nlWord)) {
                prefixMatches++;
                break;
              }
            }
          }
        }
        if (exactMatches >= 2) return true;
        if (exactMatches >= 1 && prefixMatches >= 1) return true;
        if (prefixMatches >= 1 && defnWords.length <= 2) return true;
        return false;
      };

      if (resolved.length === 1) {
        if (!isStrong(resolved[0][0], resolved[0][1])) return null;
        if (!defnMatchesContext(resolved[0][0], resolved[0][1])) return null;
      } else if (resolved.length === 2) {
        const strong = resolved.filter(([ns, op]) => isStrong(ns, op)).length;
        if (strong === 0) return null;
      } else if (resolved.length >= 3) {
        const strong = resolved.filter(([ns, op]) => isStrong(ns, op)).length;
        const nlWordCount = nlText.split(/\s+/).length;
        if (strong === 0 && nlWordCount < 8) return null;
      }
    }

    // OOV chain gap detection
    if (resolved.length > 0 && !hasPhraseMatch) {
      const segments = nlText.toLowerCase().split(/,\s+then\s+|,\s+and\s+then\s+|\bthen\b|,\s+/);
      if (segments.length >= 3) {
        let unresolved = 0;
        for (const seg of segments) {
          const s = seg.trim();
          if (!s || s.length < 5) continue;
          let segHasMatch = false;
          for (const [ns, op] of resolved) {
            const defn = ASD_BASIS[ns]?.[op] ?? "";
            const defnWords = defn.toLowerCase().replace(/_/g, " ").split(/\s+/);
            if (defnWords.some(w => w.length > 3 && s.includes(w))) {
              segHasMatch = true;
              break;
            }
          }
          if (!segHasMatch) unresolved++;
        }
        if (unresolved > 0) return null;
      }
    }

    // Sort sensing before action when conditions present
    if (intent.conditions.length > 0 && resolved.length > 1) {
      const sensing = resolved.filter(([ns]) => SENSING_NS.has(ns));
      const acting = resolved.filter(([ns]) => ACTION_NS.has(ns));
      const other = resolved.filter(([ns]) => !SENSING_NS.has(ns) && !ACTION_NS.has(ns));
      resolved = [...sensing, ...other, ...acting];
    }

    // Grammar assembly
    const frames: string[] = [];
    for (const [ns, op] of resolved) {
      let frame = `${ns}:${op}`;

      // Parametric values
      if (ns === "H" && op === "ICD" && intent.parameters["icd"]) {
        frame += `[${intent.parameters["icd"]}]`;
      } else if (ns === "Z" && op === "TEMP" && intent.parameters["temperature"]) {
        frame += `:${intent.parameters["temperature"]}`;
      } else if (ns === "Z" && op === "TOPP" && intent.parameters["top-p"]) {
        frame += `:${intent.parameters["top-p"]}`;
      }

      // Target
      const validTargets = intent.targets.filter(t => !TARGET_FALSE_POSITIVES.has(t));
      if (validTargets.length > 0) frame += `@${validTargets[0]}`;

      // R namespace consequence class
      if (ns === "R" && op !== "ESTOP") frame += "\u21ba";

      frames.push(frame);
    }

    // Attach conditions
    if (intent.conditions.length > 0 && frames.length > 0) {
      frames[0] += intent.conditions[0];
    }

    // Join
    let sal: string;
    if (frames.length === 1) {
      sal = frames[0];
    } else if (intent.conditions.length > 0) {
      sal = frames.join("\u2192");
    } else {
      sal = frames.join("\u2227");
    }

    // Validate
    const result = validateComposition(sal, nlText);
    if (result.valid) return sal;

    // Fallback: try without conditions
    if (intent.conditions.length > 0 && frames.length > 1) {
      const simple = resolved.map(([ns, op]) => `${ns}:${op}`).join("\u2227");
      const r2 = validateComposition(simple, nlText);
      if (r2.valid) return simple;
    }

    return null;
  }

  composeOrPassthrough(nlText: string, intent?: ComposedIntent): [string, boolean] {
    const sal = this.compose(nlText, intent);
    if (sal !== null) return [sal, true];
    return [nlText, false];
  }
}
