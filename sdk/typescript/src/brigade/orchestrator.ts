/** Orchestrator — head chef. Faithful TS port. */
import {
  BRIDGE_ALLOWED_NAMESPACES, BRIDGE_FORBIDDEN_FRAMES,
  ACTUATOR_OBJECT_NOUNS, MODIFIER_MARKERS_PATTERN,
  parse,
} from "./parser.js";
import type { FrameProposal, ParsedRequest } from "./request.js";
import { assembleFrame, makeProposal } from "./request.js";
import { defaultRegistry, type BrigadeRegistry } from "./stations/index.js";
import { validateComposition as sdkValidate } from "../validate.js";

export interface ComposeResult {
  sal: string | null;
  mode: "sal" | "bridge" | "passthrough" | "refused";
  hint?: string | null;
  residue?: string | null;
  reason_code?: string | null;
}

const PRONOUN_OBJECTS = new Set(["that", "it", "this", "them", "these", "those", "everything"]);
const ACTION_VERBS_NEEDING_VALID_OBJECT = new Set([
  "stop", "halt", "cease", "block", "close", "lock", "open", "unlock",
  "start", "kill", "shutdown", "shut", "reboot", "restart",
]);
const ACTION_NAMESPACES = new Set(["R", "K", "M", "C", "S"]);

const WRAPPER_FRAMES = new Set(["L:REPORT", "L:SEND", "L:LOG", "A:SHOW", "A:BROADCAST", "Q:RPRT"]);

const SCHEDULABLE_OPCODES = new Set([
  "PING", "STOP", "BK", "CFG", "RSTRT", "ENC", "SIGN",
  "ALERT", "NOTIFY", "PUSH", "FETCH", "STORE", "BACKUP",
  "Q", "MOV", "CAM", "MIC", "TORCH", "HAPTIC", "REPORT",
  "AUDIT", "LOG", "VFY", "ID",
]);

const STOPWORDS_RESIDUE = new Set([
  "the", "a", "an", "to", "of", "for", "from", "with",
  "and", "or", "is", "are", "be", "been", "this", "that",
  "please", "could", "you", "i", "me", "my",
]);

function utf8Bytes(s: string): number {
  return new TextEncoder().encode(s).length;
}

function validateOk(sal: string, nl: string): boolean {
  try {
    const r = sdkValidate(sal);
    // sdkValidate returns object with .valid or similar; accept if no errors
    if (typeof r === "object" && r !== null) {
      if ("valid" in r) return Boolean((r as { valid: boolean }).valid);
      if ("ok" in r) return Boolean((r as { ok: boolean }).ok);
      if ("issues" in r) {
        const issues = (r as { issues?: Array<{ severity?: string }> }).issues || [];
        return !issues.some((i) => i.severity === "error");
      }
    }
    return true;
  } catch {
    return false;
  }
}

export class Orchestrator {
  registry: BrigadeRegistry;

  constructor(registry?: BrigadeRegistry) {
    this.registry = registry ?? defaultRegistry();
  }

  compose(nl: string): string | null {
    const result = this.composeWithHint(nl);
    return result.sal;
  }

  composeWithHint(nl: string): ComposeResult {
    const req = parse(nl);
    return this._composeRequestWithHint(req, nl);
  }

