// Package osmpwire implements OSMP wire modes: SAIL (Semantic Assembly Isomorphic Language)
// and SEC (Security Envelope) for the Octid Semantic Mesh Protocol.
//
// Zero external dependencies. Compiles into a binary.
// Dictionary: OSMP-semantic-dictionary-v14.csv
package osmpwire

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/binary"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// WireMode selects the encoding mode for transmission.
type WireMode uint8

const (
	ModeMnemonic WireMode = 0x00 // UTF-8 SAL text (human-readable)
	ModeSAIL     WireMode = 0x01 // Binary SAIL (table-decoded)
	ModeSEC      WireMode = 0x02 // SAL + security envelope
	ModeSAILSEC  WireMode = 0x03 // SAIL + security envelope
)

func (m WireMode) Label() string {
	switch m {
	case ModeMnemonic: return "OSMP"
	case ModeSAIL:     return "OSMP-SAIL"
	case ModeSEC:      return "OSMP-SEC"
	case ModeSAILSEC:  return "OSMP-SAIL-SEC"
	}
	return fmt.Sprintf("?%d", m)
}

// ─── Token Constants ─────────────────────────────────────────────────────────

const (
	tokAND           = 0x80
	tokOR            = 0x81
	tokNOT           = 0x82
	tokTHEN          = 0x83
	tokIFF           = 0x84
	tokFOR_ALL       = 0x85
	tokEXISTS        = 0x86
	tokPARALLEL      = 0x87
	tokPRIORITY      = 0x88
	tokAPPROX        = 0x89
	tokWILDCARD      = 0x8A
	tokASSIGN        = 0x8B
	tokSEQUENCE      = 0x8C
	tokQUERY         = 0x8D
	tokTARGET        = 0x8E
	tokREPEAT_EVERY  = 0x8F
	tokNOT_EQUAL     = 0x90
	tokPRIORITY_ORD  = 0x91
	tokUNLESS        = 0x92

	tokHAZARDOUS     = 0xA0
	tokREVERSIBLE    = 0xA1
	tokIRREVERSIBLE  = 0xA2

	tokPASS_TRUE     = 0xA8
	tokFAIL_FALSE    = 0xA9

	tokDELTA         = 0xB0
	tokHOME          = 0xB1
	tokABORT_CANCEL  = 0xB2
	tokTIMEOUT       = 0xB3
	tokSCOPE_WITHIN  = 0xB4
	tokMISSING       = 0xB5

	tokFAIL_SAFE     = 0xC0
	tokGRACEFUL_DEG  = 0xC1
	tokATOMIC        = 0xC2

	tokADDITIVE      = 0xD0
	tokREPLACE       = 0xD1
	tokDEPRECATE     = 0xD2

	tokFRAME         = 0xE0
	tokBRACKET_OPEN  = 0xE4
	tokBRACKET_CLOSE = 0xE5

	tokVARINT        = 0xF0
	tokNEGINT        = 0xF1
	tokFLOAT16       = 0xF2
	tokFLOAT32       = 0xF3
	tokSTRING        = 0xF4
	tokREF           = 0xF5
	tokEND           = 0xFF

	secVersion1  = 0x00
	nodeIDLong   = 0x04
)

// ─── Glyph Maps ──────────────────────────────────────────────────────────────

