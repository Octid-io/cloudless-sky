/** Sensing-namespace stations: E, H, G, V, W, N, A. Faithful TS ports. */
import type { FrameProposal, ParsedRequest, SlotValue } from "../request.js";
import { makeProposal } from "../request.js";
import type { Station } from "./base.js";

function pickTarget(req: ParsedRequest): string | null {
  if (req.is_broadcast && req.targets.length === 0) return "*";
  for (const t of req.targets) if (t.source === "entity") return t.id;
  if (req.targets.length > 0) return req.targets[0].id;
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// E-station — Environmental sensor
// ─────────────────────────────────────────────────────────────────────────────

const E_SENSOR_TO_OPCODE: Record<string, string> = {
  temperature: "TH", temp: "TH", humidity: "HU", pressure: "PU",
  pump: "PU", barometric: "PU", gps: "GPS", coordinates: "GPS",
  air: "EQ", vibration: "VIB", moisture: "TH", soil: "TH",
};
const E_PHRASE_TO_OPCODE: Record<string, string> = {
  "air quality": "EQ", "soil moisture": "TH", "temperature humidity": "EQ",
};

export class EStation implements Station {
  namespace = "E";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();

    // Generic sensor read default
    if (req.verb_lemma === "read" && req.direct_object_kind === "sensor"
      && !["temperature", "humidity", "pressure", "wind"].some((w) => rawLow.includes(w))) {
      out.push(makeProposal({
        namespace: "E", opcode: "TH",
        target: pickTarget(req), is_query: true,
        rationale: "generic sensor read defaults to E:TH",
      }));
    }

    // Phrases
    for (const [phrase, op] of Object.entries(E_PHRASE_TO_OPCODE).sort((a, b) => b[0].length - a[0].length)) {
      if (rawLow.includes(phrase)) {
        out.push(makeProposal({
          namespace: "E", opcode: op,
          target: pickTarget(req),
          is_query: req.is_query || ["report", "show", "get", "read"].includes(req.verb_lemma ?? ""),
          rationale: `phrase '${phrase}' -> E:${op}`,
        }));
      }
    }

    // Single-word
    const cands: Array<[string, string]> = [];
    if (req.direct_object) {
      for (const w of req.direct_object.toLowerCase().split(/\s+/)) {
        if (w in E_SENSOR_TO_OPCODE) cands.push([w, E_SENSOR_TO_OPCODE[w]]);
      }
    }
    if (cands.length === 0) {
      for (const tok of rawLow.split(/\s+/)) {
        const c = tok.replace(/[,.\!?;:'"]/g, "");
        if (c in E_SENSOR_TO_OPCODE) cands.push([c, E_SENSOR_TO_OPCODE[c]]);
      }
    }

    for (const [word, op] of cands) {
      if (out.some((p) => p.opcode === op)) continue;
      let slots: SlotValue[] = [];
      if (op === "PU") {
        for (const sv of req.slot_values) {
          if (sv.value_type === "float" && (sv.key === "pressure" || sv.key === "pump")) {
            slots = [{ key: "", value: sv.value, value_type: "float" }];
            break;
          }
        }
        if (slots.length === 0) {
          const m = rawLow.match(/to\s+(\d+\.?\d*)\s*(?:millibar|mbar|psi|kpa)?/);
          if (m) slots = [{ key: "", value: m[1], value_type: "float" }];
        }
      }
      out.push(makeProposal({
        namespace: "E", opcode: op,
        target: pickTarget(req),
        slot_values: slots,
        is_query: req.is_query || (["report", "show", "get", "read", "what", null].includes(req.verb_lemma ?? null) && slots.length === 0),
        rationale: `sensor '${word}' -> E:${op}`,
      }));
    }
    return out;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// H-station — Health / Clinical
// ─────────────────────────────────────────────────────────────────────────────

const H_PHRASE_TO_OPCODE: Record<string, string> = {
  "blood pressure": "BP", "heart rate": "HR",
  "oxygen level": "SPO2", "oxygen saturation": "SPO2",
  "oxygen sat": "SPO2", "oxygen drops": "SPO2", spo2: "SPO2",
  "all vitals": "VITALS", "vital signs": "VITALS", "vitals check": "VITALS",
  "body temperature": "TEMP", "body temp": "TEMP",
  "patient pulse": "HR", "patient temperature": "TEMP",
  "respiratory rate": "RR",
};
const H_HIGH_CONF_PHRASES = new Set(["body temperature", "body temp", "patient temperature", "oxygen drops"]);
const H_SINGLE_WORD: Record<string, string> = { vitals: "VITALS", pulse: "HR", bp: "BP", hr: "HR" };

export class HStation implements Station {
  namespace = "H";
  propose(req: ParsedRequest): FrameProposal[] {
    const proposals: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const rawDearticled = rawLow.split(/\s+/).filter((w) => !["the", "a", "an"].includes(w)).join(" ");

    // ICD codes
    for (const sv of req.slot_values) {
      if (sv.value_type === "code" && sv.key === "icd") {
        proposals.push(makeProposal({
          namespace: "H", opcode: "ICD",
          slot_values: [{ key: "", value: sv.value, value_type: "code" }],
          target: pickTarget(req),
          rationale: `ICD code ${sv.value}`,
        }));
      }
    }

    // Phrase match (longest first)
    const sortedPhrases = Object.entries(H_PHRASE_TO_OPCODE).sort((a, b) => b[0].length - a[0].length);
    for (const [phrase, op] of sortedPhrases) {
      if (rawLow.includes(phrase) || rawDearticled.includes(phrase)) {
        const conf = H_HIGH_CONF_PHRASES.has(phrase) ? 2.5 : 1.0;
        proposals.push(makeProposal({
          namespace: "H", opcode: op,
          target: pickTarget(req), confidence: conf,
          is_query: req.is_query || [null, "report", "show", "give", "check", "what"].includes(req.verb_lemma ?? null),
          rationale: `phrase '${phrase}' -> H:${op}`,
        }));
        break;
      }
    }

    // Single-word fallback
    const hasMain = proposals.some((p) => ["BP", "HR", "VITALS", "SPO2", "TEMP", "RR"].includes(p.opcode));
    if (!hasMain) {
      for (const w of rawLow.split(/\s+/)) {
        const c = w.replace(/[,.\!?;:'"]/g, "");
        if (c in H_SINGLE_WORD) {
          proposals.push(makeProposal({
            namespace: "H", opcode: H_SINGLE_WORD[c],
            target: pickTarget(req), is_query: req.is_query,
            rationale: `single-word '${c}' -> H:${H_SINGLE_WORD[c]}`,
          }));
          break;
        }
      }
    }

    if (rawLow.includes("casualty") || rawLow.includes("casrep")) {
      proposals.push(makeProposal({
        namespace: "H", opcode: "CASREP",
        target: pickTarget(req),
        rationale: "casualty report",
      }));
    }

    if (["alert", "warn", "notify"].includes(req.verb_lemma ?? "") || rawLow.includes("alert")) {
      if (proposals.some((p) => p.namespace === "H" && ["BP", "HR", "SPO2", "TEMP", "VITALS"].includes(p.opcode))) {
        proposals.push(makeProposal({
          namespace: "H", opcode: "ALERT",
          rationale: "clinical alert (H sensing context)",
        }));
      }
    }

    return proposals;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// G-station — Geospatial
// ─────────────────────────────────────────────────────────────────────────────

const G_POSITION_WORDS = new Set(["position", "location", "place", "where", "spot",
  "altitude", "elevation", "latlon", "lat", "lng", "long", "coords"]);
const G_HEADING_WORDS = new Set(["heading", "bearing", "direction", "course", "azimuth", "compass"]);

export class GStation implements Station {
  namespace = "G";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const tokens = new Set(rawLow.replace(/[,.]/g, " ").split(/\s+/));

    if ([...G_POSITION_WORDS].some((w) => tokens.has(w))) {
      const target = pickTarget(req);
      out.push(makeProposal({
        namespace: "G", opcode: "POS",
        target: req.is_broadcast && !target ? "*" : target,
        is_query: req.is_query,
        rationale: "position keyword",
      }));
    }
    if ([...G_HEADING_WORDS].some((w) => tokens.has(w))) {
      out.push(makeProposal({
        namespace: "G", opcode: "BEARING",
        target: pickTarget(req), is_query: req.is_query,
        rationale: "heading keyword",
      }));
    }
    return out;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// V-station — Vehicle / Transport Fleet
// ─────────────────────────────────────────────────────────────────────────────

const V_VEHICLE_CONTEXT = new Set(["vehicle", "vessel", "ship", "boat", "fleet", "ais", "drone", "uav"]);

export class VStation implements Station {
  namespace = "V";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();

    // V:CSPOS removed — not in v15 ASD active set.

    const inVehicleCtx = [...V_VEHICLE_CONTEXT].some((w) => rawLow.includes(w));
    if (!inVehicleCtx) return out;

    if (rawLow.includes("heading") || rawLow.includes("bearing") || rawLow.includes("course")) {
      out.push(makeProposal({
        namespace: "V", opcode: "HDG",
        target: pickTarget(req), is_query: req.is_query,
        rationale: "vehicle heading context",
      }));
    }
    if (rawLow.includes("position") || rawLow.includes("location") || rawLow.includes("where")) {
      out.push(makeProposal({
        namespace: "V", opcode: "POS",
        target: pickTarget(req), is_query: req.is_query,
        rationale: "vehicle position context",
      }));
    }
    if (rawLow.includes("fleet") && (rawLow.includes("status") || req.is_query)) {
      out.push(makeProposal({
        namespace: "V", opcode: "FLEET",
        is_query: true, rationale: "fleet status",
      }));
    }
    if (rawLow.split(/\s+/).includes("ais") || ` ${rawLow} `.includes(" ais ")) {
      out.push(makeProposal({
        namespace: "V", opcode: "AIS",
        target: pickTarget(req), confidence: 2.5,
        rationale: "AIS keyword (overrides V:POS)",
      }));
    }

    return out;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// W-station — Weather
// ─────────────────────────────────────────────────────────────────────────────

export class WStation implements Station {
  namespace = "W";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    const tokens = new Set(rawLow.replace(/[,.]/g, " ").split(/\s+/));

    if (rawLow.includes("wind farm") || rawLow.includes("wind generation")) return out;
    if (rawLow.includes("wind down") || rawLow.includes("wind up")) return out;

    if (tokens.has("wind")) {
      out.push(makeProposal({
        namespace: "W", opcode: "WIND",
        target: pickTarget(req),
        is_query: req.is_query || [null, "report", "show", "get"].includes(req.verb_lemma ?? null),
        rationale: "wind keyword",
      }));
    }
    if (rawLow.includes("weather alert") || (req.verb_lemma === "alert" && rawLow.includes("wind"))) {
      out.push(makeProposal({
        namespace: "W", opcode: "ALERT",
        rationale: "weather alert",
      }));
    }
    return out;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// N-station — Network / Routing
// ─────────────────────────────────────────────────────────────────────────────

export class NStation implements Station {
  namespace = "N";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();

    // CFG
    if ((["set", "configure", "update", "modify", "change", "adjust"].includes(req.verb_lemma ?? ""))
      || rawLow.includes("config") || rawLow.includes("configuration") || rawLow.includes("settings")) {
      let slots: SlotValue[] = [];
      for (const sv of req.slot_values) {
        if (sv.value_type === "float" && sv.key !== "at_time") { slots = [sv]; break; }
      }
      out.push(makeProposal({
        namespace: "N", opcode: "CFG",
        slot_values: slots, target: pickTarget(req),
        rationale: "config verb or config keyword",
      }));
    }

    // BK
    if (req.verb_lemma === "back" || req.verb_lemma === "backup" || rawLow.includes("back up")) {
      let target: string | null = null;
      for (const sv of req.slot_values) {
        if (sv.value_type === "time") { target = sv.value; break; }
      }
      out.push(makeProposal({
        namespace: "N", opcode: "BK",
        target, rationale: "backup verb",
      }));
    }

    // STS
    if (rawLow.includes("status") || rawLow.includes("uptime") || rawLow.includes("alive") || rawLow.includes("online")) {
      out.push(makeProposal({
        namespace: "N", opcode: "STS",
        target: pickTarget(req), is_query: true,
        rationale: "status keyword",
      }));
    }

    // Q
    if (req.verb_lemma === "discover" || rawLow.includes("discover")) {
      out.push(makeProposal({
        namespace: "N", opcode: "Q",
        target: req.is_broadcast || rawLow.includes("peers") || rawLow.includes("all") ? "*" : null,
        rationale: "discover verb",
      }));
    }

    // RLY
    if (rawLow.includes("relay") && [null, "find", "what", "where", "show", "report", "get"].includes(req.verb_lemma ?? null)) {
      out.push(makeProposal({
        namespace: "N", opcode: "RLY",
        is_query: true, rationale: "relay query",
      }));
    }

    return out;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// A-station — Agentic / OSMP-Native
// ─────────────────────────────────────────────────────────────────────────────

export class AStation implements Station {
  namespace = "A";
  propose(req: ParsedRequest): FrameProposal[] {
    const out: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();
    if (req.verb_lemma === "ping") {
      out.push(makeProposal({
        namespace: "A", opcode: "PING",
        target: pickTarget(req), rationale: "ping verb",
      }));
    }
    if (req.verb_lemma === "summarize" || rawLow.includes("summarize")) {
      out.push(makeProposal({
        namespace: "A", opcode: "SUM",
        rationale: "summarize verb",
      }));
    }
    return out;
  }
}
