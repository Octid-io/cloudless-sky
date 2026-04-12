// Package osmp implements OSMP wire modes: SAIL (Semantic Assembly Isomorphic Language)
// and SEC (Security Envelope) for the Octid Semantic Mesh Protocol.
//
// Zero external dependencies. Compiles into a binary.
// Dictionary: OSMP-semantic-dictionary-v15.csv
package osmp

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/crypto/chacha20poly1305"
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
			filepath.Join("protocol", "OSMP-semantic-dictionary-v15.csv"),
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

// ─── Dictionary Basis Manifest (ADR-004) ─────────────────────────────────────
//
// A Dictionary Basis is an ordered list of (corpus_id, corpus_hash) pairs that
// determines a node's SAIL intern table by pure-function construction. Two
// nodes loading the same ordered basis produce byte-identical intern tables
// and unlock SAIL with each other; nodes with different bases interoperate in
// SAL-only mode via FNP capability grading (spec §9.5).
//
// See ADR-004 and spec §9.8.

// CorpusEntry is a single entry in a Dictionary Basis.
type CorpusEntry struct {
	// CorpusID is a stable UTF-8 identifier (1-255 bytes), e.g. "asd-v15".
	CorpusID string
	// CorpusHash is the full 32-byte SHA-256 over the corpus file bytes verbatim.
	CorpusHash [32]byte
}

func validateCorpusEntry(e CorpusEntry) error {
	idLen := len([]byte(e.CorpusID))
	if idLen < 1 || idLen > 255 {
		return fmt.Errorf("corpus_id must be 1-255 UTF-8 bytes, got %d", idLen)
	}
	// CorpusHash is a fixed 32-byte array, length is structural.
	return nil
}

// DictionaryBasis is the ordered, content-addressed set of dictionary corpora
// (ADR-004). It is the input to deterministic SAIL intern table construction.
type DictionaryBasis struct {
	entries     []CorpusEntry
	fingerprint [8]byte
	fpCached    bool
}

// NewDictionaryBasis constructs a basis from an ordered list of entries.
// Returns an error if the entries slice is empty or any entry is invalid.
func NewDictionaryBasis(entries []CorpusEntry) (*DictionaryBasis, error) {
	if len(entries) == 0 {
		return nil, errors.New("DictionaryBasis must contain at least one entry")
	}
	for i, e := range entries {
		if err := validateCorpusEntry(e); err != nil {
			return nil, fmt.Errorf("entry %d: %w", i, err)
		}
	}
	// Defensive copy to mirror Python's frozen dataclass semantics.
	cp := make([]CorpusEntry, len(entries))
	copy(cp, entries)
	return &DictionaryBasis{entries: cp}, nil
}

// Entries returns a read-only view of the basis entries.
func (b *DictionaryBasis) Entries() []CorpusEntry {
	out := make([]CorpusEntry, len(b.entries))
	copy(out, b.entries)
	return out
}

// Len returns the number of corpora in the basis.
func (b *DictionaryBasis) Len() int { return len(b.entries) }

// IsBaseOnly returns true if this basis contains only the base ASD (length 1).
func (b *DictionaryBasis) IsBaseOnly() bool { return len(b.entries) == 1 }

// CanonicalSerialization returns the canonical wire form per spec §9.3.
// For each entry in basis order:
//
//	corpus_id_length (1 byte) || corpus_id (UTF-8 bytes) || corpus_hash (32 bytes)
//
// This is unambiguous across platforms because no padding, alignment, or text
// encoding is involved beyond the explicit length prefix and the raw hash bytes.
func (b *DictionaryBasis) CanonicalSerialization() []byte {
	var out []byte
	for _, e := range b.entries {
		idBytes := []byte(e.CorpusID)
		out = append(out, byte(len(idBytes)))
		out = append(out, idBytes...)
		out = append(out, e.CorpusHash[:]...)
	}
	return out
}

// Fingerprint returns the 8-byte basis fingerprint per spec §9.3.
// First 8 bytes of SHA-256 over the canonical serialization.
func (b *DictionaryBasis) Fingerprint() [8]byte {
	if !b.fpCached {
		digest := sha256.Sum256(b.CanonicalSerialization())
		copy(b.fingerprint[:], digest[:8])
		b.fpCached = true
	}
	return b.fingerprint
}

