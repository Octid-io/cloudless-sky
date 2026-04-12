// FNP Dictionary Basis Wire-Level Tests (ADR-004)
//
// Mirrors tests/test_fnp_basis.py and sdk/typescript/tests/fnp_basis.test.ts.
// Verifies the wire-level FNP changes that carry the Dictionary Basis
// Manifest through the capability handshake.
package osmp

import (
	"bytes"
	"encoding/hex"
	"testing"
)

// ─── ADV wire layout: base form ────────────────────────────────────────────

func TestBasisFNP_BaseForm_MsgType(t *testing.T) {
	asd := NewASD()
	s := NewFNPSession(asd, "NODE_A", 1, FNPCapFloor)
	adv, err := s.Initiate()
	if err != nil {
		t.Fatal(err)
	}
	if adv[0] != FNPMsgADV {
		t.Errorf("expected msg_type 0x01, got 0x%02x", adv[0])
	}
	if adv[0]&FNPADVExtFlag != 0 {
		t.Errorf("base form must not set extended flag")
	}
}

func TestBasisFNP_BaseForm_TotalSize(t *testing.T) {
	asd := NewASD()
	s := NewFNPSession(asd, "NODE_A", 1, FNPCapFloor)
	adv, _ := s.Initiate()
	if len(adv) != 40 {
		t.Errorf("expected 40-byte ADV, got %d", len(adv))
	}
}

func TestBasisFNP_BaseForm_NodeIdField23Bytes(t *testing.T) {
	asd := NewASD()
	s := NewFNPSession(asd, "NODE_LONG_NAME_22BYTES", 1, FNPCapFloor)
	adv, _ := s.Initiate()
	if !bytes.Contains(adv[17:40], []byte("NODE_LONG_NAME_22BYTES")) {
		t.Error("base-form node_id field should fit 22-byte ID in 23-byte slot")
	}
}

func TestBasisFNP_BaseForm_ParseNoBasisFingerprint(t *testing.T) {
	asd := NewASD()
	s := NewFNPSession(asd, "NODE_A", 1, FNPCapFloor)
	adv, _ := s.Initiate()
	parsed, err := parseADV(adv)
	if err != nil {
		t.Fatal(err)
	}
	if parsed.isExtended {
		t.Error("base form must parse as not extended")
	}
	if parsed.basisFingerprint != nil {
		t.Error("base form must have nil basisFingerprint")
	}
}

// ─── ADV wire layout: extended form ────────────────────────────────────────

func TestBasisFNP_ExtendedForm_MsgType(t *testing.T) {
	asd := NewASD()
	bfp := []byte{0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88}
	s := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bfp})
	adv, _ := s.Initiate()
	if adv[0] != FNPMsgADVExtended {
		t.Errorf("expected msg_type 0x81, got 0x%02x", adv[0])
	}
	if adv[0]&FNPADVExtFlag != FNPADVExtFlag {
		t.Error("extended form must set extended flag")
	}
}

func TestBasisFNP_ExtendedForm_TotalSize40(t *testing.T) {
	asd := NewASD()
	bfp := bytes.Repeat([]byte{0xaa}, 8)
	s := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bfp})
	adv, _ := s.Initiate()
	if len(adv) != 40 {
		t.Errorf("extended form must stay at 40 bytes, got %d", len(adv))
	}
}

func TestBasisFNP_ExtendedForm_BasisFpAtOffset32(t *testing.T) {
	asd := NewASD()
	bfp := []byte{0, 1, 2, 3, 4, 5, 6, 7}
	s := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bfp})
	adv, _ := s.Initiate()
	if !bytes.Equal(adv[32:40], bfp) {
		t.Errorf("basis fingerprint at offset 32 mismatch: got %s", hex.EncodeToString(adv[32:40]))
	}
}

