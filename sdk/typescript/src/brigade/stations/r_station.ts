/** R-station — Robotic / Physical Agent. Faithful TS port. */
import type { FrameProposal, ParsedRequest, SlotValue } from "../request.js";
import { makeProposal } from "../request.js";
import type { Station } from "./base.js";

const VERB_TO_OPCODE: Record<string, string> = {
  stop: "STOP", halt: "STOP", cease: "STOP", block: "STOP",
  close: "STOP", lock: "STOP",
  move: "MOV", go: "MOV", navigate: "MOV", fly: "MOV",
  return: "RTH", rtb: "RTH", rth: "RTH",
};

const PERIPHERAL_OBJECT_TO_OPCODE: Record<string, string> = {
  camera: "CAM", microphone: "MIC", speaker: "SPKR",
  flashlight: "TORCH", torch: "TORCH",
  haptic: "HAPTIC", vibration: "VIBE",
  wifi: "WIFI", bluetooth: "BT", gps: "GPS",
  screen: "DISP", display: "DISP", accelerometer: "ACCEL",
};

const PERIPHERAL_VERBS = new Set(["turn", "activate", "enable", "engage", "start"]);

function pickTarget(req: ParsedRequest): string | null {
  if (req.is_broadcast && req.targets.length === 0) return "*";
  for (const t of req.targets) if (t.source === "entity") return t.id;
  for (const t of req.targets) if (t.source === "action_verb") return t.id;
  if (req.targets.length > 0) return req.targets[0].id;
  return null;
}

function slotsForOpcode(opcode: string, req: ParsedRequest): SlotValue[] {
  if (opcode === "MOV") {
    for (const sv of req.slot_values) {
      if (sv.value_type === "latlon") {
        return [{ key: "", value: sv.value, value_type: "latlon" }];
      }
    }
    for (const sv of req.slot_values) {
      if (sv.key === "formation" || sv.key === "spacing") return [sv];
    }
  }
  return [];
}

export class RStation implements Station {
  namespace = "R";

  propose(req: ParsedRequest): FrameProposal[] {
    const proposals: FrameProposal[] = [];
    const rawLow = req.raw.toLowerCase();

    // Emergency override: R:ESTOP
    const emergencyVerbs = new Set([null, "stop", "halt", "cease", "block", "kill", "shutdown", "shut"]);
    if (req.is_emergency && emergencyVerbs.has(req.verb_lemma ?? null)) {
      proposals.push(makeProposal({
        namespace: "R", opcode: "ESTOP",
        rationale: "emergency marker + stop verb (or no verb)",
      }));
      return proposals;
    }

    // Verb-to-opcode
    if (req.verb_lemma && req.verb_lemma in VERB_TO_OPCODE) {
      const opcode = VERB_TO_OPCODE[req.verb_lemma];
      proposals.push(makeProposal({
        namespace: "R", opcode,
        target: pickTarget(req),
        slot_values: slotsForOpcode(opcode, req),
        consequence_class: "\u21ba",
        rationale: `verb '${req.verb_lemma}' -> R:${opcode}`,
      }));
    }

    // Peripheral activation
    if (req.verb_lemma && PERIPHERAL_VERBS.has(req.verb_lemma) && req.direct_object) {
      const objWord = req.direct_object.toLowerCase().split(/\s+/).pop()!;
      if (objWord in PERIPHERAL_OBJECT_TO_OPCODE) {
        proposals.push(makeProposal({
          namespace: "R", opcode: PERIPHERAL_OBJECT_TO_OPCODE[objWord],
          target: pickTarget(req),
          consequence_class: "\u21ba",
          rationale: `peripheral activation '${objWord}' -> R:${PERIPHERAL_OBJECT_TO_OPCODE[objWord]}`,
        }));
      }
    }

    // Direct-object-only peripheral
    if (!req.verb_lemma && req.direct_object_kind === "peripheral" && req.direct_object) {
      const objWord = req.direct_object.toLowerCase().split(/\s+/).pop()!;
      if (objWord in PERIPHERAL_OBJECT_TO_OPCODE) {
        proposals.push(makeProposal({
          namespace: "R", opcode: PERIPHERAL_OBJECT_TO_OPCODE[objWord],
          consequence_class: "\u21ba",
          rationale: `nominal peripheral '${objWord}' -> R:${PERIPHERAL_OBJECT_TO_OPCODE[objWord]}`,
        }));
      }
    }

    // Haptic phrase
    if ((rawLow.includes("haptic feedback") || (rawLow.includes("vibrate") && proposals.length === 0))) {
      proposals.push(makeProposal({
        namespace: "R", opcode: "HAPTIC",
        consequence_class: "\u21ba",
        rationale: "haptic feedback phrase",
      }));
    }

    // RTH from any rtb/rth/return-to-base/return-home phrase
    const hasRTH = proposals.some((p) => p.opcode === "RTH");
    if (!hasRTH && (rawLow.includes("rtb") || rawLow.includes("rth")
      || rawLow.includes("return to base") || rawLow.includes("return home"))) {
      proposals.push(makeProposal({
        namespace: "R", opcode: "RTH",
        consequence_class: "\u21ba", confidence: 2.0,
        rationale: "rtb/rth/return phrase",
      }));
    }

    // FORM — swarm formation
    const shapes = ["wedge", "column", "line", "vee", "diamond", "echelon"];
    if (req.verb_lemma === "form" && (rawLow.includes("swarm") || rawLow.includes("formation")
      || shapes.some((s) => rawLow.includes(s)))) {
      const slots: SlotValue[] = [];
      for (const shape of shapes) {
        if (rawLow.includes(shape)) {
          slots.push({ key: "", value: shape, value_type: "string" });
          break;
        }
      }
      for (const sv of req.slot_values) {
        if (sv.key === "spacing") {
          slots.push({ key: "", value: sv.value, value_type: "float" });
          break;
        }
      }
      proposals.push(makeProposal({
        namespace: "R", opcode: "FORM",
        consequence_class: "\u21ba",
        slot_values: slots,
        rationale: "swarm formation",
      }));
    }

    return proposals;
  }
}