// Equals reports whether two bases have identical entries in identical order.
func (b *DictionaryBasis) Equals(other *DictionaryBasis) bool {
	if other == nil || len(b.entries) != len(other.entries) {
		return false
	}
	for i := range b.entries {
		if b.entries[i].CorpusID != other.entries[i].CorpusID {
			return false
		}
		if b.entries[i].CorpusHash != other.entries[i].CorpusHash {
			return false
		}
	}
	return true
}

// hashFile computes SHA-256 over file bytes verbatim. No canonicalization.
func hashFile(path string) ([32]byte, error) {
	var out [32]byte
	f, err := os.Open(path)
	if err != nil {
		return out, err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return out, err
	}
	copy(out[:], h.Sum(nil))
	return out, nil
}

// deriveAsdID derives a stable ASD corpus identifier from the dictionary file.
// Looks for "vNN" in the first ~20 lines; falls back to "asd-v15".
func deriveAsdID(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return "asd-v15"
	}
	lines := strings.Split(string(data), "\n")
	if len(lines) > 20 {
		lines = lines[:20]
	}
	head := strings.Join(lines, "\n")
	for i := 0; i < len(head)-2; i++ {
		if head[i] == 'v' && head[i+1] >= '0' && head[i+1] <= '9' && head[i+2] >= '0' && head[i+2] <= '9' {
			return fmt.Sprintf("asd-v%c%c", head[i+1], head[i+2])
		}
	}
	return "asd-v15"
}

// MDRSpec is a (corpus_id, file path) pair for an MDR corpus to load.
type MDRSpec struct {
	CorpusID string
	Path     string
}

// DictionaryBasisFromPaths constructs a basis from corpus files on disk.
// asdPath: path to the base ASD CSV (the dictionary).
// asdID: optional override for the base ASD identifier (empty for autodetect).
// mdrCorpora: optional list of MDR corpora to append in the given order.
func DictionaryBasisFromPaths(asdPath, asdID string, mdrCorpora []MDRSpec) (*DictionaryBasis, error) {
	if _, err := os.Stat(asdPath); err != nil {
		return nil, fmt.Errorf("base ASD not found: %s: %w", asdPath, err)
	}
	asdHash, err := hashFile(asdPath)
	if err != nil {
		return nil, err
	}
	id := asdID
	if id == "" {
		id = deriveAsdID(asdPath)
	}
	entries := []CorpusEntry{{CorpusID: id, CorpusHash: asdHash}}
	for _, c := range mdrCorpora {
		if _, err := os.Stat(c.Path); err != nil {
			return nil, fmt.Errorf("MDR corpus not found: %s: %w", c.Path, err)
		}
		ch, err := hashFile(c.Path)
		if err != nil {
			return nil, err
		}
		entries = append(entries, CorpusEntry{CorpusID: c.CorpusID, CorpusHash: ch})
	}
	return NewDictionaryBasis(entries)
}

// DefaultDictionaryBasis constructs the default base-ASD-only basis from
// the canonical default file locations.
func DefaultDictionaryBasis(dictPath string) (*DictionaryBasis, error) {
	if dictPath == "" {
		candidates := []string{
			filepath.Join("protocol", "OSMP-semantic-dictionary-v15.csv"),
		}
		for _, c := range candidates {
			if _, err := os.Stat(c); err == nil {
				dictPath = c
				break
			}
		}
	}
	if dictPath == "" {
		return nil, errors.New("base ASD not found in any default location")
	}
	return DictionaryBasisFromPaths(dictPath, "", nil)
}

