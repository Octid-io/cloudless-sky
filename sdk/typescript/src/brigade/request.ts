/**
 * ParsedRequest IR — the mise en place of the brigade.
 *
 * Set up once by the grammar parser; every station reads from this
 * immutable shared structure to produce its frame proposals. No station
 * mutates it; no station reaches into another's pantry.
 *
 * Faithful TS port of sdk/python/osmp/brigade/request.py.
 */

export interface Condition {
  operator: string;       // ">", "<", ">=", "<=", "==", "!="
  value: string;
  bound_to?: string;      // the sensor/opcode the condition gates
}

export type SlotValueType =
  | "string"
  | "uint"
  | "float"
  | "code"
  | "duration"
  | "latlon"
  | "time";

export interface SlotValue {
  key: string;
  value: string;
  value_type: SlotValueType;
}

export interface Target {
  id: string;             // what goes after @
  kind: string;           // "drone", "node", "*", "patient"
  source: string;         // "entity", "preposition", "implicit"
}

export interface ParsedRequest {
  raw: string;

  // Predicate-argument structure
  verb?: string | null;
  verb_lemma?: string | null;
  direct_object?: string | null;
  direct_object_kind?: string | null;

  // Bindings
  targets: Target[];
  slot_values: SlotValue[];
  conditions: Condition[];

  // Modifiers
  schedule?: string | null;
  authorization_required: boolean;
  is_emergency: boolean;
  is_broadcast: boolean;
  is_query: boolean;
  is_passthrough_likely: boolean;
  is_negated: boolean;
  has_glyph_injection: boolean;

  // Chain structure
  chain_segments: ParsedRequest[];
  chain_operator?: string | null;

  // Hints
  namespace_hints: string[];
  domain_hint?: string | null;
}

export interface FrameProposal {
  namespace: string;
  opcode: string;
  target?: string | null;
  slot_values: SlotValue[];
  consequence_class?: string | null;
  is_query: boolean;
  confidence: number;
  rationale: string;
}

/**
 * Assemble a FrameProposal into its canonical SAL frame string.
 * Mirrors the Python FrameProposal.assemble() method.
 */
export function assembleFrame(p: FrameProposal): string {
  let s = `${p.namespace}:${p.opcode}`;
  if (p.consequence_class) s += p.consequence_class;
  if (p.target) s += `@${p.target}`;
  if (p.is_query) s += "?";
  if (p.slot_values && p.slot_values.length > 0) {
    if (
      p.slot_values.length === 1 &&
      (p.slot_values[0].key === "" || p.slot_values[0].key === "_")
    ) {
      s += `[${p.slot_values[0].value}]`;
    } else {
      const slots = p.slot_values
        .map((sv) => (sv.key ? `${sv.key}:${sv.value}` : sv.value))
        .join(",");
      s += `[${slots}]`;
    }
  }
  return s;
}

/** Default-construct a ParsedRequest with empty fields. */
export function emptyParsedRequest(raw: string): ParsedRequest {
  return {
    raw,
    targets: [],
    slot_values: [],
    conditions: [],
    authorization_required: false,
    is_emergency: false,
    is_broadcast: false,
    is_query: false,
    is_passthrough_likely: false,
    is_negated: false,
    has_glyph_injection: false,
    chain_segments: [],
    namespace_hints: [],
  };
}

/** Default-construct a FrameProposal. */
export function makeProposal(
  partial: Partial<FrameProposal> & { namespace: string; opcode: string },
): FrameProposal {
  return {
    namespace: partial.namespace,
    opcode: partial.opcode,
    target: partial.target ?? null,
    slot_values: partial.slot_values ?? [],
    consequence_class: partial.consequence_class ?? null,
    is_query: partial.is_query ?? false,
    confidence: partial.confidence ?? 1.0,
    rationale: partial.rationale ?? "",
  };
}