var glyphToToken = map[rune]byte{
	'\u2227': tokAND, '\u2228': tokOR, '\u00AC': tokNOT, '\u2192': tokTHEN,
	'\u2194': tokIFF, '\u2200': tokFOR_ALL, '\u2203': tokEXISTS, '\u2225': tokPARALLEL,
	'>': tokPRIORITY, '~': tokAPPROX, '*': tokWILDCARD,
	':': tokASSIGN, ';': tokSEQUENCE, '?': tokQUERY, '@': tokTARGET,
	'\u27F3': tokREPEAT_EVERY, '\u2260': tokNOT_EQUAL, '\u2295': tokPRIORITY_ORD,
	'\u26A0': tokHAZARDOUS, '\u21BA': tokREVERSIBLE, '\u2298': tokIRREVERSIBLE,
	'\u22A4': tokPASS_TRUE, '\u22A5': tokFAIL_FALSE,
	'\u0394': tokDELTA, '\u2302': tokHOME, '\u2297': tokABORT_CANCEL,
	'\u03C4': tokTIMEOUT, '\u2208': tokSCOPE_WITHIN, '\u2216': tokMISSING,
	'\u03A6': tokFAIL_SAFE, '\u0393': tokGRACEFUL_DEG, '\u039B': tokATOMIC,
	'+': tokADDITIVE, '\u2190': tokREPLACE, '\u2020': tokDEPRECATE,
	'[': tokBRACKET_OPEN, ']': tokBRACKET_CLOSE,
}

var tokenToGlyph map[byte]rune

func init() {
	tokenToGlyph = make(map[byte]rune, len(glyphToToken))
	for g, t := range glyphToToken {
		tokenToGlyph[t] = g
	}
}

// ─── Varint ──────────────────────────────────────────────────────────────────

func encodeVarint(v uint64) []byte {
	var out []byte
	for v > 0x7F {
		out = append(out, byte(v&0x7F)|0x80)
		v >>= 7
	}
	out = append(out, byte(v&0x7F))
	return out
}

func decodeVarint(data []byte, off int) (uint64, int) {
	var val uint64
	var shift uint
	for off < len(data) {
		b := data[off]
		off++
		val |= uint64(b&0x7F) << shift
		if b&0x80 == 0 {
			return val, off
		}
		shift += 7
	}
	return val, off
}

// ─── Dictionary Loader ───────────────────────────────────────────────────────

type opcodeIndex map[string]map[string]int
type indexOpcode map[string]map[int]string

func buildOpcodeTables(dictPath string) (opcodeIndex, indexOpcode, error) {
	if dictPath == "" {
		candidates := []string{
			filepath.Join("protocol", "OSMP-semantic-dictionary-v14.csv"),
		}
		for _, c := range candidates {
			if _, err := os.Stat(c); err == nil {
				dictPath = c
				break
			}
		}
	}
	if dictPath == "" {
		return nil, nil, errors.New("semantic dictionary not found")
	}
	data, err := os.ReadFile(dictPath)
	if err != nil {
		return nil, nil, err
	}
	lines := strings.Split(string(data), "\n")
	s3 := -1
	for i, line := range lines {
		if strings.Contains(line, "SECTION 3") {
			s3 = i
			break
		}
	}
	if s3 < 0 {
		return nil, nil, errors.New("SECTION 3 not found")
	}
	nsOps := map[string][]string{}
	for _, line := range lines[s3:] {
		parts := strings.SplitN(line, ",", 6)
		if len(parts) >= 5 {
			prefix := strings.TrimSpace(parts[1])
			opcode := strings.TrimSpace(parts[3])
			if len(prefix) >= 1 && len(prefix) <= 2 && prefix[0] >= 'A' && prefix[0] <= 'Z' && opcode != "" && opcode != "Opcode" {
				nsOps[prefix] = append(nsOps[prefix], opcode)
			}
		}
	}
	opToIdx := opcodeIndex{}
	idxToOp := indexOpcode{}
	for ns, ops := range nsOps {
		uniq := map[string]bool{}
		var sorted []string
		for _, op := range ops {
			if !uniq[op] {
				uniq[op] = true
				sorted = append(sorted, op)
			}
		}
		sort.Strings(sorted)
		opToIdx[ns] = map[string]int{}
		idxToOp[ns] = map[int]string{}
		for i, op := range sorted {
			opToIdx[ns][op] = i
			idxToOp[ns][i] = op
		}
	}
	return opToIdx, idxToOp, nil
}

// ─── Intern Table ────────────────────────────────────────────────────────────