// extractAsdOpcodes adds every opcode name from the base ASD Section 3 to the
// given set. Used by basis-driven intern table construction and the historical
// default-search fallback.
func extractAsdOpcodes(strSet map[string]bool, dictPath string) {
	if dictPath == "" {
		candidates := []string{
			filepath.Join("protocol", "OSMP-semantic-dictionary-v15.csv"),
		}
		for _, c := range candidates {
			if _, err := os.Stat(c); err == nil {
				dictPath = c
				break
			}
		}
	}
	if dictPath == "" {
		return
	}
	data, err := os.ReadFile(dictPath)
	if err != nil {
		return
	}
	lines := splitLines(string(data))
	inS3 := false
	for _, line := range lines {
		if containsStr(line, "SECTION 3") {
			inS3 = true
			continue
		}
		if containsStr(line, "SECTION 4") {
			break
		}
		if !inS3 {
			continue
		}
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

// ─── Intern Table ────────────────────────────────────────────────────────────


// buildInternTable constructs the SAIL intern table from a Dictionary Basis (ADR-004).
//
// The intern table is a pure function of the basis: two basis instances with
// equal entries produce byte-identical intern tables. Index assignment is
// deterministic over (basis order, deduplicated first-seen order, length-
// descending sort, cost filter).
//
// Future corpus types declare their own extraction rules per the corpus's
// sidecar manifest. This implementation supports the base ASD CSV extractor
// as the only shipping rule. Historical "Phase 2" MDR CSV SECTION B parsing
// is removed; it produced zero observable intern entries on every shipped MDR.
func buildInternTable(basis *DictionaryBasis, dictPath string) []string {
	strSet := map[string]bool{}

	if basis != nil {
		for _, entry := range basis.entries {
			if strings.HasPrefix(entry.CorpusID, "asd-") {
				extractAsdOpcodes(strSet, dictPath)
			}
			// MDR corpus extraction rules deferred until corpora ship sidecar manifests.
		}
	} else {
		extractAsdOpcodes(strSet, dictPath)
	}

	// Sort by length descending, filter to entries where interning saves bytes
	var all []string
	for s := range strSet {
		all = append(all, s)
	}
	sort.Slice(all, func(i, j int) bool {
		if len(all[i]) != len(all[j]) {
			return len(all[i]) > len(all[j])
		}
		return all[i] < all[j]
	})

	var result []string
	for _, s := range all {
		idx := len(result)
		refCost := 2
		if idx >= 128 {
			refCost = 3
		}
		if idx >= 16384 {
			refCost = 4
		}
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
	Basis    *DictionaryBasis // ADR-004: Dictionary Basis bound to this codec
}

// NewSAILCodec constructs a SAIL codec from a dictionary path. The default
// base-ASD-only basis is constructed automatically. Use NewSAILCodecWithBasis
// for explicit basis control (ADR-004).
func NewSAILCodec(dictPath string) (*SAILCodec, error) {
	return NewSAILCodecWithBasis(dictPath, nil)
}

// NewSAILCodecWithBasis constructs a SAIL codec with an explicit Dictionary
// Basis. When basis is nil, a default base-ASD-only basis is constructed
// from dictPath.
func NewSAILCodecWithBasis(dictPath string, basis *DictionaryBasis) (*SAILCodec, error) {
	op, idx, err := buildOpcodeTables(dictPath)
	if err != nil {
		return nil, err
	}
	if basis == nil {
		basis, err = DefaultDictionaryBasis(dictPath)
		if err != nil {
			// Last-resort fallback when the dictionary cannot be located on
			// disk: synthesize a basis from a placeholder hash so the codec
			// is still constructible. Tests that exercise BasisFingerprint()
			// must supply a real basis or a valid dictPath.
			placeholder := sha256.Sum256([]byte("asd-unknown"))
			basis, _ = NewDictionaryBasis([]CorpusEntry{
				{CorpusID: "asd-unknown", CorpusHash: placeholder},
			})
		}
	}
	internTbl := buildInternTable(basis, dictPath)
	str2ref := make(map[string]int, len(internTbl))
	ref2str := make(map[int]string, len(internTbl))
	for i, s := range internTbl {
		str2ref[s] = i
		ref2str[i] = s
	}
	return &SAILCodec{opToIdx: op, idxToOp: idx, strToRef: str2ref, refToStr: ref2str, Basis: basis}, nil
}

// BasisFingerprint returns the 8-byte basis fingerprint for FNP capability
// negotiation (spec §9.3).
func (s *SAILCodec) BasisFingerprint() [8]byte {
	return s.Basis.Fingerprint()
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
	// Finding 49: U+00A7 (§) is admitted into the opcode character class to
	// match Python (sal[op_end] == "\xa7") and TypeScript (charCodeAt == 0xA7).
	// The I:§ sentinel opcode (Instructional namespace frame marker) must round-trip
	// through TOK_FRAME (3 bytes) rather than falling through to the UTF-8 atomic
	// fallback (5 bytes, first byte 0xC2 which collides with SAIL tokATOMIC on decode).
	for opEnd < n && ((runes[opEnd] >= 'A' && runes[opEnd] <= 'Z') || (runes[opEnd] >= '0' && runes[opEnd] <= '9') || runes[opEnd] == 0x00A7) {
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

// SecCodec is the security envelope encoder/decoder.
//
// Uses real cryptographic primitives:
//   - Ed25519 (RFC 8032) for sender authentication via 64-byte signatures
//     (crypto/ed25519 from the Go standard library)
//   - ChaCha20-Poly1305 (RFC 7539, RFC 8439) for AEAD payload integrity
//     with a 16-byte authentication tag
//     (golang.org/x/crypto/chacha20poly1305)
//   - 12-byte nonces derived deterministically from the envelope header
//     padded with the canonical OSMP nonce salt
//
// The wire format is byte-identical to the Python and TypeScript SecCodec
// implementations so cross-SDK envelopes interoperate natively.
//
// Key management is external (MDR node identity service). For ephemeral
// sessions or local testing, omit the key arguments and the constructor
// will generate fresh keys via crypto/rand.
type SecCodec struct {
	nodeID                   []byte
	signingKeySeed           []byte
	symmetricKey             []byte
	ed25519Private           ed25519.PrivateKey
	ed25519Public            ed25519.PublicKey
	verifyPublicKeyDefault   ed25519.PublicKey
	aead                     interface { // chacha20poly1305 AEAD interface
		Seal(dst, nonce, plaintext, additionalData []byte) []byte
		Open(dst, nonce, ciphertext, additionalData []byte) ([]byte, error)
		NonceSize() int
		Overhead() int
	}
	seqCounter uint32
}

// nonceSalt pads short envelope headers up to the 12-byte ChaCha20-Poly1305
// nonce length. Identical across Python, TypeScript, and Go SDKs.
var secNonceSalt = []byte("OSMP-SEC-v1\x00")

// NewSecCodec constructs a SecCodec with the given node identity and keys.
// signingKey must be 32 bytes (Ed25519 seed), symmetricKey must be 32 bytes
// (ChaCha20-Poly1305 key). Pass nil for either to generate a fresh random key.
func NewSecCodec(nodeID, signingKey, symmetricKey []byte) (*SecCodec, error) {
	return NewSecCodecWithVerifyKey(nodeID, signingKey, symmetricKey, nil)
}

// NewSecCodecWithVerifyKey is the full constructor including a peer public
// key for inter-node verification. If verifyKey is nil, the codec defaults
// to verifying with its own public key (loopback / local-only).
func NewSecCodecWithVerifyKey(nodeID, signingKey, symmetricKey, verifyKey []byte) (*SecCodec, error) {
	if len(nodeID) != 2 && len(nodeID) != 4 {
		return nil, errors.New("nodeID must be 2 or 4 bytes")
	}
	if signingKey == nil {
		signingKey = make([]byte, 32)
		if _, err := rand.Read(signingKey); err != nil {
			return nil, fmt.Errorf("generate signing key: %w", err)
		}
	}
	if len(signingKey) != 32 {
		return nil, fmt.Errorf("signingKey must be 32 bytes (Ed25519 seed), got %d", len(signingKey))
	}
	if symmetricKey == nil {
		symmetricKey = make([]byte, 32)
		if _, err := rand.Read(symmetricKey); err != nil {
			return nil, fmt.Errorf("generate symmetric key: %w", err)
		}
	}
	if len(symmetricKey) != 32 {
		return nil, fmt.Errorf("symmetricKey must be 32 bytes (ChaCha20-Poly1305), got %d", len(symmetricKey))
	}

	priv := ed25519.NewKeyFromSeed(signingKey)
	pub := priv.Public().(ed25519.PublicKey)

	var verifyPub ed25519.PublicKey
	if verifyKey != nil {
		if len(verifyKey) != 32 {
			return nil, fmt.Errorf("verifyKey must be 32 bytes (Ed25519 public key), got %d", len(verifyKey))
		}
		verifyPub = ed25519.PublicKey(verifyKey)
	} else {
		verifyPub = pub
	}

	aead, err := chacha20poly1305.New(symmetricKey)
	if err != nil {
		return nil, fmt.Errorf("init ChaCha20-Poly1305: %w", err)
	}

	return &SecCodec{
		nodeID:                 nodeID,
		signingKeySeed:         signingKey,
		symmetricKey:           symmetricKey,
		ed25519Private:         priv,
		ed25519Public:          pub,
		verifyPublicKeyDefault: verifyPub,
		aead:                   aead,
	}, nil
}

// PublicSigningKey returns the 32-byte raw Ed25519 public key for
// distributing to peers via the MDR identity service.
func (c *SecCodec) PublicSigningKey() []byte {
	out := make([]byte, ed25519.PublicKeySize)
	copy(out, c.ed25519Public)
	return out
}

// deriveNonce produces a 12-byte ChaCha20-Poly1305 nonce from the envelope
// header. Per-envelope uniqueness comes from the monotonic seq counter.
func (c *SecCodec) deriveNonce(header []byte) []byte {
	if len(header) >= 12 {
		out := make([]byte, 12)
		copy(out, header)
		return out
	}
	out := make([]byte, 0, 12)
	out = append(out, header...)
	out = append(out, secNonceSalt...)
	return out[:12]
}

func (c *SecCodec) seal(ad, payload []byte) ([]byte, []byte) {
	nonce := c.deriveNonce(ad)
	sealed := c.aead.Seal(nil, nonce, payload, ad)
	// chacha20poly1305.Seal returns ciphertext || tag; split into the two parts.
	tagOff := len(sealed) - 16
	ciphertext := make([]byte, tagOff)
	copy(ciphertext, sealed[:tagOff])
	authTag := make([]byte, 16)
	copy(authTag, sealed[tagOff:])
	return ciphertext, authTag
}

func (c *SecCodec) open(ad, payload, authTag []byte) ([]byte, bool) {
	nonce := c.deriveNonce(ad)
	combined := make([]byte, 0, len(payload)+len(authTag))
	combined = append(combined, payload...)
	combined = append(combined, authTag...)
	plaintext, err := c.aead.Open(nil, nonce, combined, ad)
	if err != nil {
		return nil, false
	}
	return plaintext, true
}

func (c *SecCodec) sign(msg []byte) []byte {
	return ed25519.Sign(c.ed25519Private, msg)
}

func (c *SecCodec) verify(msg, signature []byte) bool {
	return c.verifyWithKey(msg, signature, nil)
}

// verifyWithKey allows the caller to override the default verify public key.
// Pass nil to use the codec's default (set at construction time).
func (c *SecCodec) verifyWithKey(msg, signature, verifyKey []byte) bool {
	var pub ed25519.PublicKey
	if verifyKey != nil {
		if len(verifyKey) != ed25519.PublicKeySize {
			return false
		}
		pub = ed25519.PublicKey(verifyKey)
	} else {
		pub = c.verifyPublicKeyDefault
	}
	return ed25519.Verify(pub, msg, signature)
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

func NewOSMPWireCodec(dictPath string, basis *DictionaryBasis, nodeID, signingKey, symmetricKey []byte) (*OSMPWireCodec, error) {
	sail, err := NewSAILCodecWithBasis(dictPath, basis)
	if err != nil { return nil, err }
	if nodeID == nil { nodeID = []byte{0x00, 0x01} }
	sec, err := NewSecCodec(nodeID, signingKey, symmetricKey)
	if err != nil { return nil, err }
	return &OSMPWireCodec{Sail: sail, Sec: sec}, nil
}

// Basis returns the Dictionary Basis bound to this codec (ADR-004).
func (c *OSMPWireCodec) Basis() *DictionaryBasis {
	return c.Sail.Basis
}

// BasisFingerprint returns the 8-byte basis fingerprint for FNP capability
// negotiation (spec §9.3).
func (c *OSMPWireCodec) BasisFingerprint() [8]byte {
	return c.Sail.BasisFingerprint()
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
