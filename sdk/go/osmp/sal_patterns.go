package osmp

// OSMP SAL Regex Building Blocks
//
// Single source of truth for the namespace and opcode character classes used
// across the validator (Rule 4) and the regulatory_dependency parser (Rule 8).
//
// The § glyph is the human-authorization presence marker (I:§) and must be
// accepted as a valid opcode character; any regex that excludes it would
// silently miss frames involving I:§ and break dependency rules that
// reference human authorization as a precondition.
//
// Mirrors the Python `_NS_PATTERN` and `_OPCODE_PATTERN` constants in
// `sdk/python/osmp/protocol.py` and the TypeScript constants in
// `sdk/typescript/src/sal_patterns.ts`.
//
// Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
// License: Apache 2.0

import "regexp"

const (
	// nsPattern matches Tier 1 (single char) and Tier 2 (two char) namespaces.
	nsPattern = `[A-Z]{1,2}`

	// opcodePattern matches an opcode body, including § for I:§ (human
	// authorization presence marker).
	opcodePattern = `[A-Z§][A-Z0-9§]*`
)

// Operators that split compound SAL instructions into frames
var salFrameSplitRe = regexp.MustCompile(`([→∧∨↔∥;])`)

// Pattern matching namespace:opcode after @ (prohibited: namespace-as-target)
var salNsTargetRe = regexp.MustCompile(`@(` + nsPattern + `):(` + opcodePattern + `)`)

// Pattern extracting namespace:opcode from a SAL frame
var salFrameNsOpRe = regexp.MustCompile(`^(` + nsPattern + `):(` + opcodePattern + `)`)

// Pattern for prerequisite expressions: NS:OPCODE or NS:OPCODE[SLOT]
var salPrereqRe = regexp.MustCompile(`(` + nsPattern + `):(` + opcodePattern + `)(?:\[([^\]]+)\])?`)

// Chain frame extraction: captures bracket [VAL] and colon :VAL notation
var salChainFrameRe = regexp.MustCompile(`(` + nsPattern + `):(` + opcodePattern + `)(?:\[([^\]]+)\]|:([A-Z0-9][A-Z0-9_.]+))?`)

// Pattern detecting SAL frames embedded in natural language (used by SALBridge).
// Uses a leading word boundary and relies on the greedy opcode pattern to
// absorb the full opcode body. No trailing boundary because § (the human-
// authorization marker) is a Unicode non-word character that breaks symmetric
// \b matching. This approach is cross-SDK identical: Python re, JavaScript,
// and Go RE2 all behave the same way for this regex.
var salBridgeFrameRe = regexp.MustCompile(`\b(` + nsPattern + `):(` + opcodePattern + `)`)

// Comprehensive frame-with-tail pattern for Finding 48 isPureSAL strip pass.
// Matches a single complete SAL frame including any @target, ?query, :slot,
// [bracket], and consequence class glyph tail. Used to strip every valid
// SAL frame from a message and check if any natural-language residue
// remains. Mirrors the Python and TypeScript versions byte-for-byte.
var salFrameWithTailRe = regexp.MustCompile(
	`\b` + nsPattern + `:` + opcodePattern +
		`(?:@[A-Za-z0-9_*\-]+)?` +
		`(?:\?[A-Za-z0-9_]+)?` +
		`(?:\[[^\]]*\])?` +
		`(?::[A-Za-z0-9_]+(?::[A-Za-z0-9_.\-]+)?)*` +
		`(?:[\x{26a0}\x{21ba}\x{2298}])?`,
)

// Chain operators, parentheses, and whitespace stripped after frames
// are removed during the Finding 48 isPureSAL residue check.
var salOperatorWhitespaceRe = regexp.MustCompile(
	`[\x{2227}\x{2228}\x{00ac}\x{2192}\x{2194}\x{2225}\x{27f3}\x{2260}\x{2295};\s()]`,
)
