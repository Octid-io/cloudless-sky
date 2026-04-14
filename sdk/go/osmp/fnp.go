// Package osmp provides the OSMP protocol implementation.
//
// This file implements the Frame Negotiation Protocol (FNP):
// two-message capability advertisement + acknowledgment completing
// within 78 bytes total (40 ADV + 38 ACK), designed for the LoRa
// physical layer payload floor.
//
// Negotiates three properties in two packets:
//   1. Dictionary alignment (ASD fingerprint match)
//   2. Namespace intersection (shared domain capabilities)
//   3. Channel capacity (byte budget for the session)
//
package osmp

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
)

// FNP message types
const (
	FNPMsgADV  = 0x01
	FNPMsgACK  = 0x02
	FNPMsgNACK = 0x03

	// ADR-004: extended-form ADV signaled by msg_type bit 7 (high bit set).
	// Extended form narrows node_id from 23 to 15 bytes and carries an
	// 8-byte basis_fingerprint at offset 32. Total ADV size remains 40
	// bytes in both forms; only the field layout differs. See spec §9.1.
	FNPMsgADVExtended = 0x81
	FNPADVExtFlag     = 0x80
)

// FNP match status codes
const (
	FNPMatchExact            = 0x00
	FNPMatchVersion          = 0x01
	FNPMatchFingerprint      = 0x02
	FNPMatchBasisMismatch    = 0x03 // ADR-004: ASD matches, bases differ (both extended)
	FNPMatchBasisExtVsBase   = 0x04 // ADR-004: ASD matches, base form vs extended (length mismatch)
)

// FNP channel capacity classes
const (
	FNPCapFloor         = 0x00 // 51 bytes (LoRa SF12 BW125kHz)
	FNPCapStandard      = 0x01 // 255 bytes (LoRa SF11 BW250kHz)
	FNPCapBLE           = 0x02 // 512 bytes
	FNPCapUnconstrained = 0x03 // no limit
)

// FNPCapBytes maps capacity class to byte budget.
var FNPCapBytes = map[byte]int{
	FNPCapFloor:         51,
	FNPCapStandard:      255,
	FNPCapBLE:           512,
	FNPCapUnconstrained: 0,
}

const (
	fnpADVSize         = 40
	fnpACKSize         = 38
	fnpProtocolVersion = 0x01
)

const nsLetters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

// FNP state
type FNPState string

const (
	FNPStateIdle             FNPState = "IDLE"
	FNPStateADVSent          FNPState = "ADV_SENT"
	FNPStateEstablished      FNPState = "ESTABLISHED"
	FNPStateEstablishedSAIL  FNPState = "ESTABLISHED_SAIL"
	FNPStateEstablishedSALOnly FNPState = "ESTABLISHED_SAL_ONLY"
	FNPStateSyncNeeded       FNPState = "SYNC_NEEDED"
	FNPStateFallback         FNPState = "FALLBACK"
	FNPStateAcquired         FNPState = "ACQUIRED"
)

// FNPSession manages the two-message handshake between sovereign nodes.
//
// Usage (initiator):
//
//	session := NewFNPSession(asd, "NODE_A", 1, FNPCapFloor)
//	adv := session.Initiate()
//	// ... transmit adv, receive ackPacket ...
//	session.Receive(ackPacket)
//	// session.State == FNPStateEstablished
//
// Usage (responder):
//
//	session := NewFNPSession(asd, "NODE_B", 1, FNPCapFloor)
//	ack, _ := session.Receive(advPacket)
//	// ... transmit ack ...
//	// session.State == FNPStateEstablished
type FNPSession struct {
	State               FNPState
	RemoteNodeID        string
	RemoteFingerprint   []byte
	CommonNamespaces    []string
	MatchStatus         int
	NegotiatedCapacity  int

	// ADR-004 basis manifest support
	BasisFingerprint         []byte // 8 bytes when set; nil for base-form sessions
	ExpectedBasisFingerprint []byte
	RequireSail              bool
	RemoteBasisFingerprint   []byte
	DegradationEvent         map[string]interface{}

	asd             *AdaptiveSharedDictionary
	nodeID          string
	asdVersion      uint16
	channelCapacity byte
	ownFp           []byte
	ownBitmap       uint32
}

