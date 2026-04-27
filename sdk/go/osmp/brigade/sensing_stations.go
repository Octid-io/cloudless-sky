// Sensing-namespace stations: R, E, H, G, V, W, N, A. Faithful Go port.
package brigade

import (
	"regexp"
	"strings"
)

// ─────────────────────────────────────────────────────────────────────────
// R-station — Robotic / Physical Agent
// ─────────────────────────────────────────────────────────────────────────

var rVerbToOpcode = map[string]string{
	"stop": "STOP", "halt": "STOP", "cease": "STOP", "block": "STOP",
	"close": "STOP", "lock": "STOP",
	"move": "MOV", "go": "MOV", "navigate": "MOV", "fly": "MOV",
	"return": "RTH", "rtb": "RTH", "rth": "RTH",
}

var rPeripheralObjectToOpcode = map[string]string{
	"camera": "CAM", "microphone": "MIC", "speaker": "SPKR",
	"flashlight": "TORCH", "torch": "TORCH",
	"haptic": "HAPTIC", "vibration": "VIBE",
	"wifi": "WIFI", "bluetooth": "BT", "gps": "GPS",
	"screen": "DISP", "display": "DISP", "accelerometer": "ACCEL",
}

var rPeripheralVerbs = map[string]bool{
	"turn": true, "activate": true, "enable": true, "engage": true, "start": true,
}

func rPickTarget(req ParsedRequest) string {
	return pickTarget(req)
}

func rSlotsForOpcode(opcode string, req ParsedRequest) []SlotValue {
	if opcode == "MOV" {
		for _, sv := range req.SlotValues {
			if sv.ValueType == "latlon" {
				return []SlotValue{{Key: "", Value: sv.Value, ValueType: "latlon"}}
			}
		}
		for _, sv := range req.SlotValues {
			if sv.Key == "formation" || sv.Key == "spacing" {
				return []SlotValue{sv}
			}
		}
	}
	return nil
}

type RStation struct{}

func (s *RStation) Namespace() string { return "R" }

func (s *RStation) Propose(req ParsedRequest) []FrameProposal {
	var props []FrameProposal
	rawLow := strings.ToLower(req.Raw)

	emergencyVerbs := map[string]bool{
		"": true, "stop": true, "halt": true, "cease": true, "block": true,
		"kill": true, "shutdown": true, "shut": true,
	}
	if req.IsEmergency && emergencyVerbs[req.VerbLemma] {
		p := MakeProposal("R", "ESTOP")
		p.Rationale = "emergency marker + stop verb (or no verb)"
		props = append(props, p)
		return props
	}

	if op, ok := rVerbToOpcode[req.VerbLemma]; ok {
		p := MakeProposal("R", op)
		p.Target = rPickTarget(req)
		p.SlotValues = rSlotsForOpcode(op, req)
		p.ConsequenceClass = "\u21ba"
		p.Rationale = "verb '" + req.VerbLemma + "' -> R:" + op
		props = append(props, p)
	}

	if rPeripheralVerbs[req.VerbLemma] && req.DirectObject != "" {
		parts := strings.Fields(strings.ToLower(req.DirectObject))
		objWord := parts[len(parts)-1]
		if op, ok := rPeripheralObjectToOpcode[objWord]; ok {
			p := MakeProposal("R", op)
			p.Target = rPickTarget(req)
			p.ConsequenceClass = "\u21ba"
			p.Rationale = "peripheral activation '" + objWord + "' -> R:" + op
			props = append(props, p)
		}
	}

	if req.VerbLemma == "" && req.DirectObjectKind == "peripheral" && req.DirectObject != "" {
		parts := strings.Fields(strings.ToLower(req.DirectObject))
		objWord := parts[len(parts)-1]
		if op, ok := rPeripheralObjectToOpcode[objWord]; ok {
			p := MakeProposal("R", op)
			p.ConsequenceClass = "\u21ba"
			p.Rationale = "nominal peripheral '" + objWord + "' -> R:" + op
			props = append(props, p)
		}
	}

	if strings.Contains(rawLow, "haptic feedback") || (strings.Contains(rawLow, "vibrate") && len(props) == 0) {
		p := MakeProposal("R", "HAPTIC")
		p.ConsequenceClass = "\u21ba"
		p.Rationale = "haptic feedback phrase"
		props = append(props, p)
	}

	hasRTH := false
	for _, p := range props {
		if p.Opcode == "RTH" {
			hasRTH = true
			break
		}
	}
	if !hasRTH && (strings.Contains(rawLow, "rtb") || strings.Contains(rawLow, "rth") ||
		strings.Contains(rawLow, "return to base") || strings.Contains(rawLow, "return home")) {
		p := MakeProposal("R", "RTH")
		p.ConsequenceClass = "\u21ba"
		p.Confidence = 2.0
		p.Rationale = "rtb/rth/return phrase"
		props = append(props, p)
	}

	shapes := []string{"wedge", "column", "line", "vee", "diamond", "echelon"}
	hasShape := false
	for _, sh := range shapes {
		if strings.Contains(rawLow, sh) {
			hasShape = true
			break
		}
	}
	if req.VerbLemma == "form" && (strings.Contains(rawLow, "swarm") ||
		strings.Contains(rawLow, "formation") || hasShape) {
		var slots []SlotValue
		for _, shape := range shapes {
			if strings.Contains(rawLow, shape) {
				slots = append(slots, SlotValue{Key: "", Value: shape, ValueType: "string"})
				break
			}
		}
		for _, sv := range req.SlotValues {
			if sv.Key == "spacing" {
				slots = append(slots, SlotValue{Key: "", Value: sv.Value, ValueType: "float"})
				break
			}
		}
		p := MakeProposal("R", "FORM")
		p.ConsequenceClass = "\u21ba"
		p.SlotValues = slots
		p.Rationale = "swarm formation"
		props = append(props, p)
	}

	return props
}

