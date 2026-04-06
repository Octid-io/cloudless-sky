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
// Patent ref: OSMP-001-UTIL Section II.C, FIG. 5
package osmp

import (
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
)

// FNP message types
const (
	FNPMsgADV  = 0x01
	FNPMsgACK  = 0x02
	FNPMsgNACK = 0x03
)

// FNP match status codes
const (
	FNPMatchExact       = 0x00
	FNPMatchVersion     = 0x01
	FNPMatchFingerprint = 0x02
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
	FNPStateIdle        FNPState = "IDLE"
	FNPStateADVSent     FNPState = "ADV_SENT"
	FNPStateEstablished FNPState = "ESTABLISHED"
	FNPStateSyncNeeded  FNPState = "SYNC_NEEDED"
	FNPStateFallback    FNPState = "FALLBACK"
	FNPStateAcquired    FNPState = "ACQUIRED"
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
	buf[0] = FNPMsgADV
	buf[1] = fnpProtocolVersion
	copy(buf[2:10], s.ownFp)
	binary.BigEndian.PutUint16(buf[10:12], s.asdVersion)
	binary.BigEndian.PutUint32(buf[12:16], s.ownBitmap)
	buf[16] = s.channelCapacity
	nid := []byte(s.nodeID)
	if len(nid) > 23 {
		nid = nid[:23]
	}
	copy(buf[17:], nid)
	return buf
}

func (s *FNPSession) buildACK(remoteFp []byte, match int, commonBitmap uint32, negCap byte) []byte {
	buf := make([]byte, fnpACKSize)
	if match == FNPMatchExact {
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
	protocolVersion  byte
	fingerprint      []byte
	asdVersion       uint16
	namespaceBitmap  uint32
	channelCapacity  byte
	nodeID           string
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
	if len(data) < fnpADVSize || data[0] != FNPMsgADV {
		return nil, errors.New("invalid FNP_ADV packet")
	}
	nid := data[17:40]
	end := len(nid)
	for end > 0 && nid[end-1] == 0 {
		end--
	}
	return &fnpADVParsed{
		protocolVersion: data[1],
		fingerprint:     append([]byte{}, data[2:10]...),
		asdVersion:      binary.BigEndian.Uint16(data[10:12]),
		namespaceBitmap: binary.BigEndian.Uint32(data[12:16]),
		channelCapacity: data[16],
		nodeID:          string(nid[:end]),
	}, nil
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

	if msgType == FNPMsgADV && s.State == FNPStateIdle {
		adv, err := parseADV(data)
		if err != nil {
			return nil, err
		}
		s.RemoteNodeID = adv.nodeID
		s.RemoteFingerprint = adv.fingerprint

		var match int
		if bytesEqual(adv.fingerprint, s.ownFp) {
			if adv.asdVersion == s.asdVersion {
				match = FNPMatchExact
			} else {
				match = FNPMatchVersion
			}
		} else {
			match = FNPMatchFingerprint
		}

		common := s.ownBitmap & adv.namespaceBitmap
		s.CommonNamespaces = bitmapToNamespacesGo(common)
		s.MatchStatus = match

		negCap := adv.channelCapacity
		if s.channelCapacity < negCap {
			negCap = s.channelCapacity
		}
		s.NegotiatedCapacity = int(negCap)

		if match == FNPMatchExact {
			s.State = FNPStateEstablished
		} else {
			s.State = FNPStateSyncNeeded
		}
		return s.buildACK(adv.fingerprint, match, common, negCap), nil
	}

	if (msgType == FNPMsgACK || msgType == FNPMsgNACK) && s.State == FNPStateADVSent {
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

		if ack.matchStatus == FNPMatchExact {
			s.State = FNPStateEstablished
		} else {
			s.State = FNPStateSyncNeeded
		}
		return nil, nil
	}

	return nil, fmt.Errorf("unexpected msg_type 0x%02x in state %s", msgType, s.State)
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
