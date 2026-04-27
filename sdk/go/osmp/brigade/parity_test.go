// Brigade Cross-SDK Parity Test (Go reader)
// ==========================================
//
// Reads tests/parity/brigade_parity_vectors.json (generated from Python via
// tests/parity/gen_brigade_parity.py) and asserts that this SDK's brigade
// Orchestrator produces byte-identical SAL + matching mode/reason_code for
// every vector.
//
// Python brigade is the reference SDK. Any mismatch is a parity bug here.
//
// Patent pending. Inventor: Clay Holberg. License: Apache 2.0.
package brigade

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

type parityVector struct {
	Category   string  `json:"category"`
	NL         string  `json:"nl"`
	SAL        *string `json:"sal"`
	Mode       string  `json:"mode"`
	ReasonCode *string `json:"reason_code"`
}

type parityFile struct {
	SpecVersion  string         `json:"spec_version"`
	ReferenceSDK string         `json:"reference_sdk"`
	Vectors      []parityVector `json:"vectors"`
}

func loadParityVectors(t *testing.T) parityFile {
	t.Helper()
	_, thisFile, _, _ := runtime.Caller(0)
	repoRoot := filepath.Join(filepath.Dir(thisFile), "..", "..", "..", "..")
	vectorsPath := filepath.Join(repoRoot, "tests", "parity", "brigade_parity_vectors.json")
	data, err := os.ReadFile(vectorsPath)
	if err != nil {
		t.Fatalf("failed to read parity vectors at %s: %v", vectorsPath, err)
	}
	var pf parityFile
	if err := json.Unmarshal(data, &pf); err != nil {
		t.Fatalf("failed to parse parity vectors: %v", err)
	}
	return pf
}

func TestBrigadeCrossSDKParity(t *testing.T) {
	pf := loadParityVectors(t)
	if len(pf.Vectors) == 0 {
		t.Fatal("no vectors loaded")
	}
	t.Logf("brigade parity: %s (ref=%s, vectors=%d)",
		pf.SpecVersion, pf.ReferenceSDK, len(pf.Vectors))

	orch := NewOrchestrator()
	for _, v := range pf.Vectors {
		v := v
		t.Run(v.Category+"/"+v.NL, func(t *testing.T) {
			got := orch.ComposeWithHint(v.NL)

			expectedSAL := ""
			if v.SAL != nil {
				expectedSAL = *v.SAL
			}
			expectedReason := ""
			if v.ReasonCode != nil {
				expectedReason = *v.ReasonCode
			}

			if got.SAL != expectedSAL {
				t.Errorf("SAL mismatch:\n  expected: %q\n  got:      %q",
					expectedSAL, got.SAL)
			}
			if string(got.Mode) != v.Mode {
				t.Errorf("mode mismatch: expected=%s got=%s", v.Mode, got.Mode)
			}
			if got.ReasonCode != expectedReason {
				t.Errorf("reason_code mismatch: expected=%q got=%q",
					expectedReason, got.ReasonCode)
			}
		})
	}
}
