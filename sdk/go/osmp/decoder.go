package osmp

import "strings"

type DecodedInstruction struct {
	Namespace, Opcode, OpcodeMeaning      string
	Target, QuerySlot                     string
	Slots                                 map[string]string
	ConsequenceClass, ConsequenceClassName string
	Raw                                   string
}

type Decoder struct{ asd *AdaptiveSharedDictionary }

func NewDecoder(asd *AdaptiveSharedDictionary) *Decoder {
	if asd == nil { asd = NewASD() }
	return &Decoder{asd: asd}
}

func (d *Decoder) resolveShortForm(op string) string {
	for ns, ops := range ASDFloorBasis {
		if _, ok := ops[op]; ok { return ns }
	}
	return "A"
}

func firstStop(s string, stops []string) int {
	earliest := len(s)
	for _, sc := range stops {
		if i := strings.Index(s, sc); i != -1 && i < earliest { earliest = i }
	}
	return earliest
}

var ccNames = map[string]string{"⚠":"HAZARDOUS","↺":"REVERSIBLE","⊘":"IRREVERSIBLE"}

func (d *Decoder) DecodeFrame(encoded string) (DecodedInstruction, error) {
	raw := strings.TrimSpace(encoded)
	rem := raw

	var cc, ccName string
	for g, name := range ccNames {
		if strings.HasSuffix(rem, g) {
			cc = g; ccName = name
			runes := []rune(rem); gr := []rune(g)
			rem = string(runes[:len(runes)-len(gr)])
			break
		}
	}

	beforeTarget := rem
	if i := strings.Index(rem, "@"); i != -1 { beforeTarget = rem[:i] }
	if i := strings.Index(beforeTarget, "?"); i != -1 { beforeTarget = beforeTarget[:i] }
	hasExplicit := strings.Contains(beforeTarget, ":")

	var ns string
	if hasExplicit {
		ci := strings.Index(rem, ":")
		ns = rem[:ci]; rem = rem[ci+1:]
	} else {
		pre := rem
		if i := strings.Index(rem, "@"); i != -1 { pre = rem[:i] }
		if i := strings.Index(pre, "?"); i != -1 { pre = pre[:i] }
		ns = d.resolveShortForm(pre)
	}

	opEnd := firstStop(rem, []string{"@","?",":"})
	opcode := rem[:opEnd]; rem = rem[opEnd:]
	meaning := d.asd.Lookup(ns, opcode)

	var target string
	if strings.HasPrefix(rem, "@") {
		rem = rem[1:]
		e := firstStop(rem, []string{"?",":","∧","∨","→","↔",";","∥"})
		target = rem[:e]; rem = rem[e:]
	}

	var querySlot string
	if strings.HasPrefix(rem, "?") {
		rem = rem[1:]
		e := firstStop(rem, []string{":","∧","∨","→",";"})
		querySlot = rem[:e]; rem = rem[e:]
	}

	slots := make(map[string]string)
	for strings.HasPrefix(rem, ":") {
		rem = rem[1:]
		ci := strings.Index(rem, ":")
		if ci == -1 { slots[rem] = ""; rem = ""; break }
		sn := rem[:ci]; rem = rem[ci+1:]
		ve := firstStop(rem, []string{":","∧","∨","→",";","⚠","↺","⊘"})
		slots[sn] = rem[:ve]; rem = rem[ve:]
	}

	return DecodedInstruction{
		Namespace: ns, Opcode: opcode, OpcodeMeaning: meaning,
		Target: target, QuerySlot: querySlot, Slots: slots,
		ConsequenceClass: cc, ConsequenceClassName: ccName, Raw: raw,
	}, nil
}
