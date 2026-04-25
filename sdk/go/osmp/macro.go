// OSMP Macro Registry — Go port from sdk/python/osmp/protocol.py
//
// A pre-validated multi-step SAL instruction chain template carries an opcode
// sequence with operator glyphs and {slot_name} placeholders. The MacroRegistry
// stores templates, validates that referenced opcodes exist in the ASD, and
// produces compact wire form (A:MACRO[id]:slot[val]) or expanded chain form
// (the full chain with values substituted). Templates inherit a consequence
// class from the most-severe R namespace frame in the chain.
//
// This file ports the Python implementation 1:1 to keep cross-SDK parity.
// The compose-time macro priority check (a registered macro is preferred over
// individual opcode composition) is wired in composer.go.
//
// Patent pending -- inventor Clay Holberg
// License: Apache 2.0

package osmp

import (
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// SlotDefinition is a typed parameter slot in a macro chain template.
type SlotDefinition struct {
	Name      string
	SlotType  string // "string", "uint", "int", "float", "enum", "bool"
	Namespace string // optional namespace hint for Layer 2 accessors; "" if unset
}

// MacroTemplate is a pre-validated multi-step SAL instruction chain template.
//
// The ChainTemplate contains namespace-prefixed opcodes connected by glyph
// operators, with {slot_name} placeholders at positions where the invoking
// agent supplies context-specific values.
type MacroTemplate struct {
	MacroID          string
	ChainTemplate    string
	Slots            []SlotDefinition
	Description      string
	ConsequenceClass string // "" if none
	Triggers         []string
}

// macroCorpusEntry is the on-disk JSON shape for a single macro definition.
type macroCorpusEntry struct {
	MacroID       string `json:"macro_id"`
	ChainTemplate string `json:"chain_template"`
	Description   string `json:"description"`
	Triggers      []string `json:"triggers"`
	Slots         []struct {
		Name      string `json:"name"`
		SlotType  string `json:"slot_type"`
		Namespace string `json:"namespace"`
	} `json:"slots"`
}

// MacroCorpus is the on-disk JSON shape for a corpus file.
type MacroCorpus struct {
	CorpusID    string             `json:"corpus_id"`
	Version     string             `json:"version"`
	Description string             `json:"description"`
	ASDVersion  string             `json:"asd_version"`
	Macros      []macroCorpusEntry `json:"macros"`
}

// Consequence-class severity ordering for inheritance.
//
//	REVERSIBLE (↺) < HAZARDOUS (⚠) < IRREVERSIBLE (⊘)
var (
	ccSeverity = map[string]int{
		"\u21ba": 1, // ↺ REVERSIBLE
		"\u26a0": 2, // ⚠ HAZARDOUS
		"\u2298": 3, // ⊘ IRREVERSIBLE
	}
	ccBySeverity = map[int]string{
		1: "\u21ba",
		2: "\u26a0",
		3: "\u2298",
	}

	// Operators stripped when scanning frames for macro/CC analysis.
	macroOperatorTokens = map[string]bool{
		"\u2192": true, // → THEN
		"\u2227": true, // ∧ AND
		"\u2228": true, // ∨ OR
		"\u2194": true, // ↔ IFF
		"\u2225": true, // ∥ PARALLEL
		";":      true,
		"->":     true,
	}

	macroPlaceholderRe   = regexp.MustCompile(`\{(\w+)\}`)
	macroSlotStripRe     = regexp.MustCompile(`\{[^}]+\}`)
	macroAnnotationCCRe  = regexp.MustCompile(`[\x{21ba}\x{26a0}\x{2298}]$`)
)

// MacroRegistry stores pre-validated SAL instruction chain templates.
//
// Macros are an ASD extension: stored alongside regular opcodes, queried
// through the same lookup path, but with template expansion triggered when
// A:MACRO is detected.
type MacroRegistry struct {
	asd    *AdaptiveSharedDictionary
	macros map[string]MacroTemplate
	order  []string // insertion order for stable ListMacros output
}

// NewMacroRegistry creates an empty registry bound to the given ASD.
// If asd is nil, a fresh default ASD is allocated.
func NewMacroRegistry(asd *AdaptiveSharedDictionary) *MacroRegistry {
	if asd == nil {
		asd = NewASD()
	}
	return &MacroRegistry{
		asd:    asd,
		macros: make(map[string]MacroTemplate),
	}
}

// ASD returns the dictionary the registry is bound to.
func (r *MacroRegistry) ASD() *AdaptiveSharedDictionary { return r.asd }

// Register validates and stores a macro template. Returns an error if any
// referenced opcode is not in the ASD or if the slot/placeholder sets do
// not match.
func (r *MacroRegistry) Register(t MacroTemplate) error {
	clean := macroSlotStripRe.ReplaceAllString(t.ChainTemplate, "X")
	parts := salFrameSplitRe.Split(clean, -1)

	for _, raw := range parts {
		frame := strings.TrimSpace(raw)
		if frame == "" || macroOperatorTokens[frame] {
			continue
		}
		m := salFrameNsOpRe.FindStringSubmatch(frame)
		if m != nil {
			ns, op := m[1], m[2]
			if r.asd.Lookup(ns, op) == "" {
				return fmt.Errorf("Macro %s: opcode %s:%s not found in ASD",
					t.MacroID, ns, op)
			}
		}
	}

	// Validate slot placeholders have matching definitions
	placeholders := map[string]bool{}
	for _, m := range macroPlaceholderRe.FindAllStringSubmatch(t.ChainTemplate, -1) {
		placeholders[m[1]] = true
	}
	defined := map[string]bool{}
	for _, s := range t.Slots {
		defined[s.Name] = true
	}

	var missing []string
	for p := range placeholders {
		if !defined[p] {
			missing = append(missing, p)
		}
	}
	if len(missing) > 0 {
		sort.Strings(missing)
		return fmt.Errorf("Macro %s: slot placeholders %v have no matching SlotDefinition",
			t.MacroID, missing)
	}

	var extra []string
	for s := range defined {
		if !placeholders[s] {
			extra = append(extra, s)
		}
	}
	if len(extra) > 0 {
		sort.Strings(extra)
		return fmt.Errorf("Macro %s: SlotDefinitions %v have no matching placeholder in chain template",
			t.MacroID, extra)
	}

	// Compute inherited consequence class
	if t.ConsequenceClass == "" {
		if cc := r.computeInheritedCC(clean); cc != "" {
			t.ConsequenceClass = cc
		}
	}

	if _, exists := r.macros[t.MacroID]; !exists {
		r.order = append(r.order, t.MacroID)
	}
	r.macros[t.MacroID] = t
	return nil
}

// Lookup returns the registered macro by ID, or nil if not found.
func (r *MacroRegistry) Lookup(macroID string) *MacroTemplate {
	if t, ok := r.macros[macroID]; ok {
		return &t
	}
	return nil
}

// formatSlotValue mirrors Python's str(value) for cross-SDK byte-identical
// wire output. Go's default formatting drops trailing zeros on floats and
// emits lowercase booleans; Python preserves "1013.0" and emits "True"/"False".
// The slot type is the canonical disambiguator since Go conflates
// integer-valued float64s with ints in many call sites.
func formatSlotValue(slotType string, value any) string {
	if slotType == "float" {
		switch v := value.(type) {
		case float64:
			if v == float64(int64(v)) {
				return strconv.FormatInt(int64(v), 10) + ".0"
			}
			return strconv.FormatFloat(v, 'f', -1, 64)
		case float32:
			f := float64(v)
			if f == float64(int64(f)) {
				return strconv.FormatInt(int64(f), 10) + ".0"
			}
			return strconv.FormatFloat(f, 'f', -1, 32)
		case int:
			return strconv.Itoa(v) + ".0"
		case int64:
			return strconv.FormatInt(v, 10) + ".0"
		}
	}
	if slotType == "bool" {
		if b, ok := value.(bool); ok {
			if b {
				return "True"
			}
			return "False"
		}
	}
	switch v := value.(type) {
	case string:
		return v
	case int:
		return strconv.Itoa(v)
	case int64:
		return strconv.FormatInt(v, 10)
	case uint:
		return strconv.FormatUint(uint64(v), 10)
	case uint64:
		return strconv.FormatUint(v, 10)
	case float64:
		return strconv.FormatFloat(v, 'f', -1, 64)
	case float32:
		return strconv.FormatFloat(float64(v), 'f', -1, 32)
	case bool:
		if v {
			return "True"
		}
		return "False"
	}
	return fmt.Sprint(value)
}

// Expand returns the fully expanded SAL chain with all placeholders
// substituted. This is the "slot-fill" operation the patent describes.
func (r *MacroRegistry) Expand(macroID string, slotValues map[string]any) (string, error) {
	t, ok := r.macros[macroID]
	if !ok {
		return "", fmt.Errorf("Macro not found: %s", macroID)
	}

	required := map[string]bool{}
	for _, s := range t.Slots {
		required[s.Name] = true
	}
	var missing []string
	for name := range required {
		if _, present := slotValues[name]; !present {
			missing = append(missing, name)
		}
	}
	if len(missing) > 0 {
		sort.Strings(missing)
		return "", fmt.Errorf("Macro %s: missing slot values: %v", macroID, missing)
	}

	slotTypeByName := map[string]string{}
	for _, s := range t.Slots {
		slotTypeByName[s.Name] = s.SlotType
	}

	result := t.ChainTemplate
	for name, value := range slotValues {
		slotType := slotTypeByName[name]
		if slotType == "" {
			slotType = "string"
		}
		formatted := formatSlotValue(slotType, value)
		result = strings.ReplaceAll(result, "{"+name+"}", formatted)
	}
	return result, nil
}

// EncodeCompact returns the wire form: A:MACRO[id]:slot1[val1]:slot2[val2]...
// Used when both nodes share the macro definition.
func (r *MacroRegistry) EncodeCompact(macroID string, slotValues map[string]any) (string, error) {
	t, ok := r.macros[macroID]
	if !ok {
		return "", fmt.Errorf("Macro not found: %s", macroID)
	}

	parts := []string{fmt.Sprintf("A:MACRO[%s]", macroID)}
	for _, slot := range t.Slots {
		if v, present := slotValues[slot.Name]; present {
			parts = append(parts, fmt.Sprintf(":%s[%s]", slot.Name, formatSlotValue(slot.SlotType, v)))
		}
	}
	out := strings.Join(parts, "")
	if t.ConsequenceClass != "" {
		out += t.ConsequenceClass
	}
	return out, nil
}

// EncodeExpanded returns the full chain with values substituted.
// Used when the receiving node doesn't have the macro definition.
func (r *MacroRegistry) EncodeExpanded(macroID string, slotValues map[string]any) (string, error) {
	return r.Expand(macroID, slotValues)
}

// EncodeWithAnnotation returns the compact form with an _EXP slot carrying
// the fully expanded chain, for monitoring at unconstrained bandwidth.
func (r *MacroRegistry) EncodeWithAnnotation(macroID string, slotValues map[string]any) (string, error) {
	compact, err := r.EncodeCompact(macroID, slotValues)
	if err != nil {
		return "", err
	}
	expanded, err := r.Expand(macroID, slotValues)
	if err != nil {
		return "", err
	}
	if loc := macroAnnotationCCRe.FindStringIndex(compact); loc != nil {
		cc := compact[loc[0]:]
		base := compact[:loc[0]]
		return fmt.Sprintf("%s:_EXP[%s]%s", base, expanded, cc), nil
	}
	return fmt.Sprintf("%s:_EXP[%s]", compact, expanded), nil
}

// InheritedConsequenceClass returns the inherited CC for the macro, or "" if
// none. Computed at registration time and stored on the template.
func (r *MacroRegistry) InheritedConsequenceClass(macroID string) string {
	t, ok := r.macros[macroID]
	if !ok {
		return ""
	}
	return t.ConsequenceClass
}

// computeInheritedCC scans the chain's R-namespace frames and returns the
// highest-severity consequence class glyph found. Empty if no R frame.
func (r *MacroRegistry) computeInheritedCC(cleanChain string) string {
	maxSev := 0
	for _, raw := range salFrameSplitRe.Split(cleanChain, -1) {
		part := strings.TrimSpace(raw)
		if part == "" || macroOperatorTokens[part] {
			continue
		}
		m := salFrameNsOpRe.FindStringSubmatch(part)
		if m == nil || m[1] != "R" {
			continue
		}
		for glyph, sev := range ccSeverity {
			if strings.Contains(part, glyph) && sev > maxSev {
				maxSev = sev
			}
		}
	}
	if maxSev == 0 {
		return ""
	}
	return ccBySeverity[maxSev]
}

// ListMacros returns all registered macros in registration order.
func (r *MacroRegistry) ListMacros() []MacroTemplate {
	out := make([]MacroTemplate, 0, len(r.order))
	for _, id := range r.order {
		out = append(out, r.macros[id])
	}
	return out
}

// LoadCorpus parses a JSON corpus and registers each macro. Returns the
// count of macros loaded.
func (r *MacroRegistry) LoadCorpus(data []byte) (int, error) {
	var corpus MacroCorpus
	if err := json.Unmarshal(data, &corpus); err != nil {
		return 0, fmt.Errorf("macro corpus parse: %w", err)
	}

	count := 0
	for _, entry := range corpus.Macros {
		slots := make([]SlotDefinition, 0, len(entry.Slots))
		for _, s := range entry.Slots {
			slotType := s.SlotType
			if slotType == "" {
				slotType = "string"
			}
			slots = append(slots, SlotDefinition{
				Name:      s.Name,
				SlotType:  slotType,
				Namespace: s.Namespace,
			})
		}
		t := MacroTemplate{
			MacroID:       entry.MacroID,
			ChainTemplate: entry.ChainTemplate,
			Slots:         slots,
			Description:   entry.Description,
			Triggers:      entry.Triggers,
		}
		if err := r.Register(t); err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}
