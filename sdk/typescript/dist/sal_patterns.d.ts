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
export declare const NS_PATTERN = "[A-Z]{1,2}";
export declare const OPCODE_PATTERN = "[A-Z\u00A7][A-Z0-9\u00A7]*";
export declare const FRAME_SPLIT_RE: RegExp;
export declare const NS_TARGET_RE: RegExp;
export declare const FRAME_NS_OP_RE: RegExp;
export declare const PREREQ_RE: RegExp;
export declare const CHAIN_FRAME_RE: RegExp;
export declare const SAL_FRAME_RE_BRIDGE: RegExp;
