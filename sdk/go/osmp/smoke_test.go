package osmp_test

import (
	"testing"
	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)

func TestCanonicalOpcodeNames(t *testing.T) {
	// Verify opcodes match canonical dictionary v14
	asd := osmp.NewASD()
	cases := []struct{ ns, op, want string }{
		{"A","MACRO","registered_macro_invocation"},
		{"Z","INF","invoke_inference"},          // was Z:INFER in prior drift
		{"V","HDG","heading"},                    // was V:HDNG
		{"V","ROUTE","routing_instruction"},      // was V:ROUT
		{"D","PACK","two_tier_corpus_encoding_for_at_rest_storage"},
		{"D","UNPACK","inference_free_semantic_retrieval_from_encoded_corpus"},
		{"H","ICD","ICD-10_diagnosis_code_accessor"},
		{"H","SNOMED","SNOMED_CT_concept_identifier_accessor"},
		{"H","CPT","CPT_procedure_code_accessor"},
		{"N","INET","internet_uplink_capability_query"},
		{"A","CMPR","structured_comparison_returning_result"},
		{"C","ALLOC","resource_allocation"},
		{"C","FREE","release_resource"},
		{"S","ROTATE","key_rotation"},
		{"T","AFTER","execute_after_condition"},
		{"T","BEFORE","execute_before_deadline"},
		{"U","ALERT","urgent_operator_alert"},
		{"U","DISPLAY","display_information_to_operator"},
		{"U","INPUT","request_operator_input"},
		{"Y","RETRIEVE","retrieve_from_LCS"},
		{"Z","ROUTE","route_to_model_with_specified_capability"},
		{"L","QUERY","audit_trail_query"},
		{"Q","CORRECT","correction_directive"},
	}
	for _, c := range cases {
		got := asd.Lookup(c.ns, c.op)
		if got != c.want {
			t.Errorf("%s:%s = %q, want %q", c.ns, c.op, got, c.want)
		}
	}
}

func TestDecodeAllNamespaces(t *testing.T) {
	dec := osmp.NewDecoder(nil)
	cases := []struct{ encoded, ns, op string }{
		{"A:SUM","A","SUM"}, {"B:ALRM","B","ALRM"}, {"C:SPAWN","C","SPAWN"},
		{"D:XFER","D","XFER"}, {"D:PACK","D","PACK"}, {"D:UNPACK","D","UNPACK"},
		{"E:TH","E","TH"}, {"F:QRY","F","QRY"}, {"G:POS","G","POS"},
		{"H:HR","H","HR"}, {"H:ICD","H","ICD"}, {"H:SNOMED","H","SNOMED"},
		{"I:KYC","I","KYC"}, {"J:GOAL","J","GOAL"}, {"K:PAY","K","PAY"},
		{"L:AUDIT","L","AUDIT"}, {"M:EVA","M","EVA"}, {"N:CFG","N","CFG"},
		{"N:INET","N","INET"}, {"O:MODE","O","MODE"}, {"P:GUIDE","P","GUIDE"},
		{"Q:SCORE","Q","SCORE"}, {"R:ESTOP","R","ESTOP"}, {"S:ENC","S","ENC"},
		{"S:ROTATE","S","ROTATE"}, {"T:NOW","T","NOW"}, {"T:AFTER","T","AFTER"},
		{"T:BEFORE","T","BEFORE"}, {"U:ESCALATE","U","ESCALATE"},
		{"U:ALERT","U","ALERT"}, {"U:DISPLAY","U","DISPLAY"},
		{"V:POS","V","POS"}, {"V:HDG","V","HDG"}, {"V:ROUTE","V","ROUTE"},
		{"W:METAR","W","METAR"}, {"X:PROD","X","PROD"}, {"Y:SEARCH","Y","SEARCH"},
		{"Y:RETRIEVE","Y","RETRIEVE"}, {"Z:INF","Z","INF"}, {"Z:ROUTE","Z","ROUTE"},
	}
	for _, c := range cases {
		r, err := dec.DecodeFrame(c.encoded)
		if err != nil { t.Errorf("%s: decode error: %v", c.encoded, err); continue }
		if r.Namespace != c.ns || r.Opcode != c.op {
			t.Errorf("%s: got ns=%q op=%q, want ns=%q op=%q", c.encoded, r.Namespace, r.Opcode, c.ns, c.op)
		}
	}
}