// buildInternTable dynamically constructs the intern table from dictionary content.
// Extracts opcode names and known wire tokens. Loading an MDR corpus expands
// both vocabulary AND compression table from a single artifact.
func buildInternTable(dictPath string, mdrPaths []string) []string {
	// Dynamically construct intern table from dictionary and MDR content.
	// Phase 1: Opcode names from base dictionary Section 3.
	// Phase 2: Slot values from each loaded MDR corpus Section B.
	// Zero static data. Every string originates from a loaded file.
	strSet := map[string]bool{}

	// Phase 1: Opcode names from base dictionary
	if dictPath != "" {
		data, err := os.ReadFile(dictPath)
		if err == nil {
			lines := splitLines(string(data))
			inS3 := false
			for _, line := range lines {
				if containsStr(line, "SECTION 3") { inS3 = true; continue }
				if containsStr(line, "SECTION 4") { break }
				if !inS3 { continue }
				parts := splitCSV(line)
				if len(parts) >= 5 {
					prefix := trimSpace(parts[1])
					opcode := trimSpace(parts[3])
					if len(prefix) >= 1 && len(prefix) <= 2 && prefix[0] >= 'A' && prefix[0] <= 'Z' && opcode != "" && opcode != "Opcode" {
						strSet[opcode] = true
					}
				}
			}
		}
	}

	// Phase 2: Slot values from each MDR corpus Section B
	for _, mdrPath := range mdrPaths {
		data, err := os.ReadFile(mdrPath)
		if err != nil { continue }
		lines := splitLines(string(data))
		inSB := false
		for _, line := range lines {
			trimmed := trimSpace(line)
			if containsStr(trimmed, "SECTION B") { inSB = true; continue }
			if inSB && strings.HasPrefix(trimmed, "SECTION ") && !containsStr(trimmed, "SECTION B") { break }
			if !inSB { continue }
			if trimmed == "" || strings.HasPrefix(trimmed, "Format:") || strings.HasPrefix(trimmed, "===") || strings.HasPrefix(trimmed, "---") || strings.HasPrefix(trimmed, "Note:") { continue }

			parts := splitCSV(trimmed)
			if len(parts) >= 2 && containsStr(parts[0], ":") {
				slotValue := trimSpace(parts[1])
				if slotValue != "" { strSet[slotValue] = true }
			}
			// Extract bracket references from dependency rules
			if len(parts) >= 5 {
				depRule := parts[4]
				for i := 0; i < len(depRule); i++ {
					if depRule[i] == '[' {
						for j := i + 1; j < len(depRule); j++ {
							if depRule[j] == ']' {
								strSet[depRule[i+1:j]] = true
								i = j
								break
							}
						}
					}
				}
			}
		}
	}

	// Sort by length descending, filter to entries where interning saves bytes
	var all []string
	for s := range strSet { all = append(all, s) }
	sort.Slice(all, func(i, j int) bool {
		if len(all[i]) != len(all[j]) { return len(all[i]) > len(all[j]) }
		return all[i] < all[j]
	})

	var result []string
	for _, s := range all {
		idx := len(result)
		refCost := 2
		if idx >= 128 { refCost = 3 }
		if idx >= 16384 { refCost = 4 }
		if len(s) > refCost {
			result = append(result, s)
		}
	}
	return result
}


func splitLines(s string) []string { return splitStr(s, "\n") }
func splitCSV(s string) []string { return splitN(s, ",", 6) }
func splitStr(s, sep string) []string { return splitGeneric(s, sep) }
func splitGeneric(s, sep string) []string {
	return splitByString(s, sep)
}
func splitByString(s, sep string) []string {
	var result []string
	for {
		i := indexStr(s, sep)
		if i < 0 { result = append(result, s); break }
		result = append(result, s[:i])
		s = s[i+len(sep):]
	}
	return result
}
func splitN(s, sep string, n int) []string { return strings.SplitN(s, sep, n) }
func containsStr(s, sub string) bool { return strings.Contains(s, sub) }
func trimSpace(s string) string { return strings.TrimSpace(s) }
func indexStr(s, sub string) int { return strings.Index(s, sub) }

