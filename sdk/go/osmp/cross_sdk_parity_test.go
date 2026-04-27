// Cross-SDK Parity Test (Go reader)
// ==================================
//
// Reads tests/parity/parity_vectors.json (generated from Python via
// tests/parity/gen_parity_vectors.py) and asserts this SDK's composer
// produces byte-identical SAL for every vector.
//
// Python is the reference SDK. Any mismatch is a parity bug here.
//
// Patent pending | License: Apache 2.0
package osmp_test

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
	_ "github.com/octid-io/cloudless-sky/sdk/go/osmp/brigade" // wires brigade into osmp.Composer.Compose
)

type parityVector struct {
	Category string  `json:"category"`
	NL       string  `json:"nl"`
	SAL      *string `json:"sal"` // null in JSON → nil pointer
}

type parityFile struct {
	SpecVersion   string         `json:"spec_version"`
	ReferenceSDK  string         `json:"reference_sdk"`
	MacroCorpus   string         `json:"macro_corpus"`
	MacrosLoaded  int            `json:"macros_loaded"`
	Vectors       []parityVector `json:"vectors"`
}

func parityRepoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, _ := runtime.Caller(0)
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", ".."))
}

func loadParityFile(t *testing.T) parityFile {
	t.Helper()
	path := filepath.Join(parityRepoRoot(t), "tests", "parity", "parity_vectors.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read parity vectors: %v", err)
	}
	var pf parityFile
	if err := json.Unmarshal(data, &pf); err != nil {
		t.Fatalf("parse parity vectors: %v", err)
	}
	return pf
}

func loadParityComposer(t *testing.T) *osmp.Composer {
	t.Helper()
	path := filepath.Join(parityRepoRoot(t), "mdr", "meshtastic", "meshtastic-macros.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read corpus: %v", err)
	}
	reg := osmp.NewMacroRegistry(nil)
	if _, err := reg.LoadCorpus(data); err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	return osmp.NewComposerWithMacros(nil, reg)
}

func TestCrossSDKParity_CorpusCount(t *testing.T) {
	pf := loadParityFile(t)
	path := filepath.Join(parityRepoRoot(t), "mdr", "meshtastic", "meshtastic-macros.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read corpus: %v", err)
	}
	reg := osmp.NewMacroRegistry(nil)
	count, err := reg.LoadCorpus(data)
	if err != nil {
		t.Fatalf("load corpus: %v", err)
	}
	if count != pf.MacrosLoaded {
		t.Errorf("loaded %d macros; ref SDK loaded %d", count, pf.MacrosLoaded)
	}
}

func TestCrossSDKParity_AllVectors(t *testing.T) {
	pf := loadParityFile(t)
	c := loadParityComposer(t)

	for _, v := range pf.Vectors {
		v := v // capture
		name := fmt.Sprintf("[%s] %s", v.Category, v.NL)
		t.Run(name, func(t *testing.T) {
			got := c.Compose(v.NL, nil)
			want := ""
			if v.SAL != nil {
				want = *v.SAL
			}
			if got != want {
				if v.SAL == nil {
					t.Errorf("expected PASSTHROUGH (empty); got %q", got)
				} else {
					t.Errorf("parity mismatch:\n  nl   %q\n  got  %q\n  want %q",
						v.NL, got, want)
				}
			}
		})
	}
}