// NewFNPSession creates a new FNP session in IDLE state.
func NewFNPSession(asd *AdaptiveSharedDictionary, nodeID string, asdVersion uint16, channelCapacity byte) *FNPSession {
	return &FNPSession{
		State:           FNPStateIdle,
		MatchStatus:     -1,
		NegotiatedCapacity: -1,
		asd:             asd,
		nodeID:          nodeID,
		asdVersion:      asdVersion,
		channelCapacity: channelCapacity,
		ownFp:           fingerprintBytesGo(asd),
		ownBitmap:       namespaceBitmapGo(asd.Namespaces()),
	}
}

// FNPSessionOptions configures ADR-004 basis manifest behavior on a session.
type FNPSessionOptions struct {
	// BasisFingerprint, when set to an 8-byte value, switches the session
	// to extended-form ADV (msg_type 0x81) with the basis fingerprint
	// carried in the wire packet at offset 32. When nil, the session uses
	// base-form ADV and is treated as base-ASD-only.
	BasisFingerprint []byte

	// ExpectedBasisFingerprint, when set, causes the session to record a
	// degradation event when a peer presents a different basis fingerprint
	// than expected. Used for operator monitoring.
	ExpectedBasisFingerprint []byte

	// RequireSail is the operator policy flag that converts SAL-only
	// sessions (basis mismatch) into local refusals.
	RequireSail bool
}

// NewFNPSessionWithOptions creates a new FNP session with ADR-004 basis
// manifest support. Pass nil for opts to behave like NewFNPSession.
func NewFNPSessionWithOptions(asd *AdaptiveSharedDictionary, nodeID string, asdVersion uint16, channelCapacity byte, opts *FNPSessionOptions) *FNPSession {
	s := NewFNPSession(asd, nodeID, asdVersion, channelCapacity)
	if opts != nil {
		if opts.BasisFingerprint != nil {
			if len(opts.BasisFingerprint) != 8 {
				// Defensive: silently ignore malformed inputs would mask
				// configuration bugs. Caller is expected to pass exactly
				// 8 bytes.
				panic("BasisFingerprint must be exactly 8 bytes")
			}
			s.BasisFingerprint = append([]byte{}, opts.BasisFingerprint...)
		}
		if opts.ExpectedBasisFingerprint != nil {
			s.ExpectedBasisFingerprint = append([]byte{}, opts.ExpectedBasisFingerprint...)
		}
		s.RequireSail = opts.RequireSail
	}
	return s
}

// IsExtendedForm reports whether this session uses extended-form ADV
// (basis fingerprint set).
func (s *FNPSession) IsExtendedForm() bool {
	return s.BasisFingerprint != nil
}

// IsSailCapable reports whether the negotiated session supports SAIL wire
// mode. Per ADR-004, SAIL is available only when the session reaches
// ESTABLISHED_SAIL.
func (s *FNPSession) IsSailCapable() bool {
	return s.State == FNPStateEstablishedSAIL
}

func namespaceBitmapGo(namespaces []string) uint32 {
	var bitmap uint32
	for _, ns := range namespaces {
		if len(ns) == 1 {
			idx := -1
			for i, c := range nsLetters {
				if string(c) == ns {
					idx = i
					break
				}
			}
			if idx >= 0 {
				bitmap |= 1 << uint(idx)
			}
		}
		if ns == "\u03A9" {
			bitmap |= 1 << 26
		}
	}
	return bitmap
}

func bitmapToNamespacesGo(bitmap uint32) []string {
	var result []string
	for i := 0; i < len(nsLetters); i++ {
		if bitmap&(1<<uint(i)) != 0 {
			result = append(result, string(nsLetters[i]))
		}
	}
	if bitmap&(1<<26) != 0 {
		result = append(result, "\u03A9")
	}
	return result
}

func fingerprintBytesGo(asd *AdaptiveSharedDictionary) []byte {
	b := asd.CanonicalJSON()
	sum := sha256.Sum256(b)
	return sum[:8]
}

func bytesEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// ── packet construction ─────────────────────────────────────────────

func (s *FNPSession) buildADV() []byte {
	buf := make([]byte, fnpADVSize)
	buf[1] = fnpProtocolVersion
	copy(buf[2:10], s.ownFp)
	binary.BigEndian.PutUint16(buf[10:12], s.asdVersion)
	binary.BigEndian.PutUint32(buf[12:16], s.ownBitmap)
	buf[16] = s.channelCapacity

	if s.IsExtendedForm() {
		// Extended form: msg_type bit 7 set, node_id narrowed to 15 bytes,
		// basis_fingerprint at offset 32. Spec §9.1.
		buf[0] = FNPMsgADVExtended
		nid := []byte(s.nodeID)
		if len(nid) > 15 {
			nid = nid[:15]
		}
		copy(buf[17:32], nid)
		copy(buf[32:40], s.BasisFingerprint)
	} else {
		// Base form: msg_type 0x01, node_id reserves the full 23 bytes.
		buf[0] = FNPMsgADV
		nid := []byte(s.nodeID)
		if len(nid) > 23 {
			nid = nid[:23]
		}
		copy(buf[17:], nid)
	}
	return buf
}

func (s *FNPSession) buildACK(remoteFp []byte, match int, commonBitmap uint32, negCap byte) []byte {
	buf := make([]byte, fnpACKSize)
	// ADR-004: basis-graded matches (0x03 / 0x04) are NOT failures, they
	// are graded capability and use ACK rather than NACK.
	if match == FNPMatchExact || match == FNPMatchBasisMismatch || match == FNPMatchBasisExtVsBase {
		buf[0] = FNPMsgACK
	} else {
		buf[0] = FNPMsgNACK
	}
	buf[1] = byte(match)
	copy(buf[2:10], remoteFp)
	copy(buf[10:18], s.ownFp)
	binary.BigEndian.PutUint32(buf[18:22], commonBitmap)
	buf[22] = negCap
	nid := []byte(s.nodeID)
	if len(nid) > 15 {
		nid = nid[:15]
	}
	copy(buf[23:], nid)
	return buf
}

// ── packet parsing ──────────────────────────────────────────────────

type fnpADVParsed struct {
	msgType          byte
	isExtended       bool
	protocolVersion  byte
	fingerprint      []byte
	asdVersion       uint16
	namespaceBitmap  uint32
	channelCapacity  byte
	nodeID           string
	basisFingerprint []byte
}

type fnpACKParsed struct {
	msgType             byte
	matchStatus         byte
	echoFingerprint     []byte
	ownFingerprint      []byte
	commonBitmap        uint32
	negotiatedCapacity  byte
	nodeID              string
}

func parseADV(data []byte) (*fnpADVParsed, error) {
	if len(data) < fnpADVSize {
		return nil, errors.New("invalid FNP_ADV packet")
	}
	baseType := data[0] &^ FNPADVExtFlag
	if baseType != FNPMsgADV {
		return nil, errors.New("invalid FNP_ADV packet")
	}
	isExtended := (data[0] & FNPADVExtFlag) != 0

	out := &fnpADVParsed{
		msgType:         data[0],
		isExtended:      isExtended,
		protocolVersion: data[1],
		fingerprint:     append([]byte{}, data[2:10]...),
		asdVersion:      binary.BigEndian.Uint16(data[10:12]),
		namespaceBitmap: binary.BigEndian.Uint32(data[12:16]),
		channelCapacity: data[16],
	}

	if isExtended {
		// Extended: 15-byte node_id, basis_fingerprint at offset 32.
		nid := data[17:32]
		end := len(nid)
		for end > 0 && nid[end-1] == 0 {
			end--
		}
		out.nodeID = string(nid[:end])
		out.basisFingerprint = append([]byte{}, data[32:40]...)
	} else {
		// Base: full 23-byte node_id reservation.
		nid := data[17:40]
		end := len(nid)
		for end > 0 && nid[end-1] == 0 {
			end--
		}
		out.nodeID = string(nid[:end])
	}
	return out, nil
}

