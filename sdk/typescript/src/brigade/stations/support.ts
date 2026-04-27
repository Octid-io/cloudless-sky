/** Support stations: C, T, I, S, K, B, U, L, M, D, J, F, O, P, Q, X, Y, Z. */
import type { FrameProposal, ParsedRequest, SlotValue } from "../request.js";
import { makeProposal } from "../request.js";
import type { Station } from "./base.js";
import { opcodeExists } from "../base_helpers.js";

function pickTarget(req: ParsedRequest): string | null {
  if (req.is_broadcast && req.targets.length === 0) return "*";
  for (const t of req.targets) if (t.source === "entity") return t.id;
  if (req.targets.length > 0) return req.targets[0].id;
  return null;
}

// C — Compute
export class CStation implements Station {
  namespace = "C";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    if (["kill", "shutdown", "shut", "terminate"].includes(req.verb_lemma ?? "")) {
      out.push(makeProposal({
        namespace: "C", opcode: "KILL", target: pickTarget(req),
        rationale: `verb '${req.verb_lemma}' -> C:KILL`,
      }));
    }
    if (["restart", "reboot"].includes(req.verb_lemma ?? "")) {
      out.push(makeProposal({
        namespace: "C", opcode: "RSTRT", target: pickTarget(req),
        rationale: `verb '${req.verb_lemma}' -> C:RSTRT`,
      }));
    }
    return out;
  }
}

// T — Time / Scheduling
export class TStation implements Station {
  namespace = "T";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (req.verb_lemma === "expire" || rawLow.includes("expire") || rawLow.includes("ttl")) {
      let slot: SlotValue[] = [];
      for (const sv of req.slot_values) {
        if (sv.value_type === "duration") {
          slot = [{ key: "", value: sv.value, value_type: "duration" }];
          break;
        }
      }
      out.push(makeProposal({
        namespace: "T", opcode: "EXP",
        slot_values: slot, rationale: "expire verb + duration",
      }));
    }
    for (const sv of req.slot_values) {
      if (sv.value_type === "duration" && rawLow.includes("every")) {
        out.push(makeProposal({
          namespace: "T", opcode: "SCHED",
          slot_values: [{ key: "", value: sv.value, value_type: "duration" }],
          rationale: "schedule with every-N pattern",
        }));
        break;
      }
    }
    if (rawLow.includes("maintenance window") || (rawLow.includes("window") && req.verb_lemma === "schedule")) {
      out.push(makeProposal({
        namespace: "T", opcode: "WIN",
        rationale: "maintenance window",
      }));
    }
    return out;
  }
}

// I — Identity
export class IStation implements Station {
  namespace = "I";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    // I:§ NOT proposed standalone — orchestrator prepends as precondition
    if ((req.verb_lemma === "authenticate")
      || rawLow.includes("verify identity") || rawLow.includes("verify the identity")
      || rawLow.includes("identity check") || rawLow.includes("who is")
      || rawLow.includes("check identity") || rawLow.includes("confirm identity")
      || (rawLow.includes("identity") && req.verb_lemma === "verify")) {
      let target: string | null = null;
      for (const t of req.targets) if (t.source === "entity") { target = t.id; break; }
      out.push(makeProposal({
        namespace: "I", opcode: "ID",
        target, is_query: req.is_query,
        confidence: 2.0,
        rationale: "identity verification (overrides S:VFY)",
      }));
    }
    return out;
  }
}

// S — Crypto
const S_VERB_TO_OPCODE: Record<string, string> = {
  encrypt: "ENC", decrypt: "DEC", sign: "SIGN", hash: "HASH", verify: "VFY",
};
export class SStation implements Station {
  namespace = "S";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (req.verb_lemma && req.verb_lemma in S_VERB_TO_OPCODE) {
      out.push(makeProposal({
        namespace: "S", opcode: S_VERB_TO_OPCODE[req.verb_lemma],
        rationale: `verb '${req.verb_lemma}' -> S:${S_VERB_TO_OPCODE[req.verb_lemma]}`,
      }));
    }
    if (((rawLow.includes("key pair") || rawLow.includes("keypair"))
      || (rawLow.includes("key") && rawLow.includes("generate")))
      && !out.some((p) => p.opcode === "KEYGEN")) {
      out.push(makeProposal({
        namespace: "S", opcode: "KEYGEN",
        rationale: "keypair generation",
      }));
    }
    if (rawLow.includes("rotate") && (rawLow.includes("key") || rawLow.includes("credentials"))) {
      out.push(makeProposal({
        namespace: "S", opcode: "ROTATE",
        rationale: "key rotation",
      }));
    }
    return out;
  }
}

