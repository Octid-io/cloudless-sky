// D:PACK/BLK Tier 1 unit tests — Go
//
// 14 hardcoded test codes (7 ICD-10-CM, 7 ISO 20022).
// Verifies ResolveBlk against exact or prefix-matched SAL descriptions
// from dict-free DBLK binaries.
//
// Run from repo root:
//   go test ./tests/tier1/ -v
//
// Binary paths assume execution from repo root (cloudless-sky/).
package tier1_test

import (
	"os"
	"strings"
	"testing"

	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)

type testCase struct {
	code     string
	expected string
	prefix   bool
}

var icdTests = []testCase{
	{"A000", "Cholera d/t Vibrio cholerae 01, biovar cholerae", false},
	{"E0AW", "Type 2 diabetes mellitus w/o comps", false},
	{"I00Z", "Essential (primary) hypertension", false},
	{"M2AB", "Radiculopathy, lumbar region", false},
	{"R001", "Bradycardia, unsp", false},
	{"S083", "Laceration without foreign body of scalp, init", false},
	{"Z135", "Dependence on supplemental oxygen", false},
}

var isoTests = []testCase{
	{"AAMVAFormat", "AAMVAFormat: American driver license.", false},
	{"ACH", "ACH: Automated Clearing House.", true},
	{"AccountIdentification4Choice", "AcctID4Choice:", true},
	{"ActiveCurrencyAndAmount", "ActiveCcyAndAmt:", true},
	{"PaymentIdentification7", "PmtID7: Provides further means of referencing a pmt txn.", false},
	{"SupplementaryData1", "SupplementaryData1:", true},
	{"TransactionReferences6", "TxnRefs6: Identifies the underlying txn.", false},
}

func loadBinary(t *testing.T, path string) []byte {
	t.Helper()
	// Paths are relative to repo root; adjust from tests/tier1/
	full := "../../" + path
	data, err := os.ReadFile(full)
	if err != nil {
		t.Fatalf("Failed to read %s: %v", full, err)
	}
	return data
}

func TestDpackICD(t *testing.T) {
	data := loadBinary(t, "mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack")
	for _, tc := range icdTests {
		t.Run(tc.code, func(t *testing.T) {
			got, err := osmp.ResolveBlk(data, tc.code)
			if err != nil {
				t.Fatalf("ResolveBlk error: %v", err)
			}
			if got == "" {
				t.Fatalf("ResolveBlk returned empty for %s", tc.code)
			}
			if tc.prefix {
				if !strings.HasPrefix(got, tc.expected) {
					t.Errorf("prefix mismatch\n  got:  %s\n  want: %s...", got[:80], tc.expected)
				}
			} else {
				if got != tc.expected {
					t.Errorf("exact mismatch\n  got:  %s\n  want: %s", got, tc.expected)
				}
			}
		})
	}
}

func TestDpackISO(t *testing.T) {
	data := loadBinary(t, "mdr/iso20022/MDR-ISO20022-K-ISO-blk.dpack")
	for _, tc := range isoTests {
		t.Run(tc.code, func(t *testing.T) {
			got, err := osmp.ResolveBlk(data, tc.code)
			if err != nil {
				t.Fatalf("ResolveBlk error: %v", err)
			}
			if got == "" {
				t.Fatalf("ResolveBlk returned empty for %s", tc.code)
			}
			if tc.prefix {
				if !strings.HasPrefix(got, tc.expected) {
					t.Errorf("prefix mismatch\n  got:  %s\n  want: %s...", got[:80], tc.expected)
				}
			} else {
				if got != tc.expected {
					t.Errorf("exact mismatch\n  got:  %s\n  want: %s", got, tc.expected)
				}
			}
		})
	}
}