func TestConsequenceClasses(t *testing.T) {
	dec := osmp.NewDecoder(nil)
	cases := []struct{ encoded, cc, name string }{
		{"R:MOV@BOT1↺","↺","REVERSIBLE"},
		{"R:CAM@NODE⚠","⚠","HAZARDOUS"},
		{"R:DRVE@BOT1⊘","⊘","IRREVERSIBLE"},
	}
	for _, c := range cases {
		r, err := dec.DecodeFrame(c.encoded)
		if err != nil { t.Errorf("%s: %v", c.encoded, err); continue }
		if r.ConsequenceClass != c.cc || r.ConsequenceClassName != c.name {
			t.Errorf("%s: cc=%q/%q, want %q/%q", c.encoded, r.ConsequenceClass, r.ConsequenceClassName, c.cc, c.name)
		}
	}
}

func TestESTOPOverridesAtomic(t *testing.T) {
	op := osmp.NewOverflowProtocol(255, osmp.LossPolicyAtomic)
	frags := op.Fragment([]byte("R:ESTOP"), false)
	result := op.Receive(frags[0])
	if result == nil { t.Error("R:ESTOP must return immediately under ATOMIC policy") }
}

func TestHumanConfirmationOpcode(t *testing.T) {
	dec := osmp.NewDecoder(nil)
	r, err := dec.DecodeFrame("I:§")
	if err != nil { t.Fatal(err) }
	if r.Namespace != "I" || r.Opcode != "§" {
		t.Errorf("got ns=%q op=%q", r.Namespace, r.Opcode)
	}
	if r.OpcodeMeaning != "human_operator_confirmation" {
		t.Errorf("got meaning %q", r.OpcodeMeaning)
	}
}

func TestMEDEVACChain(t *testing.T) {
	dec := osmp.NewDecoder(nil)
	r, err := dec.DecodeFrame("H:HR@NODE1>120→H:CASREP∧M:EVA@*")
	if err != nil { t.Fatal(err) }
	if r.Namespace != "H" || r.Opcode != "HR" || r.Target != "NODE1>120" {
		t.Errorf("ns=%q op=%q tgt=%q", r.Namespace, r.Opcode, r.Target)
	}
}

func TestFingerprint(t *testing.T) {
	asd := osmp.NewASD()
	fp := asd.Fingerprint()
	if len(fp) != 16 { t.Errorf("fingerprint length %d", len(fp)) }
	if fp != asd.Fingerprint() { t.Error("fingerprint not stable") }
}

func TestBAELFloor(t *testing.T) {
	b := &osmp.BAELEncoder{}
	r := b.SelectMode("Stop", "R:ESTOP@*", "")
	if r.Mode != osmp.BAELModeNLPassthrough { t.Errorf("expected NL_PASSTHROUGH, got %v", r.Mode) }
	if r.Payload != "Stop" { t.Errorf("payload %q", r.Payload) }
}

func TestLoRaFragmentation(t *testing.T) {
	op := osmp.NewOverflowProtocol(osmp.LoRaFloorBytes, osmp.LossPolicyGracefulDegradation)
	payload := []byte("H:HR@NODE1>120→H:CASREP∧M:EVA@*")
	frags := op.Fragment(append(payload, payload...), false) // force multi-frag
	if len(frags) < 2 { t.Skip("payload fit single packet") }
	for _, f := range frags {
		packed := f.Pack()
		if len(packed) > osmp.LoRaFloorBytes {
			t.Errorf("fragment %d: %d bytes > LoRa floor %d", f.FragIdx, len(packed), osmp.LoRaFloorBytes)
		}
	}
}

