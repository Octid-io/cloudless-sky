package osmp

import (
	"fmt"
	"strings"
)

type Encoder struct{ asd *AdaptiveSharedDictionary }

func NewEncoder(asd *AdaptiveSharedDictionary) *Encoder {
	if asd == nil { asd = NewASD() }
	return &Encoder{asd: asd}
}

func (e *Encoder) EncodeFrame(ns, opcode, target, querySlot string,
	slots map[string]string, cc string) (string, error) {
	if ns == "R" {
		if _, ok := consequenceClasses[cc]; !ok {
			return "", fmt.Errorf("R namespace requires consequence class (⚠/↺/⊘), got %q", cc)
		}
	}
	var sb strings.Builder
	sb.WriteString(ns); sb.WriteString(":"); sb.WriteString(opcode)
	if target != "" { sb.WriteString("@"); sb.WriteString(target) }
	if querySlot != "" { sb.WriteString("?"); sb.WriteString(querySlot) }
	for k, v := range slots { sb.WriteString(":"); sb.WriteString(k); sb.WriteString(":"); sb.WriteString(v) }
	if cc != "" { sb.WriteString(cc) }
	return sb.String(), nil
}

func (e *Encoder) EncodeCompound(left, op, right string) (string, error) {
	if _, ok := glyphOperators[op]; !ok {
		if _, ok2 := compoundOperators[op]; !ok2 {
			return "", fmt.Errorf("unknown operator: %q", op)
		}
	}
	return left + op + right, nil
}

func (e *Encoder) EncodeParallel(instructions []string) string {
	parts := make([]string, len(instructions))
	for i, inst := range instructions {
		if strings.HasPrefix(inst, "?") { parts[i] = inst } else { parts[i] = "?" + inst }
	}
	return "A∥[" + strings.Join(parts, "∧") + "]"
}

func (e *Encoder) EncodeSequence(instructions []string) string { return strings.Join(instructions, ";") }
func (e *Encoder) EncodeBroadcast(ns, opcode string) string    { return ns + ":" + opcode + "@*" }

// Static glyph tables for encoder validation
var glyphOperators = map[string]bool{
	"∧":true,"∨":true,"¬":true,"→":true,"↔":true,"∀":true,"∃":true,
	"∥":true,">":true,"~":true,"*":true,":":true,";":true,"?":true,"@":true,
	"⟳":true,"≠":true,"⊕":true,
}
var compoundOperators = map[string]bool{"¬→":true}
var consequenceClasses = map[string]bool{"⚠":true,"↺":true,"⊘":true}
