// Package osmp provides the OSMP protocol implementation.
//
// This file implements the SALBridge: boundary translator between
// OSMP-native agents and non-OSMP peers. The bridge manages FNP
// negotiation, FALLBACK translation, SAL annotation for context
// seeding, and acquisition monitoring.
//
// OSMP does not spread by installation. It spreads by contact.
//
// Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
// License: Apache 2.0
package osmp

import (
	"fmt"
	"regexp"
	"strings"
	"time"
)

// SAL frame pattern: Namespace:Opcode (e.g., H:HR, A:ACK, M:EVA)
var salFrameRE = regexp.MustCompile(`\b([A-Z]):([A-Z]{2,})\b`)

const (
	DefaultAcquisitionThreshold = 5
	DefaultRegressionThreshold  = 3
)

// AcquisitionMetrics tracks SAL acquisition progress for a single remote peer.
type AcquisitionMetrics struct {
	TotalMessages       int
	MessagesWithSal     int
	ConsecutiveSalHits  int
	ConsecutiveSalMisses int
	PeakConsecutiveHits int
	ValidFramesSeen     int
	UniqueOpcodesSeen   map[string]bool
	FirstSalSeenAt      *time.Time
	LastSalSeenAt       *time.Time
}

// AcquisitionScore returns 0.0 to 1.0 based on consecutive valid SAL production.
func (m *AcquisitionMetrics) AcquisitionScore(threshold int) float64 {
	if m.TotalMessages == 0 {
		return 0.0
	}
	score := float64(m.ConsecutiveSalHits) / float64(threshold)
	if score > 1.0 {
		return 1.0
	}
	return score
}

func (m *AcquisitionMetrics) recordHit(frames [][2]string) {
	now := time.Now()
	m.TotalMessages++
	m.MessagesWithSal++
	m.ConsecutiveSalHits++
	m.ConsecutiveSalMisses = 0
	m.ValidFramesSeen += len(frames)
	for _, f := range frames {
		m.UniqueOpcodesSeen[f[0]+":"+f[1]] = true
	}
	if m.ConsecutiveSalHits > m.PeakConsecutiveHits {
		m.PeakConsecutiveHits = m.ConsecutiveSalHits
	}
	if m.FirstSalSeenAt == nil {
		m.FirstSalSeenAt = &now
	}
	m.LastSalSeenAt = &now
}

func (m *AcquisitionMetrics) recordMiss() {
	m.TotalMessages++
	m.ConsecutiveSalHits = 0
	m.ConsecutiveSalMisses++
}

// BridgeEvent is a log entry for bridge activity.
type BridgeEvent struct {
	Timestamp      time.Time
	EventType      string // "fallback", "annotate", "detect_sal", "acquire", "regress", "send_sal", "passthrough"
	RemoteID       string
	SAL            string
	NL             string
	FramesDetected int
	Detail         string
}

// BridgeInbound is the result of Bridge.Receive().
type BridgeInbound struct {
	SAL            string   // SAL representation if the message was valid SAL
	NL             string   // Natural language content if the message was NL or mixed
	Passthrough    bool     // True if this is NL_PASSTHROUGH
	PeerID         string   // Identity of the sending peer
	State          FNPState // FNP session state at time of receipt
	DetectedFrames []string // Valid SAL frames detected in mixed content
}

// SALBridge is the boundary translator between OSMP-native agents and non-OSMP peers.
type SALBridge struct {
	NodeID               string
	ASD                  *AdaptiveSharedDictionary
	Annotate             bool
	AcquisitionThreshold int
	RegressionThreshold  int

	sessions map[string]*FNPSession
	metrics  map[string]*AcquisitionMetrics
	log      []BridgeEvent
}

// NewSALBridge creates a new bridge instance.
func NewSALBridge(nodeID string, asd *AdaptiveSharedDictionary, annotate bool) *SALBridge {
	if asd == nil {
		asd = NewASD()
	}
	return &SALBridge{
		NodeID:               nodeID,
		ASD:                  asd,
		Annotate:             annotate,
		AcquisitionThreshold: DefaultAcquisitionThreshold,
		RegressionThreshold:  DefaultRegressionThreshold,
		sessions:             make(map[string]*FNPSession),
		metrics:              make(map[string]*AcquisitionMetrics),
		log:                  nil,
	}
}