// ─── SAIL Codec ──────────────────────────────────────────────────────────────

type SAILCodec struct {
	opToIdx  opcodeIndex
	idxToOp  indexOpcode
	strToRef map[string]int
	refToStr map[int]string
}

func NewSAILCodec(dictPath string, mdrPaths []string) (*SAILCodec, error) {
	op, idx, err := buildOpcodeTables(dictPath)
	if err != nil {
		return nil, err
	}
	internTbl := buildInternTable(dictPath, mdrPaths)
	str2ref := make(map[string]int, len(internTbl))
	ref2str := make(map[int]string, len(internTbl))
	for i, s := range internTbl {
		str2ref[s] = i
		ref2str[i] = s
	}
	return &SAILCodec{opToIdx: op, idxToOp: idx, strToRef: str2ref, refToStr: ref2str}, nil
}

func isAlnumExt(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.'
}

func (s *SAILCodec) encodeToken(token string) []byte {
	if idx, ok := s.strToRef[token]; ok {
		ref := append([]byte{tokREF}, encodeVarint(uint64(idx))...)
		if len(ref) < len(token) {
			return ref
		}
	}
	return []byte(token)
}

func (s *SAILCodec) Encode(sal string) []byte {
	out := make([]byte, 0, len(sal))
	runes := []rune(sal)
	pos := 0
	n := len(runes)

	for pos < n {
		ch := runes[pos]

		// Compound operator: NOT-THEN
		if pos+1 < n && runes[pos] == 0xAC && runes[pos+1] == 0x2192 {
			out = append(out, tokUNLESS)
			pos += 2
			continue
		}

		// Multi-byte Unicode glyph
		if ch >= 0x80 {
			if tok, ok := glyphToToken[ch]; ok {
				out = append(out, tok)
				pos++
				continue
			}
		}

		// Namespace:Opcode
		if ch >= 'A' && ch <= 'Z' {
			if encoded, newPos, ok := s.tryNsOp(runes, pos, n); ok {
				out = append(out, encoded...)
				pos = newPos
				continue
			}
		}

		// ASCII structural tokens
		switch ch {
		case '@', '?', ';', '*', '~':
			out = append(out, glyphToToken[ch])
			pos++
			continue
		case ':':
			out = append(out, tokASSIGN)
			pos++
			continue
		case '>':
			out = append(out, tokPRIORITY)
			pos++
			continue
		case '+':
			out = append(out, tokADDITIVE)
			pos++
			continue
		case '[':
			out = append(out, tokBRACKET_OPEN)
			pos++
			continue
		case ']':
			out = append(out, tokBRACKET_CLOSE)
			pos++
			continue
		}

		// Alphanumeric run
		if ch < 128 && isAlnumExt(byte(ch)) || (ch == '-' && pos+1 < n && runes[pos+1] >= '0' && runes[pos+1] <= '9') {
			start := pos
			for pos < n && runes[pos] < 128 && isAlnumExt(byte(runes[pos])) {
				pos++
			}
			if runes[start] == '-' {
				pos = start + 1
				for pos < n && runes[pos] < 128 && isAlnumExt(byte(runes[pos])) {
					pos++
				}
			}
			token := string(runes[start:pos])
			if numBytes, ok := s.tryNumeric(token); ok {
				out = append(out, numBytes...)
			} else {
				out = append(out, s.encodeToken(token)...)
			}
			continue
		}

		// Remaining ASCII
		if ch < 128 {
			out = append(out, s.encodeToken(string(ch))...)
			pos++
			continue
		}

		// Unknown Unicode
		out = append(out, []byte(string(ch))...)
		pos++
	}

	out = append(out, tokEND)
	return out
}

