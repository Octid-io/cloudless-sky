package osmp

// ─────────────────────────────────────────────────────────────────────────────
// v16 NAMESPACE STRUCTURE — 33 active namespaces
//
//   - 20 cleanly-converged 3c primaries
//   - 9 refactored splits across 4 v15 letters: C/D/K/Q
//   - 3 v15 namespaces locked at 2c form: I→ID, V→VT, X→EP
//   - 1 sovereign extension: Ω
//
// v15 single-letter forms are PRESERVED as deprecated siblings.
// NewASD loads BOTH v15 letters AND v16 primaries into the data map so
// wire-format lookups resolve under either form.
//
// Cross-SDK byte-identical with Python ASD_BASIS_V16 and TypeScript ASD_BASIS_V16.
// ─────────────────────────────────────────────────────────────────────────────

// ASDV15ToV16 maps each v15 single-letter namespace to its v16 primary
// (single-element slice for direct mapping) or split set (multi-element
// slice for the four split letters C/D/K/Q).
var ASDV15ToV16 = map[string][]string{
	"A": {"AGT"},
	"B": {"BLD"},
	"C": {"CMP", "RES"},
	"D": {"DAT", "QRY", "XFR"},
	"E": {"ENV"},
	"F": {"FED"},
	"G": {"GEO"},
	"H": {"HLT"},
	"I": {"ID"},
	"J": {"CES"},
	"K": {"FIN", "TXN"},
	"L": {"LOG"},
	"M": {"MUN"},
	"N": {"NET"},
	"O": {"OPE"},
	"P": {"PRO"},
	"Q": {"QLT", "EVL", "GND"},
	"R": {"ROB"},
	"S": {"SEC"},
	"T": {"TIM"},
	"U": {"USR"},
	"V": {"VT"},
	"W": {"WEA"},
	"X": {"EP"},
	"Y": {"MEM"},
	"Z": {"INF"},
	"Ω": {"Ω"},
}

// BridgeSplitDisambiguation maps v15_letter -> opcode -> v16_primary for
// the four split letters. Opcodes outside these sets fall to NL_PASSTHROUGH
// at the composer.
//
// The Q namespace additionally defaults unmatched opcodes to QLT — that
// fallback is applied in buildASDBasisV16() below.
var BridgeSplitDisambiguation = map[string]map[string]string{
	"C": {
		// C -> CMP: process / compute lifecycle
		"ALLOC":  "CMP",
		"FREE":   "CMP",
		"KILL":   "CMP",
		"CHKPT":  "CMP",
		"MIGRT":  "CMP",
		"PAUSE":  "CMP",
		"PRTY":   "CMP",
		"RESUME": "CMP",
		"RSTRT":  "CMP",
		"SCALE":  "CMP",
		"SPAWN":  "CMP",
		// C -> RES: resource constraints / status
		"QUOTA": "RES",
		"LIMIT": "RES",
		"STAT":  "RES",
	},
	"D": {
		// D -> DAT: data records / storage encoding
		"DEL":    "DAT",
		"LOG":    "DAT",
		"PACK":   "DAT",
		"UNPACK": "DAT",
		// D -> QRY: query / search
		"Q": "QRY",
		// D -> XFR: transfer lifecycle
		"CHUNK":  "XFR",
		"PUSH":   "XFR",
		"PULL":   "XFR",
		"FEED":   "XFR",
		"ABORT":  "XFR",
		"CSUM":   "XFR",
		// Same opcode name resolves differently by namespace context
		// (D:RESUME -> XFR; C:RESUME -> CMP).
		"RESUME": "XFR",
		"RTN":    "XFR",
		"STAT":   "XFR",
		"XFER":   "XFR",
	},
	"K": {
		// K -> FIN: financial instrument / asset class
		"DIG": "FIN",
		// K -> TXN: transaction
		"TRD": "TXN",
		"PAY": "TXN",
		"XFR": "TXN",
		"ORD": "TXN",
	},
	"Q": {
		// Q -> EVL: evaluation / metrics
		"SCORE": "EVL",
		"BENCH": "EVL",
		// Q -> GND: groundedness / citation
		"CITE":   "GND",
		"GROUND": "GND",
		// All other Q opcodes fall to QLT per default rule (applied below).
	},
}

