/**
 * Garde manger — the grammar parser. Mise en place for the brigade.
 *
 * Faithful TS port of sdk/python/osmp/brigade/parser.py.
 *
 * Reads NL once, produces ParsedRequest IR. Every other station starts here.
 */

import type {
  Condition,
  ParsedRequest,
  SlotValue,
  Target,
} from "./request.js";
import { emptyParsedRequest } from "./request.js";

// ─────────────────────────────────────────────────────────────────────────────
// MODIFIER MARKERS, NEGATION, INJECTION, BRIDGE POLICY
// ─────────────────────────────────────────────────────────────────────────────

export const MODIFIER_MARKERS_PATTERN = /\b(unless|only if|except|but not|without|after|before|while|if not)\b/i;

export const BRIDGE_ALLOWED_NAMESPACES = new Set<string>([
  "E", "G", "W", "N", "O", "Q", "X", "A", "H", "V", "I",
]);

// Frames that are NEVER safe to bridge — action-bearing within otherwise-sensing namespaces
export const BRIDGE_FORBIDDEN_FRAMES = new Set<string>([
  "H:ALERT", "H:CASREP", "W:ALERT", "N:CFG", "N:BK",
  "V:FLEET", "I:§", "A:PROPOSE", "A:BROADCAST",
]);

const NEGATION_MARKERS: RegExp[] = [
  /\bdon'?t\b/i,
  /\bdo not\b/i,
  /\bdoes not\b/i,
  /\bdoesn'?t\b/i,
  /\bnever\b/i,
  /\bno longer\b/i,
  /\bnot\b/i,
  /\bcancel\b/i,
  /\babort\b/i,
  /\bstop doing\b/i,
];