func TestConformanceBenchmark(t *testing.T) {
	report, err := osmp.RunBenchmark("../../../protocol/test-vectors/canonical-test-vectors.json")
	if err != nil { t.Fatalf("benchmark error: %v", err) }
	if !report.Conformant { t.Errorf("non-conformant: mean=%.1f%%", report.MeanReductionPct) }
	if report.MeanReductionPct < 60.0 { t.Errorf("mean %.1f%% < 60%%", report.MeanReductionPct) }
}

func TestValidateCompositionValid(t *testing.T) {
	r := osmp.ValidateComposition("H:HR[130]→H:ALERT", "Alert if heart rate exceeds 130", nil, true, nil)
	if !r.Valid { t.Errorf("expected valid, got errors: %v", r.Errors()) }
}

func TestValidateCompositionHallucination(t *testing.T) {
	r := osmp.ValidateComposition("H:FAKE→H:ALERT", "", nil, true, nil)
	if r.Valid { t.Error("expected invalid for hallucinated opcode") }
	found := false
	for _, e := range r.Errors() { if e.Rule == "HALLUCINATED_OPCODE" { found = true } }
	if !found { t.Error("expected HALLUCINATED_OPCODE error") }
}

func TestValidateCompositionNamespaceAsTarget(t *testing.T) {
	r := osmp.ValidateComposition("H:CASREP@H:ICD[J083]", "", nil, true, nil)
	if r.Valid { t.Error("expected invalid for namespace-as-target") }
	found := false
	for _, e := range r.Errors() { if e.Rule == "NAMESPACE_AS_TARGET" { found = true } }
	if !found { t.Error("expected NAMESPACE_AS_TARGET error") }
}

func TestValidateCompositionMissingConsequenceClass(t *testing.T) {
	r := osmp.ValidateComposition("R:MOV@BOT1", "", nil, true, nil)
	if r.Valid { t.Error("expected invalid for missing consequence class") }
	found := false
	for _, e := range r.Errors() { if e.Rule == "CONSEQUENCE_CLASS_OMISSION" { found = true } }
	if !found { t.Error("expected CONSEQUENCE_CLASS_OMISSION error") }
}

func TestValidateCompositionMissingAuthorization(t *testing.T) {
	r := osmp.ValidateComposition("R:MOV@BOT1⚠", "", nil, true, nil)
	if r.Valid { t.Error("expected invalid for missing I:§ before ⚠") }
	found := false
	for _, e := range r.Errors() { if e.Rule == "AUTHORIZATION_OMISSION" { found = true } }
	if !found { t.Error("expected AUTHORIZATION_OMISSION error") }
}

func TestValidateCompositionESTOPExempt(t *testing.T) {
	r := osmp.ValidateComposition("R:ESTOP@*", "", nil, true, nil)
	if !r.Valid { t.Errorf("R:ESTOP should be exempt from consequence class, got: %v", r.Errors()) }
}

func TestValidateCompositionSlash(t *testing.T) {
	r := osmp.ValidateComposition("H:HR/H:ALERT", "", nil, true, nil)
	if r.Valid { t.Error("expected invalid for slash operator") }
	found := false
	for _, e := range r.Errors() { if e.Rule == "SLASH_OPERATOR" { found = true } }
	if !found { t.Error("expected SLASH_OPERATOR error") }
}

func TestValidateCompositionSafetyChainValid(t *testing.T) {
	r := osmp.ValidateComposition("I:§→R:WPT[35.7,-122.4]⚠", "Navigate drone to coordinates", nil, true, nil)
	if !r.Valid { t.Errorf("expected valid safety chain, got: %v", r.Errors()) }
}