func (s *SAILCodec) tryNsOp(runes []rune, pos, n int) ([]byte, int, bool) {
	colonPos := -1
	for i := pos; i < n && i < pos+3; i++ {
		if runes[i] == ':' {
			colonPos = i
			break
		}
	}
	if colonPos <= pos || colonPos-pos > 2 {
		return nil, 0, false
	}
	ns := string(runes[pos:colonPos])
	nsIdx, ok := map[string]int{}[ns]
	_ = nsIdx
	if ns[0] < 'A' || ns[0] > 'Z' {
		return nil, 0, false
	}
	nsIndex := int(ns[0] - 'A')
	opStart := colonPos + 1
	opEnd := opStart
	for opEnd < n && ((runes[opEnd] >= 'A' && runes[opEnd] <= 'Z') || (runes[opEnd] >= '0' && runes[opEnd] <= '9')) {
		opEnd++
	}
	opcode := string(runes[opStart:opEnd])
	if opcode == "" {
		return nil, 0, false
	}
	nsOps, ok := s.opToIdx[ns]
	if !ok {
		return nil, 0, false
	}
	opIdx, ok := nsOps[opcode]
	if !ok {
		return nil, 0, false
	}
	return []byte{tokFRAME, byte(nsIndex), byte(opIdx)}, opEnd, true
}

func (s *SAILCodec) tryNumeric(token string) ([]byte, bool) {
	isNeg := strings.HasPrefix(token, "-")
	numPart := token
	if isNeg {
		numPart = token[1:]
	}
	if numPart == "" {
		return nil, false
	}
	hasDot := false
	pure := true
	for _, c := range numPart {
		if c == '.' {
			if hasDot { pure = false; break }
			hasDot = true
		} else if c < '0' || c > '9' {
			pure = false
			break
		}
	}
	if !pure {
		return nil, false
	}
	hasLeadingZero := !isNeg && len(numPart) > 1 && numPart[0] == '0'
	if hasDot || hasLeadingZero {
		return nil, false // encode as token instead
	}
	val := uint64(0)
	for _, c := range numPart {
		val = val*10 + uint64(c-'0')
	}
	var out []byte
	if isNeg {
		out = append(out, tokNEGINT)
	} else {
		out = append(out, tokVARINT)
	}
	out = append(out, encodeVarint(val)...)
	return out, true
}

func (s *SAILCodec) Decode(data []byte) string {
	var parts []string
	pos := 0
	n := len(data)

	for pos < n {
		b := data[pos]
		if b == tokEND {
			break
		}
		if b == tokFRAME {
			pos++
			if pos+1 >= n { break }
			nsIdx := data[pos]; pos++
			opIdx := data[pos]; pos++
			ns := ""
			if nsIdx < 26 { ns = string(rune('A' + nsIdx)) } else { ns = fmt.Sprintf("?%d", nsIdx) }
			opcode := fmt.Sprintf("?%d", opIdx)
			if nsOps, ok := s.idxToOp[ns]; ok {
				if op, ok := nsOps[int(opIdx)]; ok { opcode = op }
			}
			parts = append(parts, ns+":"+opcode)
			continue
		}
		if b == tokREF {
			pos++
			idx, newPos := decodeVarint(data, pos)
			pos = newPos
			if s, ok := s.refToStr[int(idx)]; ok {
				parts = append(parts, s)
			} else {
				parts = append(parts, fmt.Sprintf("?REF%d", idx))
			}
			continue
		}
		if b == tokSTRING {
			pos++
			strLen, newPos := decodeVarint(data, pos)
			pos = newPos
			if pos+int(strLen) <= n {
				parts = append(parts, string(data[pos:pos+int(strLen)]))
				pos += int(strLen)
			}
			continue
		}
		if g, ok := tokenToGlyph[b]; ok {
			parts = append(parts, string(g))
			pos++
			continue
		}
		if b == tokVARINT { pos++; v, p := decodeVarint(data, pos); pos = p; parts = append(parts, fmt.Sprintf("%d", v)); continue }
		if b == tokNEGINT { pos++; v, p := decodeVarint(data, pos); pos = p; parts = append(parts, fmt.Sprintf("-%d", v)); continue }
		if b == tokFLOAT16 && pos+2 < n {
			pos++
			bits := binary.BigEndian.Uint16(data[pos : pos+2])
			parts = append(parts, fmt.Sprintf("%.4g", math.Float32frombits(halfToFloat32(bits))))
			pos += 2
			continue
		}
		if b == tokFLOAT32 && pos+4 < n {
			pos++
			bits := binary.BigEndian.Uint32(data[pos : pos+4])
			parts = append(parts, fmt.Sprintf("%g", math.Float32frombits(bits)))
			pos += 4
			continue
		}
		if b < 0x80 { parts = append(parts, string(rune(b))); pos++; continue }
		pos++
	}
	return strings.Join(parts, "")
}