  private _composeRequestWithHint(req: ParsedRequest, raw: string): ComposeResult {
    if (utf8Bytes(raw) < 5) {
      return { sal: null, mode: "refused", reason_code: "INPUT_TOO_SHORT",
        hint: `Input too short (${utf8Bytes(raw)}B); minimum 5B for any compose attempt.` };
    }
    if (req.is_negated) {
      return { sal: null, mode: "refused", reason_code: "NEGATION",
        hint: "Input contains negation marker. Refused per safety doctrine — emitting affirmative SAL would fire the wrong action." };
    }
    if (req.has_glyph_injection) {
      return { sal: null, mode: "refused", reason_code: "UNSAFE_INPUT",
        hint: "Input contains SAL-like syntax, code-injection patterns, email addresses, or known verb idioms. Refused per safety doctrine." };
    }
    if (req.verb_lemma && req.direct_object) {
      const dobjFirst = req.direct_object.toLowerCase().trim().split(/\s+/)[0];
      if (PRONOUN_OBJECTS.has(dobjFirst) && req.targets.length === 0) {
        return { sal: null, mode: "refused", reason_code: "UNRESOLVED_PRONOUN",
          hint: `Verb '${req.verb_lemma}' followed by pronoun '${dobjFirst}' with no antecedent.` };
      }
    }
    if (req.verb_lemma && ACTION_VERBS_NEEDING_VALID_OBJECT.has(req.verb_lemma) && req.direct_object) {
      const objFirst = req.direct_object.toLowerCase().trim().split(/\s+/)[0];
      if (!ACTUATOR_OBJECT_NOUNS.has(objFirst)
        && !req.targets.some((t) => t.source === "entity")) {
        return { sal: null, mode: "refused", reason_code: "NON_ACTUATOR_OBJECT",
          hint: `Verb '${req.verb_lemma}' applied to '${objFirst}' — not a known actuator.` };
      }
    }

    if (req.chain_segments.length > 0) {
      const sal = this._composeChain(req, raw);
      if (sal) return { sal, mode: "sal" };
      return { sal: null, mode: "passthrough", reason_code: "CHAIN_INCOMPLETE",
        hint: "Input has chain markers but at least one segment couldn't be composed." };
    }

    const sal = this._composeSingleFrame(req, raw);
    if (sal) return { sal, mode: "sal" };

    const proposalsByNs = this.registry.proposeAll(req);
    const bridge = this._tryBridgeMode(req, proposalsByNs, raw);
    if (bridge) {
      if (bridge.includes("::")) {
        const [salPart, residue] = bridge.split("::");
        return { sal: salPart, mode: "bridge", residue,
          reason_code: "PARTIAL_COMPOSE",
          hint: `Composed primary intent as SAL; residue '${residue.trim()}' carried as NL context.` };
      }
      return { sal: bridge, mode: "sal" };
    }

    if (req.namespace_hints.length === 0 && req.targets.length === 0 && req.slot_values.length === 0) {
      return { sal: null, mode: "passthrough", reason_code: "NO_PROTOCOL_CONTENT",
        hint: "Input doesn't contain protocol-recognizable content." };
    }
    const signals: string[] = [];
    if (req.verb_lemma) signals.push(`verb='${req.verb_lemma}'`);
    if (req.targets.length > 0) signals.push(`targets=${req.targets.map((t) => t.id)}`);
    if (req.namespace_hints.length > 0) signals.push(`namespaces=${req.namespace_hints}`);
    return { sal: null, mode: "passthrough", reason_code: "NO_OPCODE_MATCH",
      hint: `Parsed signals (${signals.join(", ")}) but no station produced a valid frame.` };
  }

  private _composeChain(req: ParsedRequest, raw: string): string | null {
    const subSals: string[] = [];
    for (const seg of req.chain_segments) {
      let sub = this._composeRequestNoHint(seg, raw);
      if (!sub) sub = this._composeRequestNoHint(seg, seg.raw);
      if (!sub) return null;
      subSals.push(sub);
    }
    if (subSals.length < 2) return null;
    const joined = subSals.join(req.chain_operator || "\u2227");
    if (validateOk(joined, raw)) return joined;
    return null;
  }

  private _composeRequestNoHint(req: ParsedRequest, raw: string): string | null {
    const r = this._composeRequestWithHint(req, raw);
    return r.sal;
  }

  private _composeSingleFrame(req: ParsedRequest, raw: string): string | null {
    const proposalsByNs = this.registry.proposeAll(req);
    if (Object.keys(proposalsByNs).length === 0) return null;

    // Rule 1: emergency override
    for (const p of proposalsByNs["R"] || []) {
      if (p.opcode === "ESTOP") {
        const sal = assembleFrame(p);
        if (validateOk(sal, raw)) return sal;
      }
    }

    if (req.conditions.length > 0) {
      const sal = this._buildConditionalChain(req, proposalsByNs, raw);
      if (sal) return sal;
    }
    if (req.schedule && req.verb_lemma) {
      const sal = this._buildScheduledChain(req, proposalsByNs, raw);
      if (sal) return sal;
    }

    let sal = this._buildSingleBest(req, proposalsByNs, raw);
    if (sal) {
      if (req.authorization_required) {
        const m = sal.match(/^([A-Z\u03a9]):/);
        const primaryNs = m ? m[1] : null;
        if (primaryNs && ACTION_NAMESPACES.has(primaryNs)) {
          sal = `I:\u00a7\u2192${sal}`;
        } else {
          return null;
        }
      }
      if (validateOk(sal, raw)) return sal;
    }
    return null;
  }

