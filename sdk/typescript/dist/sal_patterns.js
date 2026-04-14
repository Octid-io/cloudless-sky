/**
 * OSMP SAL Regex Building Blocks
 *
 * Single source of truth for the namespace and opcode character classes used
 * across the validator (Rule 4) and the regulatory_dependency parser (Rule 8).
 *
 * The § glyph is the human-authorization presence marker (I:§) and must be
 * accepted as a valid opcode character; any regex that excludes it would
 * silently miss frames involving I:§ and break dependency rules that
 * reference human authorization as a precondition.
 *
 * Mirrors the Python `_NS_PATTERN` and `_OPCODE_PATTERN` constants in
 * `osmp/protocol.py` and the Go `nsPattern` / `opcodePattern` constants in
 * `sdk/go/osmp/sal_patterns.go`.
 *
 * Patent pending -- inventor Clay Holberg
 * License: Apache 2.0
 */
// Tier 1 (single char) and Tier 2 (two char) namespaces
export const NS_PATTERN = "[A-Z]{1,2}";
// Opcode body — includes § for I:§ (human authorization presence marker)
export const OPCODE_PATTERN = "[A-Z§][A-Z0-9§]*";
// Operators that split compound SAL instructions into frames
export const FRAME_SPLIT_RE = /([→∧∨↔∥;])/;
// Pattern matching namespace:opcode after @ (prohibited: namespace-as-target)
export const NS_TARGET_RE = new RegExp(`@(${NS_PATTERN}):(${OPCODE_PATTERN})`, "g");
// Pattern extracting namespace:opcode from a SAL frame
export const FRAME_NS_OP_RE = new RegExp(`^(${NS_PATTERN}):(${OPCODE_PATTERN})`);
// Pattern for prerequisite expressions: NS:OPCODE or NS:OPCODE[SLOT]
export const PREREQ_RE = new RegExp(`(${NS_PATTERN}):(${OPCODE_PATTERN})(?:\\[([^\\]]+)\\])?`);
// Chain frame extraction: captures bracket [VAL] and colon :VAL notation
export const CHAIN_FRAME_RE = new RegExp(`(${NS_PATTERN}):(${OPCODE_PATTERN})(?:\\[([^\\]]+)\\]|:([A-Z0-9][A-Z0-9_.]+))?`, "g");
// Pattern detecting SAL frames embedded in natural language (used by SALBridge).
// Uses a leading word boundary and relies on the greedy opcode pattern to
// absorb the full opcode body. No trailing boundary because § (the human-
// authorization marker) is a Unicode non-word character that breaks symmetric
// \b matching. This approach is cross-SDK identical: Python re, JavaScript,
// and Go RE2 all behave the same way for this regex.
export const SAL_FRAME_RE_BRIDGE = new RegExp(`\\b(${NS_PATTERN}):(${OPCODE_PATTERN})`, "g");
//# sourceMappingURL=sal_patterns.js.map