func parseACK(data []byte) (*fnpACKParsed, error) {
	if len(data) < fnpACKSize || (data[0] != FNPMsgACK && data[0] != FNPMsgNACK) {
		return nil, errors.New("invalid FNP_ACK packet")
	}
	nid := data[23:38]
	end := len(nid)
	for end > 0 && nid[end-1] == 0 {
		end--
	}
	return &fnpACKParsed{
		msgType:            data[0],
		matchStatus:        data[1],
		echoFingerprint:    append([]byte{}, data[2:10]...),
		ownFingerprint:     append([]byte{}, data[10:18]...),
		commonBitmap:       binary.BigEndian.Uint32(data[18:22]),
		negotiatedCapacity: data[22],
		nodeID:             string(nid[:end]),
	}, nil
}

// ── state machine ───────────────────────────────────────────────────

// Initiate starts a handshake by building and returning a 40-byte ADV packet.
// Transitions: IDLE -> ADV_SENT.
func (s *FNPSession) Initiate() ([]byte, error) {
	if s.State != FNPStateIdle {
		return nil, fmt.Errorf("cannot initiate from state %s", s.State)
	}
	s.State = FNPStateADVSent
	return s.buildADV(), nil
}

// Receive processes a received FNP packet.
//
// If IDLE and an ADV is received, returns an ACK packet for transmission.
// If ADV_SENT and an ACK is received, reads the match result and returns nil.
func (s *FNPSession) Receive(data []byte) ([]byte, error) {
	if len(data) == 0 {
		return nil, errors.New("empty packet")
	}
	msgType := data[0]
	msgTypeBase := msgType &^ FNPADVExtFlag

	if msgTypeBase == FNPMsgADV && s.State == FNPStateIdle {
		adv, err := parseADV(data)
		if err != nil {
			return nil, err
		}
		s.RemoteNodeID = adv.nodeID
		s.RemoteFingerprint = adv.fingerprint
		s.RemoteBasisFingerprint = adv.basisFingerprint

		var match int
		if !bytesEqual(adv.fingerprint, s.ownFp) {
			match = FNPMatchFingerprint
		} else if adv.asdVersion != s.asdVersion {
			match = FNPMatchVersion
		} else {
			// ADR-004 basis fingerprint capability grading.
			remoteExt := adv.basisFingerprint != nil
			localExt := s.IsExtendedForm()
			switch {
			case remoteExt && localExt:
				if bytesEqual(adv.basisFingerprint, s.BasisFingerprint) {
					match = FNPMatchExact
				} else {
					match = FNPMatchBasisMismatch
				}
			case remoteExt != localExt:
				match = FNPMatchBasisExtVsBase
			default:
				match = FNPMatchExact
			}
		}

		common := s.ownBitmap & adv.namespaceBitmap
		s.CommonNamespaces = bitmapToNamespacesGo(common)
		s.MatchStatus = match

		negCap := adv.channelCapacity
		if s.channelCapacity < negCap {
			negCap = s.channelCapacity
		}
		s.NegotiatedCapacity = int(negCap)

		s.applyMatchToState(match, adv.basisFingerprint)
		return s.buildACK(adv.fingerprint, match, common, negCap), nil
	}

	if (msgTypeBase == FNPMsgACK || msgTypeBase == FNPMsgNACK) && s.State == FNPStateADVSent {
		ack, err := parseACK(data)
		if err != nil {
			return nil, err
		}

		if !bytesEqual(ack.echoFingerprint, s.ownFp) {
			return nil, errors.New("FNP_ACK echo fingerprint mismatch")
		}

		s.RemoteNodeID = ack.nodeID
		s.RemoteFingerprint = ack.ownFingerprint
		s.CommonNamespaces = bitmapToNamespacesGo(ack.commonBitmap)
		s.MatchStatus = int(ack.matchStatus)
		s.NegotiatedCapacity = int(ack.negotiatedCapacity)

		// ACK does not carry remote basis fingerprint per ADR-004 spec §9.2;
		// initiator learns basis agreement via match_status.
		s.applyMatchToState(int(ack.matchStatus), nil)
		return nil, nil
	}

	return nil, fmt.Errorf("unexpected msg_type 0x%02x in state %s", msgType, s.State)
}

