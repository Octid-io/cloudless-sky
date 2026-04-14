package osmp

// Tier 1 API: Package-level functions. Zero instantiation.
//
//     import "github.com/octid-io/cloudless-sky/sdk/go/osmp"
//
//     sal := osmp.Encode([]string{"H:HR@NODE1>120", "H:CASREP", "M:EVA@*"})
//     text := osmp.Decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
//
// Singleton ASD, encoder, and decoder are initialized on first call
// via sync.Once. Thread-safe.
//
// Patent pending -- inventor Clay Holberg
// License: Apache 2.0

import (
	"fmt"
	"strings"
	"sync"
)

var (
	once    sync.Once
	defASD  *AdaptiveSharedDictionary
	defEnc  *Encoder
	defDec  *Decoder
)

func init1() {
	once.Do(func() {
		defASD = NewASD()
		defEnc = NewEncoder(defASD)
		defDec = NewDecoder(defASD)
	})
}

// Encode joins opcode strings into a SAL instruction chain.
//
//     osmp.Encode([]string{"H:HR@NODE1>120", "H:CASREP", "M:EVA@*"})
//     // => "H:HR@NODE1>120;H:CASREP;M:EVA@*"
func Encode(instructions []string) string {
	init1()
	return defEnc.EncodeSequence(instructions)
}

// Decode expands a SAL instruction chain to natural language.
// Each frame is resolved by ASD dictionary lookup. Zero inference.
//
//     osmp.Decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
//     // => "H:heart_rate @NODE1 >120; H:casualty_report; M:evacuation @*"
func Decode(sal string) string {
	init1()
	frames := strings.Split(sal, ";")
	parts := make([]string, 0, len(frames))
	for _, frame := range frames {
		frame = strings.TrimSpace(frame)
		if frame == "" {
			continue
		}
		parts = append(parts, decodeFrameNL(defDec, frame))
	}
	return strings.Join(parts, "; ")
}

// decodeFrameNL decodes a single SAL frame to a natural-language string.
// Mirrors Python SALDecoder.decode_natural_language.
func decodeFrameNL(dec *Decoder, frame string) string {
	d, err := dec.DecodeFrame(frame)
	if err != nil {
		return fmt.Sprintf("[malformed: %q]", frame)
	}
	meaning := d.OpcodeMeaning
	if meaning == "" {
		meaning = d.Opcode
	}
	var sb strings.Builder
	sb.WriteString(d.Namespace)
	sb.WriteString(":")
	sb.WriteString(meaning)
	if d.Target != "" {
		if d.Target == "*" {
			sb.WriteString(" \u2192*")
		} else {
			sb.WriteString(" \u2192")
			sb.WriteString(d.Target)
		}
	}
	if d.QuerySlot != "" {
		sb.WriteString(" ?")
		sb.WriteString(d.QuerySlot)
	}
	for k, v := range d.Slots {
		sb.WriteString(" ")
		sb.WriteString(k)
		sb.WriteString("=")
		sb.WriteString(v)
	}
	if d.ConsequenceClassName != "" {
		sb.WriteString(" [")
		sb.WriteString(d.ConsequenceClassName)
		sb.WriteString("]")
	}
	return sb.String()
}

// Validate checks a SAL instruction chain against all composition rules.
// Returns a CompositionResult with Valid (bool) and Issues ([]CompositionIssue).
func Validate(sal string) *CompositionResult {
	init1()
	return ValidateComposition(sal, "", defASD, false, nil)
}

// ValidateWithRules checks a SAL chain against composition rules including
// regulatory dependency rules loaded from an MDR corpus.
func ValidateWithRules(sal string, rules []DependencyRule) *CompositionResult {
	init1()
	return ValidateComposition(sal, "", defASD, false, rules)
}

// Lookup resolves an opcode definition from the ASD.
// Accepts "H:HR" format. Returns the definition string, or empty if not found.
func Lookup(nsOpcode string) string {
	init1()
	parts := strings.SplitN(nsOpcode, ":", 2)
	if len(parts) != 2 {
		return ""
	}
	return defASD.Lookup(parts[0], parts[1])
}

// ByteSize returns the UTF-8 byte count of a SAL string.
func ByteSize(sal string) int {
	return len([]byte(sal))
}
