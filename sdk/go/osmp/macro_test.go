// Registered Macro Architecture Tests (Go parity)
// =================================================
//
// Mirrors tests/tier1/test_macros.py and sdk/typescript/tests/macro.test.ts
// 1:1 to lock cross-SDK byte-identical behavior for the MacroRegistry,
// MacroTemplate, and SlotDefinition types.
//
// Patent pending | License: Apache 2.0
package osmp_test

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)

// repoRoot returns the absolute path to the repo root from this file's location.
func repoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, _ := runtime.Caller(0)
	// file is .../sdk/go/osmp/macro_test.go
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", ".."))
}

func corpusBytes(t *testing.T) []byte {
	t.Helper()
	path := filepath.Join(repoRoot(t), "mdr", "meshtastic", "meshtastic-macros.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read corpus: %v", err)
	}
	return data
}

// ── Registration and Lookup ────────────────────────────────────────────────

func TestMacroRegister_AndLookup(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	if err := r.Register(osmp.MacroTemplate{
		MacroID:       "TEST:SIMPLE",
		ChainTemplate: "H:HR[bpm:{bpm}]",
		Slots:         []osmp.SlotDefinition{{Name: "bpm", SlotType: "uint"}},
		Description:   "Simple heart rate macro",
	}); err != nil {
		t.Fatalf("register: %v", err)
	}
	got := r.Lookup("TEST:SIMPLE")
	if got == nil {
		t.Fatalf("lookup TEST:SIMPLE returned nil")
	}
	if got.MacroID != "TEST:SIMPLE" {
		t.Errorf("MacroID: got %q want TEST:SIMPLE", got.MacroID)
	}
}

func TestMacroLookup_NonexistentNil(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	if got := r.Lookup("DOES:NOT:EXIST"); got != nil {
		t.Errorf("expected nil, got %+v", got)
	}
}

func TestMacroRegister_OpcodeNotInASD(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	err := r.Register(osmp.MacroTemplate{
		MacroID:       "BAD:OPCODE",
		ChainTemplate: "Z:NONEXISTENT[val:{v}]",
		Slots:         []osmp.SlotDefinition{{Name: "v", SlotType: "string"}},
		Description:   "Uses a nonexistent opcode",
	})
	if err == nil || !strings.Contains(err.Error(), "not found in ASD") {
		t.Errorf("expected 'not found in ASD' error, got %v", err)
	}
}

func TestMacroRegister_RejectsExtraSlot(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	err := r.Register(osmp.MacroTemplate{
		MacroID:       "BAD:SLOTS",
		ChainTemplate: "H:HR[bpm:{bpm}]",
		Slots: []osmp.SlotDefinition{
			{Name: "bpm", SlotType: "uint"},
			{Name: "extra", SlotType: "string"},
		},
		Description: "Extra slot with no placeholder",
	})
	if err == nil || !strings.Contains(err.Error(), "no matching placeholder") {
		t.Errorf("expected 'no matching placeholder' error, got %v", err)
	}
}

func TestMacroRegister_RejectsMissingDef(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	err := r.Register(osmp.MacroTemplate{
		MacroID:       "BAD:MISSING",
		ChainTemplate: "H:HR[bpm:{bpm}]\u2227H:SPO2[o2:{spo2}]",
		Slots:         []osmp.SlotDefinition{{Name: "bpm", SlotType: "uint"}},
		Description:   "Missing slot definition",
	})
	if err == nil || !strings.Contains(err.Error(), "no matching SlotDefinition") {
		t.Errorf("expected 'no matching SlotDefinition' error, got %v", err)
	}
}