// ─────────────────────────────────────────────────────────────────────────
// E-station — Environmental sensor
// ─────────────────────────────────────────────────────────────────────────

var eSensorToOpcode = map[string]string{
	"temperature": "TH", "temp": "TH", "humidity": "HU", "pressure": "PU",
	"pump": "PU", "barometric": "PU", "gps": "GPS", "coordinates": "GPS",
	"air": "EQ", "vibration": "VIB", "moisture": "TH", "soil": "TH",
}

var ePhraseToOpcode = map[string]string{
	"air quality": "EQ", "soil moisture": "TH", "temperature humidity": "EQ",
}

var ePunctStripRe = regexp.MustCompile(`[,.!?;:'"]`)
var pumpToNRe = regexp.MustCompile(`to\s+(\d+\.?\d*)\s*(?:millibar|mbar|psi|kpa)?`)

type EStation struct{}

func (s *EStation) Namespace() string { return "E" }

func (s *EStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)

	if req.VerbLemma == "read" && req.DirectObjectKind == "sensor" {
		hasGuard := false
		for _, w := range []string{"temperature", "humidity", "pressure", "wind"} {
			if strings.Contains(rawLow, w) {
				hasGuard = true
				break
			}
		}
		if !hasGuard {
			p := MakeProposal("E", "TH")
			p.Target = pickTargetSensing(req)
			p.IsQuery = true
			p.Rationale = "generic sensor read defaults to E:TH"
			out = append(out, p)
		}
	}

	for _, phrase := range sortedByLengthDesc(ePhraseToOpcode) {
		if strings.Contains(rawLow, phrase) {
			op := ePhraseToOpcode[phrase]
			p := MakeProposal("E", op)
			p.Target = pickTargetSensing(req)
			isQ := req.IsQuery || containsString([]string{"report", "show", "get", "read"}, req.VerbLemma)
			p.IsQuery = isQ
			p.Rationale = "phrase '" + phrase + "' -> E:" + op
			out = append(out, p)
		}
	}

	type cand struct{ word, op string }
	var cands []cand
	if req.DirectObject != "" {
		for _, w := range strings.Fields(strings.ToLower(req.DirectObject)) {
			if op, ok := eSensorToOpcode[w]; ok {
				cands = append(cands, cand{w, op})
			}
		}
	}
	if len(cands) == 0 {
		for _, tok := range strings.Fields(rawLow) {
			c := ePunctStripRe.ReplaceAllString(tok, "")
			if op, ok := eSensorToOpcode[c]; ok {
				cands = append(cands, cand{c, op})
			}
		}
	}

	for _, c := range cands {
		dup := false
		for _, p := range out {
			if p.Opcode == c.op {
				dup = true
				break
			}
		}
		if dup {
			continue
		}
		var slots []SlotValue
		if c.op == "PU" {
			for _, sv := range req.SlotValues {
				if sv.ValueType == "float" && (sv.Key == "pressure" || sv.Key == "pump") {
					slots = []SlotValue{{Key: "", Value: sv.Value, ValueType: "float"}}
					break
				}
			}
			if len(slots) == 0 {
				if m := pumpToNRe.FindStringSubmatch(rawLow); m != nil {
					slots = []SlotValue{{Key: "", Value: m[1], ValueType: "float"}}
				}
			}
		}
		p := MakeProposal("E", c.op)
		p.Target = pickTargetSensing(req)
		p.SlotValues = slots
		isQ := req.IsQuery
		if !isQ && len(slots) == 0 {
			for _, w := range []string{"", "report", "show", "get", "read", "what"} {
				if req.VerbLemma == w {
					isQ = true
					break
				}
			}
		}
		p.IsQuery = isQ
		p.Rationale = "sensor '" + c.word + "' -> E:" + c.op
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// H-station — Health / Clinical
// ─────────────────────────────────────────────────────────────────────────

var hPhraseToOpcode = map[string]string{
	"blood pressure": "BP", "heart rate": "HR",
	"oxygen level": "SPO2", "oxygen saturation": "SPO2",
	"oxygen sat": "SPO2", "oxygen drops": "SPO2", "spo2": "SPO2",
	"all vitals": "VITALS", "vital signs": "VITALS", "vitals check": "VITALS",
	"body temperature": "TEMP", "body temp": "TEMP",
	"patient pulse": "HR", "patient temperature": "TEMP",
	"respiratory rate": "RR",
}

var hHighConfPhrases = map[string]bool{
	"body temperature": true, "body temp": true,
	"patient temperature": true, "oxygen drops": true,
}

var hSingleWord = map[string]string{
	"vitals": "VITALS", "pulse": "HR", "bp": "BP", "hr": "HR",
}

type HStation struct{}

func (s *HStation) Namespace() string { return "H" }

func (s *HStation) Propose(req ParsedRequest) []FrameProposal {
	var props []FrameProposal
	rawLow := strings.ToLower(req.Raw)

	rawDearticled := dearticled(rawLow)

	for _, sv := range req.SlotValues {
		if sv.ValueType == "code" && sv.Key == "icd" {
			p := MakeProposal("H", "ICD")
			p.SlotValues = []SlotValue{{Key: "", Value: sv.Value, ValueType: "code"}}
			p.Target = pickTargetSensing(req)
			p.Rationale = "ICD code " + sv.Value
			props = append(props, p)
		}
	}

	for _, phrase := range sortedByLengthDesc(hPhraseToOpcode) {
		if strings.Contains(rawLow, phrase) || strings.Contains(rawDearticled, phrase) {
			op := hPhraseToOpcode[phrase]
			conf := 1.0
			if hHighConfPhrases[phrase] {
				conf = 2.5
			}
			p := MakeProposal("H", op)
			p.Target = pickTargetSensing(req)
			p.Confidence = conf
			isQ := req.IsQuery || containsString([]string{"", "report", "show", "give", "check", "what"}, req.VerbLemma)
			p.IsQuery = isQ
			p.Rationale = "phrase '" + phrase + "' -> H:" + op
			props = append(props, p)
			break
		}
	}

	hasMain := false
	mainOps := map[string]bool{"BP": true, "HR": true, "VITALS": true, "SPO2": true, "TEMP": true, "RR": true}
	for _, p := range props {
		if mainOps[p.Opcode] {
			hasMain = true
			break
		}
	}
	if !hasMain {
		for _, w := range strings.Fields(rawLow) {
			c := ePunctStripRe.ReplaceAllString(w, "")
			if op, ok := hSingleWord[c]; ok {
				p := MakeProposal("H", op)
				p.Target = pickTargetSensing(req)
				p.IsQuery = req.IsQuery
				p.Rationale = "single-word '" + c + "' -> H:" + op
				props = append(props, p)
				break
			}
		}
	}

	if strings.Contains(rawLow, "casualty") || strings.Contains(rawLow, "casrep") {
		p := MakeProposal("H", "CASREP")
		p.Target = pickTargetSensing(req)
		p.Rationale = "casualty report"
		props = append(props, p)
	}

	if containsString([]string{"alert", "warn", "notify"}, req.VerbLemma) || strings.Contains(rawLow, "alert") {
		hasSensing := false
		for _, p := range props {
			if p.Namespace == "H" && containsString([]string{"BP", "HR", "SPO2", "TEMP", "VITALS"}, p.Opcode) {
				hasSensing = true
				break
			}
		}
		if hasSensing {
			p := MakeProposal("H", "ALERT")
			p.Rationale = "clinical alert (H sensing context)"
			props = append(props, p)
		}
	}

	return props
}

func dearticled(text string) string {
	parts := strings.Fields(text)
	out := []string{}
	for _, w := range parts {
		if w == "the" || w == "a" || w == "an" {
			continue
		}
		out = append(out, w)
	}
	return strings.Join(out, " ")
}

// ─────────────────────────────────────────────────────────────────────────
// G-station — Geospatial
// ─────────────────────────────────────────────────────────────────────────

var gPositionWords = map[string]bool{
	"position": true, "location": true, "place": true, "where": true,
	"spot": true, "altitude": true, "elevation": true, "latlon": true,
	"lat": true, "lng": true, "long": true, "coords": true,
}

var gHeadingWords = map[string]bool{
	"heading": true, "bearing": true, "direction": true, "course": true,
	"azimuth": true, "compass": true,
}

var gPunctNormRe = regexp.MustCompile(`[,.]`)

type GStation struct{}

func (s *GStation) Namespace() string { return "G" }

func (s *GStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	cleaned := gPunctNormRe.ReplaceAllString(rawLow, " ")
	tokens := map[string]bool{}
	for _, t := range strings.Fields(cleaned) {
		tokens[t] = true
	}

	hasPos := false
	for w := range gPositionWords {
		if tokens[w] {
			hasPos = true
			break
		}
	}
	if hasPos {
		target := pickTargetSensing(req)
		if req.IsBroadcast && target == "" {
			target = "*"
		}
		p := MakeProposal("G", "POS")
		p.Target = target
		p.IsQuery = req.IsQuery
		p.Rationale = "position keyword"
		out = append(out, p)
	}
	hasHdg := false
	for w := range gHeadingWords {
		if tokens[w] {
			hasHdg = true
			break
		}
	}
	if hasHdg {
		p := MakeProposal("G", "BEARING")
		p.Target = pickTargetSensing(req)
		p.IsQuery = req.IsQuery
		p.Rationale = "heading keyword"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// V-station — Vehicle / Transport Fleet
// ─────────────────────────────────────────────────────────────────────────

var vVehicleContext = map[string]bool{
	"vehicle": true, "vessel": true, "ship": true, "boat": true, "fleet": true,
	"ais": true, "drone": true, "uav": true,
}

type VStation struct{}

func (s *VStation) Namespace() string { return "V" }

func (s *VStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)

	inCtx := false
	for w := range vVehicleContext {
		if strings.Contains(rawLow, w) {
			inCtx = true
			break
		}
	}
	if !inCtx {
		return out
	}

	if strings.Contains(rawLow, "heading") || strings.Contains(rawLow, "bearing") || strings.Contains(rawLow, "course") {
		p := MakeProposal("V", "HDG")
		p.Target = pickTargetSensing(req)
		p.IsQuery = req.IsQuery
		p.Rationale = "vehicle heading context"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "position") || strings.Contains(rawLow, "location") || strings.Contains(rawLow, "where") {
		p := MakeProposal("V", "POS")
		p.Target = pickTargetSensing(req)
		p.IsQuery = req.IsQuery
		p.Rationale = "vehicle position context"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "fleet") && (strings.Contains(rawLow, "status") || req.IsQuery) {
		p := MakeProposal("V", "FLEET")
		p.IsQuery = true
		p.Rationale = "fleet status"
		out = append(out, p)
	}
	tokens := strings.Fields(rawLow)
	hasAIS := false
	for _, t := range tokens {
		if t == "ais" {
			hasAIS = true
			break
		}
	}
	if !hasAIS && strings.Contains(" "+rawLow+" ", " ais ") {
		hasAIS = true
	}
	if hasAIS {
		p := MakeProposal("V", "AIS")
		p.Target = pickTargetSensing(req)
		p.Confidence = 2.5
		p.Rationale = "AIS keyword (overrides V:POS)"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// W-station — Weather
// ─────────────────────────────────────────────────────────────────────────

type WStation struct{}

func (s *WStation) Namespace() string { return "W" }

func (s *WStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	cleaned := gPunctNormRe.ReplaceAllString(rawLow, " ")
	tokens := map[string]bool{}
	for _, t := range strings.Fields(cleaned) {
		tokens[t] = true
	}
	if strings.Contains(rawLow, "wind farm") || strings.Contains(rawLow, "wind generation") {
		return out
	}
	if strings.Contains(rawLow, "wind down") || strings.Contains(rawLow, "wind up") {
		return out
	}
	if tokens["wind"] {
		isQ := req.IsQuery || containsString([]string{"", "report", "show", "get"}, req.VerbLemma)
		p := MakeProposal("W", "WIND")
		p.Target = pickTargetSensing(req)
		p.IsQuery = isQ
		p.Rationale = "wind keyword"
		out = append(out, p)
	}
	if strings.Contains(rawLow, "weather alert") ||
		(req.VerbLemma == "alert" && strings.Contains(rawLow, "wind")) {
		p := MakeProposal("W", "ALERT")
		p.Rationale = "weather alert"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// N-station — Network / Routing
// ─────────────────────────────────────────────────────────────────────────

type NStation struct{}

func (s *NStation) Namespace() string { return "N" }

func (s *NStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)

	cfgVerbs := []string{"set", "configure", "update", "modify", "change", "adjust"}
	if containsString(cfgVerbs, req.VerbLemma) ||
		strings.Contains(rawLow, "config") || strings.Contains(rawLow, "configuration") || strings.Contains(rawLow, "settings") {
		var slots []SlotValue
		for _, sv := range req.SlotValues {
			if sv.ValueType == "float" && sv.Key != "at_time" {
				slots = []SlotValue{sv}
				break
			}
		}
		p := MakeProposal("N", "CFG")
		p.SlotValues = slots
		p.Target = pickTargetSensing(req)
		p.Rationale = "config verb or config keyword"
		out = append(out, p)
	}

	if req.VerbLemma == "back" || req.VerbLemma == "backup" || strings.Contains(rawLow, "back up") {
		target := ""
		for _, sv := range req.SlotValues {
			if sv.ValueType == "time" {
				target = sv.Value
				break
			}
		}
		p := MakeProposal("N", "BK")
		p.Target = target
		p.Rationale = "backup verb"
		out = append(out, p)
	}

	if strings.Contains(rawLow, "status") || strings.Contains(rawLow, "uptime") ||
		strings.Contains(rawLow, "alive") || strings.Contains(rawLow, "online") {
		p := MakeProposal("N", "STS")
		p.Target = pickTargetSensing(req)
		p.IsQuery = true
		p.Rationale = "status keyword"
		out = append(out, p)
	}

	if req.VerbLemma == "discover" || strings.Contains(rawLow, "discover") {
		target := ""
		if req.IsBroadcast || strings.Contains(rawLow, "peers") || strings.Contains(rawLow, "all") {
			target = "*"
		}
		p := MakeProposal("N", "Q")
		p.Target = target
		p.Rationale = "discover verb"
		out = append(out, p)
	}

	if strings.Contains(rawLow, "relay") &&
		containsString([]string{"", "find", "what", "where", "show", "report", "get"}, req.VerbLemma) {
		p := MakeProposal("N", "RLY")
		p.IsQuery = true
		p.Rationale = "relay query"
		out = append(out, p)
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// A-station — Agentic / OSMP-Native
// ─────────────────────────────────────────────────────────────────────────

type AStation struct{}

func (s *AStation) Namespace() string { return "A" }

func (s *AStation) Propose(req ParsedRequest) []FrameProposal {
	var out []FrameProposal
	rawLow := strings.ToLower(req.Raw)
	if req.VerbLemma == "ping" {
		p := MakeProposal("A", "PING")
		p.Target = pickTargetSensing(req)
		p.Rationale = "ping verb"
		out = append(out, p)
	}
	if req.VerbLemma == "summarize" || strings.Contains(rawLow, "summarize") {
		p := MakeProposal("A", "SUM")
		p.Rationale = "summarize verb"
		out = append(out, p)
	}
	return out
}