// applyMatchToState is the ADR-004 capability grading helper.
// It chooses ESTABLISHED_SAIL, ESTABLISHED_SAL_ONLY, SYNC_NEEDED, or
// (with require_sail) refuses the session locally. It also records a
// degradation event when the peer's basis fingerprint differs from the
// locally configured ExpectedBasisFingerprint.
func (s *FNPSession) applyMatchToState(match int, peerBasisFp []byte) {
	if match == FNPMatchExact {
		s.State = FNPStateEstablishedSAIL
		return
	}
	if match == FNPMatchBasisMismatch || match == FNPMatchBasisExtVsBase {
		if s.RequireSail {
			s.State = FNPStateIdle
			s.DegradationEvent = map[string]interface{}{
				"reason":         "require_sail policy refused basis-mismatched session",
				"match_status":   match,
				"remote_node_id": s.RemoteNodeID,
				"remote_basis_fingerprint": func() interface{} {
					if peerBasisFp != nil {
						return hex.EncodeToString(peerBasisFp)
					}
					return nil
				}(),
			}
			return
		}
		s.State = FNPStateEstablishedSALOnly
		if s.ExpectedBasisFingerprint != nil && peerBasisFp != nil &&
			!bytesEqual(peerBasisFp, s.ExpectedBasisFingerprint) {
			s.DegradationEvent = map[string]interface{}{
				"reason":                    "remote basis fingerprint differs from expected",
				"match_status":              match,
				"remote_node_id":            s.RemoteNodeID,
				"remote_basis_fingerprint":  hex.EncodeToString(peerBasisFp),
				"expected_basis_fingerprint": hex.EncodeToString(s.ExpectedBasisFingerprint),
			}
		}
		return
	}
	// FNPMatchVersion or FNPMatchFingerprint
	s.State = FNPStateSyncNeeded
}

// Timeout handles handshake timeout. ADV_SENT -> IDLE.
func (s *FNPSession) Timeout() {
	if s.State == FNPStateADVSent {
		s.State = FNPStateIdle
		s.RemoteNodeID = ""
		s.RemoteFingerprint = nil
		s.CommonNamespaces = nil
		s.MatchStatus = -1
		s.NegotiatedCapacity = -1
	}
}

// Fallback transitions to FALLBACK when the remote peer does not speak OSMP.
//
// Called when:
//   - ADV was sent but the response is not a valid FNP packet
//   - The transport is known to be non-OSMP (e.g., plain JSON-RPC, NL)
//   - Timeout occurred during negotiation attempt with a new peer
//
// Transitions: ADV_SENT -> FALLBACK, or IDLE -> FALLBACK (direct).
func (s *FNPSession) Fallback(remoteID string) {
	if s.State == FNPStateADVSent || s.State == FNPStateIdle {
		s.State = FNPStateFallback
		s.RemoteNodeID = remoteID
		s.RemoteFingerprint = nil
		s.CommonNamespaces = []string{}
		s.MatchStatus = -1
		s.NegotiatedCapacity = -1
	}
}

// Acquire transitions to ACQUIRED when the remote peer starts producing valid SAL.
// Called by SALBridge when the acquisition score exceeds threshold.
// Transitions: FALLBACK -> ACQUIRED.
func (s *FNPSession) Acquire() {
	if s.State == FNPStateFallback {
		s.State = FNPStateAcquired
	}
}

// Regress transitions back to FALLBACK when an ACQUIRED peer stops producing valid SAL.
// Transitions: ACQUIRED -> FALLBACK.
func (s *FNPSession) Regress() {
	if s.State == FNPStateAcquired {
		s.State = FNPStateFallback
	}
}

// IsLegacyPeer returns true if the session is in FALLBACK or ACQUIRED state.
func (s *FNPSession) IsLegacyPeer() bool {
	return s.State == FNPStateFallback || s.State == FNPStateAcquired
}

// IsAcquired returns true if the session is in ACQUIRED state.
func (s *FNPSession) IsAcquired() bool {
	return s.State == FNPStateAcquired
}
