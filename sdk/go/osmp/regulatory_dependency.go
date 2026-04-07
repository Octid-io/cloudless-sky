package osmp

// Regulatory Dependency Grammar — Rule 8 for ValidateComposition
// Validates instruction chains against REQUIRES rules loaded from MDR corpora.
// Dependency rules are SAL expressions using the same glyph operators as
// the instructions they govern.
//
// Patent ref: OSMP-001-UTIL Claim 40 (pending)
// License: Apache 2.0

import (
	"fmt"
	"os"
	"strings"
)

// DependencyRule represents a single regulatory prerequisite from the MDR.
type DependencyRule struct {
	Entry       string     // e.g. "F:BVLOS[P]"
	Namespace   string     // e.g. "F"
	Opcode      string     // e.g. "BVLOS"
	SlotValue   string     // e.g. "P" or "" if no slot
	RequiresRaw string     // e.g. "REQUIRES:F:REMID[S]∨F:REMID[M]"
	Alternatives [][]string // parsed: [[prereq_pattern, ...], ...]
}

// SAL regex building blocks live in sal_patterns.go.
// Local alias preserves the existing name without changing call sites.
var prereqRe = salPrereqRe

// ParseRequiresExpression parses "REQUIRES:F:REMID[S]∧F:AV[Part107]∨F:REMID[M]" into alternatives.
// Each ∨-split alternative is further split on ∧ for conjunctive prerequisites.
// Result: [[conjunct, ...], ...] — at least ONE group where ALL conjuncts satisfied.
func ParseRequiresExpression(requires string) [][]string {
	expr := requires
	if strings.HasPrefix(expr, "REQUIRES:") {
		expr = expr[9:]
	}
	parts := strings.Split(expr, "\u2228") // ∨
	var result [][]string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		conjuncts := strings.Split(p, "\u2227") // ∧
		var group []string
		for _, c := range conjuncts {
			c = strings.TrimSpace(c)
			if c != "" {
				group = append(group, c)
			}
		}
		if len(group) > 0 {
			result = append(result, group)
		}
	}
	return result
}

// LoadMDRDependencyRules loads regulatory dependency rules from an MDR CSV.
func LoadMDRDependencyRules(mdrPath string) ([]DependencyRule, error) {
	data, err := os.ReadFile(mdrPath)
	if err != nil {
		return nil, err
	}

	var rules []DependencyRule
	lines := strings.Split(string(data), "\n")
	inSectionB := false

	for _, line := range lines {
		stripped := strings.TrimSpace(line)
		if strings.Contains(stripped, "SECTION B") {
			inSectionB = true
			continue
		}
		if strings.HasPrefix(stripped, "SECTION ") && !strings.Contains(stripped, "SECTION B") {
			if inSectionB {
				break
			}
		}
		if !inSectionB {
			continue
		}
		if stripped == "" || strings.HasPrefix(stripped, "Format:") ||
			strings.HasPrefix(stripped, "===") || strings.HasPrefix(stripped, "---") ||
			strings.HasPrefix(stripped, "Note:") || strings.HasPrefix(stripped, "Dependency rules") {
			continue
		}

		parts := strings.SplitN(stripped, ",", 8)
		if len(parts) < 5 || !strings.Contains(parts[0], ":") {
			continue
		}

		depRule := strings.TrimSpace(parts[4])
		if !strings.HasPrefix(depRule, "REQUIRES:") {
			continue
		}

		nsOp := strings.TrimSpace(parts[0])
		slotValue := strings.TrimSpace(parts[1])
		nsParts := strings.SplitN(nsOp, ":", 2)
		if len(nsParts) < 2 {
			continue
		}

		ns := nsParts[0]
		opcode := nsParts[1]
		entry := ns + ":" + opcode
		if slotValue != "" {
			entry = fmt.Sprintf("%s:%s[%s]", ns, opcode, slotValue)
		}

		rules = append(rules, DependencyRule{
			Entry:        entry,
			Namespace:    ns,
			Opcode:       opcode,
			SlotValue:    slotValue,
			RequiresRaw:  depRule,
			Alternatives: ParseRequiresExpression(depRule),
		})
	}
	return rules, nil
}

