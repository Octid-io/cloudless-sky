package osmp

import (
	"crypto/sha256"
	"encoding/json"
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
	type kv struct{ K string; V map[string]string }
	keys := make([]string, 0, len(d.data))
	for k := range d.data { keys = append(keys, k) }
	sort.Strings(keys)
	rows := make([]kv, len(keys))
	for i, k := range keys { rows[i] = kv{K: k, V: d.data[k]} }
	b, _ := json.Marshal(rows)
	sum := sha256.Sum256(b)
	return fmt.Sprintf("%x", sum[:8])
}

func (d *AdaptiveSharedDictionary) Namespaces() []string {
	ns := make([]string, 0, len(d.data))
	for k := range d.data { ns = append(ns, k) }
	sort.Strings(ns)
	return ns
}
