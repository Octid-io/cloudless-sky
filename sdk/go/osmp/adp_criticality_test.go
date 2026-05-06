package osmp

import "testing"

// TestRequiredOverflowFlagsAdditive verifies an additive-only delta does
// not require the criticality flag.
func TestRequiredOverflowFlagsAdditive(t *testing.T) {
	d := &ADPDelta{
		FromVersion: "15.0", ToVersion: "15.1",
		Operations: []ADPDeltaOp{{
			Namespace: "H", Mode: "+", Opcode: "LACTATE", Definition: "lactate",
		}},
	}
	if got := d.RequiredOverflowFlags(); got != 0 {
		t.Fatalf("additive delta: want 0, got 0x%02x", got)
	}
}

// TestRequiredOverflowFlagsDeprecate verifies deprecate deltas do not
// require the criticality flag.
func TestRequiredOverflowFlagsDeprecate(t *testing.T) {
	d := &ADPDelta{
		FromVersion: "15.0", ToVersion: "15.1",
		Operations: []ADPDeltaOp{{
			Namespace: "M", Mode: "†", Opcode: "OLDOP",
		}},
	}
	if got := d.RequiredOverflowFlags(); got != 0 {
		t.Fatalf("deprecate delta: want 0, got 0x%02x", got)
	}
}

// TestRequiredOverflowFlagsReplace verifies REPLACE deltas require the
// criticality flag (spec §6 / §7 mandatory retransmission).
func TestRequiredOverflowFlagsReplace(t *testing.T) {
	d := &ADPDelta{
		FromVersion: "15.0", ToVersion: "15.1",
		Operations: []ADPDeltaOp{{
			Namespace: "H", Mode: "←", Opcode: "HR", Definition: "heart_rate_v2",
		}},
	}
	if got := d.RequiredOverflowFlags(); got != FlagCritical {
		t.Fatalf("REPLACE delta: want FlagCritical (0x%02x), got 0x%02x",
			FlagCritical, got)
	}
}

// TestRequiredOverflowFlagsMixed verifies a mixed delta with at least one
// REPLACE op requires criticality even when other ops are additive.
func TestRequiredOverflowFlagsMixed(t *testing.T) {
	d := &ADPDelta{
		FromVersion: "15.0", ToVersion: "15.1",
		Operations: []ADPDeltaOp{
			{Namespace: "H", Mode: "+", Opcode: "LACTATE"},
			{Namespace: "H", Mode: "←", Opcode: "HR", Definition: "v2"},
		},
	}
	if got := d.RequiredOverflowFlags(); got != FlagCritical {
		t.Fatalf("mixed delta: want FlagCritical, got 0x%02x", got)
	}
}

// TestValidateReceivedDeltaReplaceWithoutCriticalRejects verifies a REPLACE
// delta arriving without FlagCritical is rejected.
func TestValidateReceivedDeltaReplaceWithoutCriticalRejects(t *testing.T) {
	sal := "A:ASD:DELTA[15.0→15.1:H←[HR]]"
	if err := ValidateReceivedDelta(sal, 0); err == nil {
		t.Fatal("expected error on REPLACE without FlagCritical")
	}
}

// TestValidateReceivedDeltaReplaceWithCriticalAccepts verifies a REPLACE
// delta with FlagCritical set is accepted.
func TestValidateReceivedDeltaReplaceWithCriticalAccepts(t *testing.T) {
	sal := "A:ASD:DELTA[15.0→15.1:H←[HR]]"
	if err := ValidateReceivedDelta(sal, FlagCritical); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

// TestValidateReceivedDeltaAdditiveWithoutCriticalAccepts verifies a
// non-REPLACE delta does not require FlagCritical.
func TestValidateReceivedDeltaAdditiveWithoutCriticalAccepts(t *testing.T) {
	sal := "A:ASD:DELTA[15.0→15.1:H+[LACTATE]]"
	if err := ValidateReceivedDelta(sal, 0); err != nil {
		t.Fatalf("expected no error for additive delta, got %v", err)
	}
}

// TestValidateReceivedDeltaNonDeltaPassthrough verifies non-DELTA SAL is a
// pass-through (validator is scoped to A:ASD:DELTA traffic).
func TestValidateReceivedDeltaNonDeltaPassthrough(t *testing.T) {
	for _, sal := range []string{"H:HR@NODE1", "A:ASD[15.1]", "A:ASD?"} {
		if err := ValidateReceivedDelta(sal, 0); err != nil {
			t.Fatalf("non-DELTA passthrough failed for %q: %v", sal, err)
		}
	}
}