func halfToFloat32(h uint16) uint32 {
	sign := uint32(h>>15) & 1
	exp := uint32(h>>10) & 0x1F
	mant := uint32(h) & 0x3FF
	if exp == 0 {
		if mant == 0 { return sign << 31 }
		for mant&0x400 == 0 { mant <<= 1; exp-- }
		exp++; mant &= 0x3FF
		return (sign << 31) | ((exp + 112) << 23) | (mant << 13)
	}
	if exp == 31 {
		if mant == 0 { return (sign << 31) | 0x7F800000 }
		return (sign << 31) | 0x7FC00000
	}
	return (sign << 31) | ((exp + 112) << 23) | (mant << 13)
}

// ─── SEC Codec ───────────────────────────────────────────────────────────────

type SecEnvelope struct {
	Mode       WireMode
	NodeID     []byte
	SeqCounter uint32
	Payload    []byte
	AuthTag    []byte
	Signature  []byte
}

type SecCodec struct {
	nodeID       []byte
	signingKey   []byte
	symmetricKey []byte
	seqCounter   uint32
}

func NewSecCodec(nodeID, signingKey, symmetricKey []byte) (*SecCodec, error) {
	if len(nodeID) != 2 && len(nodeID) != 4 {
		return nil, errors.New("nodeID must be 2 or 4 bytes")
	}
	if signingKey == nil { signingKey = make([]byte, 32); rand.Read(signingKey) }
	if symmetricKey == nil { symmetricKey = make([]byte, 32); rand.Read(symmetricKey) }
	return &SecCodec{nodeID: nodeID, signingKey: signingKey, symmetricKey: symmetricKey}, nil
}

func (c *SecCodec) seal(ad, payload []byte) ([]byte, []byte) {
	mac := hmac.New(sha256.New, c.symmetricKey)
	mac.Write(ad)
	mac.Write(payload)
	tag := mac.Sum(nil)[:16]
	return payload, tag
}

func (c *SecCodec) open(ad, payload, authTag []byte) ([]byte, bool) {
	mac := hmac.New(sha256.New, c.symmetricKey)
	mac.Write(ad)
	mac.Write(payload)
	expected := mac.Sum(nil)[:16]
	if subtle.ConstantTimeCompare(authTag, expected) == 1 { return payload, true }
	return nil, false
}

func (c *SecCodec) sign(msg []byte) []byte {
	mac := hmac.New(sha256.New, c.signingKey)
	mac.Write(msg)
	sig := mac.Sum(nil)
	return append(sig, sig...) // 64 bytes
}

func (c *SecCodec) verify(msg, signature []byte) bool {
	mac := hmac.New(sha256.New, c.signingKey)
	mac.Write(msg)
	expected := mac.Sum(nil)
	expectedSig := append(expected, expected...)
	return subtle.ConstantTimeCompare(signature, expectedSig) == 1
}