func TestBasisFNP_ExtendedForm_MeshtasticIdFits(t *testing.T) {
	asd := NewASD()
	bfp := bytes.Repeat([]byte{0xaa}, 8)
	s := NewFNPSessionWithOptions(asd, "!2048ad45", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bfp})
	adv, _ := s.Initiate()
	if !bytes.Contains(adv[17:32], []byte("!2048ad45")) {
		t.Error("9-byte Meshtastic-style ID should fit the 15-byte field")
	}
}

func TestBasisFNP_ExtendedForm_LongIdTruncatedNotOverwritingBfp(t *testing.T) {
	asd := NewASD()
	bfp := bytes.Repeat([]byte{0xaa}, 8)
	s := NewFNPSessionWithOptions(asd, "NODE_LONG_NAME_22BYTES", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bfp})
	adv, _ := s.Initiate()
	if !bytes.Equal(adv[32:40], bfp) {
		t.Error("long node_id must be truncated, not overwriting basis fingerprint")
	}
}

func TestBasisFNP_ExtendedForm_RoundTripParse(t *testing.T) {
	asd := NewASD()
	bfp := []byte{0xde, 0xad, 0xbe, 0xef, 0xca, 0xfe, 0xba, 0xbe}
	s := NewFNPSessionWithOptions(asd, "NODE_X", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bfp})
	adv, _ := s.Initiate()
	parsed, err := parseADV(adv)
	if err != nil {
		t.Fatal(err)
	}
	if !parsed.isExtended {
		t.Error("parsed.isExtended should be true")
	}
	if !bytes.Equal(parsed.basisFingerprint, bfp) {
		t.Error("parsed basis fingerprint mismatch")
	}
	if parsed.nodeID != "NODE_X" {
		t.Errorf("parsed nodeID %q, want NODE_X", parsed.nodeID)
	}
}

// ─── State machine: ESTABLISHED_SAIL vs ESTABLISHED_SAL_ONLY ───────────────

func makePair(fpA, fpB []byte, requireSailA bool) (*FNPSession, *FNPSession) {
	asd := NewASD()
	a := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{
		BasisFingerprint: fpA,
		RequireSail:      requireSailA,
	})
	b := NewFNPSessionWithOptions(asd, "NODE_B", 1, FNPCapFloor, &FNPSessionOptions{
		BasisFingerprint: fpB,
	})
	return a, b
}

func handshake(t *testing.T, a, b *FNPSession) {
	t.Helper()
	adv, err := a.Initiate()
	if err != nil {
		t.Fatal(err)
	}
	ack, err := b.Receive(adv)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := a.Receive(ack); err != nil {
		t.Fatal(err)
	}
}

func TestBasisFNP_State_BothBaseFormSAIL(t *testing.T) {
	a, b := makePair(nil, nil, false)
	handshake(t, a, b)
	if a.State != FNPStateEstablishedSAIL || b.State != FNPStateEstablishedSAIL {
		t.Errorf("expected both ESTABLISHED_SAIL, got A=%s B=%s", a.State, b.State)
	}
	if a.MatchStatus != FNPMatchExact {
		t.Errorf("expected match_status 0x00, got 0x%02x", a.MatchStatus)
	}
	if !a.IsSailCapable() || !b.IsSailCapable() {
		t.Error("both peers should be SAIL-capable")
	}
}

func TestBasisFNP_State_MatchingExtendedSAIL(t *testing.T) {
	bfp := []byte{1, 2, 3, 4, 5, 6, 7, 8}
	a, b := makePair(bfp, bfp, false)
	handshake(t, a, b)
	if a.State != FNPStateEstablishedSAIL || b.State != FNPStateEstablishedSAIL {
		t.Errorf("expected both ESTABLISHED_SAIL, got A=%s B=%s", a.State, b.State)
	}
	if a.MatchStatus != FNPMatchExact {
		t.Errorf("expected match_status 0x00, got 0x%02x", a.MatchStatus)
	}
}