// RegisterPeer registers a remote peer. If attemptFnp is false,
// immediately enters FALLBACK (use for peers known to be non-OSMP).
func (b *SALBridge) RegisterPeer(peerID string, attemptFnp bool) FNPState {
	session := NewFNPSession(b.ASD, b.NodeID, 1, FNPCapUnconstrained)
	b.sessions[peerID] = session
	b.metrics[peerID] = &AcquisitionMetrics{
		UniqueOpcodesSeen: make(map[string]bool),
	}

	if !attemptFnp {
		session.Fallback(peerID)
		b.emit("fallback", peerID, "", "", 0, "direct registration, no FNP attempt")
	}

	return session.State
}

// PeerState returns the FNP session state for a peer, or empty string if unregistered.
func (b *SALBridge) PeerState(peerID string) FNPState {
	session, ok := b.sessions[peerID]
	if !ok {
		return ""
	}
	return session.State
}

// Send translates outbound SAL for the target peer.
// ESTABLISHED/ACQUIRED: returns SAL unchanged.
// FALLBACK: decodes to NL, optionally annotated with SAL.
func (b *SALBridge) Send(sal string, peerID string) string {
	session, ok := b.sessions[peerID]
	if !ok {
		b.RegisterPeer(peerID, false)
		session = b.sessions[peerID]
	}

	// Native OSMP peer
	if session.State == FNPStateEstablished || session.State == FNPStateSyncNeeded {
		b.emit("send_sal", peerID, sal, "", 0, "native OSMP peer")
		return sal
	}

	// ACQUIRED peer
	if session.State == FNPStateAcquired {
		b.emit("send_sal", peerID, sal, "", 0, "acquired peer, sending SAL")
		return sal
	}

	// FALLBACK — decode to NL
	nl := b.decodeToNL(sal)

	if b.Annotate {
		annotated := fmt.Sprintf("%s\n[SAL: %s]", nl, sal)
		b.emit("annotate", peerID, sal, nl, 0, "annotated outbound for context seeding")
		return annotated
	}

	b.emit("passthrough", peerID, sal, nl, 0, "outbound decoded to NL, no annotation")
	return nl
}

// Receive processes an inbound message from a peer.
// Scans for valid SAL fragments, updates acquisition metrics,
// and handles state transitions.
func (b *SALBridge) Receive(message string, peerID string) BridgeInbound {
	session, ok := b.sessions[peerID]
	if !ok {
		b.RegisterPeer(peerID, false)
		session = b.sessions[peerID]
	}

	m := b.metrics[peerID]

	// Native OSMP peer
	if session.State == FNPStateEstablished || session.State == FNPStateSyncNeeded {
		return BridgeInbound{SAL: message, Passthrough: false, PeerID: peerID, State: session.State}
	}

	// Scan for SAL fragments
	detected := b.detectSALFrames(message)

	if len(detected) > 0 {
		m.recordHit(detected)

		frameStrs := make([]string, len(detected))
		for i, f := range detected {
			frameStrs[i] = f[0] + ":" + f[1]
		}
		b.emit("detect_sal", peerID, message, "", len(detected),
			fmt.Sprintf("valid SAL frames: %v", frameStrs))

		// Check acquisition transition
		if session.State == FNPStateFallback && m.ConsecutiveSalHits >= b.AcquisitionThreshold {
			session.Acquire()
			b.emit("acquire", peerID, "", "", 0,
				fmt.Sprintf("acquisition threshold met (%d consecutive hits, %d unique opcodes)",
					b.AcquisitionThreshold, len(m.UniqueOpcodesSeen)))
		}

		// If entire message is pure SAL
		if b.isPureSAL(message) {
			return BridgeInbound{SAL: message, Passthrough: false, PeerID: peerID, State: session.State}
		}

		// Mixed content
		return BridgeInbound{
			NL: message, Passthrough: true, PeerID: peerID,
			State: session.State, DetectedFrames: frameStrs,
		}
	}

	// No SAL detected
	m.recordMiss()

	// Check regression
	if session.State == FNPStateAcquired && m.ConsecutiveSalMisses >= b.RegressionThreshold {
		session.Regress()
		b.emit("regress", peerID, "", "", 0,
			fmt.Sprintf("regression threshold met (%d consecutive misses)", b.RegressionThreshold))
	}

	return BridgeInbound{NL: message, Passthrough: true, PeerID: peerID, State: session.State}
}