func TestMacroList(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "A:ONE", ChainTemplate: "A:ACK[m:{m}]",
		Slots: []osmp.SlotDefinition{{Name: "m", SlotType: "string"}},
		Description: "first",
	})
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "A:TWO", ChainTemplate: "A:NACK[m:{m}]",
		Slots: []osmp.SlotDefinition{{Name: "m", SlotType: "string"}},
		Description: "second",
	})
	macros := r.ListMacros()
	if len(macros) != 2 {
		t.Fatalf("want 2 macros, got %d", len(macros))
	}
	ids := map[string]bool{}
	for _, m := range macros {
		ids[m.MacroID] = true
	}
	if !ids["A:ONE"] || !ids["A:TWO"] {
		t.Errorf("missing expected macros, got %v", ids)
	}
}

// ── Expansion and Slot-Fill ───────────────────────────────────────────────

func TestMacroExpand_Simple(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:HR", ChainTemplate: "H:HR[bpm:{bpm}]",
		Slots: []osmp.SlotDefinition{{Name: "bpm", SlotType: "uint"}},
		Description: "heart rate",
	})
	got, err := r.Expand("TEST:HR", map[string]any{"bpm": 72})
	if err != nil {
		t.Fatalf("expand: %v", err)
	}
	if got != "H:HR[bpm:72]" {
		t.Errorf("got %q want H:HR[bpm:72]", got)
	}
}

func TestMacroExpand_MultiSlotChainParity(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID:       "TEST:ENV",
		ChainTemplate: "E:TH[t:{temp},h:{hum}]\u2227E:PU[p:{press}]",
		Slots: []osmp.SlotDefinition{
			{Name: "temp", SlotType: "float"},
			{Name: "hum", SlotType: "float"},
			{Name: "press", SlotType: "float"},
		},
		Description: "environment",
	})
	got, err := r.Expand("TEST:ENV", map[string]any{
		"temp":  22.5,
		"hum":   65.0, // float-typed, integer value → "65.0" via formatSlotValue
		"press": 1013.25,
	})
	if err != nil {
		t.Fatalf("expand: %v", err)
	}
	want := "E:TH[t:22.5,h:65.0]\u2227E:PU[p:1013.25]"
	if got != want {
		t.Errorf("cross-SDK parity mismatch:\n  got  %q\n  want %q", got, want)
	}
}

func TestMacroExpand_Medevac(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID:       "MEDEVAC",
		ChainTemplate: "H:ICD[{dx_code}]\u2192H:CASREP\u2227M:EVA@{target}",
		Slots: []osmp.SlotDefinition{
			{Name: "dx_code", SlotType: "string", Namespace: "H"},
			{Name: "target", SlotType: "string"},
		},
		Description: "Clinical MEDEVAC",
	})
	got, err := r.Expand("MEDEVAC", map[string]any{"dx_code": "J930", "target": "MED1"})
	if err != nil {
		t.Fatalf("expand: %v", err)
	}
	if got != "H:ICD[J930]\u2192H:CASREP\u2227M:EVA@MED1" {
		t.Errorf("got %q", got)
	}
}

func TestMacroExpand_MissingSlotErrors(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID:       "TEST:TWO",
		ChainTemplate: "H:HR[bpm:{bpm}]\u2227H:SPO2[o2:{spo2}]",
		Slots: []osmp.SlotDefinition{
			{Name: "bpm", SlotType: "uint"},
			{Name: "spo2", SlotType: "uint"},
		},
		Description: "two slots",
	})
	_, err := r.Expand("TEST:TWO", map[string]any{"bpm": 72})
	if err == nil || !strings.Contains(err.Error(), "missing slot values") {
		t.Errorf("expected 'missing slot values' error, got %v", err)
	}
}

func TestMacroExpand_NonexistentErrors(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	_, err := r.Expand("NOPE", map[string]any{"x": 1})
	if err == nil || !strings.Contains(err.Error(), "Macro not found") {
		t.Errorf("expected 'Macro not found' error, got %v", err)
	}
}

func TestMacroExpand_NoCompositionValidation(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:CHAIN", ChainTemplate: "A:ACK\u2227A:NACK",
		Slots: nil, Description: "no slots",
	})
	got, err := r.Expand("TEST:CHAIN", map[string]any{})
	if err != nil {
		t.Fatalf("expand: %v", err)
	}
	if got != "A:ACK\u2227A:NACK" {
		t.Errorf("got %q", got)
	}
}

