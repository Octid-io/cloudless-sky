// Support stations: C, T, I, S, K, B, U, L, M, D, J, F, O, P, Q, X, Y, Z. Faithful Go port.
package brigade

import (
	"regexp"
	"strings"
)

// ─────────────────────────────────────────────────────────────────────────
// C — Compute
// ─────────────────────────────────────────────────────────────────────────

type CStation struct{}

func (s *CStation) Namespace() string { return "C" }

func (s *CStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	if containsString([]string{"kill", "shutdown", "shut", "terminate"}, req.VerbLemma) {
		p := MakeProposal("C", "KILL")
		p.Target = pickTarget(req)
		p.Rationale = "verb '" + req.VerbLemma + "' -> C:KILL"
		out = append(out, p)
	}
	if containsString([]string{"restart", "reboot"}, req.VerbLemma) {
		p := MakeProposal("C", "RSTRT")
		p.Target = pickTarget(req)
		p.Rationale = "verb '" + req.VerbLemma + "' -> C:RSTRT"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// T — Time / Scheduling
// ─────────────────────────────────────────────────────────────────────────

type TStation struct{}

func (s *TStation) Namespace() string { return "T" }

func (s *TStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if req.VerbLemma == "expire" || strings.Contains(rawLow, "expire") || strings.Contains(rawLow, "ttl") {
		var slot []SlotValue
		for _, sv := range req.SlotValues {
			if sv.ValueType == "duration" {
				slot = []SlotValue{{Key: "", Value: sv.Value, ValueType: "duration"}}
				break
			}
		}
		p := MakeProposal("T", "EXP")
		p.SlotValues = slot
		p.Rationale = "expire verb + duration"
		out = append(out, p)
	}
	for _, sv := range req.SlotValues {
		if sv.ValueType == "duration" && strings.Contains(rawLow, "every") {
			p := MakeProposal("T", "SCHED")
			p.SlotValues = []SlotValue{{Key: "", Value: sv.Value, ValueType: "duration"}}
			p.Rationale = "schedule with every-N pattern"
			out = append(out, p)
			break
		}
	}
	if strings.Contains(rawLow, "maintenance window") ||
		(strings.Contains(rawLow, "window") && req.VerbLemma == "schedule") {
		p := MakeProposal("T", "WIN")
		p.Rationale = "maintenance window"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// I — Identity
// ─────────────────────────────────────────────────────────────────────────

type IStation struct{}

func (s *IStation) Namespace() string { return "I" }

func (s *IStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if req.VerbLemma == "authenticate" ||
		strings.Contains(rawLow, "verify identity") || strings.Contains(rawLow, "verify the identity") ||
		strings.Contains(rawLow, "identity check") || strings.Contains(rawLow, "who is") ||
		strings.Contains(rawLow, "check identity") || strings.Contains(rawLow, "confirm identity") ||
		(strings.Contains(rawLow, "identity") && req.VerbLemma == "verify") {
		target := ""
		for _, t := range req.Targets {
			if t.Source == "entity" {
				target = t.ID
				break
			}
		}
		p := MakeProposal("I", "ID")
		p.Target = target
		p.IsQuery = req.IsQuery
		p.Confidence = 2.0
		p.Rationale = "identity verification (overrides S:VFY)"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// S — Crypto
// ─────────────────────────────────────────────────────────────────────────

var sVerbToOpcode = map[string]string{
	"encrypt": "ENC", "decrypt": "DEC", "sign": "SIGN", "hash": "HASH", "verify": "VFY",
}

type SStation struct{}

func (s *SStation) Namespace() string { return "S" }

func (s *SStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if op, ok := sVerbToOpcode[req.VerbLemma]; ok {
		p := MakeProposal("S", op)
		p.Rationale = "verb '" + req.VerbLemma + "' -> S:" + op
		out = append(out, p)
	}
	hasKEYGEN := false
	for _, p := range out {
		if p.Opcode == "KEYGEN" {
			hasKEYGEN = true
			break
		}
	}
	if !hasKEYGEN && (strings.Contains(rawLow, "key pair") || strings.Contains(rawLow, "keypair") ||
		(strings.Contains(rawLow, "key") && strings.Contains(rawLow, "generate"))) {
		p := MakeProposal("S", "KEYGEN")
		p.Rationale = "keypair generation"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "rotate") &&
		(strings.Contains(rawLow, "key") || strings.Contains(rawLow, "credentials")) {
		p := MakeProposal("S", "ROTATE")
		p.Rationale = "key rotation"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// K — Commerce
// ─────────────────────────────────────────────────────────────────────────

type KStation struct{}

func (s *KStation) Namespace() string { return "K" }

func (s *KStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if req.VerbLemma == "pay" || strings.Contains(rawLow, "payment") || strings.Contains(rawLow, "transfer") {
		conf := 1.0
		if strings.Contains(rawLow, "payment") {
			conf = 2.0
		}
		p := MakeProposal("K", "PAY")
		p.Confidence = conf
		p.Rationale = "payment intent"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "order") && strings.Contains(rawLow, "financial") {
		p := MakeProposal("K", "ORD")
		p.Rationale = "financial order"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// B — Building
// ─────────────────────────────────────────────────────────────────────────

var buildingNumRe = regexp.MustCompile(`(?i)\bbuilding\s+(\w+)`)

type BStation struct{}

func (s *BStation) Namespace() string { return "B" }

func (s *BStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if strings.Contains(rawLow, "fire alarm") ||
		(strings.Contains(rawLow, "alarm") && strings.Contains(rawLow, "building")) {
		target := ""
		for _, t := range req.Targets {
			if t.Kind == "building" {
				target = t.ID
				break
			}
		}
		if target == "" {
			if m := buildingNumRe.FindStringSubmatch(req.Raw); m != nil {
				target = strings.ToUpper(m[1])
			}
		}
		p := MakeProposal("B", "ALRM")
		p.Target = target
		p.Rationale = "building fire alarm"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// U — User Interaction
// ─────────────────────────────────────────────────────────────────────────

type UStation struct{}

func (s *UStation) Namespace() string { return "U" }

func (s *UStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	actionVerbs := []string{
		"pay", "process", "transfer", "delete", "send", "execute",
		"shutdown", "kill", "stop", "move", "fire", "deploy", "start",
	}
	hasAction := containsString(actionVerbs, req.VerbLemma)
	if !hasAction {
		for _, v := range actionVerbs {
			if strings.Contains(rawLow, v) {
				hasAction = true
				break
			}
		}
	}
	if (strings.Contains(rawLow, "approve") || strings.Contains(rawLow, "approval")) && hasAction {
		p := MakeProposal("U", "APPROVE")
		p.Confidence = 0.5
		p.Rationale = "approval pattern with action verb"
		out = append(out, p)
	}
	if req.VerbLemma == "notify" || strings.Contains(rawLow, "notify") {
		p := MakeProposal("U", "NOTIFY")
		p.Rationale = "notify verb"
		out = append(out, p)
	}
	if containsString([]string{"alert", "warn"}, req.VerbLemma) {
		hasH := false
		for _, h := range req.NamespaceHints {
			if h == "H" {
				hasH = true
				break
			}
		}
		if !hasH {
			p := MakeProposal("U", "ALERT")
			p.Rationale = "operator alert (non-clinical)"
			out = append(out, p)
		}
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// L — Logging / Compliance
// ─────────────────────────────────────────────────────────────────────────

type LStation struct{}

func (s *LStation) Namespace() string { return "L" }

func (s *LStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	if containsString([]string{"alert", "warn", "trigger"}, req.VerbLemma) {
		p := MakeProposal("L", "ALERT")
		p.Confidence = 0.5
		p.Rationale = "generic alert (compliance default)"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// M — Municipal / Routing
// ─────────────────────────────────────────────────────────────────────────

type MStation struct{}

func (s *MStation) Namespace() string { return "M" }

func (s *MStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if req.VerbLemma == "evacuate" || strings.Contains(rawLow, "evacuation") || strings.Contains(rawLow, "evacuate") {
		target := ""
		if req.IsBroadcast {
			target = "*"
		}
		p := MakeProposal("M", "EVA")
		p.Target = target
		p.Rationale = "evacuate verb"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "route") &&
		(strings.Contains(rawLow, "emergency") || strings.Contains(rawLow, "incident")) {
		p := MakeProposal("M", "RTE")
		p.Rationale = "emergency route"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// D — Data
// ─────────────────────────────────────────────────────────────────────────

type DStation struct{}

func (s *DStation) Namespace() string { return "D" }

func (s *DStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if (req.VerbLemma == "push" || req.VerbLemma == "send") && len(req.Targets) > 0 && OpcodeExists("D", "PUSH") {
		for _, t := range req.Targets {
			if t.Source == "preposition" || t.Source == "entity" {
				p := MakeProposal("D", "PUSH")
				p.Target = t.ID
				p.Rationale = "send to " + t.ID
				out = append(out, p)
				break
			}
		}
	}
	if (req.VerbLemma == "query" || strings.Contains(rawLow, "query")) && OpcodeExists("D", "Q") {
		p := MakeProposal("D", "Q")
		p.Rationale = "data query"
		out = append(out, p)
	}
	if (req.VerbLemma == "delete" || strings.Contains(rawLow, "delete")) && OpcodeExists("D", "DEL") {
		p := MakeProposal("D", "DEL")
		p.ConsequenceClass = "\u2298"
		p.Confidence = 2.0
		p.Rationale = "delete"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// J — Cognitive task
// ─────────────────────────────────────────────────────────────────────────

type JStation struct{}

func (s *JStation) Namespace() string { return "J" }

func (s *JStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if strings.Contains(rawLow, "hand off") || strings.Contains(rawLow, "handoff") ||
		req.VerbLemma == "handoff" || strings.Contains(rawLow, "hand this") {
		target := ""
		for _, t := range req.Targets {
			if t.Source == "entity" || t.Source == "preposition" {
				target = t.ID
				break
			}
		}
		p := MakeProposal("J", "HANDOFF")
		p.Target = target
		p.Rationale = "handoff"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// F — Flow control
// ─────────────────────────────────────────────────────────────────────────

type FStation struct{}

func (s *FStation) Namespace() string { return "F" }

func (s *FStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if strings.Contains(rawLow, "flow authorization") || strings.Contains(rawLow, "authorization to proceed") {
		p := MakeProposal("F", "AV")
		p.Rationale = "flow auth"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "proceed") &&
		containsString([]string{"", "may", "request"}, req.VerbLemma) {
		p := MakeProposal("F", "PRCD")
		p.Rationale = "proceed protocol"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "wait") || strings.Contains(rawLow, "pause") {
		p := MakeProposal("F", "WAIT")
		p.Confidence = 2.5
		p.Rationale = "wait/pause"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// O — Operational context
// ─────────────────────────────────────────────────────────────────────────

var oKeywordMap = map[string]string{
	"bandwidth": "BW", "authority": "LVL", "channel": "CHAN",
	"concept of operations": "CONOPS", "constraint": "CONSTRAINT",
	"deescalation": "DESC", "emcon": "EMCON", "escalation": "ESCL",
	"fallback": "FALLBACK", "floor": "FLOOR",
	"incident action plan": "IAP", "latency": "LATENCY",
	"link quality": "LINK", "mesh": "MESH",
	"operational mode": "MODE", "posture": "POSTURE",
	"signal strength": "LINK", "conspicuity": "CONSPIC",
	"autonomy level": "AUTOLEV",
}

type OStation struct{}

func (s *OStation) Namespace() string { return "O" }

func (s *OStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	for _, phrase := range sortedByLengthDesc(oKeywordMap) {
		if strings.Contains(rawLow, phrase) {
			op := oKeywordMap[phrase]
			p := MakeProposal("O", op)
			p.IsQuery = req.IsQuery
			p.Rationale = "O-context phrase '" + phrase + "'"
			out = append(out, p)
			break
		}
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// P — Procedure / Maintenance
// ─────────────────────────────────────────────────────────────────────────

var pKeywordMap = map[string]string{
	"maintenance code": "CODE", "compliance code": "CODE",
	"device class": "DEVICE", "procedure guide": "GUIDE",
	"part reference": "PART", "completion status": "STAT",
	"step index": "STEP",
}

type PStation struct{}

func (s *PStation) Namespace() string { return "P" }

func (s *PStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	for _, phrase := range sortedByLengthDesc(pKeywordMap) {
		if strings.Contains(rawLow, phrase) {
			op := pKeywordMap[phrase]
			p := MakeProposal("P", op)
			p.Rationale = "procedure phrase '" + phrase + "'"
			out = append(out, p)
			break
		}
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// Q — Quality
// ─────────────────────────────────────────────────────────────────────────

var qKeywordMap = map[string]string{
	"analysis": "ANL", "benchmark": "BENCH", "cite": "CITE", "citation": "CITE",
	"confidence interval": "CONF", "correction": "CORRECT", "critique": "CRIT",
	"evaluate": "EVAL", "evaluation": "EVAL", "feedback": "FB",
	"ground truth": "GT", "report quality": "RPRT",
	"structured report": "RPRT", "review": "REVIEW",
	"verify quality": "VERIFY", "revise": "REVISE",
}

type QStation struct{}

func (s *QStation) Namespace() string { return "Q" }

func (s *QStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	for _, phrase := range sortedByLengthDesc(qKeywordMap) {
		if strings.Contains(rawLow, phrase) {
			op := qKeywordMap[phrase]
			p := MakeProposal("Q", op)
			p.Confidence = 0.6
			p.IsQuery = req.IsQuery
			p.Rationale = "Q phrase '" + phrase + "'"
			out = append(out, p)
			break
		}
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// X — Energy
// ─────────────────────────────────────────────────────────────────────────

var xKeywordMap = map[string]string{
	"demand response": "DR", "ev charging": "CHG", "charging state": "CHG",
	"fault event": "FAULT", "grid frequency": "FREQ",
	"grid connection": "GRD", "islanding": "ISLND",
	"battery level": "STORE", "battery status": "STORE",
	"battery report": "STORE", "voltage": "VOLT",
	"wind generation": "WND", "wind farm": "WND",
	"production": "PROD", "frequency": "FREQ",
}

var xHighConf = map[string]bool{
	"wind farm": true, "wind generation": true,
}

type XStation struct{}

func (s *XStation) Namespace() string { return "X" }

func (s *XStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	rawDearticled := dearticled(rawLow)
	for _, phrase := range sortedByLengthDesc(xKeywordMap) {
		if strings.Contains(rawLow, phrase) || strings.Contains(rawDearticled, phrase) {
			op := xKeywordMap[phrase]
			conf := 1.0
			if xHighConf[phrase] {
				conf = 2.5
			}
			p := MakeProposal("X", op)
			p.Confidence = conf
			isQ := req.IsQuery || containsString([]string{"", "report", "show", "check"}, req.VerbLemma)
			p.IsQuery = isQ
			p.Rationale = "X energy phrase '" + phrase + "'"
			out = append(out, p)
			break
		}
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// Y — Memory
// ─────────────────────────────────────────────────────────────────────────

var yVerbToOpcode = map[string]string{
	"store": "STORE", "save": "STORE", "remember": "STORE",
	"fetch": "FETCH", "recall": "FETCH", "forget": "FORGET",
	"index": "INDEX", "commit": "COMMIT", "embed": "EMBED", "clear": "CLEAR",
}

var yKeywordMap = map[string]string{
	"page out memory": "PAGEOUT", "store to memory": "STORE",
	"save to memory": "STORE", "embedding": "EMBED",
	"memory tier": "CLEAR",
}

type YStation struct{}

func (s *YStation) Namespace() string { return "Y" }

func (s *YStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	tokens := map[string]bool{}
	for _, t := range strings.Fields(rawLow) {
		tokens[t] = true
	}
	if strings.Contains(rawLow, "memory") || tokens["store"] || tokens["fetch"] ||
		req.VerbLemma == "forget" || req.VerbLemma == "store" {
		if op, ok := yVerbToOpcode[req.VerbLemma]; ok {
			p := MakeProposal("Y", op)
			p.Confidence = 1.5
			p.Rationale = "memory verb '" + req.VerbLemma + "'"
			out = append(out, p)
		}
	}
	for _, phrase := range sortedByLengthDesc(yKeywordMap) {
		if strings.Contains(rawLow, phrase) {
			op := yKeywordMap[phrase]
			p := MakeProposal("Y", op)
			p.Confidence = 0.7
			p.Rationale = "Y phrase '" + phrase + "'"
			out = append(out, p)
			break
		}
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// Z — Inference
// ─────────────────────────────────────────────────────────────────────────

var zKeywordMap = map[string]string{
	"batch inference": "BATCH", "kv cache": "CACHE",
	"capability query": "CAPS", "agent confidence": "CONF",
	"inference cost": "COST", "context window": "CTX",
	"context utilization": "CTX", "run inference": "INF",
	"invoke model": "INF", "tokens": "TOKENS",
	"token count": "TOKENS", "sampling temperature": "TEMP",
	"top-p": "TOPP", "top p": "TOPP", "max tokens": "MAX",
	"model response": "RESP",
}

type ZStation struct{}

func (s *ZStation) Namespace() string { return "Z" }

func (s *ZStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	for _, sv := range req.SlotValues {
		if sv.Key == "temperature" && containsString([]string{"", "set", "configure"}, req.VerbLemma) {
			p := MakeProposal("Z", "TEMP")
			p.SlotValues = []SlotValue{{Key: "", Value: sv.Value, ValueType: "float"}}
			p.Confidence = 0.6
			p.Rationale = "Z:TEMP for inference sampling temp"
			out = append(out, p)
		}
	}
	for _, phrase := range sortedByLengthDesc(zKeywordMap) {
		if strings.Contains(rawLow, phrase) {
			op := zKeywordMap[phrase]
			p := MakeProposal("Z", op)
			p.Confidence = 0.7
			p.IsQuery = req.IsQuery
			p.Rationale = "Z phrase '" + phrase + "'"
			out = append(out, p)
			break
		}
	}
	return out
}
