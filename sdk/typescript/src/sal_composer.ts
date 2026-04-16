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

// ── Types ────────────────────────────────────────────────────────────────────

export interface ComposedIntent {
  actions: string[];
  conditions: string[];
  targets: string[];
  parameters: Record<string, string>;
  raw: string;
}

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
};

// ── SALComposer ──────────────────────────────────────────────────────────────

export class SALComposer {
  private _asd: AdaptiveSharedDictionary;
  private _keywordIndex: Map<string, [string, string][]> = new Map();
  private _phraseIndex: Map<string, [string, string]> = new Map();
  private _phrasesByLength: string[] = [];

  constructor(asd?: AdaptiveSharedDictionary) {
    this._asd = asd ?? new AdaptiveSharedDictionary();
    this._buildKeywordIndex();
    this._buildPhraseIndex();
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

    // Phase 2: Single-word keyword fallback
    for (let i = 0; i < words.length; i++) {
      if (consumed.has(i)) continue;
      const word = words[i];
      if (word.length > 2 && !SKIP_WORDS.has(word)) {
        if (this.lookupByKeyword(word).length > 0) {
          actions.push(word);
        }
      }
    }

    return { actions, conditions, targets, parameters, raw };
  }

  compose(nlText: string, intent?: ComposedIntent): string | null {
    if (!intent) intent = this.extractIntentKeywords(nlText);

    // BAEL byte pre-check
    if (new TextEncoder().encode(nlText).length < 6) return null;

    // ASD lookup
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
        const matches = qualifiers.filter(w => nlLower.includes(w)).length;
        return matches >= 2;
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
