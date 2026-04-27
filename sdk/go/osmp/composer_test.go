package osmp_test

import (
	"strings"
	"testing"

	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)

func TestComposerBasicComposition(t *testing.T) {
	c := osmp.NewComposer(nil)

	cases := []struct {
		nl       string
		wantSAL  bool
		contains string // substring that must appear in the SAL
	}{
		{"Alert if heart rate exceeds 130", true, "H:HR"},
		{"Order me some tacos", false, ""},
		{"Stop everything immediately. Emergency.", true, "R:ESTOP"},
		{"What is the wind and visibility?", true, "W:WIND"},
		{"Hey, how is it going?", false, ""},
		{"Go.", false, ""},
		{"Stop.", false, ""},
	}

	for _, tc := range cases {
		sal, isSAL := c.ComposeOrPassthrough(tc.nl, nil)
		if isSAL != tc.wantSAL {
			t.Errorf("ComposeOrPassthrough(%q): got isSAL=%v, want %v (sal=%q)",
				tc.nl, isSAL, tc.wantSAL, sal)
			continue
		}
		if tc.contains != "" && !strings.Contains(sal, tc.contains) {
			t.Errorf("ComposeOrPassthrough(%q): sal=%q missing %q",
				tc.nl, sal, tc.contains)
		}
	}
}

func TestComposerPassthrough(t *testing.T) {
	c := osmp.NewComposer(nil)

	// Brigade-era passthroughs: inputs that produce no protocol-relevant
	// SAL across all three SDKs. "Send an email to the team" was on this
	// list pre-brigade but now resolves to D:PUSH@TEAM under the brigade
	// composer (the verb 'send' + entity target is a legitimate D:PUSH
	// frame), matching Python and TypeScript.
	passthroughs := []string{
		"Order me some tacos",
		"Book me a flight to Denver",
		"Post this photo to Instagram",
		"What is 247 times 83?",
		"Who painted the Mona Lisa?",
	}

	for _, nl := range passthroughs {
		sal := c.Compose(nl, nil)
		if sal != "" {
			t.Errorf("Compose(%q) should be passthrough, got %q", nl, sal)
		}
	}
}

func TestComposerPhraseIndex(t *testing.T) {
	c := osmp.NewComposer(nil)

	// Curated trigger: "fire alarm" -> B:ALRM
	sal := c.Compose("Fire alarm in the building", nil)
	if sal == "" || !strings.Contains(sal, "B:ALRM") {
		t.Errorf("fire alarm should resolve B:ALRM, got %q", sal)
	}

	// Curated trigger: "generate key" -> S:KEYGEN
	intent := c.ExtractIntentKeywords("Generate a key pair")
	found := false
	for _, a := range intent.Actions {
		if a == "key pair" || a == "generate key" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected phrase match for 'key pair' or 'generate key', actions=%v", intent.Actions)
	}
}