// K — Commerce
export class KStation implements Station {
  namespace = "K";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (req.verb_lemma === "pay" || rawLow.includes("payment") || rawLow.includes("transfer")) {
      out.push(makeProposal({
        namespace: "K", opcode: "PAY",
        confidence: rawLow.includes("payment") ? 2.0 : 1.0,
        rationale: "payment intent",
      }));
    }
    if (rawLow.includes("order") && rawLow.includes("financial")) {
      out.push(makeProposal({
        namespace: "K", opcode: "ORD", rationale: "financial order",
      }));
    }
    return out;
  }
}

// B — Building
export class BStation implements Station {
  namespace = "B";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (rawLow.includes("fire alarm") || (rawLow.includes("alarm") && rawLow.includes("building"))) {
      let target: string | null = null;
      for (const t of req.targets) if (t.kind === "building") { target = t.id; break; }
      if (!target) {
        const m = req.raw.match(/\bbuilding\s+(\w+)/i);
        if (m) target = m[1].toUpperCase();
      }
      out.push(makeProposal({
        namespace: "B", opcode: "ALRM", target,
        rationale: "building fire alarm",
      }));
    }
    return out;
  }
}

// U — User Interaction
export class UStation implements Station {
  namespace = "U";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const ACTION_VERBS = new Set(["pay", "process", "transfer", "delete", "send", "execute",
      "shutdown", "kill", "stop", "move", "fire", "deploy", "start"]);
    const hasGatedAction = ACTION_VERBS.has(req.verb_lemma ?? "")
      || [...ACTION_VERBS].some((v) => rawLow.includes(v));
    if ((rawLow.includes("approve") || rawLow.includes("approval")) && hasGatedAction) {
      out.push(makeProposal({
        namespace: "U", opcode: "APPROVE",
        confidence: 0.5,
        rationale: "approval pattern with action verb",
      }));
    }
    if (req.verb_lemma === "notify" || rawLow.includes("notify")) {
      out.push(makeProposal({
        namespace: "U", opcode: "NOTIFY", rationale: "notify verb",
      }));
    }
    if (["alert", "warn"].includes(req.verb_lemma ?? "") && !req.namespace_hints.includes("H")) {
      out.push(makeProposal({
        namespace: "U", opcode: "ALERT",
        rationale: "operator alert (non-clinical)",
      }));
    }
    return out;
  }
}

// L — Logging / Compliance
export class LStation implements Station {
  namespace = "L";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    if (["alert", "warn", "trigger"].includes(req.verb_lemma ?? "")) {
      out.push(makeProposal({
        namespace: "L", opcode: "ALERT",
        confidence: 0.5,
        rationale: "generic alert (compliance default)",
      }));
    }
    return out;
  }
}

// M — Municipal / Routing
export class MStation implements Station {
  namespace = "M";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (req.verb_lemma === "evacuate" || rawLow.includes("evacuation") || rawLow.includes("evacuate")) {
      out.push(makeProposal({
        namespace: "M", opcode: "EVA",
        target: req.is_broadcast ? "*" : null,
        rationale: "evacuate verb",
      }));
    }
    if (rawLow.includes("route") && (rawLow.includes("emergency") || rawLow.includes("incident"))) {
      out.push(makeProposal({
        namespace: "M", opcode: "RTE", rationale: "emergency route",
      }));
    }
    return out;
  }
}

// D — Data
export class DStation implements Station {
  namespace = "D";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (["push", "send"].includes(req.verb_lemma ?? "") && req.targets.length > 0
      && opcodeExists("D", "PUSH")) {
      for (const t of req.targets) {
        if (["preposition", "entity"].includes(t.source)) {
          out.push(makeProposal({
            namespace: "D", opcode: "PUSH", target: t.id,
            rationale: `send to ${t.id}`,
          }));
          break;
        }
      }
    }
    if ((req.verb_lemma === "query" || rawLow.includes("query")) && opcodeExists("D", "Q")) {
      out.push(makeProposal({
        namespace: "D", opcode: "Q", rationale: "data query",
      }));
    }
    if ((req.verb_lemma === "delete" || rawLow.includes("delete")) && opcodeExists("D", "DEL")) {
      out.push(makeProposal({
        namespace: "D", opcode: "DEL",
        consequence_class: "\u2298", confidence: 2.0,
        rationale: "delete",
      }));
    }
    return out;
  }
}

