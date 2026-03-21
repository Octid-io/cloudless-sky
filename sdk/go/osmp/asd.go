package osmp

import (
	"crypto/sha256"
	"fmt"
	"sort"
)

// DictUpdateMode controls ASD delta application.
// ADDITIVE = G-Set (grow-only), REPLACE = LWW-Register, DEPRECATE = tombstone.
// Source: Shapiro et al. "A comprehensive study of CRDTs" (2011) INRIA-00555588
type DictUpdateMode int

const (
	DictModeAdditive  DictUpdateMode = iota
	DictModeReplace
	DictModeDeprecate
)

type DeltaLogEntry struct {
	NS, Op, Def, Ver string
	Mode             DictUpdateMode
}

// AdaptiveSharedDictionary — version-pinned, compiled-in floor basis.
// Analog: QUIC static table (RFC 9204 §A)
type AdaptiveSharedDictionary struct {
	FloorVersion string
	data         map[string]map[string]string
	tombstones   map[string]bool
	log          []DeltaLogEntry
}

func NewASD() *AdaptiveSharedDictionary {
	d := &AdaptiveSharedDictionary{
		FloorVersion: ASDFloorVersion,
		data:         make(map[string]map[string]string),
		tombstones:   make(map[string]bool),
	}
	for ns, ops := range ASDFloorBasis {
		d.data[ns] = make(map[string]string, len(ops))
		for op, def := range ops {
			d.data[ns][op] = def
		}
	}
	return d
}

func (d *AdaptiveSharedDictionary) Lookup(ns, op string) string {
	if d.tombstones[ns+"::"+op] {
		return ""
	}
	return d.data[ns][op]
}

func (d *AdaptiveSharedDictionary) ApplyDelta(ns, op, def string, mode DictUpdateMode, ver string) {
	d.log = append(d.log, DeltaLogEntry{NS: ns, Op: op, Def: def, Mode: mode, Ver: ver})
	key := ns + "::" + op
	switch mode {
	case DictModeAdditive:
		if d.data[ns] == nil {
			d.data[ns] = make(map[string]string)
		}
		if _, exists := d.data[ns][op]; !exists {
			d.data[ns][op] = def
		}
	case DictModeReplace:
		if d.data[ns] == nil {
			d.data[ns] = make(map[string]string)
		}
		d.data[ns][op] = def
		delete(d.tombstones, key)
	case DictModeDeprecate:
		d.tombstones[key] = true
	}
}

func (d *AdaptiveSharedDictionary) Fingerprint() string {
	b := d.CanonicalJSON()
	sum := sha256.Sum256(b)
	return fmt.Sprintf("%x", sum[:8])
}

// CanonicalJSON returns the ASD serialized to match Python's
// json.dumps(data, sort_keys=True, ensure_ascii=True).
// Uses ", " and ": " separators; escapes non-ASCII to \uXXXX.
// Required for cross-SDK FNP fingerprint wire compatibility.
func (d *AdaptiveSharedDictionary) CanonicalJSON() []byte {
	nsList := d.Namespaces()
	var buf []byte
	buf = append(buf, '{')
	for i, ns := range nsList {
		if i > 0 {
			buf = append(buf, ',', ' ')
		}
		buf = pyQuoteGo(ns, &buf)
		buf = append(buf, ':', ' ')
		ops := make([]string, 0, len(d.data[ns]))
		for op := range d.data[ns] {
			ops = append(ops, op)
		}
		sort.Strings(ops)
		buf = append(buf, '{')
		for j, op := range ops {
			if j > 0 {
				buf = append(buf, ',', ' ')
			}
			buf = pyQuoteGo(op, &buf)
			buf = append(buf, ':', ' ')
			buf = pyQuoteGo(d.data[ns][op], &buf)
		}
		buf = append(buf, '}')
	}
	buf = append(buf, '}')
	return buf
}

func pyQuoteGo(s string, buf *[]byte) []byte {
	*buf = append(*buf, '"')
	for _, c := range s {
		switch {
		case c == '"':
			*buf = append(*buf, '\\', '"')
		case c == '\\':
			*buf = append(*buf, '\\', '\\')
		case c < 0x20:
			*buf = append(*buf, []byte(fmt.Sprintf("\\u%04x", c))...)
		case c > 0x7e:
			*buf = append(*buf, []byte(fmt.Sprintf("\\u%04x", c))...)
		default:
			*buf = append(*buf, byte(c))
		}
	}
	*buf = append(*buf, '"')
	return *buf
}

func (d *AdaptiveSharedDictionary) Namespaces() []string {
	ns := make([]string, 0, len(d.data))
	for k := range d.data { ns = append(ns, k) }
	sort.Strings(ns)
	return ns
}
