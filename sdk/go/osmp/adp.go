package osmp

// ASD Distribution Protocol (ADP) — SAL-layer dictionary synchronization
//
// Complements the binary FNP handshake with SAL-level instructions for
// version identity exchange, delta delivery, micro-delta, hash verification,
// and MDR corpus version tracking.
//
// Patent ref: OSMP-001-UTIL Claims 20-21, Section VII.F, X-L
// License: Apache 2.0

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
)

// ── Version mapping: u16 wire as u8.u8 (MAJOR.MINOR) ──────────────────────

// ASDVersionPack encodes MAJOR.MINOR into u16 for FNP wire format.
func ASDVersionPack(major, minor int) (uint16, error) {
	if major < 0 || major > 255 || minor < 0 || minor > 255 {
		return 0, fmt.Errorf("version %d.%d out of u8.u8 range", major, minor)
	}
	return uint16(major<<8 | minor), nil
}

// ASDVersionUnpack decodes u16 from FNP wire format into (major, minor).
func ASDVersionUnpack(u16 uint16) (int, int) {
	return int(u16 >> 8), int(u16 & 0xFF)
}

// ASDVersionStr returns display string for SAL instructions: "2.7".
func ASDVersionStr(u16 uint16) string {
	major, minor := ASDVersionUnpack(u16)
	return fmt.Sprintf("%d.%d", major, minor)
}

// ASDVersionParse parses "2.7" into u16.
func ASDVersionParse(s string) (uint16, error) {
	parts := strings.Split(s, ".")
	if len(parts) != 2 {
		return 0, fmt.Errorf("invalid version string: %s", s)
	}
	major, err1 := strconv.Atoi(parts[0])
	minor, err2 := strconv.Atoi(parts[1])
	if err1 != nil || err2 != nil {
		return 0, fmt.Errorf("invalid version string: %s", s)
	}
	return ASDVersionPack(major, minor)
}

// ASDVersionIsBreaking returns true if the version change includes a MAJOR increment.
func ASDVersionIsBreaking(oldU16, newU16 uint16) bool {
	return (newU16 >> 8) > (oldU16 >> 8)
}

// ── Priority constants ─────────────────────────────────────────────────────

const (
	ADPPriorityMission = 0 // Non-ADP instruction traffic
	ADPPriorityMicro   = 1 // Task-relevant micro-delta (A:ASD:DEF)
	ADPPriorityDelta   = 2 // Background delta (A:ASD:DELTA)
	ADPPriorityTrickle = 3 // Trickle charge request (A:ASD:REQ, A:ASD)
)

// ── Delta operation ────────────────────────────────────────────────────────

// ADPDeltaOp represents a single operation within a delta payload.
type ADPDeltaOp struct {
	Namespace  string
	Mode       string // "+" | "←" | "†"
	Opcode     string
	Definition string
}

// IsBreaking returns true if this is a REPLACE operation.
func (op *ADPDeltaOp) IsBreaking() bool { return op.Mode == "\u2190" }

// ToSAL returns the SAL representation: "H+[LACTATE]".
func (op *ADPDeltaOp) ToSAL() string {
	return fmt.Sprintf("%s%s[%s]", op.Namespace, op.Mode, op.Opcode)
}

// ── Delta payload ──────────────────────────────────────────────────────────

// ADPDelta represents a complete delta payload with version range and operations.
type ADPDelta struct {
	FromVersion string
	ToVersion   string
	Operations  []ADPDeltaOp
}

// HasBreaking returns true if any operation is a REPLACE.
func (d *ADPDelta) HasBreaking() bool {
	for _, op := range d.Operations {
		if op.IsBreaking() {
			return true
		}
	}
	return false
}

// ToSAL returns the full SAL instruction.
func (d *ADPDelta) ToSAL() string {
	ops := make([]string, len(d.Operations))
	for i, op := range d.Operations {
		ops[i] = op.ToSAL()
	}
	return fmt.Sprintf("A:ASD:DELTA[%s\u2192%s:%s]",
		d.FromVersion, d.ToVersion, strings.Join(ops, ":"))
}

// ── Pending instruction ────────────────────────────────────────────────────

// PendingInstruction is held in the semantic pending queue.
type PendingInstruction struct {
	SAL                 string
	UnresolvedNamespace string
	UnresolvedOpcode    string
	Timestamp           time.Time
}

// ── ADP Session ────────────────────────────────────────────────────────────

// ADPSession manages SAL-layer dictionary synchronization.
type ADPSession struct {
	ASD                    *AdaptiveSharedDictionary
	ASDVersion             uint16
	NamespaceVersions      map[string]string
	PendingQueue           []PendingInstruction
	DeltaLog               []string
	RemoteVersion          *uint16
	RemoteNamespaceVersions map[string]string
}

// NewADPSession creates a new ADP session manager.
func NewADPSession(asd *AdaptiveSharedDictionary, asdVersion uint16,
	nsVersions map[string]string) *ADPSession {
	if nsVersions == nil {
		nsVersions = make(map[string]string)
	}
	return &ADPSession{
		ASD:               asd,
		ASDVersion:        asdVersion,
		NamespaceVersions: nsVersions,
		PendingQueue:      nil,
		DeltaLog:          nil,
	}
}