func TestBasisFNP_State_MismatchedExtendedSALOnly(t *testing.T) {
	a, b := makePair(bytes.Repeat([]byte{0x01}, 8), bytes.Repeat([]byte{0x02}, 8), false)
	handshake(t, a, b)
	if a.State != FNPStateEstablishedSALOnly || b.State != FNPStateEstablishedSALOnly {
		t.Errorf("expected both ESTABLISHED_SAL_ONLY, got A=%s B=%s", a.State, b.State)
	}
	if a.MatchStatus != FNPMatchBasisMismatch {
		t.Errorf("expected match_status 0x03, got 0x%02x", a.MatchStatus)
	}
	if a.IsSailCapable() || b.IsSailCapable() {
		t.Error("neither peer should be SAIL-capable")
	}
}

func TestBasisFNP_State_ExtendedVsBaseSALOnly(t *testing.T) {
	a, b := makePair(bytes.Repeat([]byte{0xab}, 8), nil, false)
	handshake(t, a, b)
	if a.State != FNPStateEstablishedSALOnly || b.State != FNPStateEstablishedSALOnly {
		t.Errorf("expected both ESTABLISHED_SAL_ONLY, got A=%s B=%s", a.State, b.State)
	}
	if a.MatchStatus != FNPMatchBasisExtVsBase || b.MatchStatus != FNPMatchBasisExtVsBase {
		t.Errorf("expected match_status 0x04, got A=0x%02x B=0x%02x", a.MatchStatus, b.MatchStatus)
	}
}

func TestBasisFNP_State_BaseVsExtendedSALOnly(t *testing.T) {
	a, b := makePair(nil, bytes.Repeat([]byte{0xab}, 8), false)
	handshake(t, a, b)
	if a.State != FNPStateEstablishedSALOnly || b.State != FNPStateEstablishedSALOnly {
		t.Errorf("expected both ESTABLISHED_SAL_ONLY, got A=%s B=%s", a.State, b.State)
	}
	if a.MatchStatus != FNPMatchBasisExtVsBase || b.MatchStatus != FNPMatchBasisExtVsBase {
		t.Errorf("expected match_status 0x04, got A=0x%02x B=0x%02x", a.MatchStatus, b.MatchStatus)
	}
}

// ─── require_sail policy ───────────────────────────────────────────────────

func TestBasisFNP_RequireSail_RefusesMismatch(t *testing.T) {
	a, b := makePair(bytes.Repeat([]byte{0x01}, 8), bytes.Repeat([]byte{0x02}, 8), true)
	handshake(t, a, b)
	if a.State != FNPStateIdle {
		t.Errorf("require_sail initiator should refuse to IDLE, got %s", a.State)
	}
	if a.DegradationEvent == nil {
		t.Error("require_sail refusal should record a degradation event")
	}
	if b.State != FNPStateEstablishedSALOnly {
		t.Errorf("responder without policy should still establish SAL_ONLY, got %s", b.State)
	}
}

func TestBasisFNP_RequireSail_DoesNotAffectMatching(t *testing.T) {
	bfp := bytes.Repeat([]byte{0x42}, 8)
	a, b := makePair(bfp, bfp, true)
	handshake(t, a, b)
	if a.State != FNPStateEstablishedSAIL {
		t.Errorf("require_sail with matching basis should still ESTABLISHED_SAIL, got %s", a.State)
	}
	if a.DegradationEvent != nil {
		t.Error("matching basis should not record a degradation event")
	}
}

func TestBasisFNP_RequireSail_DoesNotAffectBaseForm(t *testing.T) {
	asd := NewASD()
	a := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{RequireSail: true})
	b := NewFNPSession(asd, "NODE_B", 1, FNPCapFloor)
	handshake(t, a, b)
	if a.State != FNPStateEstablishedSAIL {
		t.Errorf("require_sail with base form pair should ESTABLISHED_SAIL, got %s", a.State)
	}
}

// ─── Degradation event recording ───────────────────────────────────────────