  private _pickNamespacePriority(req: ParsedRequest, proposalsByNs: Record<string, FrameProposal[]>): string[] {
    const order: string[] = [];
    if (req.domain_hint) {
      const DOMAIN_PRIORITY: Record<string, string[]> = {
        medical: ["H", "I", "U", "L"],
        uav: ["V", "R", "G", "I"],
        weather: ["W", "E"],
        device_control: ["R", "C"],
        meshtastic: ["A", "N", "G", "O"],
        crypto: ["S", "I"],
        config: ["N", "T"],
        vehicle: ["V", "G"],
        sensor: ["E"],
      };
      for (const ns of DOMAIN_PRIORITY[req.domain_hint] || []) order.push(ns);
    }
    for (const ns of req.namespace_hints) if (!order.includes(ns)) order.push(ns);
    for (const ns of Object.keys(proposalsByNs)) if (!order.includes(ns)) order.push(ns);
    return order;
  }

  private _buildSingleBest(req: ParsedRequest, proposalsByNs: Record<string, FrameProposal[]>, raw: string): string | null {
    const order = this._pickNamespacePriority(req, proposalsByNs);

    const allProps: FrameProposal[] = [];
    for (const ns of Object.keys(proposalsByNs)) allProps.push(...proposalsByNs[ns]);

    // Phase 1: high-confidence (>= 2.0) across all namespaces
    const highConf = allProps.filter((p) => p.confidence >= 2.0);
    highConf.sort((a, b) => (b.confidence - a.confidence) || (utf8Bytes(assembleFrame(a)) - utf8Bytes(assembleFrame(b))));
    for (const p of highConf) {
      for (const variant of this._frameVariants(p)) {
        if (validateOk(variant, raw)) return variant;
      }
    }

    // Phase 2: namespace-priority
    for (const ns of order) {
      const props = proposalsByNs[ns] || [];
      const normal = props.filter((p) => p.confidence < 2.0);
      if (normal.length === 0) continue;
      normal.sort((a, b) => (b.confidence - a.confidence) || (utf8Bytes(assembleFrame(a)) - utf8Bytes(assembleFrame(b))));
      for (const p of normal) {
        for (const variant of this._frameVariants(p)) {
          if (validateOk(variant, raw)) return variant;
        }
      }
    }

    // Phase 3: 2-frame conjunctive
    if (allProps.length >= 2) {
      for (let i = 0; i < allProps.length; i++) {
        for (let j = i + 1; j < allProps.length; j++) {
          const p1 = allProps[i]; const p2 = allProps[j];
          if (p1.namespace === p2.namespace && p1.opcode === p2.opcode) continue;
          const sal = assembleFrame(p1) + "\u2227" + assembleFrame(p2);
          if (validateOk(sal, raw)) return sal;
        }
      }
    }
    return null;
  }

  private _frameVariants(p: FrameProposal): string[] {
    const variants: string[] = [assembleFrame(p)];
    if (p.target) {
      variants.push(assembleFrame({ ...p, target: null }));
    }
    if (p.is_query) {
      variants.push(assembleFrame({ ...p, is_query: false }));
    }
    if (p.target && p.is_query) {
      variants.push(assembleFrame({ ...p, target: null, is_query: false, consequence_class: p.consequence_class }));
    }
    return [...new Set(variants)];
  }