// GetMetrics returns acquisition metrics for a peer.
func (b *SALBridge) GetMetrics(peerID string) *AcquisitionMetrics {
	return b.metrics[peerID]
}

// GetLog returns the bridge event log, optionally filtered by peer.
func (b *SALBridge) GetLog(peerID string) []BridgeEvent {
	if peerID == "" {
		return b.log
	}
	var filtered []BridgeEvent
	for _, e := range b.log {
		if e.RemoteID == peerID {
			filtered = append(filtered, e)
		}
	}
	return filtered
}

// GetComparison returns side-by-side SAL vs NL for all annotated messages to a peer.
func (b *SALBridge) GetComparison(peerID string) []map[string]interface{} {
	var comparisons []map[string]interface{}
	for _, e := range b.log {
		if e.RemoteID == peerID && e.EventType == "annotate" && e.SAL != "" && e.NL != "" {
			salBytes := len([]byte(e.SAL))
			nlBytes := len([]byte(e.NL))
			reduction := 0.0
			if nlBytes > 0 {
				reduction = (1.0 - float64(salBytes)/float64(nlBytes)) * 100
			}
			comparisons = append(comparisons, map[string]interface{}{
				"sal":           e.SAL,
				"nl":            e.NL,
				"sal_bytes":     salBytes,
				"nl_bytes":      nlBytes,
				"reduction_pct": reduction,
				"timestamp":     e.Timestamp,
			})
		}
	}
	return comparisons
}

// ── internal ────────────────────────────────────────────────────────

func (b *SALBridge) decodeToNL(sal string) string {
	frames := strings.Split(sal, ";")
	parts := make([]string, 0, len(frames))
	for _, f := range frames {
		f = strings.TrimSpace(f)
		if f == "" {
			continue
		}
		matches := salFrameRE.FindStringSubmatch(f)
		if len(matches) >= 3 {
			def := b.ASD.Lookup(matches[1], matches[2])
			if def != "" {
				rest := strings.TrimPrefix(f, matches[0])
				parts = append(parts, strings.TrimSpace(def+" "+rest))
				continue
			}
		}
		parts = append(parts, f)
	}
	return strings.Join(parts, "; ")
}

func (b *SALBridge) detectSALFrames(message string) [][2]string {
	matches := salFrameRE.FindAllStringSubmatch(message, -1)
	var valid [][2]string
	for _, m := range matches {
		ns, op := m[1], m[2]
		if b.ASD.Lookup(ns, op) != "" {
			valid = append(valid, [2]string{ns, op})
		}
	}
	return valid
}

func (b *SALBridge) isPureSAL(message string) bool {
	trimmed := strings.TrimSpace(message)
	if trimmed == "" {
		return false
	}
	frames := strings.Split(trimmed, ";")
	for _, f := range frames {
		f = strings.TrimSpace(f)
		if f == "" {
			continue
		}
		if !salFrameRE.MatchString(f) {
			return false
		}
	}
	return true
}

func (b *SALBridge) emit(eventType, remoteID, sal, nl string, framesDetected int, detail string) {
	b.log = append(b.log, BridgeEvent{
		Timestamp:      time.Now(),
		EventType:      eventType,
		RemoteID:       remoteID,
		SAL:            sal,
		NL:             nl,
		FramesDetected: framesDetected,
		Detail:         detail,
	})
}