// ── Compact and Expanded Wire Format ──────────────────────────────────────

func TestMacroEncodeCompact(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:HR", ChainTemplate: "H:HR[bpm:{bpm}]",
		Slots: []osmp.SlotDefinition{{Name: "bpm", SlotType: "uint"}},
		Description: "heart rate",
	})
	got, err := r.EncodeCompact("TEST:HR", map[string]any{"bpm": 72})
	if err != nil {
		t.Fatalf("encode compact: %v", err)
	}
	if got != "A:MACRO[TEST:HR]:bpm[72]" {
		t.Errorf("got %q", got)
	}
}

func TestMacroEncodeExpanded(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:HR", ChainTemplate: "H:HR[bpm:{bpm}]",
		Slots: []osmp.SlotDefinition{{Name: "bpm", SlotType: "uint"}},
		Description: "heart rate",
	})
	got, err := r.EncodeExpanded("TEST:HR", map[string]any{"bpm": 72})
	if err != nil {
		t.Fatalf("encode expanded: %v", err)
	}
	if got != "H:HR[bpm:72]" {
		t.Errorf("got %q", got)
	}
}

func TestMacroEncodeCompact_PreservesSlotOrder(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:MULTI", ChainTemplate: "E:TH[t:{t}]\u2227E:PU[p:{p}]",
		Slots: []osmp.SlotDefinition{
			{Name: "t", SlotType: "float"},
			{Name: "p", SlotType: "float"},
		},
		Description: "multi",
	})
	got, err := r.EncodeCompact("TEST:MULTI", map[string]any{"t": 22.5, "p": 1013.0})
	if err != nil {
		t.Fatalf("encode compact: %v", err)
	}
	if !strings.Contains(got, ":t[22.5]") {
		t.Errorf(":t[22.5] missing from %q", got)
	}
	if !strings.Contains(got, ":p[1013.0]") {
		t.Errorf(":p[1013.0] missing from %q", got)
	}
	if strings.Index(got, ":t[") >= strings.Index(got, ":p[") {
		t.Errorf("slot order mismatch: %q", got)
	}
}

func TestMacroEncodeWithAnnotation(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:ANN", ChainTemplate: "A:ACK[m:{m}]",
		Slots: []osmp.SlotDefinition{{Name: "m", SlotType: "string"}},
		Description: "annotated",
	})
	got, err := r.EncodeWithAnnotation("TEST:ANN", map[string]any{"m": "hello"})
	if err != nil {
		t.Fatalf("encode with annotation: %v", err)
	}
	if !strings.Contains(got, "A:MACRO[TEST:ANN]") {
		t.Errorf("missing A:MACRO[TEST:ANN] in %q", got)
	}
	if !strings.Contains(got, "_EXP[A:ACK[m:hello]]") {
		t.Errorf("missing _EXP[...] in %q", got)
	}
}

// ── Consequence Class Inheritance ─────────────────────────────────────────

func TestMacroCC_NoneWhenNoR(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:NOCC", ChainTemplate: "H:HR[bpm:{bpm}]",
		Slots: []osmp.SlotDefinition{{Name: "bpm", SlotType: "uint"}},
		Description: "no R namespace",
	})
	if cc := r.InheritedConsequenceClass("TEST:NOCC"); cc != "" {
		t.Errorf("got %q want empty", cc)
	}
}

func TestMacroCC_Reversible(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:REV", ChainTemplate: "R:MOV@BOT1\u21ba",
		Description: "reversible R",
	})
	if cc := r.InheritedConsequenceClass("TEST:REV"); cc != "\u21ba" {
		t.Errorf("got %q want ↺", cc)
	}
}

