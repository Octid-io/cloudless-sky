package osmp

import (
	"fmt"
	"regexp"
	"strings"
)

// CompositionIssue represents a single validation issue found in a composed instruction.
type CompositionIssue struct {
	Rule     string // e.g. "HALLUCINATED_OPCODE", "NAMESPACE_AS_TARGET"
	Severity string // "error" (blocks emission) or "warning" (advisory)
	Message  string
	Frame    string // the offending frame or substring
}

// CompositionResult holds the result of composition validation.
type CompositionResult struct {
	Valid    bool
	Issues   []CompositionIssue
	SAL      string
	NL       string
}

// Errors returns only issues with severity "error".
func (r *CompositionResult) Errors() []CompositionIssue {
	var out []CompositionIssue
	for _, i := range r.Issues {
		if i.Severity == "error" {
			out = append(out, i)
		}
	}
	return out
}

// Warnings returns only issues with severity "warning".
func (r *CompositionResult) Warnings() []CompositionIssue {
	var out []CompositionIssue
	for _, i := range r.Issues {
		if i.Severity == "warning" {
			out = append(out, i)
		}
	}
	return out
}

var (
	frameSplitRe  = regexp.MustCompile(`([→∧∨↔∥;])`)
	nsTargetRe    = regexp.MustCompile(`@([A-Z]{1,2}):([A-Z][A-Z0-9]+)`)
	frameNsOpRe   = regexp.MustCompile(`^([A-Z]{1,2}):([A-Z§][A-Z0-9§]*)`)
)

// ValidateComposition validates a composed SAL instruction against eight
// deterministic rules (Section 12.5 of OSMP-SPEC-v1):
//   1. Hallucination check — every opcode must exist in the ASD
//   2. Namespace-as-target — @ must not be followed by NS:OPCODE
//   3. R namespace consequence class — mandatory except R:ESTOP
//   4. I:§ precondition — ⚠ and ⊘ require I:§ in the chain
//   5. Byte check — SAL bytes must not exceed NL bytes (exception: R safety chains)
//   6. Slash rejection — / is not a SAL operator
//   7. Mixed-mode check — no natural language text embedded in SAL frames
//   8. Regulatory dependency — REQUIRES rules from MDR corpora
func ValidateComposition(sal, nl string, asd *AdaptiveSharedDictionary, rSafetyExempt bool, depRules []DependencyRule) *CompositionResult {
	if asd == nil {
		asd = NewASD()
	}

	var issues []CompositionIssue

	// ── Rule 6: Slash rejection ──────────────────────────────────────────
	if strings.Contains(sal, "/") {
		issues = append(issues, CompositionIssue{
			Rule:     "SLASH_OPERATOR",
			Severity: "error",
			Message:  "/ is not a SAL operator. Use → for THEN, ∧ for AND, ∨ for OR.",
			Frame:    sal,
		})
	}

	// ── Rule 2: Namespace-as-target ──────────────────────────────────────
	nsTargetMatches := nsTargetRe.FindAllStringSubmatch(sal, -1)
	for _, m := range nsTargetMatches {
		issues = append(issues, CompositionIssue{
			Rule:     "NAMESPACE_AS_TARGET",
			Severity: "error",
			Message:  fmt.Sprintf("@ target must be a node_id or *, not a namespace:opcode. Found @%s:%s", m[1], m[2]),
			Frame:    fmt.Sprintf("@%s:%s", m[1], m[2]),
		})
	}

	// ── Split into frames and validate each ──────────────────────────────
	parts := frameSplitRe.Split(sal, -1)
	operators := map[string]bool{"→": true, "∧": true, "∨": true, "↔": true, "∥": true, ";": true}

	var frames []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" && !operators[p] {
			frames = append(frames, p)
		}
	}

	hasRNamespace := false
	hasRHazardousOrIrreversible := false
	hasISection := false

	for _, frame := range frames {
		m := frameNsOpRe.FindStringSubmatch(frame)
		if m == nil {
			// Frame doesn't start with NS:OP pattern
			if len(frame) > 20 && strings.Contains(frame, " ") {
				trunc := frame
				if len(trunc) > 40 {
					trunc = trunc[:40] + "..."
				}
				issues = append(issues, CompositionIssue{
					Rule:     "MIXED_MODE",
					Severity: "warning",
					Message:  fmt.Sprintf("Frame appears to contain embedded natural language: '%s'", trunc),
					Frame:    frame,
				})
			}
			continue
		}

		ns := m[1]
		op := m[2]

		// ── Rule 1: Hallucination check ──────────────────────────────────
		if !(ns == "I" && op == "§") {
			def := asd.Lookup(ns, op)
			if def == "" {
				issues = append(issues, CompositionIssue{
					Rule:     "HALLUCINATED_OPCODE",
					Severity: "error",
					Message:  fmt.Sprintf("%s:%s does not exist in the Adaptive Shared Dictionary.", ns, op),
					Frame:    frame,
				})
			}
		}

		// ── Rules 3 & 4: R namespace consequence class and I:§ ───────────
		if ns == "R" {
			hasRNamespace = true
			if op != "ESTOP" {
				hasCc := strings.ContainsAny(frame, "⚠↺⊘")
				if !hasCc {
					issues = append(issues, CompositionIssue{
						Rule:     "CONSEQUENCE_CLASS_OMISSION",
						Severity: "error",
						Message:  fmt.Sprintf("R:%s requires a consequence class designator (⚠/↺/⊘). R:ESTOP is the sole exception.", op),
						Frame:    frame,
					})
				}
				if strings.ContainsRune(frame, '⚠') || strings.ContainsRune(frame, '⊘') {
					hasRHazardousOrIrreversible = true
				}
			}
		}

		if ns == "I" && op == "§" {
			hasISection = true
		}
	}

	// ── Rule 4 (chain-level): I:§ must precede ⚠/⊘ ──────────────────────
	if hasRHazardousOrIrreversible && !hasISection {
		issues = append(issues, CompositionIssue{
			Rule:     "AUTHORIZATION_OMISSION",
			Severity: "error",
			Message:  "R namespace instructions with ⚠ (HAZARDOUS) or ⊘ (IRREVERSIBLE) require I:§ as a structural precondition in the instruction chain.",
		})
	}

	// ── Rule 5: Byte check ───────────────────────────────────────────────
	if nl != "" {
		salBytes := len([]byte(sal))
		nlBytes := len([]byte(nl))
		if salBytes >= nlBytes {
			if rSafetyExempt && hasRNamespace {
				issues = append(issues, CompositionIssue{
					Rule:     "BYTE_CHECK_EXEMPT",
					Severity: "warning",
					Message:  fmt.Sprintf("SAL (%dB) >= NL (%dB). Exempt: safety-complete R namespace chain.", salBytes, nlBytes),
				})
			} else {
				issues = append(issues, CompositionIssue{
					Rule:     "BYTE_INFLATION",
					Severity: "error",
					Message:  fmt.Sprintf("SAL (%dB) >= NL (%dB). Use NL_PASSTHROUGH. BAEL compression floor guarantee violated.", salBytes, nlBytes),
				})
			}
		}
	}

	// ── Rule 8: Regulatory dependency grammar ─────────────────────────────
	if len(depRules) > 0 {
		depIssues := ValidateRegulatoryDependencies(sal, depRules)
		issues = append(issues, depIssues...)
	}

	var errors []CompositionIssue
	for _, i := range issues {
		if i.Severity == "error" {
			errors = append(errors, i)
		}
	}

	return &CompositionResult{
		Valid:  len(errors) == 0,
		Issues: issues,
		SAL:    sal,
		NL:     nl,
	}
}