// buildASDBasisV16 constructs the v16-keyed ASD basis from the ASDFloorBasis
// map (defined in glyphs.go) via the v15->v16 sibling map and the split
// disambiguation rules.
//
// For non-split letters, the entire opcode dict is migrated to the v16
// primary key (a copy, not a shared reference).
//
// For split letters (C/D/K/Q), opcodes are partitioned into v16 split
// namespaces per BridgeSplitDisambiguation. Opcodes not in any split's
// rule set remain in ASDFloorBasis under the v15 letter (deprecated sibling
// path) and are NOT mirrored to any v16 primary.
//
// The Q namespace applies a default-to-QLT rule for unmapped opcodes.
func buildASDBasisV16() map[string]map[string]string {
	v16 := map[string]map[string]string{}
	for v15Letter, targets := range ASDV15ToV16 {
		opcodes, ok := ASDFloorBasis[v15Letter]
		if !ok {
			continue
		}
		if len(targets) == 1 {
			// Single mapping (or sovereign Ω): copy entire opcode dict.
			cp := map[string]string{}
			for k, v := range opcodes {
				cp[k] = v
			}
			v16[targets[0]] = cp
		} else {
			// Split letter: partition opcodes per disambiguation table.
			disamb := BridgeSplitDisambiguation[v15Letter]
			for _, split := range targets {
				if _, exists := v16[split]; !exists {
					v16[split] = map[string]string{}
				}
			}
			for op, defn := range opcodes {
				v16Target, ok := disamb[op]
				if !ok {
					// Orphan opcode: stays v15-only.
					// Q applies default-to-QLT below; other splits do not.
					continue
				}
				v16[v16Target][op] = defn
			}
		}
	}
	// Apply Q's default-to-QLT fallback.
	if qOpcodes, ok := ASDFloorBasis["Q"]; ok {
		qDisamb := BridgeSplitDisambiguation["Q"]
		if _, exists := v16["QLT"]; !exists {
			v16["QLT"] = map[string]string{}
		}
		for op, defn := range qOpcodes {
			if _, mapped := qDisamb[op]; !mapped {
				v16["QLT"][op] = defn
			}
		}
	}
	return v16
}

// ASDBasisV16 is the v16-keyed ASD basis built at package load. Cross-SDK
// byte-identical with Python ASD_BASIS_V16 and TypeScript ASD_BASIS_V16.
var ASDBasisV16 = buildASDBasisV16()

// DisambiguateToV16 resolves a (namespace, opcode) pair to its v16 primary
// namespace.
//
// Returns:
//   - The v16 primary namespace string for known mappings (e.g.,
//     ("A", "ACK") -> "AGT"; ("C", "ALLOC") -> "CMP"; ("D", "STAT") -> "XFR").
//   - The input namespace itself if it is already a v16 primary.
//   - Empty string if the namespace is unknown or the opcode is an orphan
//     under a split letter that has no rule for it.
//
// The Q namespace's default-to-QLT rule for unmapped opcodes is applied here.
//
// Cross-SDK byte-identical with Python disambiguate_to_v16 and TypeScript
// disambiguateToV16.
func DisambiguateToV16(namespace, opcode string) string {
	// Already a v16 primary? Pass through.
	if _, ok := ASDBasisV16[namespace]; ok {
		return namespace
	}
	targets, ok := ASDV15ToV16[namespace]
	if !ok {
		return ""
	}
	if len(targets) == 1 {
		return targets[0]
	}
	disamb := BridgeSplitDisambiguation[namespace]
	if v16Target, ok := disamb[opcode]; ok {
		return v16Target
	}
	// Q applies default-to-QLT for unmapped opcodes.
	if namespace == "Q" {
		return "QLT"
	}
	// Other split letters (C, D, K) without a rule: orphan — no v16 home.
	return ""
}