// chain frame extraction regex: captures bracket [VAL] and colon :VAL notation
// chainFrameRe aliases the shared salChainFrameRe from sal_patterns.go.
var chainFrameRe = salChainFrameRe

// ExtractChainFrames extracts all frames from a SAL instruction chain.
// Returns (frames with slots normalized to bracket notation, bare opcodes).
func ExtractChainFrames(sal string) (map[string]bool, map[string]bool) {
	frames := map[string]bool{}
	opcodes := map[string]bool{}

	for _, m := range chainFrameRe.FindAllStringSubmatch(sal, -1) {
		ns, opcode := m[1], m[2]
		bracketVal, colonVal := m[3], m[4]
		opcodes[ns+":"+opcode] = true
		val := bracketVal
		if val == "" {
			val = colonVal
		}
		if val != "" {
			frames[fmt.Sprintf("%s:%s[%s]", ns, opcode, val)] = true
		}
	}
	return frames, opcodes
}

func prereqSatisfied(pattern string, frames, opcodes map[string]bool) bool {
	m := prereqRe.FindStringSubmatch(pattern)
	if m == nil {
		return false
	}
	ns, opcode, slot := m[1], m[2], m[3]
	if slot != "" {
		return frames[fmt.Sprintf("%s:%s[%s]", ns, opcode, slot)]
	}
	return opcodes[ns+":"+opcode]
}

func checkAlternatives(alts [][]string, frames, opcodes map[string]bool) bool {
	for _, group := range alts {
		allSatisfied := true
		for _, prereq := range group {
			if !prereqSatisfied(prereq, frames, opcodes) {
				allSatisfied = false
				break
			}
		}
		if allSatisfied {
			return true
		}
	}
	return false
}

// ValidateRegulatoryDependencies checks an instruction chain against MDR
// dependency rules. Returns CompositionIssue list (empty if all satisfied).
func ValidateRegulatoryDependencies(sal string, rules []DependencyRule) []CompositionIssue {
	if len(rules) == 0 {
		return nil
	}

	frames, opcodes := ExtractChainFrames(sal)

	// Build lookup
	lookup := map[string]*DependencyRule{}
	for i := range rules {
		lookup[rules[i].Entry] = &rules[i]
		if rules[i].SlotValue == "" {
			lookup[rules[i].Namespace+":"+rules[i].Opcode] = &rules[i]
		}
	}

	var issues []CompositionIssue

	for frame := range frames {
		if rule, ok := lookup[frame]; ok {
			if !checkAlternatives(rule.Alternatives, frames, opcodes) {
				reqDisplay := strings.TrimPrefix(rule.RequiresRaw, "REQUIRES:")
				issues = append(issues, CompositionIssue{
					Rule:     "REGULATORY_DEPENDENCY",
					Severity: "error",
					Message: fmt.Sprintf(
						"%s requires %s as a regulatory prerequisite. "+
							"The prerequisite is absent from the instruction chain.",
						rule.Entry, reqDisplay),
					Frame: rule.Entry,
				})
			}
		}
	}

	for bare := range opcodes {
		if _, inFrames := frames[bare]; inFrames {
			continue
		}
		if rule, ok := lookup[bare]; ok {
			if rule.SlotValue != "" {
				continue
			}
			if !checkAlternatives(rule.Alternatives, frames, opcodes) {
				reqDisplay := strings.TrimPrefix(rule.RequiresRaw, "REQUIRES:")
				issues = append(issues, CompositionIssue{
					Rule:     "REGULATORY_DEPENDENCY",
					Severity: "error",
					Message: fmt.Sprintf(
						"%s requires %s as a regulatory prerequisite. "+
							"The prerequisite is absent from the instruction chain.",
						rule.Entry, reqDisplay),
					Frame: rule.Entry,
				})
			}
		}
	}

	return issues
}
