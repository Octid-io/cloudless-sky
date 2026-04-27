// Station base + registry. Pure functions of ParsedRequest.
package brigade

import "sort"

type Station interface {
	Namespace() string
	Propose(req ParsedRequest) []FrameProposal
}

type BrigadeRegistry struct {
	stations map[string]Station
	order    []string
}

func NewBrigadeRegistry() *BrigadeRegistry {
	return &BrigadeRegistry{stations: map[string]Station{}}
}

func (r *BrigadeRegistry) Register(s Station) {
	ns := s.Namespace()
	if _, exists := r.stations[ns]; !exists {
		r.order = append(r.order, ns)
	}
	r.stations[ns] = s
}

func (r *BrigadeRegistry) Get(namespace string) Station {
	return r.stations[namespace]
}

func (r *BrigadeRegistry) AllStations() []Station {
	out := make([]Station, 0, len(r.stations))
	for _, ns := range r.order {
		out = append(out, r.stations[ns])
	}
	return out
}

// ProposeAll returns each namespace's proposals. Stations that error
// (panic) are silently dropped.
func (r *BrigadeRegistry) ProposeAll(req ParsedRequest) map[string][]FrameProposal {
	out := map[string][]FrameProposal{}
	for _, ns := range r.order {
		st := r.stations[ns]
		props := safeCallStation(st, req)
		if len(props) > 0 {
			out[ns] = props
		}
	}
	return out
}

func safeCallStation(st Station, req ParsedRequest) (props []FrameProposal) {
	defer func() {
		if r := recover(); r != nil {
			props = nil
		}
	}()
	return st.Propose(req)
}

// pickTarget chooses the best target id for a frame.
func pickTarget(req ParsedRequest) string {
	if req.IsBroadcast && len(req.Targets) == 0 {
		return "*"
	}
	for _, t := range req.Targets {
		if t.Source == "entity" {
			return t.ID
		}
	}
	for _, t := range req.Targets {
		if t.Source == "action_verb" {
			return t.ID
		}
	}
	if len(req.Targets) > 0 {
		return req.Targets[0].ID
	}
	return ""
}

// pickTargetSensing matches sensing.ts pickTarget (no action_verb fallback).
func pickTargetSensing(req ParsedRequest) string {
	if req.IsBroadcast && len(req.Targets) == 0 {
		return "*"
	}
	for _, t := range req.Targets {
		if t.Source == "entity" {
			return t.ID
		}
	}
	if len(req.Targets) > 0 {
		return req.Targets[0].ID
	}
	return ""
}

// sortedByLengthDesc returns map keys sorted by length descending.
// Ties broken by lexicographic order to match Object.entries() insertion-order
// behavior in JS / dict iteration in Python.
func sortedByLengthDesc(m map[string]string) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		if len(keys[i]) != len(keys[j]) {
			return len(keys[i]) > len(keys[j])
		}
		return keys[i] < keys[j]
	})
	return keys
}

// containsAny returns true if any of the words is in the set.
func containsString(slice []string, target string) bool {
	for _, s := range slice {
		if s == target {
			return true
		}
	}
	return false
}

// inSliceOrEmpty returns true if val is "" (treated as null in TS) or in slice.
func inSliceOrEmpty(slice []string, val string) bool {
	for _, s := range slice {
		if s == val {
			return true
		}
	}
	return false
}

// DefaultRegistry instantiates all 26 stations.
func DefaultRegistry() *BrigadeRegistry {
	r := NewBrigadeRegistry()
	r.Register(&RStation{})
	r.Register(&EStation{})
	r.Register(&HStation{})
	r.Register(&GStation{})
	r.Register(&VStation{})
	r.Register(&WStation{})
	r.Register(&NStation{})
	r.Register(&AStation{})
	r.Register(&CStation{})
	r.Register(&TStation{})
	r.Register(&IStation{})
	r.Register(&SStation{})
	r.Register(&KStation{})
	r.Register(&BStation{})
	r.Register(&UStation{})
	r.Register(&LStation{})
	r.Register(&MStation{})
	r.Register(&DStation{})
	r.Register(&JStation{})
	r.Register(&FStation{})
	r.Register(&OStation{})
	r.Register(&PStation{})
	r.Register(&QStation{})
	r.Register(&XStation{})
	r.Register(&YStation{})
	r.Register(&ZStation{})
	return r
}
