// Orchestrator — head chef. Faithful Go port.
package brigade

import (
	"regexp"
	"sort"
	"strings"

	"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)

// init registers the brigade Orchestrator as the osmp.Composer's primary
// path. This avoids an import cycle (brigade imports osmp; osmp can't
// directly import brigade). See osmp.SetBrigadeCompose for the wiring
// contract. Side-effect import users can opt in via:
//
//	import _ "github.com/octid-io/cloudless-sky/sdk/go/osmp/brigade"
func init() {
	var singleton *Orchestrator
	osmp.SetBrigadeCompose(func(nl string) string {
		if singleton == nil {
			singleton = NewOrchestrator()
		}
		return singleton.Compose(nl)
	})
}

// ComposeMode is the high-level decision the orchestrator made.
type ComposeMode string

const (
	ModeSAL         ComposeMode = "sal"
	ModeBridge      ComposeMode = "bridge"
	ModePassthrough ComposeMode = "passthrough"
	ModeRefused     ComposeMode = "refused"
)

// ComposeResult mirrors the Python ComposeResult / TS ComposeResult.
type ComposeResult struct {
	SAL        string
	Mode       ComposeMode
	Hint       string
	Residue    string
	ReasonCode string
}

var pronounObjects = map[string]bool{
	"that": true, "it": true, "this": true, "them": true,
	"these": true, "those": true, "everything": true,
}

var actionVerbsNeedingValidObject = map[string]bool{
	"stop": true, "halt": true, "cease": true, "block": true,
	"close": true, "lock": true, "open": true, "unlock": true,
	"start": true, "kill": true, "shutdown": true, "shut": true,
	"reboot": true, "restart": true,
}

var actionNamespaces = map[string]bool{
	"R": true, "K": true, "M": true, "C": true, "S": true,
}

var schedulableOpcodes = map[string]bool{
	"PING": true, "STOP": true, "BK": true, "CFG": true, "RSTRT": true,
	"ENC": true, "SIGN": true, "ALERT": true, "NOTIFY": true, "PUSH": true,
	"FETCH": true, "STORE": true, "BACKUP": true, "Q": true, "MOV": true,
	"CAM": true, "MIC": true, "TORCH": true, "HAPTIC": true, "REPORT": true,
	"AUDIT": true, "LOG": true, "VFY": true, "ID": true,
}

var stopwordsResidue = map[string]bool{
	"the": true, "a": true, "an": true, "to": true, "of": true,
	"for": true, "from": true, "with": true, "and": true, "or": true,
	"is": true, "are": true, "be": true, "been": true, "this": true,
	"that": true, "please": true, "could": true, "you": true, "i": true,
	"me": true, "my": true,
}

// Orchestrator is the brigade head chef.
type Orchestrator struct {
	Registry *BrigadeRegistry
}

// NewOrchestrator returns a default orchestrator with all 26 stations.
func NewOrchestrator() *Orchestrator {
	return &Orchestrator{Registry: DefaultRegistry()}
}

// Compose returns just the SAL (or "" if passthrough/refused).
func (o *Orchestrator) Compose(nl string) string {
	r := o.ComposeWithHint(nl)
	return r.SAL
}

// ComposeWithHint runs the full brigade pipeline and returns the structured
// decision, including mode and a teaching hint.
func (o *Orchestrator) ComposeWithHint(nl string) ComposeResult {
	req := Parse(nl)
	return o.composeRequestWithHint(req, nl)
}

func (o *Orchestrator) composeRequestWithHint(req ParsedRequest, raw string) ComposeResult {
	if utf8Bytes(raw) < 5 {
		return ComposeResult{
			Mode:       ModeRefused,
			ReasonCode: "INPUT_TOO_SHORT",
		}
	}
	if req.IsNegated {
		return ComposeResult{
			Mode:       ModeRefused,
			ReasonCode: "NEGATION",
		}
	}
	if req.HasGlyphInjection {
		return ComposeResult{
			Mode:       ModeRefused,
			ReasonCode: "UNSAFE_INPUT",
		}
	}
	if req.VerbLemma != "" && req.DirectObject != "" {
		dobjFirst := strings.SplitN(strings.TrimSpace(strings.ToLower(req.DirectObject)), " ", 2)[0]
		if pronounObjects[dobjFirst] && len(req.Targets) == 0 {
			return ComposeResult{
				Mode:       ModeRefused,
				ReasonCode: "UNRESOLVED_PRONOUN",
			}
		}
	}
	if req.VerbLemma != "" && actionVerbsNeedingValidObject[req.VerbLemma] && req.DirectObject != "" {
		objFirst := strings.SplitN(strings.TrimSpace(strings.ToLower(req.DirectObject)), " ", 2)[0]
		if !ActuatorObjectNouns[objFirst] {
			hasEntity := false
			for _, t := range req.Targets {
				if t.Source == "entity" {
					hasEntity = true
					break
				}
			}
			if !hasEntity {
				return ComposeResult{
					Mode:       ModeRefused,
					ReasonCode: "NON_ACTUATOR_OBJECT",
				}
			}
		}
	}

	if len(req.ChainSegments) > 0 {
		sal := o.composeChain(req, raw)
		if sal != "" {
			return ComposeResult{SAL: sal, Mode: ModeSAL}
		}
		return ComposeResult{
			Mode:       ModePassthrough,
			ReasonCode: "CHAIN_INCOMPLETE",
		}
	}

	sal := o.composeSingleFrame(req, raw)
	if sal != "" {
		return ComposeResult{SAL: sal, Mode: ModeSAL}
	}

	proposalsByNs := o.Registry.ProposeAll(req)
	bridge := o.tryBridgeMode(req, proposalsByNs, raw)
	if bridge != "" {
		if strings.Contains(bridge, "::") {
			parts := strings.SplitN(bridge, "::", 2)
			return ComposeResult{
				SAL:        parts[0],
				Mode:       ModeBridge,
				Residue:    parts[1],
				ReasonCode: "PARTIAL_COMPOSE",
			}
		}
		return ComposeResult{SAL: bridge, Mode: ModeSAL}
	}

	if len(req.NamespaceHints) == 0 && len(req.Targets) == 0 && len(req.SlotValues) == 0 {
		return ComposeResult{
			Mode:       ModePassthrough,
			ReasonCode: "NO_PROTOCOL_CONTENT",
		}
	}
	return ComposeResult{
		Mode:       ModePassthrough,
		ReasonCode: "NO_OPCODE_MATCH",
	}
}

func (o *Orchestrator) composeChain(req ParsedRequest, raw string) string {
	var subSals []string
	for _, seg := range req.ChainSegments {
		sub := o.composeRequestNoHint(seg, raw)
		if sub == "" {
			sub = o.composeRequestNoHint(seg, seg.Raw)
		}
		if sub == "" {
			return ""
		}
		subSals = append(subSals, sub)
	}
	if len(subSals) < 2 {
		return ""
	}
	op := req.ChainOperator
	if op == "" {
		op = "\u2227"
	}
	joined := strings.Join(subSals, op)
	if validateOK(joined, raw) {
		return joined
	}
	return ""
}

func (o *Orchestrator) composeRequestNoHint(req ParsedRequest, raw string) string {
	r := o.composeRequestWithHint(req, raw)
	return r.SAL
}

func (o *Orchestrator) composeSingleFrame(req ParsedRequest, raw string) string {
	proposalsByNs := o.Registry.ProposeAll(req)
	if len(proposalsByNs) == 0 {
		return ""
	}

	for _, p := range proposalsByNs["R"] {
		if p.Opcode == "ESTOP" {
			sal := p.Assemble()
			if validateOK(sal, raw) {
				return sal
			}
		}
	}

	if len(req.Conditions) > 0 {
		sal := o.buildConditionalChain(req, proposalsByNs, raw)
		if sal != "" {
			return sal
		}
	}
	if req.Schedule != "" && req.VerbLemma != "" {
		sal := o.buildScheduledChain(req, proposalsByNs, raw)
		if sal != "" {
			return sal
		}
	}

	sal := o.buildSingleBest(req, proposalsByNs, raw)
	if sal != "" {
		if req.AuthorizationRequired {
			m := nsPrefixRe.FindStringSubmatch(sal)
			if m != nil && actionNamespaces[m[1]] {
				sal = "I:\u00a7\u2192" + sal
			} else {
				return ""
			}
		}
		if validateOK(sal, raw) {
			return sal
		}
	}
	return ""
}

var nsPrefixRe = regexp.MustCompile(`^([A-Z\x{03a9}]):`)

func (o *Orchestrator) pickNamespacePriority(req ParsedRequest, proposalsByNs map[string][]FrameProposal) []string {
	var order []string
	if req.DomainHint != "" {
		domainPriority := map[string][]string{
			"medical":        {"H", "I", "U", "L"},
			"uav":            {"V", "R", "G", "I"},
			"weather":        {"W", "E"},
			"device_control": {"R", "C"},
			"meshtastic":     {"A", "N", "G", "O"},
			"crypto":         {"S", "I"},
			"config":         {"N", "T"},
			"vehicle":        {"V", "G"},
			"sensor":         {"E"},
		}
		for _, ns := range domainPriority[req.DomainHint] {
			order = append(order, ns)
		}
	}
	for _, ns := range req.NamespaceHints {
		if !containsString(order, ns) {
			order = append(order, ns)
		}
	}
	// Iterate proposals in registry-insertion order for determinism.
	for _, st := range o.Registry.AllStations() {
		ns := st.Namespace()
		if _, ok := proposalsByNs[ns]; ok && !containsString(order, ns) {
			order = append(order, ns)
		}
	}
	return order
}

func (o *Orchestrator) buildSingleBest(req ParsedRequest, proposalsByNs map[string][]FrameProposal, raw string) string {
	order := o.pickNamespacePriority(req, proposalsByNs)

	var allProps []FrameProposal
	// Iterate in registry-insertion order for determinism.
	for _, st := range o.Registry.AllStations() {
		ns := st.Namespace()
		if props, ok := proposalsByNs[ns]; ok {
			allProps = append(allProps, props...)
		}
	}

	var highConf []FrameProposal
	for _, p := range allProps {
		if p.Confidence >= 2.0 {
			highConf = append(highConf, p)
		}
	}
	sortProposals(highConf)
	for _, p := range highConf {
		for _, variant := range frameVariants(p) {
			if validateOK(variant, raw) {
				return variant
			}
		}
	}

	for _, ns := range order {
		props := proposalsByNs[ns]
		var normal []FrameProposal
		for _, p := range props {
			if p.Confidence < 2.0 {
				normal = append(normal, p)
			}
		}
		if len(normal) == 0 {
			continue
		}
		sortProposals(normal)
		for _, p := range normal {
			for _, variant := range frameVariants(p) {
				if validateOK(variant, raw) {
					return variant
				}
			}
		}
	}

	if len(allProps) >= 2 {
		for i := 0; i < len(allProps); i++ {
			for j := i + 1; j < len(allProps); j++ {
				p1 := allProps[i]
				p2 := allProps[j]
				if p1.Namespace == p2.Namespace && p1.Opcode == p2.Opcode {
					continue
				}
				sal := p1.Assemble() + "\u2227" + p2.Assemble()
				if validateOK(sal, raw) {
					return sal
				}
			}
		}
	}
	return ""
}

func sortProposals(props []FrameProposal) {
	sort.SliceStable(props, func(i, j int) bool {
		if props[i].Confidence != props[j].Confidence {
			return props[i].Confidence > props[j].Confidence
		}
		return utf8Bytes(props[i].Assemble()) < utf8Bytes(props[j].Assemble())
	})
}

func frameVariants(p FrameProposal) []string {
	seen := map[string]bool{}
	var out []string
	add := func(s string) {
		if !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	add(p.Assemble())
	if p.Target != "" {
		v := p
		v.Target = ""
		add(v.Assemble())
	}
	if p.IsQuery {
		v := p
		v.IsQuery = false
		add(v.Assemble())
	}
	if p.Target != "" && p.IsQuery {
		v := p
		v.Target = ""
		v.IsQuery = false
		add(v.Assemble())
	}
	return out
}

func (o *Orchestrator) buildConditionalChain(req ParsedRequest, proposalsByNs map[string][]FrameProposal, raw string) string {
	var sensing *FrameProposal
	sensingOpcodes := map[string]bool{
		"HR": true, "BP": true, "TH": true, "HU": true, "PU": true,
		"WIND": true, "SPO2": true, "TEMP": true, "HDG": true, "POS": true,
	}
	for _, ns := range []string{"H", "E", "W", "V"} {
		for _, p := range proposalsByNs[ns] {
			if sensingOpcodes[p.Opcode] {
				cp := p
				sensing = &cp
				break
			}
		}
		if sensing != nil {
			break
		}
	}
	if sensing == nil {
		return ""
	}

	var alert *FrameProposal
	if sensing.Namespace == "H" {
		for _, p := range proposalsByNs["H"] {
			if p.Opcode == "ALERT" || p.Opcode == "CASREP" {
				cp := p
				alert = &cp
				break
			}
		}
	}
	if alert == nil && sensing.Namespace == "W" {
		for _, p := range proposalsByNs["W"] {
			if p.Opcode == "ALERT" {
				cp := p
				alert = &cp
				break
			}
		}
	}
	if alert == nil {
		for _, ns := range []string{"U", "L"} {
			for _, p := range proposalsByNs[ns] {
				if p.Opcode == "NOTIFY" || p.Opcode == "ALERT" {
					cp := p
					alert = &cp
					break
				}
			}
			if alert != nil {
				break
			}
		}
	}
	if alert == nil {
		return ""
	}

	cond := req.Conditions[0]
	sensingSal := sensing.Assemble() + cond.Operator + cond.Value
	alertSal := alert.Assemble()
	sal := sensingSal + "\u2192" + alertSal
	if validateOK(sal, raw) {
		return sal
	}
	return ""
}

func (o *Orchestrator) buildScheduledChain(req ParsedRequest, proposalsByNs map[string][]FrameProposal, raw string) string {
	var action *FrameProposal
	for _, ns := range []string{"A", "R", "N", "C", "S", "L", "U", "H", "W", "I"} {
		for _, p := range proposalsByNs[ns] {
			if schedulableOpcodes[p.Opcode] {
				cp := p
				action = &cp
				break
			}
		}
		if action != nil {
			break
		}
	}
	if action == nil {
		return ""
	}
	schedSal := "T:SCHED[" + req.Schedule + "]"
	for _, op := range []string{"\u2192", ";"} {
		sal := schedSal + op + action.Assemble()
		if validateOK(sal, raw) {
			return sal
		}
	}
	return ""
}

func (o *Orchestrator) tryBridgeMode(req ParsedRequest, proposalsByNs map[string][]FrameProposal, raw string) string {
	bridgeForbiddenOpcodes := map[string]bool{
		"ALERT": true, "CASREP": true, "ESTOP": true, "STOP": true, "MOV": true,
		"RTH": true, "CFG": true, "BK": true, "KILL": true, "RSTRT": true,
		"ENC": true, "DEC": true, "SIGN": true, "KEYGEN": true, "PUSH": true,
		"DEL": true, "FORM": true, "CAM": true, "MIC": true, "SPKR": true,
		"TORCH": true, "HAPTIC": true, "VIBE": true, "BT": true, "WIFI": true,
		"DISP": true, "SCRN": true,
	}
	var bridgeCandidate *FrameProposal
	// Iterate in registry-insertion order for determinism.
	for _, st := range o.Registry.AllStations() {
		ns := st.Namespace()
		if !BridgeAllowedNamespaces[ns] {
			continue
		}
		props, ok := proposalsByNs[ns]
		if !ok {
			continue
		}
		for _, p := range props {
			if BridgeForbiddenFrames[p.Namespace+":"+p.Opcode] {
				continue
			}
			if bridgeForbiddenOpcodes[p.Opcode] {
				continue
			}
			if bridgeCandidate == nil || p.Confidence > bridgeCandidate.Confidence {
				cp := p
				bridgeCandidate = &cp
			}
		}
	}
	if bridgeCandidate == nil {
		return ""
	}
	salPart := bridgeCandidate.Assemble()
	if !validateOK(salPart, raw) {
		return ""
	}
	residue := o.computeResidue(req, *bridgeCandidate)
	if strings.TrimSpace(residue) == "" {
		return salPart
	}
	if ModifierMarkersPattern.MatchString(residue) {
		return ""
	}
	composite := salPart + "::" + residue
	if utf8Bytes(composite) >= utf8Bytes(raw) {
		return ""
	}
	return composite
}

var residuePunctRe = regexp.MustCompile(`[,.!?;:'"]`)

func (o *Orchestrator) computeResidue(req ParsedRequest, p FrameProposal) string {
	consumed := map[string]bool{}
	if req.Verb != "" {
		consumed[strings.ToLower(req.Verb)] = true
	}
	if req.VerbLemma != "" && req.VerbLemma != req.Verb {
		consumed[strings.ToLower(req.VerbLemma)] = true
	}
	if req.DirectObject != "" {
		for _, w := range strings.Fields(strings.ToLower(req.DirectObject)) {
			consumed[w] = true
		}
	}
	for _, t := range req.Targets {
		consumed[strings.ToLower(t.ID)] = true
	}
	for _, sv := range req.SlotValues {
		consumed[strings.ToLower(sv.Value)] = true
	}
	var tokens []string
	for _, tok := range strings.Fields(req.Raw) {
		c := residuePunctRe.ReplaceAllString(strings.ToLower(tok), "")
		if consumed[c] || stopwordsResidue[c] {
			continue
		}
		tokens = append(tokens, tok)
	}
	return strings.Join(tokens, " ")
}

// validateOK runs the SAL through the OSMP composition validator. SAL with
// errors is not safe to emit.
func validateOK(sal, nl string) bool {
	r := osmp.ValidateComposition(sal, nl, nil, true, nil)
	if r == nil {
		return true
	}
	return r.Valid
}