func (c *SecCodec) Pack(payload []byte, mode WireMode) ([]byte, error) {
	modeByte := byte(mode & 0x03)
	if len(c.nodeID) == 4 { modeByte |= nodeIDLong }
	c.seqCounter++
	seqBuf := make([]byte, 4)
	binary.BigEndian.PutUint32(seqBuf, c.seqCounter)
	header := append([]byte{modeByte}, c.nodeID...)
	header = append(header, seqBuf...)
	sealed, authTag := c.seal(header, payload)
	signInput := append(append(append([]byte{}, header...), sealed...), authTag...)
	sig := c.sign(signInput)
	result := append(append(append(append([]byte{}, header...), sealed...), authTag...), sig...)
	return result, nil
}

func (c *SecCodec) Unpack(data []byte) (*SecEnvelope, error) {
	if len(data) < 87 { return nil, errors.New("data too short") }
	pos := 0
	modeByte := data[pos]; pos++
	mode := WireMode(modeByte & 0x03)
	nodeIDLen := 2
	if modeByte&nodeIDLong != 0 { nodeIDLen = 4 }
	nodeID := data[pos : pos+nodeIDLen]; pos += nodeIDLen
	seqCounter := binary.BigEndian.Uint32(data[pos : pos+4]); pos += 4
	header := data[:pos]
	payloadEnd := len(data) - 80
	if payloadEnd < pos { return nil, errors.New("invalid envelope") }
	payload := data[pos:payloadEnd]
	authTag := data[payloadEnd : payloadEnd+16]
	signature := data[payloadEnd+16 : payloadEnd+80]
	verified, ok := c.open(header, payload, authTag)
	if !ok { return nil, errors.New("auth verification failed") }
	signInput := append(append(append([]byte{}, header...), payload...), authTag...)
	if !c.verify(signInput, signature) { return nil, errors.New("signature verification failed") }
	return &SecEnvelope{Mode: mode, NodeID: nodeID, SeqCounter: seqCounter, Payload: verified, AuthTag: authTag, Signature: signature}, nil
}

// ─── Unified Wire Codec ──────────────────────────────────────────────────────

type OSMPWireCodec struct {
	Sail *SAILCodec
	Sec  *SecCodec
}

func NewOSMPWireCodec(dictPath string, mdrPaths []string, nodeID, signingKey, symmetricKey []byte) (*OSMPWireCodec, error) {
	sail, err := NewSAILCodec(dictPath, mdrPaths)
	if err != nil { return nil, err }
	if nodeID == nil { nodeID = []byte{0x00, 0x01} }
	sec, err := NewSecCodec(nodeID, signingKey, symmetricKey)
	if err != nil { return nil, err }
	return &OSMPWireCodec{Sail: sail, Sec: sec}, nil
}

func (c *OSMPWireCodec) Encode(sal string, mode WireMode) ([]byte, error) {
	switch mode {
	case ModeMnemonic:
		return []byte(sal), nil
	case ModeSAIL:
		return c.Sail.Encode(sal), nil
	case ModeSEC:
		return c.Sec.Pack([]byte(sal), ModeSEC)
	case ModeSAILSEC:
		return c.Sec.Pack(c.Sail.Encode(sal), ModeSAILSEC)
	}
	return nil, fmt.Errorf("unknown wire mode: %d", mode)
}

func (c *OSMPWireCodec) Decode(data []byte, mode WireMode) (string, error) {
	switch mode {
	case ModeMnemonic:
		return string(data), nil
	case ModeSAIL:
		return c.Sail.Decode(data), nil
	case ModeSEC:
		env, err := c.Sec.Unpack(data)
		if err != nil { return "", err }
		return string(env.Payload), nil
	case ModeSAILSEC:
		env, err := c.Sec.Unpack(data)
		if err != nil { return "", err }
		return c.Sail.Decode(env.Payload), nil
	}
	return "", fmt.Errorf("unknown wire mode: %d", mode)
}