func TestMacroCC_Hazardous(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:HAZ", ChainTemplate: "I:\u00a7\u2192R:DRVE@UAV1\u26a0",
		Description: "hazardous R",
	})
	if cc := r.InheritedConsequenceClass("TEST:HAZ"); cc != "\u26a0" {
		t.Errorf("got %q want ⚠", cc)
	}
}

func TestMacroCC_HighestWins(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID:       "TEST:MIX",
		ChainTemplate: "R:MOV@BOT1\u21ba\u2227I:\u00a7\u2192R:DPTH@UUV1\u26a0",
		Description:   "mixed CC",
	})
	if cc := r.InheritedConsequenceClass("TEST:MIX"); cc != "\u26a0" {
		t.Errorf("got %q want ⚠ (HAZARDOUS > REVERSIBLE)", cc)
	}
}

func TestMacroCC_CarriedOnWire(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	mustRegister(t, r, osmp.MacroTemplate{
		MacroID: "TEST:CCWIRE", ChainTemplate: "R:MOV@{target}\u21ba",
		Slots: []osmp.SlotDefinition{{Name: "target", SlotType: "string"}},
		Description: "CC on wire",
	})
	got, err := r.EncodeCompact("TEST:CCWIRE", map[string]any{"target": "BOT1"})
	if err != nil {
		t.Fatalf("encode compact: %v", err)
	}
	if !strings.HasSuffix(got, "\u21ba") {
		t.Errorf("expected trailing ↺ in %q", got)
	}
}

// ── Corpus Loading (Meshtastic) ────────────────────────────────────────────

func TestCorpusLoad_Count(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	count, err := r.LoadCorpus(corpusBytes(t))
	if err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	if count != 16 {
		t.Errorf("loaded %d, want 16", count)
	}
}

func TestCorpusLoad_AllExpectedIDs(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	if _, err := r.LoadCorpus(corpusBytes(t)); err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	expected := map[string]bool{
		"MESH:DEV": true, "MESH:ENV": true, "MESH:AQ": true, "MESH:PWR": true,
		"MESH:HLTH": true, "MESH:STAT": true, "MESH:POS": true, "MESH:NODE": true,
		"MESH:ACK": true, "MESH:ALRT": true, "MESH:TRACE": true, "MESH:WPT": true,
		"MESH:TALRT": true, "MESH:BATLO": true, "MESH:NOFF": true, "MEDEVAC": true,
	}
	got := map[string]bool{}
	for _, m := range r.ListMacros() {
		got[m.MacroID] = true
	}
	for id := range expected {
		if !got[id] {
			t.Errorf("missing macro id %q", id)
		}
	}
	for id := range got {
		if !expected[id] {
			t.Errorf("unexpected macro id %q", id)
		}
	}
}

func TestCorpusLoad_MeshDevExpands(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	if _, err := r.LoadCorpus(corpusBytes(t)); err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	got, err := r.Expand("MESH:DEV", map[string]any{
		"battery_level": 87,
		"voltage":       3.72,
		"channel_util":  12.5,
		"air_util":      3.2,
		"uptime":        3600,
	})
	if err != nil {
		t.Fatalf("expand: %v", err)
	}
	if !strings.Contains(got, "X:STORE[bat:87]") {
		t.Errorf("missing X:STORE[bat:87] in %q", got)
	}
	if !strings.Contains(got, "X:VOLT[v:3.72]") {
		t.Errorf("missing X:VOLT[v:3.72] in %q", got)
	}
}

func TestCorpusLoad_MedevacByteIdenticalParity(t *testing.T) {
	r := osmp.NewMacroRegistry(nil)
	if _, err := r.LoadCorpus(corpusBytes(t)); err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	got, err := r.Expand("MEDEVAC", map[string]any{"dx_code": "J930", "target": "MED1"})
	if err != nil {
		t.Fatalf("expand: %v", err)
	}
	want := "H:ICD[J930]\u2192H:CASREP\u2227M:EVA@MED1"
	if got != want {
		t.Errorf("cross-SDK parity mismatch:\n  got  %q\n  want %q", got, want)
	}
}