func TestBasisFNP_Degradation_ResponderRecordsEvent(t *testing.T) {
	asd := NewASD()
	local := bytes.Repeat([]byte{0xaa}, 8)
	remote := bytes.Repeat([]byte{0xbb}, 8)
	a := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: remote})
	b := NewFNPSessionWithOptions(asd, "NODE_B", 1, FNPCapFloor, &FNPSessionOptions{
		BasisFingerprint:         local,
		ExpectedBasisFingerprint: local,
	})
	adv, _ := a.Initiate()
	if _, err := b.Receive(adv); err != nil {
		t.Fatal(err)
	}
	if b.State != FNPStateEstablishedSALOnly {
		t.Errorf("responder should be ESTABLISHED_SAL_ONLY, got %s", b.State)
	}
	if b.DegradationEvent == nil {
		t.Fatal("responder should record degradation event")
	}
	if b.DegradationEvent["remote_basis_fingerprint"] != hex.EncodeToString(remote) {
		t.Errorf("wrong remote_basis_fingerprint in event: %v", b.DegradationEvent)
	}
}

func TestBasisFNP_Degradation_NoEventWhenNoExpectation(t *testing.T) {
	asd := NewASD()
	a := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bytes.Repeat([]byte{0xaa}, 8)})
	b := NewFNPSessionWithOptions(asd, "NODE_B", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bytes.Repeat([]byte{0xbb}, 8)})
	adv, _ := a.Initiate()
	b.Receive(adv)
	if b.DegradationEvent != nil {
		t.Error("no event should be recorded when no expectation set")
	}
}

func TestBasisFNP_Degradation_NoEventWhenMatch(t *testing.T) {
	asd := NewASD()
	bfp := bytes.Repeat([]byte{0x42}, 8)
	a := NewFNPSessionWithOptions(asd, "NODE_A", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bfp})
	b := NewFNPSessionWithOptions(asd, "NODE_B", 1, FNPCapFloor, &FNPSessionOptions{
		BasisFingerprint:         bfp,
		ExpectedBasisFingerprint: bfp,
	})
	adv, _ := a.Initiate()
	b.Receive(adv)
	if b.State != FNPStateEstablishedSAIL {
		t.Errorf("expected ESTABLISHED_SAIL, got %s", b.State)
	}
	if b.DegradationEvent != nil {
		t.Error("matching basis should not record degradation event")
	}
}

// ─── v1.0.2 backward compatibility ─────────────────────────────────────────

func TestBasisFNP_Compat_ExtendedADVStaysAt40Bytes(t *testing.T) {
	asd := NewASD()
	s := NewFNPSessionWithOptions(asd, "NODE", 1, FNPCapFloor, &FNPSessionOptions{BasisFingerprint: bytes.Repeat([]byte{0}, 8)})
	adv, _ := s.Initiate()
	if len(adv) != fnpADVSize {
		t.Errorf("extended ADV should be %d bytes, got %d", fnpADVSize, len(adv))
	}
}

func TestBasisFNP_Compat_BaseFormByteCompatibleWithV102(t *testing.T) {
	asd := NewASD()
	s := NewFNPSession(asd, "NODE_A", 1, FNPCapFloor)
	adv, _ := s.Initiate()
	if adv[0] != 0x01 {
		t.Errorf("v1.0.2-compatible base form msg_type should be 0x01, got 0x%02x", adv[0])
	}
	if len(adv[17:40]) != 23 {
		t.Errorf("v1.0.2 node_id field should be 23 bytes, got %d", len(adv[17:40]))
	}
}

func TestBasisFNP_Compat_TwoBaseFormNodesNegotiateNormally(t *testing.T) {
	asd := NewASD()
	a := NewFNPSession(asd, "NODE_A", 1, FNPCapFloor)
	b := NewFNPSession(asd, "NODE_B", 1, FNPCapFloor)
	adv, _ := a.Initiate()
	ack, _ := b.Receive(adv)
	a.Receive(ack)
	if len(adv) != 40 || len(ack) != 38 {
		t.Errorf("expected 40-byte ADV and 38-byte ACK, got %d and %d", len(adv), len(ack))
	}
	if a.State != FNPStateEstablishedSAIL || b.State != FNPStateEstablishedSAIL {
		t.Errorf("expected both ESTABLISHED_SAIL, got A=%s B=%s", a.State, b.State)
	}
}