// J — Cognitive task
export class JStation implements Station {
  namespace = "J";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (rawLow.includes("hand off") || rawLow.includes("handoff")
      || req.verb_lemma === "handoff" || rawLow.includes("hand this")) {
      let target: string | null = null;
      for (const t of req.targets) {
        if (t.source === "entity" || t.source === "preposition") {
          target = t.id; break;
        }
      }
      out.push(makeProposal({
        namespace: "J", opcode: "HANDOFF", target,
        rationale: "handoff",
      }));
    }
    return out;
  }
}

// F — Flow control
export class FStation implements Station {
  namespace = "F";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (rawLow.includes("flow authorization") || rawLow.includes("authorization to proceed")) {
      out.push(makeProposal({ namespace: "F", opcode: "AV", rationale: "flow auth" }));
    }
    if (rawLow.includes("proceed") && [null, "may", "request"].includes(req.verb_lemma ?? null)) {
      out.push(makeProposal({ namespace: "F", opcode: "PRCD", rationale: "proceed protocol" }));
    }
    if (rawLow.includes("wait") || rawLow.includes("pause")) {
      out.push(makeProposal({
        namespace: "F", opcode: "WAIT",
        confidence: 2.5, rationale: "wait/pause",
      }));
    }
    return out;
  }
}

// O — Operational context
const O_KEYWORD_MAP: Record<string, string> = {
  bandwidth: "BW", authority: "LVL", channel: "CHAN",
  "concept of operations": "CONOPS", constraint: "CONSTRAINT",
  deescalation: "DESC", emcon: "EMCON", escalation: "ESCL",
  fallback: "FALLBACK", floor: "FLOOR",
  "incident action plan": "IAP", latency: "LATENCY",
  "link quality": "LINK", mesh: "MESH",
  "operational mode": "MODE", posture: "POSTURE",
  "signal strength": "LINK", conspicuity: "CONSPIC",
  "autonomy level": "AUTOLEV",
};
export class OStation implements Station {
  namespace = "O";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const sorted = Object.entries(O_KEYWORD_MAP).sort((a, b) => b[0].length - a[0].length);
    for (const [phrase, op] of sorted) {
      if (rawLow.includes(phrase)) {
        out.push(makeProposal({
          namespace: "O", opcode: op, is_query: req.is_query,
          rationale: `O-context phrase '${phrase}'`,
        }));
        break;
      }
    }
    return out;
  }
}

// P — Procedure / Maintenance
const P_KEYWORD_MAP: Record<string, string> = {
  "maintenance code": "CODE", "compliance code": "CODE",
  "device class": "DEVICE", "procedure guide": "GUIDE",
  "part reference": "PART", "completion status": "STAT",
  "step index": "STEP",
};
export class PStation implements Station {
  namespace = "P";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const sorted = Object.entries(P_KEYWORD_MAP).sort((a, b) => b[0].length - a[0].length);
    for (const [phrase, op] of sorted) {
      if (rawLow.includes(phrase)) {
        out.push(makeProposal({
          namespace: "P", opcode: op,
          rationale: `procedure phrase '${phrase}'`,
        }));
        break;
      }
    }
    return out;
  }
}

// Q — Quality
const Q_KEYWORD_MAP: Record<string, string> = {
  analysis: "ANL", benchmark: "BENCH", cite: "CITE", citation: "CITE",
  "confidence interval": "CONF", correction: "CORRECT", critique: "CRIT",
  evaluate: "EVAL", evaluation: "EVAL", feedback: "FB",
  "ground truth": "GT", "report quality": "RPRT",
  "structured report": "RPRT", review: "REVIEW",
  "verify quality": "VERIFY", revise: "REVISE",
};
export class QStation implements Station {
  namespace = "Q";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const sorted = Object.entries(Q_KEYWORD_MAP).sort((a, b) => b[0].length - a[0].length);
    for (const [phrase, op] of sorted) {
      if (rawLow.includes(phrase)) {
        out.push(makeProposal({
          namespace: "Q", opcode: op,
          confidence: 0.6, is_query: req.is_query,
          rationale: `Q phrase '${phrase}'`,
        }));
        break;
      }
    }
    return out;
  }
}