// VersionIdentity generates A:ASD version identity instruction.
func (s *ADPSession) VersionIdentity(includeNamespaces bool) string {
	ver := ASDVersionStr(s.ASDVersion)
	if includeNamespaces && len(s.NamespaceVersions) > 0 {
		keys := make([]string, 0, len(s.NamespaceVersions))
		for k := range s.NamespaceVersions {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		var ns strings.Builder
		for _, k := range keys {
			ns.WriteString(fmt.Sprintf(":%s%s", k, s.NamespaceVersions[k]))
		}
		return fmt.Sprintf("A:ASD[%s%s]", ver, ns.String())
	}
	return fmt.Sprintf("A:ASD[%s]", ver)
}

// VersionQuery generates version query broadcast.
func (s *ADPSession) VersionQuery() string { return "A:ASD?" }

// VersionAlert generates version update announcement.
func (s *ADPSession) VersionAlert() string {
	return fmt.Sprintf("A:ASD[%s]\u26a0", ASDVersionStr(s.ASDVersion))
}

// RequestDelta generates a delta request instruction.
func (s *ADPSession) RequestDelta(target string) string {
	myVer := ASDVersionStr(s.ASDVersion)
	return fmt.Sprintf("A:ASD:REQ[%s\u2192%s]", myVer, target)
}

// RequestDefinition generates a micro-delta request.
func (s *ADPSession) RequestDefinition(namespace, opcode string) string {
	return fmt.Sprintf("A:ASD:DEF?[%s:%s]", namespace, opcode)
}

// SendDefinition generates a micro-delta response.
func (s *ADPSession) SendDefinition(namespace, opcode, definition string, layer int) string {
	return fmt.Sprintf("A:ASD:DEF[%s:%s:%s:%d]", namespace, opcode, definition, layer)
}

// HashIdentity generates hash verification instruction.
func (s *ADPSession) HashIdentity(hexLength int) string {
	ver := ASDVersionStr(s.ASDVersion)
	fp := s.ASD.Fingerprint()
	if len(fp) > hexLength {
		fp = fp[:hexLength]
	}
	return fmt.Sprintf("A:ASD:HASH[%s:%s]", ver, fp)
}

// ResolveOrPend checks if an instruction's opcodes are resolvable.
// If not, adds it to the semantic pending queue.
func (s *ADPSession) ResolveOrPend(sal string) (resolved bool, pending bool, microReq string) {
	ns, opcode := extractNsOpcode(sal)
	if ns == "" {
		return true, false, ""
	}
	def := s.ASD.Lookup(ns, opcode)
	if def != "" {
		return true, false, ""
	}
	s.PendingQueue = append(s.PendingQueue, PendingInstruction{
		SAL: sal, UnresolvedNamespace: ns,
		UnresolvedOpcode: opcode, Timestamp: time.Now(),
	})
	return false, true, s.RequestDefinition(ns, opcode)
}

func extractNsOpcode(sal string) (string, string) {
	if len(sal) == 0 || sal[0] < 'A' || sal[0] > 'Z' || !strings.Contains(sal, ":") {
		return "", ""
	}
	parts := strings.SplitN(sal, ":", 3)
	if len(parts) < 2 || len(parts[0]) != 1 {
		return "", ""
	}
	opRaw := parts[1]
	opcode := ""
	for _, ch := range opRaw {
		if strings.ContainsRune("[]?<>@\u2227\u2228\u2192\u26a0", ch) {
			break
		}
		opcode += string(ch)
	}
	return parts[0], opcode
}

// ClassifyPriority returns the ADP priority level for a SAL instruction.
func ClassifyPriority(sal string) int {
	if !strings.HasPrefix(sal, "A:ASD") && !strings.HasPrefix(sal, "A:MDR") {
		return ADPPriorityMission
	}
	if strings.Contains(sal, "DEF") {
		return ADPPriorityMicro
	}
	if strings.Contains(sal, "DELTA") {
		return ADPPriorityDelta
	}
	return ADPPriorityTrickle
}

// MDR helpers

// MDRIdentity generates MDR corpus version identity.
func MDRIdentity(corpora map[string]string) string {
	keys := make([]string, 0, len(corpora))
	for k := range corpora {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parts := make([]string, len(keys))
	for i, k := range keys {
		parts[i] = fmt.Sprintf("%s:%s", k, corpora[k])
	}
	return fmt.Sprintf("A:MDR[%s]", strings.Join(parts, ":"))
}

// MDRRequest generates MDR delta request.
func MDRRequest(corpus, fromVer, toVer string) string {
	return fmt.Sprintf("A:MDR:REQ[%s:%s\u2192%s]", corpus, fromVer, toVer)
}

// Acknowledge helpers

func AcknowledgeVersion(version string) string { return fmt.Sprintf("A:ACK[ASD:%s]", version) }
func AcknowledgeHash() string                  { return "A:ACK[ASD:HASH]" }
func AcknowledgeDef() string                   { return "A:ACK[ASD:DEF]" }