// ── Composer integration: macro priority + chain-split ────────────────────

func TestComposer_MacroPriorityWins(t *testing.T) {
	reg := osmp.NewMacroRegistry(nil)
	if _, err := reg.LoadCorpus(corpusBytes(t)); err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	c := osmp.NewComposerWithMacros(nil, reg)

	// "battery" is a trigger on MESH:DEV
	got := c.Compose("report device status with battery details", nil)
	if got != "A:MACRO[MESH:DEV]" {
		t.Errorf("got %q want A:MACRO[MESH:DEV]", got)
	}
}

func TestComposer_FallthroughWhenNoMacroMatch(t *testing.T) {
	reg := osmp.NewMacroRegistry(nil)
	if _, err := reg.LoadCorpus(corpusBytes(t)); err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	c := osmp.NewComposerWithMacros(nil, reg)

	// "fire alarm" is a curated trigger but not in any macro
	got := c.Compose("fire alarm in building B", nil)
	if got == "" {
		t.Fatalf("expected non-empty SAL")
	}
	if strings.HasPrefix(got, "A:MACRO[") {
		t.Errorf("expected non-macro SAL, got %q", got)
	}
}

func TestComposer_SetMacroRegistry(t *testing.T) {
	c := osmp.NewComposer(nil)
	if c.MacroRegistry() != nil {
		t.Errorf("expected nil registry by default")
	}
	reg := osmp.NewMacroRegistry(nil)
	mustRegister(t, reg, osmp.MacroTemplate{
		MacroID: "FOO:BAR", ChainTemplate: "A:ACK[m:{m}]",
		Slots: []osmp.SlotDefinition{{Name: "m", SlotType: "string"}},
		Description: "test", Triggers: []string{"foo bar trigger"},
	})
	c.SetMacroRegistry(reg)
	if c.MacroRegistry() != reg {
		t.Errorf("registry not attached")
	}
	got := c.Compose("please run the foo bar trigger now", nil)
	if got != "A:MACRO[FOO:BAR]" {
		t.Errorf("got %q want A:MACRO[FOO:BAR]", got)
	}
}

// ── Chain-split composer behavior ─────────────────────────────────────────

func TestComposer_ChainSplit_SequenceComma(t *testing.T) {
	c := osmp.NewComposer(nil)
	got := c.Compose("encrypt the payload, then push to node BRAVO", nil)
	if got == "" {
		t.Fatalf("expected non-empty SAL")
	}
	if !strings.Contains(got, ";") {
		t.Errorf("expected SEQUENCE chain (;), got %q", got)
	}
}

func TestComposer_ChainSplit_SequenceNoComma(t *testing.T) {
	c := osmp.NewComposer(nil)
	got := c.Compose("sign payload then push to node ALPHA", nil)
	if got == "" {
		t.Fatalf("expected non-empty SAL")
	}
	if !strings.Contains(got, ";") {
		t.Errorf("expected SEQUENCE chain (;), got %q", got)
	}
}

func TestComposer_ChainSplit_DoesNotSplitConditional(t *testing.T) {
	c := osmp.NewComposer(nil)
	got := c.Compose("if temperature above 100 then alert operator", nil)
	if got != "" && strings.Contains(got, ";") {
		t.Errorf("conditional should not produce ;-chain, got %q", got)
	}
}

func TestComposer_ChainSplit_AbortsWhenSegmentFails(t *testing.T) {
	c := osmp.NewComposer(nil)
	got := c.Compose("xqzqzq frrrgg, then qqqq llwwww", nil)
	if got != "" {
		t.Errorf("expected empty SAL, got %q", got)
	}
}

// ── Helpers ───────────────────────────────────────────────────────────────

func mustRegister(t *testing.T, r *osmp.MacroRegistry, tpl osmp.MacroTemplate) {
	t.Helper()
	if err := r.Register(tpl); err != nil {
		t.Fatalf("register %s: %v", tpl.MacroID, err)
	}
}