  private _buildConditionalChain(req: ParsedRequest, proposalsByNs: Record<string, FrameProposal[]>, raw: string): string | null {
    let sensing: FrameProposal | null = null;
    for (const ns of ["H", "E", "W", "V"]) {
      for (const p of proposalsByNs[ns] || []) {
        if (["HR", "BP", "TH", "HU", "PU", "WIND", "SPO2", "TEMP", "HDG", "POS"].includes(p.opcode)) {
          sensing = p; break;
        }
      }
      if (sensing) break;
    }
    if (!sensing) return null;

    let alert: FrameProposal | null = null;
    if (sensing.namespace === "H") {
      for (const p of proposalsByNs["H"] || []) {
        if (["ALERT", "CASREP"].includes(p.opcode)) { alert = p; break; }
      }
    }
    if (!alert && sensing.namespace === "W") {
      for (const p of proposalsByNs["W"] || []) {
        if (p.opcode === "ALERT") { alert = p; break; }
      }
    }
    if (!alert) {
      for (const ns of ["U", "L"]) {
        for (const p of proposalsByNs[ns] || []) {
          if (["NOTIFY", "ALERT"].includes(p.opcode)) { alert = p; break; }
        }
        if (alert) break;
      }
    }
    if (!alert) return null;

    const cond = req.conditions[0];
    const sensingSal = assembleFrame(sensing) + cond.operator + cond.value;
    const alertSal = assembleFrame(alert);
    const sal = sensingSal + "\u2192" + alertSal;
    if (validateOk(sal, raw)) return sal;
    return null;
  }

  private _buildScheduledChain(req: ParsedRequest, proposalsByNs: Record<string, FrameProposal[]>, raw: string): string | null {
    let action: FrameProposal | null = null;
    for (const ns of ["A", "R", "N", "C", "S", "L", "U", "H", "W", "I"]) {
      for (const p of proposalsByNs[ns] || []) {
        if (SCHEDULABLE_OPCODES.has(p.opcode)) { action = p; break; }
      }
      if (action) break;
    }
    if (!action) return null;
    const schedSal = `T:SCHED[${req.schedule}]`;
    for (const op of ["\u2192", ";"]) {
      const sal = schedSal + op + assembleFrame(action);
      if (validateOk(sal, raw)) return sal;
    }
    return null;
  }

  private _tryBridgeMode(req: ParsedRequest, proposalsByNs: Record<string, FrameProposal[]>, raw: string): string | null {
    let bridgeCandidate: FrameProposal | null = null;
    for (const ns of Object.keys(proposalsByNs)) {
      if (!BRIDGE_ALLOWED_NAMESPACES.has(ns)) continue;
      for (const p of proposalsByNs[ns]) {
        if (BRIDGE_FORBIDDEN_FRAMES.has(`${p.namespace}:${p.opcode}`)) continue;
        if (["ALERT", "CASREP", "ESTOP", "STOP", "MOV", "RTH", "CFG", "BK",
             "KILL", "RSTRT", "ENC", "DEC", "SIGN", "KEYGEN", "PUSH", "DEL", "FORM",
             "CAM", "MIC", "SPKR", "TORCH", "HAPTIC", "VIBE", "BT", "WIFI",
             "DISP", "SCRN"].includes(p.opcode)) continue;
        if (!bridgeCandidate || p.confidence > bridgeCandidate.confidence) {
          bridgeCandidate = p;
        }
      }
    }
    if (!bridgeCandidate) return null;
    const salPart = assembleFrame(bridgeCandidate);
    if (!validateOk(salPart, raw)) return null;

    const residue = this._computeResidue(req, bridgeCandidate);
    if (!residue.trim()) return salPart;
    if (MODIFIER_MARKERS_PATTERN.test(residue)) return null;
    const composite = `${salPart}::${residue}`;
    if (utf8Bytes(composite) >= utf8Bytes(raw)) return null;
    return composite;
  }

  private _computeResidue(req: ParsedRequest, p: FrameProposal): string {
    const consumed = new Set<string>();
    if (req.verb) consumed.add(req.verb.toLowerCase());
    if (req.verb_lemma && req.verb_lemma !== req.verb) consumed.add(req.verb_lemma.toLowerCase());
    if (req.direct_object) {
      for (const w of req.direct_object.toLowerCase().split(/\s+/)) consumed.add(w);
    }
    for (const t of req.targets) consumed.add(t.id.toLowerCase());
    for (const sv of req.slot_values) consumed.add(sv.value.toLowerCase());
    const tokens: string[] = [];
    for (const tok of req.raw.split(/\s+/)) {
      const c = tok.toLowerCase().replace(/[,.\!?;:'"]/g, "");
      if (consumed.has(c) || STOPWORDS_RESIDUE.has(c)) continue;
      tokens.push(tok);
    }
    return tokens.join(" ");
  }
}
