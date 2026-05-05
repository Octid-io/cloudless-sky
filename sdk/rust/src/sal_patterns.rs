// License: Apache-2.0
//! OSMP SAL Regex Building Blocks.
//!
//! Single source of truth for the namespace and opcode character classes used
//! across the validator (Rule 4) and the regulatory_dependency parser (Rule 8).
//!
//! The § glyph is the human-authorization presence marker (`I:§`) and must be
//! accepted as a valid opcode character; any regex that excludes it would
//! silently miss frames involving `I:§` and break dependency rules that
//! reference human authorization as a precondition.
//!
//! Mirrors the Python `_NS_PATTERN` / `_OPCODE_PATTERN` constants in
//! `sdk/python/osmp/protocol.py`, the Go `nsPattern` / `opcodePattern`
//! constants in `sdk/go/osmp/sal_patterns.go`, and the TypeScript
//! `NS_PATTERN` / `OPCODE_PATTERN` constants in
//! `sdk/typescript/src/sal_patterns.ts`.

use std::sync::OnceLock;

use regex::Regex;

/// Tier 1 (single char) and Tier 2 (two char) namespaces.
pub const NS_PATTERN: &str = "[A-Z]{1,2}";

/// Opcode body — includes § for `I:§` (human authorization presence marker).
pub const OPCODE_PATTERN: &str = "[A-Z\u{00A7}][A-Z0-9\u{00A7}]*";

/// Operators that split compound SAL instructions into frames.
///
/// Cross-SDK byte-identical with Python `_FRAME_SPLIT_RE`, Go
/// `salFrameSplitRe`, TypeScript `FRAME_SPLIT_RE`.
pub fn frame_split_re() -> &'static Regex {
    static CACHE: OnceLock<Regex> = OnceLock::new();
    CACHE.get_or_init(|| {
        Regex::new(r"(\->|[\u{2192}\u{2227}\u{2228}\u{2194}\u{2225};])")
            .expect("frame_split_re must compile")
    })
}

/// Pattern matching `namespace:opcode` after `@` (prohibited:
/// namespace-as-target). Cross-SDK byte-identical with Python
/// `_NS_TARGET_RE`, Go `salNsTargetRe`, TypeScript `NS_TARGET_RE`.
pub fn ns_target_re() -> &'static Regex {
    static CACHE: OnceLock<Regex> = OnceLock::new();
    CACHE.get_or_init(|| {
        let pat = format!("@({}):({})", NS_PATTERN, OPCODE_PATTERN);
        Regex::new(&pat).expect("ns_target_re must compile")
    })
}

/// Pattern extracting `namespace:opcode` from the head of a SAL frame.
///
/// Cross-SDK byte-identical with Python `_FRAME_NS_OP_RE`, Go
/// `salFrameNsOpRe`, TypeScript `FRAME_NS_OP_RE`.
pub fn frame_ns_op_re() -> &'static Regex {
    static CACHE: OnceLock<Regex> = OnceLock::new();
    CACHE.get_or_init(|| {
        let pat = format!("^({}):({})", NS_PATTERN, OPCODE_PATTERN);
        Regex::new(&pat).expect("frame_ns_op_re must compile")
    })
}

/// Pattern detecting SAL frames embedded in natural language.
///
/// Used by the `SALBridge` outbound translator. Uses a leading word boundary
/// and relies on the greedy opcode pattern to absorb the full opcode body.
/// No trailing boundary because § (the human-authorization marker) is a
/// Unicode non-word character that breaks symmetric `\b` matching. This
/// approach is cross-SDK identical: Python `re`, JavaScript, and Go RE2 all
/// behave the same way.
///
/// Cross-SDK byte-identical with Python `_SAL_FRAME_RE_BRIDGE`, Go
/// `salBridgeFrameRe`, TypeScript `SAL_FRAME_RE_BRIDGE`.
pub fn sal_frame_re_bridge() -> &'static Regex {
    static CACHE: OnceLock<Regex> = OnceLock::new();
    CACHE.get_or_init(|| {
        let pat = format!(r"\b({}):({})", NS_PATTERN, OPCODE_PATTERN);
        Regex::new(&pat).expect("sal_frame_re_bridge must compile")
    })
}

/// Pattern for prerequisite expressions: `NS:OPCODE` or `NS:OPCODE[SLOT]`.
///
/// Cross-SDK byte-identical with Python `_PREREQ_RE`, Go `salPrereqRe`,
/// TypeScript `PREREQ_RE`.
pub fn prereq_re() -> &'static Regex {
    static CACHE: OnceLock<Regex> = OnceLock::new();
    CACHE.get_or_init(|| {
        let pat = format!(
            r"({}):({})(?:\[([^\]]+)\])?",
            NS_PATTERN, OPCODE_PATTERN,
        );
        Regex::new(&pat).expect("prereq_re must compile")
    })
}

/// Chain frame extraction: captures bracket `[VAL]` and colon `:VAL` notation.
///
/// Cross-SDK byte-identical with Python `_CHAIN_FRAME_RE`, Go
/// `salChainFrameRe`, TypeScript `CHAIN_FRAME_RE`.
pub fn chain_frame_re() -> &'static Regex {
    static CACHE: OnceLock<Regex> = OnceLock::new();
    CACHE.get_or_init(|| {
        let pat = format!(
            r"({}):({})(?:\[([^\]]+)\]|:([A-Z0-9][A-Z0-9_.]+))?",
            NS_PATTERN, OPCODE_PATTERN,
        );
        Regex::new(&pat).expect("chain_frame_re must compile")
    })
}