// X — Energy
const X_KEYWORD_MAP: Record<string, string> = {
  "demand response": "DR", "ev charging": "CHG", "charging state": "CHG",
  "fault event": "FAULT", "grid frequency": "FREQ",
  "grid connection": "GRD", islanding: "ISLND",
  "battery level": "STORE", "battery status": "STORE",
  "battery report": "STORE", voltage: "VOLT",
  "wind generation": "WND", "wind farm": "WND",
  production: "PROD", frequency: "FREQ",
};
const X_HIGH_CONF = new Set(["wind farm", "wind generation"]);
export class XStation implements Station {
  namespace = "X";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const rawDearticled = rawLow.split(/\s+/).filter((w) => !["the", "a", "an"].includes(w)).join(" ");
    const sorted = Object.entries(X_KEYWORD_MAP).sort((a, b) => b[0].length - a[0].length);
    for (const [phrase, op] of sorted) {
      if (rawLow.includes(phrase) || rawDearticled.includes(phrase)) {
        const conf = X_HIGH_CONF.has(phrase) ? 2.5 : 1.0;
        out.push(makeProposal({
          namespace: "X", opcode: op, confidence: conf,
          is_query: req.is_query || [null, "report", "show", "check"].includes(req.verb_lemma ?? null),
          rationale: `X energy phrase '${phrase}'`,
        }));
        break;
      }
    }
    return out;
  }
}

// Y — Memory
const Y_VERB_TO_OPCODE: Record<string, string> = {
  store: "STORE", save: "STORE", remember: "STORE",
  fetch: "FETCH", recall: "FETCH", forget: "FORGET",
  index: "INDEX", commit: "COMMIT", embed: "EMBED", clear: "CLEAR",
};
const Y_KEYWORD_MAP: Record<string, string> = {
  "page out memory": "PAGEOUT", "store to memory": "STORE",
  "save to memory": "STORE", embedding: "EMBED",
  "memory tier": "CLEAR",
};
export class YStation implements Station {
  namespace = "Y";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const tokens = rawLow.split(/\s+/);
    if (rawLow.includes("memory") || tokens.includes("store") || tokens.includes("fetch")
      || ["forget", "store"].includes(req.verb_lemma ?? "")) {
      if (req.verb_lemma && req.verb_lemma in Y_VERB_TO_OPCODE) {
        out.push(makeProposal({
          namespace: "Y", opcode: Y_VERB_TO_OPCODE[req.verb_lemma],
          confidence: 1.5, rationale: `memory verb '${req.verb_lemma}'`,
        }));
      }
    }
    const sorted = Object.entries(Y_KEYWORD_MAP).sort((a, b) => b[0].length - a[0].length);
    for (const [phrase, op] of sorted) {
      if (rawLow.includes(phrase)) {
        out.push(makeProposal({
          namespace: "Y", opcode: op, confidence: 0.7,
          rationale: `Y phrase '${phrase}'`,
        }));
        break;
      }
    }
    return out;
  }
}

// Z — Inference
const Z_KEYWORD_MAP: Record<string, string> = {
  "batch inference": "BATCH", "kv cache": "CACHE",
  "capability query": "CAPS", "agent confidence": "CONF",
  "inference cost": "COST", "context window": "CTX",
  "context utilization": "CTX", "run inference": "INF",
  "invoke model": "INF", tokens: "TOKENS",
  "token count": "TOKENS", "sampling temperature": "TEMP",
  "top-p": "TOPP", "top p": "TOPP", "max tokens": "MAX",
  "model response": "RESP",
};
export class ZStation implements Station {
  namespace = "Z";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    for (const sv of req.slot_values) {
      if (sv.key === "temperature" && [null, "set", "configure"].includes(req.verb_lemma ?? null)) {
        out.push(makeProposal({
          namespace: "Z", opcode: "TEMP",
          slot_values: [{ key: "", value: sv.value, value_type: "float" }],
          confidence: 0.6,
          rationale: "Z:TEMP for inference sampling temp",
        }));
      }
    }
    const sorted = Object.entries(Z_KEYWORD_MAP).sort((a, b) => b[0].length - a[0].length);
    for (const [phrase, op] of sorted) {
      if (rawLow.includes(phrase)) {
        out.push(makeProposal({
          namespace: "Z", opcode: op, confidence: 0.7,
          is_query: req.is_query,
          rationale: `Z phrase '${phrase}'`,
        }));
        break;
      }
    }
    return out;
  }
}
