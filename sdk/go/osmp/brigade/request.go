// Package brigade — ParsedRequest IR + types.
//
// Faithful Go port of sdk/python/osmp/brigade/request.py. Set up once by
// the grammar parser; every station reads from this immutable shared
// structure to produce its frame proposals.
//
// Patent pending. Inventor: Clay Holberg. License: Apache 2.0.
package brigade

import "strings"

type Condition struct {
	Operator string // ">", "<", ">=", "<=", "==", "!="
	Value    string
	BoundTo  string
}

type SlotValue struct {
	Key       string
	Value     string
	ValueType string // "string", "uint", "float", "code", "duration", "latlon", "time"
}

type Target struct {
	ID     string // what goes after @
	Kind   string // "drone", "node", "*", "patient"
	Source string // "entity", "preposition", "implicit"
}

type ParsedRequest struct {
	Raw string

	Verb              string
	VerbLemma         string
	DirectObject      string
	DirectObjectKind  string

	Targets     []Target
	SlotValues  []SlotValue
	Conditions  []Condition

	Schedule              string
	AuthorizationRequired bool
	IsEmergency           bool
	IsBroadcast           bool
	IsQuery               bool
	IsPassthroughLikely   bool
	IsNegated             bool
	HasGlyphInjection     bool

	ChainSegments []ParsedRequest
	ChainOperator string

	NamespaceHints []string
	DomainHint     string
}

type FrameProposal struct {
	Namespace        string
	Opcode           string
	Target           string
	SlotValues       []SlotValue
	ConsequenceClass string
	IsQuery          bool
	Confidence       float64
	Rationale        string
}

// Assemble produces the canonical SAL frame string.
// Mirrors Python FrameProposal.assemble() and TS assembleFrame().
func (p FrameProposal) Assemble() string {
	var b strings.Builder
	b.WriteString(p.Namespace)
	b.WriteString(":")
	b.WriteString(p.Opcode)
	if p.ConsequenceClass != "" {
		b.WriteString(p.ConsequenceClass)
	}
	if p.Target != "" {
		b.WriteString("@")
		b.WriteString(p.Target)
	}
	if p.IsQuery {
		b.WriteString("?")
	}
	if len(p.SlotValues) > 0 {
		if len(p.SlotValues) == 1 && (p.SlotValues[0].Key == "" || p.SlotValues[0].Key == "_") {
			b.WriteString("[")
			b.WriteString(p.SlotValues[0].Value)
			b.WriteString("]")
		} else {
			b.WriteString("[")
			for i, sv := range p.SlotValues {
				if i > 0 {
					b.WriteString(",")
				}
				if sv.Key != "" {
					b.WriteString(sv.Key)
					b.WriteString(":")
				}
				b.WriteString(sv.Value)
			}
			b.WriteString("]")
		}
	}
	return b.String()
}

func EmptyParsedRequest(raw string) ParsedRequest {
	return ParsedRequest{Raw: raw}
}

// MakeProposal default-constructs a FrameProposal with confidence 1.0.
func MakeProposal(ns, opcode string) FrameProposal {
	return FrameProposal{Namespace: ns, Opcode: opcode, Confidence: 1.0}
}