const INJECTION_MARKERS: RegExp[] = [
  /;\s*(?:DROP|DELETE|INSERT|UPDATE|SELECT|TRUNCATE|ALTER)\s+/i,
  /&&/,
  /\|\|/,
  /\$\(/,
  /`[^`]*`/,
  /<script/i,
  /<\/script/i,
  /javascript:/i,
  /system\s*\(/i,
  /exec\s*\(/i,
  /eval\s*\(/i,
  /rm\s+-rf/i,
  /chmod\s+777/i,
  /--\s*$/,
  /\/etc\/(?:passwd|shadow)/i,
  /\bUNION\s+SELECT\b/i,
  /\.\.\//,
];

const EMAIL_PATTERN = /\b[\w.+-]+@[\w-]+\.\w+\b/;

const IDIOM_PARTICLE_AFTER_VERB = new Set<string>([
  "wind|down", "wind|up",
  "stop|bothering", "stop|by", "stop|doing",
  "ping|me",
  "lock|in", "lock|down",
  "close|out",
  "send|off",
  "verify|that",
  "check|out", "check|in",
  "report|back", "report|in",
  "encrypt|your",
]);

export const ACTUATOR_OBJECT_NOUNS = new Set<string>([
  "conveyor", "pump", "valve", "door", "light", "lights", "lamp", "fan",
  "motor", "engine", "service", "process", "system", "device", "node",
  "gateway", "server", "drone", "vehicle", "vessel", "robot", "sensor",
  "alarm", "siren", "sprinkler", "camera", "microphone", "speaker",
  "flashlight", "torch", "screen", "display", "wifi", "bluetooth", "gps",
  "haptic", "actuator", "relay", "switch", "circuit", "breaker",
  "hatch", "window", "shutter", "blind", "tank", "reactor",
  "antenna", "transmitter", "receiver", "feed", "stream", "channel",
  "config", "configuration", "settings", "threshold", "parameter",
  "database", "cache", "queue", "log", "logs",
]);

const EMERGENCY_MARKERS = new Set<string>([
  "emergency", "immediately", "right now", "asap", "urgent", "critical",
  "panic", "sos", "mayday",
]);

const BROADCAST_MARKERS = new Set<string>([
  "everyone", "all nodes", "broadcast", "all peers", "every node",
]);

const QUERY_MARKERS = new Set<string>([
  "?", "what", "where", "when", "who", "how many", "how much",
  "tell me", "show me",
]);

const AUTH_MARKERS: RegExp[] = [
  /\bonly if\b.*\b(approves?|signs?|authorize[ds]?|confirm[s]?|allows?)\b/i,
  /\brequire[ds]?\s+(approval|sign-?off|authorization|confirmation)\b/i,
  /\bif\s+\w+\s+(approves?|signs?|authorizes?)\b/i,
  /\bafter\s+\w+\s+approves?\b/i,
  /\bwith\s+approval\b/i,
  /\bsubject to (approval|authorization)\b/i,
];

// ─────────────────────────────────────────────────────────────────────────────
// VERB LEXICON
// ─────────────────────────────────────────────────────────────────────────────

interface VerbInfo {
  lemma: string;
  ns_hints: string[];
  is_wrapper?: boolean;
  is_query?: boolean;
  primary_opcode?: string;
  takes_slot?: boolean;
}

export const VERB_LEXICON: Record<string, VerbInfo> = {
  // Sensing / read
  report:    { lemma: "report",    ns_hints: ["L", "Q"], is_wrapper: true },
  send:      { lemma: "send",      ns_hints: ["D", "L"], is_wrapper: true },
  show:      { lemma: "show",      ns_hints: ["A"],     is_wrapper: true },
  log:       { lemma: "log",       ns_hints: ["L"],     is_wrapper: true },
  broadcast: { lemma: "broadcast", ns_hints: ["L", "A"], is_wrapper: true },
  fetch:     { lemma: "fetch",     ns_hints: ["D"],     is_wrapper: true },
  retrieve:  { lemma: "retrieve",  ns_hints: ["D"],     is_wrapper: true },
  read:      { lemma: "read",      ns_hints: ["E", "D"], is_wrapper: true },
  get:       { lemma: "get",       ns_hints: ["D", "E"], is_wrapper: true },
  give:      { lemma: "give",      ns_hints: ["D"],     is_wrapper: true },
  what:      { lemma: "what",      ns_hints: [],        is_wrapper: true, is_query: true },
  where:     { lemma: "where",     ns_hints: ["G"],     is_wrapper: true, is_query: true },

  // Actuation
  stop:      { lemma: "stop",      ns_hints: ["R", "C"], primary_opcode: "STOP" },
  halt:      { lemma: "halt",      ns_hints: ["R", "C"], primary_opcode: "STOP" },
  start:     { lemma: "start",     ns_hints: ["R", "C"], primary_opcode: "START" },
  open:      { lemma: "open",      ns_hints: ["R"],     primary_opcode: "OPEN" },
  close:     { lemma: "close",     ns_hints: ["R"],     primary_opcode: "STOP" },
  lock:      { lemma: "lock",      ns_hints: ["R"],     primary_opcode: "STOP" },
  unlock:    { lemma: "unlock",    ns_hints: ["R"],     primary_opcode: "OPEN" },
  move:      { lemma: "move",      ns_hints: ["R", "V"], primary_opcode: "MOV" },
  return:    { lemma: "return",    ns_hints: ["R"],     primary_opcode: "RTH" },
  shutdown:  { lemma: "shutdown",  ns_hints: ["C", "R"], primary_opcode: "KILL" },
  shut:      { lemma: "shut",      ns_hints: ["C", "R"], primary_opcode: "KILL" },
  kill:      { lemma: "kill",      ns_hints: ["C"],     primary_opcode: "KILL" },
  reboot:    { lemma: "reboot",    ns_hints: ["C"],     primary_opcode: "RSTRT" },
  restart:   { lemma: "restart",   ns_hints: ["C"],     primary_opcode: "RSTRT" },
  evacuate:  { lemma: "evacuate",  ns_hints: ["M"],     primary_opcode: "EVA" },
  form:      { lemma: "form",      ns_hints: ["R"],     primary_opcode: "FORM" },
  find:      { lemma: "find",      ns_hints: ["N", "D"], is_wrapper: true },
  rotate:    { lemma: "rotate",    ns_hints: ["S", "R"], primary_opcode: "ROTATE" },
  ack:       { lemma: "ack",       ns_hints: ["U"],     primary_opcode: "ACK" },
  store:     { lemma: "store",     ns_hints: ["Y"],     primary_opcode: "STORE" },
  forget:    { lemma: "forget",    ns_hints: ["Y"],     primary_opcode: "FORGET" },
  wait:      { lemma: "wait",      ns_hints: ["F"],     primary_opcode: "WAIT" },
  rebroadcast: { lemma: "rebroadcast", ns_hints: ["L"], primary_opcode: "SEND" },
  engage:    { lemma: "engage",    ns_hints: ["R"],     is_wrapper: true },
  swarm:     { lemma: "swarm",     ns_hints: ["R", "V"], is_wrapper: true },
  rtb:       { lemma: "rtb",       ns_hints: ["R"],     primary_opcode: "RTH" },
  navigate:  { lemma: "navigate",  ns_hints: ["R"],     primary_opcode: "MOV" },
  fly:       { lemma: "fly",       ns_hints: ["R", "V"], primary_opcode: "MOV" },
  drive:     { lemma: "drive",     ns_hints: ["R", "V"], primary_opcode: "DRVE" },
  go:        { lemma: "go",        ns_hints: ["R"],     primary_opcode: "MOV" },
  proceed:   { lemma: "proceed",   ns_hints: ["F"],     primary_opcode: "PRCD" },
  cease:     { lemma: "cease",     ns_hints: ["R", "C"], primary_opcode: "STOP" },
  block:     { lemma: "block",     ns_hints: ["R"],     primary_opcode: "STOP" },
  turn:      { lemma: "turn",      ns_hints: ["R"],     is_wrapper: true },
  activate:  { lemma: "activate",  ns_hints: ["R"],     is_wrapper: true },
  enable:    { lemma: "enable",    ns_hints: ["R"],     is_wrapper: true },
  disable:   { lemma: "disable",   ns_hints: ["R"],     is_wrapper: true },

  // Crypto / auth
  encrypt:      { lemma: "encrypt",   ns_hints: ["S"],   primary_opcode: "ENC" },
  decrypt:      { lemma: "decrypt",   ns_hints: ["S"],   primary_opcode: "DEC" },
  sign:         { lemma: "sign",      ns_hints: ["S"],   primary_opcode: "SIGN" },
  hash:         { lemma: "hash",      ns_hints: ["S"],   primary_opcode: "HASH" },
  verify:       { lemma: "verify",    ns_hints: ["S", "I", "A"], primary_opcode: "VFY" },
  authenticate: { lemma: "authenticate", ns_hints: ["I"], primary_opcode: "ID" },

  // Auxiliary creator (wrappers — operand carries opcode)
  generate: { lemma: "generate", ns_hints: [], is_wrapper: true },
  create:   { lemma: "create",   ns_hints: [], is_wrapper: true },
  make:     { lemma: "make",     ns_hints: [], is_wrapper: true },
  produce:  { lemma: "produce",  ns_hints: [], is_wrapper: true },

  // Network / discovery
  ping:     { lemma: "ping",     ns_hints: ["A"], primary_opcode: "PING" },
  discover: { lemma: "discover", ns_hints: ["N"], primary_opcode: "Q" },

  // Alerts
  alert:    { lemma: "alert",    ns_hints: ["L", "H", "U", "W"], primary_opcode: "ALERT" },
  notify:   { lemma: "notify",   ns_hints: ["U"], primary_opcode: "NOTIFY" },
  warn:     { lemma: "warn",     ns_hints: ["L", "H", "U"], primary_opcode: "ALERT" },
  trigger:  { lemma: "trigger",  ns_hints: ["L", "U"], primary_opcode: "ALERT" },

  // Config
  set:       { lemma: "set",       ns_hints: ["N"], primary_opcode: "CFG", takes_slot: true },
  configure: { lemma: "configure", ns_hints: ["N"], primary_opcode: "CFG", takes_slot: true },
  update:    { lemma: "update",    ns_hints: ["N"], primary_opcode: "CFG" },
  modify:    { lemma: "modify",    ns_hints: ["N"], primary_opcode: "CFG" },
  change:    { lemma: "change",    ns_hints: ["N"], primary_opcode: "CFG" },
  adjust:    { lemma: "adjust",    ns_hints: ["N"], primary_opcode: "CFG" },

  // Time / schedule
  expire:   { lemma: "expire",   ns_hints: ["T"], primary_opcode: "EXP" },
  schedule: { lemma: "schedule", ns_hints: ["T"], primary_opcode: "SCHED" },

  // Storage / data
  back:    { lemma: "back",    ns_hints: ["N"], primary_opcode: "BK" },
  backup:  { lemma: "backup",  ns_hints: ["N"], primary_opcode: "BK" },
  delete:  { lemma: "delete",  ns_hints: ["D"], primary_opcode: "DEL" },
  push:    { lemma: "push",    ns_hints: ["D"], primary_opcode: "PUSH" },

  // Commerce
  process: { lemma: "process", ns_hints: ["K", "C"], is_wrapper: true },
  pay:     { lemma: "pay",     ns_hints: ["K"],      primary_opcode: "PAY" },
  approve: { lemma: "approve", ns_hints: ["U"],      primary_opcode: "APPROVE" },

  // Cognitive
  hand:      { lemma: "hand",      ns_hints: ["J"], primary_opcode: "HANDOFF" },
  handoff:   { lemma: "handoff",   ns_hints: ["J"], primary_opcode: "HANDOFF" },
  summarize: { lemma: "summarize", ns_hints: ["A"], primary_opcode: "SUM" },
  check:     { lemma: "check",     ns_hints: ["A", "Q"], is_wrapper: true },
};

const INFLECTIONS: Record<string, string> = {
  stops: "stop", stopping: "stop", stopped: "stop",
  starts: "start", starting: "start", started: "start",
  moves: "move", moving: "move", moved: "move",
  opens: "open", opening: "open", opened: "open",
  closes: "close", closing: "close", closed: "close",
  locks: "lock", locking: "lock", locked: "lock",
  encrypts: "encrypt", encrypting: "encrypt", encrypted: "encrypt",
  signs: "sign", signing: "sign", signed: "sign",
  verifies: "verify", verifying: "verify", verified: "verify",
  pings: "ping", pinging: "ping", pinged: "ping",
  alerts: "alert", alerting: "alert", alerted: "alert",
  notifies: "notify", notifying: "notify", notified: "notify",
  sets: "set", setting: "set",
  configures: "configure", configuring: "configure",
  updates: "update", updating: "update", updated: "update",
  expires: "expire", expiring: "expire", expired: "expire",
  deletes: "delete", deleting: "delete", deleted: "delete",
  pushes: "push", pushing: "push", pushed: "push",
  approves: "approve", approving: "approve", approved: "approve",
  summarizes: "summarize", summarizing: "summarize", summarized: "summarize",
  discovers: "discover", discovering: "discover", discovered: "discover",
  generates: "generate", generating: "generate", generated: "generate",
  reports: "report", reporting: "report", reported: "report",
  sends: "send", sending: "send", sent: "send",
  shows: "show", showing: "show", showed: "show",
  broadcasts: "broadcast", broadcasting: "broadcast",
  fetches: "fetch", fetching: "fetch", fetched: "fetch",
  retrieves: "retrieve", retrieving: "retrieve", retrieved: "retrieve",
  reads: "read", reading: "read",
  gets: "get", getting: "get", got: "get",
  halts: "halt", halting: "halt", halted: "halt",
  shuts: "shut", shutting: "shut",
  kills: "kill", killing: "kill", killed: "kill",
  reboots: "reboot", rebooting: "reboot", rebooted: "reboot",
  restarts: "restart", restarting: "restart", restarted: "restart",
  returns: "return", returning: "return", returned: "return",
  evacuates: "evacuate", evacuating: "evacuate", evacuated: "evacuate",
  turns: "turn", turning: "turn", turned: "turn",
  activates: "activate", activating: "activate", activated: "activate",
  warns: "warn", warning: "warn", warned: "warn",
  triggers: "trigger", triggering: "trigger", triggered: "trigger",
  processes: "process", processing: "process", processed: "process",
  schedules: "schedule", scheduling: "schedule", scheduled: "scheduled",
  checks: "check", checking: "check", checked: "check",
  hands: "hand", handing: "hand", handed: "hand",
  creates: "create", creating: "create", created: "create",
  makes: "make", making: "make", made: "make",
  produces: "produce", producing: "produce", produced: "produce",
};

const STOPWORDS = new Set<string>([
  "the", "a", "an", "this", "that", "these", "those",
  "is", "are", "was", "were", "be", "been", "being",
  "do", "does", "did", "has", "have", "had",
  "and", "or", "but", "if", "when", "while",
  "of", "in", "on", "at", "to", "for", "from", "with", "by",
  "me", "my", "you", "your", "we", "our", "they", "their",
  "it", "its", "his", "her", "them",
  "please", "now", "just", "only", "really",
]);

// ─────────────────────────────────────────────────────────────────────────────
// SLOT EXTRACTORS
// ─────────────────────────────────────────────────────────────────────────────

const ICD_PATTERN = /(?:code|icd|diagnosis|icd-?10)\s+([A-Z]\d{2}\.?\d*)/gi;
const LATLON_PATTERN = /(?:coordinates?|coords?|gps|location|latlon)\s+([-]?\d{1,3}\.?\d*)\s*[,]?\s*([-]?\d{1,3}\.?\d*)/gi;
const DURATION_PATTERN = /(?:every|in|after|for|within)\s+(\d+\.?\d*)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\b/gi;
const AT_TIME_PATTERN = /\b(?:at|by)\s+(\d{1,2}(?::\d{2})?(?:\s*[ap]m)?|midnight|noon|tonight)\b/gi;
const THRESHOLD_PATTERN = /(above|over|below|under|exceeds?|greater than|less than|higher than|lower than)\s+(-?\d+\.?\d*)/gi;
const NAMED_PARAM_PATTERN = /\b(?:set\s+(?:the\s+)?)?(\w+)\s+to\s+(\d+\.?\d*)\b/gi;

const THRESHOLD_OP_MAP: Record<string, string> = {
  above: ">", over: ">", exceeds: ">", exceed: ">",
  "greater than": ">", "higher than": ">",
  below: "<", under: "<", "less than": "<", "lower than": "<",
};

function normalizeDurationUnit(unit: string): string {
  const u = unit.toLowerCase();
  if (u.startsWith("s")) return "s";
  if (u.startsWith("min") || u === "m") return "m";
  if (u.startsWith("m")) return "s"; // Python preserves this quirk
  if (u.startsWith("h")) return "h";
  if (u.startsWith("d")) return "d";
  return "s";
}

export function extractSlots(text: string): SlotValue[] {
  const slots: SlotValue[] = [];
  const seenKeys = new Set<string>();
  const textLow = text.toLowerCase();

  // Fixed-cadence schedule keywords
  const cadence: Array<[string, string]> = [
    ["daily", "1d"], ["hourly", "1h"], ["weekly", "7d"],
    ["monthly", "30d"], ["nightly", "1d"],
  ];
  for (const [kw, val] of cadence) {
    if (textLow.includes(kw)) {
      slots.push({ key: "duration", value: val, value_type: "duration" });
      break;
    }
  }

  // ICD codes
  for (const m of text.matchAll(ICD_PATTERN)) {
    const code = m[1].replace(/\./g, "").toUpperCase();
    if (!seenKeys.has("icd")) {
      slots.push({ key: "icd", value: code, value_type: "code" });
      seenKeys.add("icd");
    }
  }

  // Lat/lon
  for (const m of text.matchAll(LATLON_PATTERN)) {
    const latlon = `${m[1]},${m[2]}`;
    if (!seenKeys.has("coordinates")) {
      slots.push({ key: "coordinates", value: latlon, value_type: "latlon" });
      seenKeys.add("coordinates");
    }
  }

  // Duration / interval
  for (const m of text.matchAll(DURATION_PATTERN)) {
    let n = m[1];
    const unit = normalizeDurationUnit(m[2]);
    if (n.endsWith(".0")) n = n.slice(0, -2);
    slots.push({ key: "duration", value: `${n}${unit}`, value_type: "duration" });
  }

  // At-time
  for (const m of text.matchAll(AT_TIME_PATTERN)) {
    const t = m[1].toUpperCase().replace(/\s+/g, "");
    if (!seenKeys.has("at_time")) {
      slots.push({ key: "at_time", value: t, value_type: "time" });
      seenKeys.add("at_time");
    }
  }

  // Named "X to N"
  const SKIP_NAMES = new Set([
    "set", "configure", "update", "schedule", ...seenKeys,
  ]);
  for (const m of text.matchAll(NAMED_PARAM_PATTERN)) {
    const name = m[1].toLowerCase();
    if (SKIP_NAMES.has(name) || STOPWORDS.has(name)) continue;
    slots.push({ key: name, value: m[2], value_type: "float" });
  }

  return slots;
}

export function extractConditions(text: string): Condition[] {
  const out: Condition[] = [];
  for (const m of text.matchAll(THRESHOLD_PATTERN)) {
    const opWord = m[1].toLowerCase().replace(/s$/, "");
    let salOp = THRESHOLD_OP_MAP[opWord] ?? ">";
    if (salOp === ">" && ["below", "under", "less than", "lower than"].includes(opWord)) {
      salOp = "<";
    }
    out.push({ operator: salOp, value: m[2] });
  }
  return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// TARGET EXTRACTOR
// ─────────────────────────────────────────────────────────────────────────────

const ENTITY_PATTERN = /\b(drone|node|patient|sensor|vehicle|vessel|gateway|turbine|server|valve|door|agent|host|relay|gate|building|cluster|peer|robot|station|tank|reactor)\s+([\w-]+)/gi;
const ACTION_VERB_OBJECT_PATTERN = /\b(stop|close|open|lock|unlock|kill|reboot|restart|shutdown|start|halt)\s+(?:the\s+)?(\w+)/gi;
const PREP_TARGET_PATTERN = /(?<!\w)(?:on|at|to|@)\s+(?:the\s+)?([\w-]+)/gi;

const TARGET_BLOCKLIST = new Set<string>([
  "the", "a", "an", "and", "or", "but", "is", "are",
  "coordinates", "position", "heading", "feedback", "control",
  "context", "service", "system", "midnight", "noon", "tonight",
  "home", "base", "this", "that", "it", "them", "me", "us",
  "temperature", "humidity", "pressure", "pneumothorax",
  "status", "uptime", "health", "french", "spanish", "german",
  "pizza", "burger", "paris", "jazz", "milk",
  "flashlight", "camera", "speaker", "microphone",
  "haptic", "vibration", "screen", "display",
  "pump", "valve", "door", "fan",
  "conveyor", "engine", "motor", "lamp", "light",
  "message", "payload", "data", "request", "response",
]);

export function extractTargets(text: string): Target[] {
  const out: Target[] = [];
  const seen = new Set<string>();

  // Priority 1: structured entity
  for (const m of text.matchAll(ENTITY_PATTERN)) {
    const kind = m[1].toLowerCase();
    const eid = m[2].toUpperCase();
    const isId = (
      /^\d+$/.test(eid) ||
      /\d/.test(eid) ||
      (/^[A-Z]+$/.test(eid) && eid.length >= 3 && !TARGET_BLOCKLIST.has(eid.toLowerCase()))
    );
    if (!isId) continue;
    let tid: string;
    if (["drone", "vehicle", "vessel", "uav", "patient"].includes(kind)) {
      tid = `${kind.toUpperCase()}${eid}`;
    } else {
      tid = eid;
    }
    if (!seen.has(tid)) {
      out.push({ id: tid, kind, source: "entity" });
      seen.add(tid);
    }
  }

  // Priority 2: action-verb + bare noun
  for (const m of text.matchAll(ACTION_VERB_OBJECT_PATTERN)) {
    const obj = m[2].toUpperCase();
    if (TARGET_BLOCKLIST.has(obj.toLowerCase())) continue;
    if (!seen.has(obj)) {
      out.push({ id: obj, kind: "object", source: "action_verb" });
      seen.add(obj);
    }
  }

  // Priority 3: prepositional
  for (const m of text.matchAll(PREP_TARGET_PATTERN)) {
    const t = m[1].toUpperCase();
    if (TARGET_BLOCKLIST.has(t.toLowerCase())) continue;
    if (!seen.has(t)) {
      out.push({ id: t, kind: "prep", source: "preposition" });
      seen.add(t);
    }
  }

  return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// DOMAIN HINT
// ─────────────────────────────────────────────────────────────────────────────

const DOMAIN_KEYWORDS: Record<string, Set<string>> = {
  medical: new Set(["patient", "vitals", "heart", "blood", "pressure", "spo2",
    "oxygen", "pulse", "icd", "diagnosis", "casualty", "pneumothorax"]),
  uav: new Set(["drone", "uav", "swarm", "rtb", "altitude", "wedge", "formation"]),
  weather: new Set(["wind", "barometric", "pressure", "humidity", "temperature",
    "rain", "storm", "atmospheric"]),
  device_control: new Set(["conveyor", "valve", "pump", "door", "lock", "lights",
    "fan", "motor", "engine", "actuator"]),
  meshtastic: new Set(["node", "peer", "relay", "broadcast", "ping", "mesh",
    "channel", "rebroadcast"]),
  crypto: new Set(["encrypt", "decrypt", "sign", "hash", "key", "keypair",
    "signature", "tls", "aes"]),
  config: new Set(["config", "configuration", "settings", "threshold",
    "parameter", "setup", "preferences"]),
  vehicle: new Set(["vehicle", "vessel", "ship", "fleet", "ais", "boat"]),
  sensor: new Set(["sensor", "humidity", "moisture", "air quality", "vibration"]),
};

const DOMAIN_TO_NS: Record<string, string[]> = {
  medical: ["H", "I", "U"],
  uav: ["V", "R", "G", "I"],
  weather: ["W", "E"],
  device_control: ["R", "C"],
  meshtastic: ["N", "O", "A", "G"],
  crypto: ["S", "I"],
  config: ["N", "T"],
  vehicle: ["V", "G"],
  sensor: ["E"],
};

export function detectDomain(text: string): { domain: string | null; nsHints: string[] } {
  const low = text.toLowerCase();
  const tokens = new Set(low.split(/\s+/));
  const scores: Record<string, number> = {};
  for (const [domain, kws] of Object.entries(DOMAIN_KEYWORDS)) {
    let s = 0;
    for (const kw of kws) {
      if (tokens.has(kw) || low.includes(kw)) s += 1;
    }
    scores[domain] = s;
  }
  const entries = Object.entries(scores);
  const max = entries.reduce((a, b) => (a[1] >= b[1] ? a : b), ["", 0])[1];
  if (max === 0) return { domain: null, nsHints: [] };
  const best = entries.find(([_, s]) => s === max)?.[0] ?? null;
  return { domain: best, nsHints: best ? DOMAIN_TO_NS[best] ?? [] : [] };
}

// ─────────────────────────────────────────────────────────────────────────────
// CHAIN DETECTION
// ─────────────────────────────────────────────────────────────────────────────

const CHAIN_PATTERNS: Array<[RegExp, string]> = [
  [/,\s+then\s+/i, ";"],
  [/,\s+and\s+then\s+/i, ";"],
  [/\s+then\s+/i, ";"],
  [/,\s+and\s+/i, "\u2227"],
  [/\s+and\s+/i, "\u2227"],
];

export function splitChain(text: string): { segments: string[]; operator: string | null } {
  const low = text.toLowerCase();
  if (low.includes(" if ") || low.startsWith("if ")) {
    return { segments: [text], operator: null };
  }
  for (const [pattern, op] of CHAIN_PATTERNS) {
    const segs = text.split(pattern);
    if (segs.length >= 2) {
      const cleaned = segs.map((s) => s.trim().replace(/[.,;]+$/, "")).filter((s) => s);
      if (cleaned.length >= 2) {
        return { segments: cleaned, operator: op };
      }
    }
  }
  return { segments: [text], operator: null };
}

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

export function lemmatize(word: string): string {
  const w = word.toLowerCase();
  if (w in VERB_LEXICON) return w;
  if (w in INFLECTIONS) return INFLECTIONS[w];
  for (const suffix of ["ing", "ed", "es", "s"]) {
    if (w.endsWith(suffix) && w.length > suffix.length + 2) {
      const stem = w.slice(0, -suffix.length);
      if (stem in VERB_LEXICON) return stem;
    }
  }
  return w;
}

export function tokenize(text: string): string[] {
  const cleaned = text.toLowerCase();
  const out: string[] = [];
  for (const raw of cleaned.split(/\s+/)) {
    const word = raw.replace(/^[^\w.-]+|[^\w.-]+$/g, "");
    if (word) out.push(word);
  }
  return out;
}

export function findVerbHead(tokens: string[]): { token: string; lemma: string } | null {
  for (const tok of tokens) {
    if (STOPWORDS.has(tok)) continue;
    const lemma = lemmatize(tok);
    if (lemma in VERB_LEXICON) return { token: tok, lemma };
  }
  return null;
}

export function detectAuthorization(text: string): boolean {
  return AUTH_MARKERS.some((p) => p.test(text));
}

export function detectEmergency(text: string): boolean {
  const low = text.toLowerCase();
  for (const m of EMERGENCY_MARKERS) if (low.includes(m)) return true;
  return false;
}

export function detectBroadcast(text: string): boolean {
  const low = text.toLowerCase();
  for (const m of BROADCAST_MARKERS) if (low.includes(m)) return true;
  return false;
}

export function detectQuery(text: string, verbLemma: string | null): boolean {
  if (text.trim().endsWith("?")) return true;
  const low = text.toLowerCase();
  for (const m of QUERY_MARKERS) if (low.includes(m)) return true;
  if (verbLemma && verbLemma in VERB_LEXICON) {
    const info = VERB_LEXICON[verbLemma];
    if (info.is_query) return true;
    if (info.is_wrapper && ["report", "show", "give", "fetch", "retrieve", "read", "what", "where"].includes(verbLemma)) {
      return true;
    }
  }
  return false;
}

export function detectNegation(text: string): boolean {
  return NEGATION_MARKERS.some((p) => p.test(text));
}

export function detectGlyphInjection(text: string): boolean {
  if (/\b[A-Z\u03a9]:[A-Z][A-Z0-9_]*\b/.test(text)) return true;
  return false;
}

export function detectCodeInjection(text: string): boolean {
  return INJECTION_MARKERS.some((p) => p.test(text));
}

export function detectEmail(text: string): boolean {
  return EMAIL_PATTERN.test(text);
}

export function detectIdiom(verbLemma: string | null, raw: string): boolean {
  if (!verbLemma) return false;
  const low = raw.toLowerCase();
  const tokens = low.split(/\s+/);
  const idx = tokens.indexOf(verbLemma);
  if (idx >= 0 && idx + 1 < tokens.length) {
    const next = tokens[idx + 1].replace(/[.,!?]/g, "");
    if (IDIOM_PARTICLE_AFTER_VERB.has(`${verbLemma}|${next}`)) return true;
  }
  for (let i = 0; i < tokens.length; i++) {
    const clean = tokens[i].replace(/[.,!?']/g, "");
    if (clean.startsWith(verbLemma) && i + 1 < tokens.length) {
      const next = tokens[i + 1].replace(/[.,!?]/g, "");
      if (IDIOM_PARTICLE_AFTER_VERB.has(`${verbLemma}|${next}`)) return true;
    }
  }
  return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// DIRECT OBJECT
// ─────────────────────────────────────────────────────────────────────────────

const DOBJ_KIND_MAP: Record<string, string> = {
  drone: "drone", uav: "drone", node: "node", sensor: "sensor",
  patient: "patient", vehicle: "vehicle", vessel: "vehicle",
  gateway: "gateway", valve: "actuator", door: "actuator",
  pump: "actuator", conveyor: "actuator", camera: "peripheral",
  microphone: "peripheral", speaker: "peripheral", flashlight: "peripheral",
  torch: "peripheral", haptic: "peripheral",
  payment: "transaction", key: "crypto_key",
  temperature: "sensor_value", humidity: "sensor_value",
  pressure: "sensor_value",
  oxygen: "vital", vitals: "vital",
  config: "config", threshold: "config",
};

export function findDirectObject(tokens: string[], verbIdx: number): { obj: string | null; kind: string | null } {
  let after = tokens.slice(verbIdx + 1);
  // Skip particle/preposition completing multi-word verb
  if (after.length > 0 && ["on", "off", "up", "down", "in", "out"].includes(after[0])) {
    after = after.slice(1);
  }
  // Skip articles
  while (after.length > 0 && ["the", "a", "an", "my", "your"].includes(after[0])) {
    after = after.slice(1);
  }
  if (after.length === 0) return { obj: null, kind: null };
  let obj = after[0];
  if (after.length >= 2) {
    const cand = `${obj} ${after[1]}`;
    if (["drone", "node", "sensor", "patient", "vehicle", "vessel", "gateway",
         "valve", "door", "agent", "key", "blood", "heart", "oxygen"].includes(obj)) {
      obj = cand;
    }
  }
  const first = obj.split(/\s+/)[0];
  const kind = DOBJ_KIND_MAP[first] ?? DOBJ_KIND_MAP[obj] ?? null;
  return { obj, kind };
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN PARSE
// ─────────────────────────────────────────────────────────────────────────────

export function parse(nl: string): ParsedRequest {
  const raw = nl.trim();
  const { segments, operator: chainOp } = splitChain(raw);
  if (segments.length > 1) {
    const subRequests = segments.map((s) => parse(s));
    const whole = parseSingle(raw);
    return {
      ...whole,
      chain_segments: subRequests,
      chain_operator: chainOp,
    };
  }
  return parseSingle(raw);
}

function parseSingle(nl: string): ParsedRequest {
  const raw = nl.trim();
  const tokens = tokenize(raw);

  const verbInfo = findVerbHead(tokens);
  const verbRaw = verbInfo?.token ?? null;
  const verbLemma = verbInfo?.lemma ?? null;
  const verbIdx = verbRaw ? tokens.indexOf(verbRaw) : -1;

  let directObject: string | null = null;
  let dobjKind: string | null = null;
  if (verbIdx >= 0) {
    const r = findDirectObject(tokens, verbIdx);
    directObject = r.obj;
    dobjKind = r.kind;
  }

  const isAuthorized = detectAuthorization(raw);
  const isEmergency = detectEmergency(raw);
  const isBroadcast = detectBroadcast(raw);
  const isQuery = detectQuery(raw, verbLemma);
  const isNegated = detectNegation(raw);
  const hasGlyphInjection = (
    detectGlyphInjection(raw) ||
    detectCodeInjection(raw) ||
    detectEmail(raw) ||
    detectIdiom(verbLemma, raw)
  );

  const slots = extractSlots(raw);
  let scheduleValue: string | null = null;
  for (const sv of slots) {
    if (sv.value_type === "duration" || sv.value_type === "time") {
      scheduleValue = sv.value;
      break;
    }
  }

  const conditions = extractConditions(raw);
  const targets = extractTargets(raw);

  const { domain, nsHints } = detectDomain(raw);
  const allHints = [...nsHints];
  if (verbLemma && verbLemma in VERB_LEXICON) {
    for (const ns of VERB_LEXICON[verbLemma].ns_hints) {
      if (!allHints.includes(ns)) allHints.push(ns);
    }
  }

  const isPassthrough = !verbInfo && slots.length === 0 && targets.length === 0;

  const req = emptyParsedRequest(raw);
  req.verb = verbRaw;
  req.verb_lemma = verbLemma;
  req.direct_object = directObject;
  req.direct_object_kind = dobjKind;
  req.targets = targets;
  req.slot_values = slots;
  req.conditions = conditions;
  req.schedule = scheduleValue;
  req.authorization_required = isAuthorized;
  req.is_emergency = isEmergency;
  req.is_broadcast = isBroadcast;
  req.is_query = isQuery;
  req.is_passthrough_likely = isPassthrough;
  req.is_negated = isNegated;
  req.has_glyph_injection = hasGlyphInjection;
  req.namespace_hints = allHints;
  req.domain_hint = domain;
  return req;
}
