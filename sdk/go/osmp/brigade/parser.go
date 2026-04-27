// Garde manger — the grammar parser. Mise en place for the brigade.
//
// Faithful Go port of sdk/python/osmp/brigade/parser.py and the TS port at
// sdk/typescript/src/brigade/parser.ts. Reads NL once, produces a
// ParsedRequest IR. Every other station starts here.
package brigade

import (
	"regexp"
	"strings"
)

// ─────────────────────────────────────────────────────────────────────────
// MODIFIER MARKERS, NEGATION, INJECTION, BRIDGE POLICY
// ─────────────────────────────────────────────────────────────────────────

var ModifierMarkersPattern = regexp.MustCompile(`(?i)\b(unless|only if|except|but not|without|after|before|while|if not)\b`)

var BridgeAllowedNamespaces = map[string]bool{
	"E": true, "G": true, "W": true, "N": true, "O": true, "Q": true,
	"X": true, "A": true, "H": true, "V": true, "I": true,
}

// Frames that are NEVER safe to bridge — action-bearing within
// otherwise-sensing namespaces.
var BridgeForbiddenFrames = map[string]bool{
	"H:ALERT": true, "H:CASREP": true, "W:ALERT": true, "N:CFG": true, "N:BK": true,
	"V:FLEET": true, "I:§": true, "A:PROPOSE": true, "A:BROADCAST": true,
}

var negationMarkers = []*regexp.Regexp{
	regexp.MustCompile(`(?i)\bdon'?t\b`),
	regexp.MustCompile(`(?i)\bdo not\b`),
	regexp.MustCompile(`(?i)\bdoes not\b`),
	regexp.MustCompile(`(?i)\bdoesn'?t\b`),
	regexp.MustCompile(`(?i)\bnever\b`),
	regexp.MustCompile(`(?i)\bno longer\b`),
	regexp.MustCompile(`(?i)\bnot\b`),
	regexp.MustCompile(`(?i)\bcancel\b`),
	regexp.MustCompile(`(?i)\babort\b`),
	regexp.MustCompile(`(?i)\bstop doing\b`),
}

var injectionMarkers = []*regexp.Regexp{
	regexp.MustCompile(`(?i);\s*(?:DROP|DELETE|INSERT|UPDATE|SELECT|TRUNCATE|ALTER)\s+`),
	regexp.MustCompile(`&&`),
	regexp.MustCompile(`\|\|`),
	regexp.MustCompile(`\$\(`),
	regexp.MustCompile("`[^`]*`"),
	regexp.MustCompile(`(?i)<script`),
	regexp.MustCompile(`(?i)</script`),
	regexp.MustCompile(`(?i)javascript:`),
	regexp.MustCompile(`(?i)system\s*\(`),
	regexp.MustCompile(`(?i)exec\s*\(`),
	regexp.MustCompile(`(?i)eval\s*\(`),
	regexp.MustCompile(`(?i)rm\s+-rf`),
	regexp.MustCompile(`(?i)chmod\s+777`),
	regexp.MustCompile(`--\s*$`),
	regexp.MustCompile(`(?i)/etc/(?:passwd|shadow)`),
	regexp.MustCompile(`(?i)\bUNION\s+SELECT\b`),
	regexp.MustCompile(`\.\./`),
}

var emailPattern = regexp.MustCompile(`\b[\w.+\-]+@[\w\-]+\.\w+\b`)

var idiomParticleAfterVerb = map[string]bool{
	"wind|down": true, "wind|up": true,
	"stop|bothering": true, "stop|by": true, "stop|doing": true,
	"ping|me":    true,
	"lock|in":    true, "lock|down": true,
	"close|out":  true,
	"send|off":   true,
	"verify|that": true,
	"check|out":  true, "check|in": true,
	"report|back": true, "report|in": true,
	"encrypt|your": true,
}

var ActuatorObjectNouns = map[string]bool{
	"conveyor": true, "pump": true, "valve": true, "door": true, "light": true,
	"lights": true, "lamp": true, "fan": true, "motor": true, "engine": true,
	"service": true, "process": true, "system": true, "device": true, "node": true,
	"gateway": true, "server": true, "drone": true, "vehicle": true, "vessel": true,
	"robot": true, "sensor": true, "alarm": true, "siren": true, "sprinkler": true,
	"camera": true, "microphone": true, "speaker": true, "flashlight": true, "torch": true,
	"screen": true, "display": true, "wifi": true, "bluetooth": true, "gps": true,
	"haptic": true, "actuator": true, "relay": true, "switch": true, "circuit": true,
	"breaker": true, "hatch": true, "window": true, "shutter": true, "blind": true,
	"tank": true, "reactor": true, "antenna": true, "transmitter": true, "receiver": true,
	"feed": true, "stream": true, "channel": true, "config": true, "configuration": true,
	"settings": true, "threshold": true, "parameter": true, "database": true, "cache": true,
	"queue": true, "log": true, "logs": true,
}

var emergencyMarkers = []string{
	"emergency", "immediately", "right now", "asap", "urgent", "critical",
	"panic", "sos", "mayday",
}

var broadcastMarkers = []string{
	"everyone", "all nodes", "broadcast", "all peers", "every node",
}

var queryMarkers = []string{
	"?", "what", "where", "when", "who", "how many", "how much",
	"tell me", "show me",
}

var authMarkers = []*regexp.Regexp{
	regexp.MustCompile(`(?i)\bonly if\b.*\b(approves?|signs?|authorize[ds]?|confirm[s]?|allows?)\b`),
	regexp.MustCompile(`(?i)\brequire[ds]?\s+(approval|sign-?off|authorization|confirmation)\b`),
	regexp.MustCompile(`(?i)\bif\s+\w+\s+(approves?|signs?|authorizes?)\b`),
	regexp.MustCompile(`(?i)\bafter\s+\w+\s+approves?\b`),
	regexp.MustCompile(`(?i)\bwith\s+approval\b`),
	regexp.MustCompile(`(?i)\bsubject to (approval|authorization)\b`),
}

// ─────────────────────────────────────────────────────────────────────────
// VERB LEXICON
// ─────────────────────────────────────────────────────────────────────────

type VerbInfo struct {
	Lemma         string
	NsHints       []string
	IsWrapper     bool
	IsQuery       bool
	PrimaryOpcode string
	TakesSlot     bool
}

var VerbLexicon = map[string]VerbInfo{
	// Sensing / read
	"report":    {Lemma: "report", NsHints: []string{"L", "Q"}, IsWrapper: true},
	"send":      {Lemma: "send", NsHints: []string{"D", "L"}, IsWrapper: true},
	"show":      {Lemma: "show", NsHints: []string{"A"}, IsWrapper: true},
	"log":       {Lemma: "log", NsHints: []string{"L"}, IsWrapper: true},
	"broadcast": {Lemma: "broadcast", NsHints: []string{"L", "A"}, IsWrapper: true},
	"fetch":     {Lemma: "fetch", NsHints: []string{"D"}, IsWrapper: true},
	"retrieve":  {Lemma: "retrieve", NsHints: []string{"D"}, IsWrapper: true},
	"read":      {Lemma: "read", NsHints: []string{"E", "D"}, IsWrapper: true},
	"get":       {Lemma: "get", NsHints: []string{"D", "E"}, IsWrapper: true},
	"give":      {Lemma: "give", NsHints: []string{"D"}, IsWrapper: true},
	"what":      {Lemma: "what", NsHints: []string{}, IsWrapper: true, IsQuery: true},
	"where":     {Lemma: "where", NsHints: []string{"G"}, IsWrapper: true, IsQuery: true},

	// Actuation
	"stop":     {Lemma: "stop", NsHints: []string{"R", "C"}, PrimaryOpcode: "STOP"},
	"halt":     {Lemma: "halt", NsHints: []string{"R", "C"}, PrimaryOpcode: "STOP"},
	"start":    {Lemma: "start", NsHints: []string{"R", "C"}, PrimaryOpcode: "START"},
	"open":     {Lemma: "open", NsHints: []string{"R"}, PrimaryOpcode: "OPEN"},
	"close":    {Lemma: "close", NsHints: []string{"R"}, PrimaryOpcode: "STOP"},
	"lock":     {Lemma: "lock", NsHints: []string{"R"}, PrimaryOpcode: "STOP"},
	"unlock":   {Lemma: "unlock", NsHints: []string{"R"}, PrimaryOpcode: "OPEN"},
	"move":     {Lemma: "move", NsHints: []string{"R", "V"}, PrimaryOpcode: "MOV"},
	"return":   {Lemma: "return", NsHints: []string{"R"}, PrimaryOpcode: "RTH"},
	"shutdown": {Lemma: "shutdown", NsHints: []string{"C", "R"}, PrimaryOpcode: "KILL"},
	"shut":     {Lemma: "shut", NsHints: []string{"C", "R"}, PrimaryOpcode: "KILL"},
	"kill":     {Lemma: "kill", NsHints: []string{"C"}, PrimaryOpcode: "KILL"},
	"reboot":   {Lemma: "reboot", NsHints: []string{"C"}, PrimaryOpcode: "RSTRT"},
	"restart":  {Lemma: "restart", NsHints: []string{"C"}, PrimaryOpcode: "RSTRT"},
	"evacuate": {Lemma: "evacuate", NsHints: []string{"M"}, PrimaryOpcode: "EVA"},
	"form":     {Lemma: "form", NsHints: []string{"R"}, PrimaryOpcode: "FORM"},
	"find":     {Lemma: "find", NsHints: []string{"N", "D"}, IsWrapper: true},
	"rotate":   {Lemma: "rotate", NsHints: []string{"S", "R"}, PrimaryOpcode: "ROTATE"},
	"ack":      {Lemma: "ack", NsHints: []string{"U"}, PrimaryOpcode: "ACK"},
	"store":    {Lemma: "store", NsHints: []string{"Y"}, PrimaryOpcode: "STORE"},
	"forget":   {Lemma: "forget", NsHints: []string{"Y"}, PrimaryOpcode: "FORGET"},
	"wait":     {Lemma: "wait", NsHints: []string{"F"}, PrimaryOpcode: "WAIT"},
	"rebroadcast": {Lemma: "rebroadcast", NsHints: []string{"L"}, PrimaryOpcode: "SEND"},
	"engage":   {Lemma: "engage", NsHints: []string{"R"}, IsWrapper: true},
	"swarm":    {Lemma: "swarm", NsHints: []string{"R", "V"}, IsWrapper: true},
	"rtb":      {Lemma: "rtb", NsHints: []string{"R"}, PrimaryOpcode: "RTH"},
	"navigate": {Lemma: "navigate", NsHints: []string{"R"}, PrimaryOpcode: "MOV"},
	"fly":      {Lemma: "fly", NsHints: []string{"R", "V"}, PrimaryOpcode: "MOV"},
	"drive":    {Lemma: "drive", NsHints: []string{"R", "V"}, PrimaryOpcode: "DRVE"},
	"go":       {Lemma: "go", NsHints: []string{"R"}, PrimaryOpcode: "MOV"},
	"proceed":  {Lemma: "proceed", NsHints: []string{"F"}, PrimaryOpcode: "PRCD"},
	"cease":    {Lemma: "cease", NsHints: []string{"R", "C"}, PrimaryOpcode: "STOP"},
	"block":    {Lemma: "block", NsHints: []string{"R"}, PrimaryOpcode: "STOP"},
	"turn":     {Lemma: "turn", NsHints: []string{"R"}, IsWrapper: true},
	"activate": {Lemma: "activate", NsHints: []string{"R"}, IsWrapper: true},
	"enable":   {Lemma: "enable", NsHints: []string{"R"}, IsWrapper: true},
	"disable":  {Lemma: "disable", NsHints: []string{"R"}, IsWrapper: true},

	// Crypto / auth
	"encrypt":      {Lemma: "encrypt", NsHints: []string{"S"}, PrimaryOpcode: "ENC"},
	"decrypt":      {Lemma: "decrypt", NsHints: []string{"S"}, PrimaryOpcode: "DEC"},
	"sign":         {Lemma: "sign", NsHints: []string{"S"}, PrimaryOpcode: "SIGN"},
	"hash":         {Lemma: "hash", NsHints: []string{"S"}, PrimaryOpcode: "HASH"},
	"verify":       {Lemma: "verify", NsHints: []string{"S", "I", "A"}, PrimaryOpcode: "VFY"},
	"authenticate": {Lemma: "authenticate", NsHints: []string{"I"}, PrimaryOpcode: "ID"},

	// Auxiliary creator
	"generate": {Lemma: "generate", NsHints: []string{}, IsWrapper: true},
	"create":   {Lemma: "create", NsHints: []string{}, IsWrapper: true},
	"make":     {Lemma: "make", NsHints: []string{}, IsWrapper: true},
	"produce":  {Lemma: "produce", NsHints: []string{}, IsWrapper: true},

	// Network / discovery
	"ping":     {Lemma: "ping", NsHints: []string{"A"}, PrimaryOpcode: "PING"},
	"discover": {Lemma: "discover", NsHints: []string{"N"}, PrimaryOpcode: "Q"},

	// Alerts
	"alert":   {Lemma: "alert", NsHints: []string{"L", "H", "U", "W"}, PrimaryOpcode: "ALERT"},
	"notify":  {Lemma: "notify", NsHints: []string{"U"}, PrimaryOpcode: "NOTIFY"},
	"warn":    {Lemma: "warn", NsHints: []string{"L", "H", "U"}, PrimaryOpcode: "ALERT"},
	"trigger": {Lemma: "trigger", NsHints: []string{"L", "U"}, PrimaryOpcode: "ALERT"},

	// Config
	"set":       {Lemma: "set", NsHints: []string{"N"}, PrimaryOpcode: "CFG", TakesSlot: true},
	"configure": {Lemma: "configure", NsHints: []string{"N"}, PrimaryOpcode: "CFG", TakesSlot: true},
	"update":    {Lemma: "update", NsHints: []string{"N"}, PrimaryOpcode: "CFG"},
	"modify":    {Lemma: "modify", NsHints: []string{"N"}, PrimaryOpcode: "CFG"},
	"change":    {Lemma: "change", NsHints: []string{"N"}, PrimaryOpcode: "CFG"},
	"adjust":    {Lemma: "adjust", NsHints: []string{"N"}, PrimaryOpcode: "CFG"},

	// Time / schedule
	"expire":   {Lemma: "expire", NsHints: []string{"T"}, PrimaryOpcode: "EXP"},
	"schedule": {Lemma: "schedule", NsHints: []string{"T"}, PrimaryOpcode: "SCHED"},

	// Storage / data
	"back":   {Lemma: "back", NsHints: []string{"N"}, PrimaryOpcode: "BK"},
	"backup": {Lemma: "backup", NsHints: []string{"N"}, PrimaryOpcode: "BK"},
	"delete": {Lemma: "delete", NsHints: []string{"D"}, PrimaryOpcode: "DEL"},
	"push":   {Lemma: "push", NsHints: []string{"D"}, PrimaryOpcode: "PUSH"},

	// Commerce
	"process": {Lemma: "process", NsHints: []string{"K", "C"}, IsWrapper: true},
	"pay":     {Lemma: "pay", NsHints: []string{"K"}, PrimaryOpcode: "PAY"},
	"approve": {Lemma: "approve", NsHints: []string{"U"}, PrimaryOpcode: "APPROVE"},

	// Cognitive
	"hand":      {Lemma: "hand", NsHints: []string{"J"}, PrimaryOpcode: "HANDOFF"},
	"handoff":   {Lemma: "handoff", NsHints: []string{"J"}, PrimaryOpcode: "HANDOFF"},
	"summarize": {Lemma: "summarize", NsHints: []string{"A"}, PrimaryOpcode: "SUM"},
	"check":     {Lemma: "check", NsHints: []string{"A", "Q"}, IsWrapper: true},
}

var inflections = map[string]string{
	"stops": "stop", "stopping": "stop", "stopped": "stop",
	"starts": "start", "starting": "start", "started": "start",
	"moves": "move", "moving": "move", "moved": "move",
	"opens": "open", "opening": "open", "opened": "open",
	"closes": "close", "closing": "close", "closed": "close",
	"locks": "lock", "locking": "lock", "locked": "lock",
	"encrypts": "encrypt", "encrypting": "encrypt", "encrypted": "encrypt",
	"signs": "sign", "signing": "sign", "signed": "sign",
	"verifies": "verify", "verifying": "verify", "verified": "verify",
	"pings": "ping", "pinging": "ping", "pinged": "ping",
	"alerts": "alert", "alerting": "alert", "alerted": "alert",
	"notifies": "notify", "notifying": "notify", "notified": "notify",
	"sets": "set", "setting": "set",
	"configures": "configure", "configuring": "configure",
	"updates": "update", "updating": "update", "updated": "update",
	"expires": "expire", "expiring": "expire", "expired": "expire",
	"deletes": "delete", "deleting": "delete", "deleted": "delete",
	"pushes": "push", "pushing": "push", "pushed": "push",
	"approves": "approve", "approving": "approve", "approved": "approve",
	"summarizes": "summarize", "summarizing": "summarize", "summarized": "summarize",
	"discovers": "discover", "discovering": "discover", "discovered": "discover",
	"generates": "generate", "generating": "generate", "generated": "generate",
	"reports": "report", "reporting": "report", "reported": "report",
	"sends": "send", "sending": "send", "sent": "send",
	"shows": "show", "showing": "show", "showed": "show",
	"broadcasts": "broadcast", "broadcasting": "broadcast",
	"fetches": "fetch", "fetching": "fetch", "fetched": "fetch",
	"retrieves": "retrieve", "retrieving": "retrieve", "retrieved": "retrieve",
	"reads": "read", "reading": "read",
	"gets": "get", "getting": "get", "got": "get",
	"halts": "halt", "halting": "halt", "halted": "halt",
	"shuts": "shut", "shutting": "shut",
	"kills": "kill", "killing": "kill", "killed": "kill",
	"reboots": "reboot", "rebooting": "reboot", "rebooted": "reboot",
	"restarts": "restart", "restarting": "restart", "restarted": "restart",
	"returns": "return", "returning": "return", "returned": "return",
	"evacuates": "evacuate", "evacuating": "evacuate", "evacuated": "evacuate",
	"turns": "turn", "turning": "turn", "turned": "turn",
	"activates": "activate", "activating": "activate", "activated": "activate",
	"warns": "warn", "warning": "warn", "warned": "warn",
	"triggers": "trigger", "triggering": "trigger", "triggered": "trigger",
	"processes": "process", "processing": "process", "processed": "process",
	"schedules": "schedule", "scheduling": "schedule", "scheduled": "scheduled",
	"checks": "check", "checking": "check", "checked": "check",
	"hands": "hand", "handing": "hand", "handed": "hand",
	"creates": "create", "creating": "create", "created": "create",
	"makes": "make", "making": "make", "made": "make",
	"produces": "produce", "producing": "produce", "produced": "produce",
}

var stopwords = map[string]bool{
	"the": true, "a": true, "an": true, "this": true, "that": true,
	"these": true, "those": true, "is": true, "are": true, "was": true,
	"were": true, "be": true, "been": true, "being": true, "do": true,
	"does": true, "did": true, "has": true, "have": true, "had": true,
	"and": true, "or": true, "but": true, "if": true, "when": true,
	"while": true, "of": true, "in": true, "on": true, "at": true,
	"to": true, "for": true, "from": true, "with": true, "by": true,
	"me": true, "my": true, "you": true, "your": true, "we": true,
	"our": true, "they": true, "their": true, "it": true, "its": true,
	"his": true, "her": true, "them": true, "please": true, "now": true,
	"just": true, "only": true, "really": true,
}

// ─────────────────────────────────────────────────────────────────────────
// SLOT EXTRACTORS
// ─────────────────────────────────────────────────────────────────────────

var (
	icdPattern       = regexp.MustCompile(`(?i)(?:code|icd|diagnosis|icd-?10)\s+([A-Z]\d{2}\.?\d*)`)
	latlonPattern    = regexp.MustCompile(`(?i)(?:coordinates?|coords?|gps|location|latlon)\s+([\-]?\d{1,3}\.?\d*)\s*[,]?\s*([\-]?\d{1,3}\.?\d*)`)
	durationPattern  = regexp.MustCompile(`(?i)(?:every|in|after|for|within)\s+(\d+\.?\d*)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\b`)
	atTimePattern    = regexp.MustCompile(`(?i)\b(?:at|by)\s+(\d{1,2}(?::\d{2})?(?:\s*[ap]m)?|midnight|noon|tonight)\b`)
	thresholdPattern = regexp.MustCompile(`(?i)(above|over|below|under|exceeds?|greater than|less than|higher than|lower than)\s+(\-?\d+\.?\d*)`)
	namedParamPattern = regexp.MustCompile(`(?i)\b(?:set\s+(?:the\s+)?)?(\w+)\s+to\s+(\d+\.?\d*)\b`)
)

var thresholdOpMap = map[string]string{
	"above": ">", "over": ">", "exceeds": ">", "exceed": ">",
	"greater than": ">", "higher than": ">",
	"below": "<", "under": "<", "less than": "<", "lower than": "<",
}

func normalizeDurationUnit(unit string) string {
	u := strings.ToLower(unit)
	if strings.HasPrefix(u, "s") {
		return "s"
	}
	if strings.HasPrefix(u, "min") || u == "m" {
		return "m"
	}
	if strings.HasPrefix(u, "m") {
		return "s"
	}
	if strings.HasPrefix(u, "h") {
		return "h"
	}
	if strings.HasPrefix(u, "d") {
		return "d"
	}
	return "s"
}

func ExtractSlots(text string) []SlotValue {
	var slots []SlotValue
	seenKeys := map[string]bool{}
	textLow := strings.ToLower(text)

	cadence := []struct{ kw, val string }{
		{"daily", "1d"}, {"hourly", "1h"}, {"weekly", "7d"},
		{"monthly", "30d"}, {"nightly", "1d"},
	}
	for _, c := range cadence {
		if strings.Contains(textLow, c.kw) {
			slots = append(slots, SlotValue{Key: "duration", Value: c.val, ValueType: "duration"})
			break
		}
	}

	for _, m := range icdPattern.FindAllStringSubmatch(text, -1) {
		code := strings.ToUpper(strings.ReplaceAll(m[1], ".", ""))
		if !seenKeys["icd"] {
			slots = append(slots, SlotValue{Key: "icd", Value: code, ValueType: "code"})
			seenKeys["icd"] = true
		}
	}

	for _, m := range latlonPattern.FindAllStringSubmatch(text, -1) {
		latlon := m[1] + "," + m[2]
		if !seenKeys["coordinates"] {
			slots = append(slots, SlotValue{Key: "coordinates", Value: latlon, ValueType: "latlon"})
			seenKeys["coordinates"] = true
		}
	}

	for _, m := range durationPattern.FindAllStringSubmatch(text, -1) {
		n := m[1]
		unit := normalizeDurationUnit(m[2])
		n = strings.TrimSuffix(n, ".0")
		slots = append(slots, SlotValue{Key: "duration", Value: n + unit, ValueType: "duration"})
	}

	for _, m := range atTimePattern.FindAllStringSubmatch(text, -1) {
		t := strings.ReplaceAll(strings.ToUpper(m[1]), " ", "")
		if !seenKeys["at_time"] {
			slots = append(slots, SlotValue{Key: "at_time", Value: t, ValueType: "time"})
			seenKeys["at_time"] = true
		}
	}

	skipNames := map[string]bool{
		"set": true, "configure": true, "update": true, "schedule": true,
	}
	for k := range seenKeys {
		skipNames[k] = true
	}
	for _, m := range namedParamPattern.FindAllStringSubmatch(text, -1) {
		name := strings.ToLower(m[1])
		if skipNames[name] || stopwords[name] {
			continue
		}
		slots = append(slots, SlotValue{Key: name, Value: m[2], ValueType: "float"})
	}
	return slots
}

func ExtractConditions(text string) []Condition {
	var out []Condition
	for _, m := range thresholdPattern.FindAllStringSubmatch(text, -1) {
		opWord := strings.ToLower(m[1])
		opWord = strings.TrimSuffix(opWord, "s")
		salOp, ok := thresholdOpMap[opWord]
		if !ok {
			salOp = ">"
		}
		if salOp == ">" {
			for _, neg := range []string{"below", "under", "less than", "lower than"} {
				if opWord == neg {
					salOp = "<"
					break
				}
			}
		}
		out = append(out, Condition{Operator: salOp, Value: m[2]})
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// TARGET EXTRACTOR
// ─────────────────────────────────────────────────────────────────────────

var (
	entityPattern            = regexp.MustCompile(`(?i)\b(drone|node|patient|sensor|vehicle|vessel|gateway|turbine|server|valve|door|agent|host|relay|gate|building|cluster|peer|robot|station|tank|reactor)\s+([\w\-]+)`)
	actionVerbObjectPattern  = regexp.MustCompile(`(?i)\b(stop|close|open|lock|unlock|kill|reboot|restart|shutdown|start|halt)\s+(?:the\s+)?(\w+)`)
	// Go's RE2 doesn't support look-behind. Capture optional non-word boundary char in group 1, target in group 2.
	prepTargetPattern = regexp.MustCompile(`(?i)(^|[^\w])(?:on|at|to|@)\s+(?:the\s+)?([\w\-]+)`)
	upperOnlyRe       = regexp.MustCompile(`^[A-Z]+$`)
	digitInRe         = regexp.MustCompile(`\d`)
	allDigitsRe       = regexp.MustCompile(`^\d+$`)
)

var targetBlocklist = map[string]bool{
	"the": true, "a": true, "an": true, "and": true, "or": true, "but": true,
	"is": true, "are": true, "coordinates": true, "position": true, "heading": true,
	"feedback": true, "control": true, "context": true, "service": true, "system": true,
	"midnight": true, "noon": true, "tonight": true, "home": true, "base": true,
	"this": true, "that": true, "it": true, "them": true, "me": true, "us": true,
	"temperature": true, "humidity": true, "pressure": true, "pneumothorax": true,
	"status": true, "uptime": true, "health": true, "french": true, "spanish": true, "german": true,
	"pizza": true, "burger": true, "paris": true, "jazz": true, "milk": true,
	"flashlight": true, "camera": true, "speaker": true, "microphone": true,
	"haptic": true, "vibration": true, "screen": true, "display": true,
	"pump": true, "valve": true, "door": true, "fan": true,
	"conveyor": true, "engine": true, "motor": true, "lamp": true, "light": true,
	"message": true, "payload": true, "data": true, "request": true, "response": true,
}

var entityKindPrefixed = map[string]bool{
	"drone": true, "vehicle": true, "vessel": true, "uav": true, "patient": true,
}

func ExtractTargets(text string) []Target {
	var out []Target
	seen := map[string]bool{}

	// Priority 1: structured entity
	for _, m := range entityPattern.FindAllStringSubmatch(text, -1) {
		kind := strings.ToLower(m[1])
		eid := strings.ToUpper(m[2])
		isID := allDigitsRe.MatchString(eid) ||
			digitInRe.MatchString(eid) ||
			(upperOnlyRe.MatchString(eid) && len(eid) >= 3 && !targetBlocklist[strings.ToLower(eid)])
		if !isID {
			continue
		}
		var tid string
		if entityKindPrefixed[kind] {
			tid = strings.ToUpper(kind) + eid
		} else {
			tid = eid
		}
		if !seen[tid] {
			out = append(out, Target{ID: tid, Kind: kind, Source: "entity"})
			seen[tid] = true
		}
	}

	// Priority 2: action-verb + bare noun
	for _, m := range actionVerbObjectPattern.FindAllStringSubmatch(text, -1) {
		obj := strings.ToUpper(m[2])
		if targetBlocklist[strings.ToLower(obj)] {
			continue
		}
		if !seen[obj] {
			out = append(out, Target{ID: obj, Kind: "object", Source: "action_verb"})
			seen[obj] = true
		}
	}

	// Priority 3: prepositional (no look-behind in Go RE2 — group 1 absorbs the boundary char)
	for _, m := range prepTargetPattern.FindAllStringSubmatch(text, -1) {
		t := strings.ToUpper(m[2])
		if targetBlocklist[strings.ToLower(t)] {
			continue
		}
		if !seen[t] {
			out = append(out, Target{ID: t, Kind: "prep", Source: "preposition"})
			seen[t] = true
		}
	}
	return out
}

// ─────────────────────────────────────────────────────────────────────────
// DOMAIN HINT
// ─────────────────────────────────────────────────────────────────────────

// Slice (not map) so iteration order is deterministic across runs.
type domainKW struct {
	domain string
	kws    []string
}

var domainKeywords = []domainKW{
	{"medical", []string{"patient", "vitals", "heart", "blood", "pressure", "spo2",
		"oxygen", "pulse", "icd", "diagnosis", "casualty", "pneumothorax"}},
	{"uav", []string{"drone", "uav", "swarm", "rtb", "altitude", "wedge", "formation"}},
	{"weather", []string{"wind", "barometric", "pressure", "humidity", "temperature",
		"rain", "storm", "atmospheric"}},
	{"device_control", []string{"conveyor", "valve", "pump", "door", "lock", "lights",
		"fan", "motor", "engine", "actuator"}},
	{"meshtastic", []string{"node", "peer", "relay", "broadcast", "ping", "mesh",
		"channel", "rebroadcast"}},
	{"crypto", []string{"encrypt", "decrypt", "sign", "hash", "key", "keypair",
		"signature", "tls", "aes"}},
	{"config", []string{"config", "configuration", "settings", "threshold",
		"parameter", "setup", "preferences"}},
	{"vehicle", []string{"vehicle", "vessel", "ship", "fleet", "ais", "boat"}},
	{"sensor", []string{"sensor", "humidity", "moisture", "air quality", "vibration"}},
}

var domainToNS = map[string][]string{
	"medical":        {"H", "I", "U"},
	"uav":            {"V", "R", "G", "I"},
	"weather":        {"W", "E"},
	"device_control": {"R", "C"},
	"meshtastic":     {"N", "O", "A", "G"},
	"crypto":         {"S", "I"},
	"config":         {"N", "T"},
	"vehicle":        {"V", "G"},
	"sensor":         {"E"},
}

func DetectDomain(text string) (string, []string) {
	low := strings.ToLower(text)
	tokens := map[string]bool{}
	for _, t := range strings.Fields(low) {
		tokens[t] = true
	}
	bestScore := 0
	bestDomain := ""
	for _, dk := range domainKeywords {
		s := 0
		for _, kw := range dk.kws {
			if tokens[kw] || strings.Contains(low, kw) {
				s++
			}
		}
		if s > bestScore {
			bestScore = s
			bestDomain = dk.domain
		}
	}
	if bestScore == 0 {
		return "", nil
	}
	hints := domainToNS[bestDomain]
	return bestDomain, hints
}

// ─────────────────────────────────────────────────────────────────────────
// CHAIN DETECTION
// ─────────────────────────────────────────────────────────────────────────

type chainPattern struct {
	re *regexp.Regexp
	op string
}

var chainPatterns = []chainPattern{
	{regexp.MustCompile(`(?i),\s+then\s+`), ";"},
	{regexp.MustCompile(`(?i),\s+and\s+then\s+`), ";"},
	{regexp.MustCompile(`(?i)\s+then\s+`), ";"},
	{regexp.MustCompile(`(?i),\s+and\s+`), "\u2227"},
	{regexp.MustCompile(`(?i)\s+and\s+`), "\u2227"},
}

var trailingPunctRe = regexp.MustCompile(`[.,;]+$`)

func SplitChain(text string) ([]string, string) {
	low := strings.ToLower(text)
	if strings.Contains(low, " if ") || strings.HasPrefix(low, "if ") {
		return []string{text}, ""
	}
	for _, cp := range chainPatterns {
		segs := cp.re.Split(text, -1)
		if len(segs) >= 2 {
			cleaned := []string{}
			for _, s := range segs {
				s = strings.TrimSpace(s)
				s = trailingPunctRe.ReplaceAllString(s, "")
				if s != "" {
					cleaned = append(cleaned, s)
				}
			}
			if len(cleaned) >= 2 {
				return cleaned, cp.op
			}
		}
	}
	return []string{text}, ""
}

// ─────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────

func Lemmatize(word string) string {
	w := strings.ToLower(word)
	if _, ok := VerbLexicon[w]; ok {
		return w
	}
	if l, ok := inflections[w]; ok {
		return l
	}
	for _, suffix := range []string{"ing", "ed", "es", "s"} {
		if strings.HasSuffix(w, suffix) && len(w) > len(suffix)+2 {
			stem := w[:len(w)-len(suffix)]
			if _, ok := VerbLexicon[stem]; ok {
				return stem
			}
		}
	}
	return w
}

var leadTrimRe = regexp.MustCompile(`^[^\w.\-]+`)
var trailTrimRe = regexp.MustCompile(`[^\w.\-]+$`)

func Tokenize(text string) []string {
	cleaned := strings.ToLower(text)
	out := []string{}
	for _, raw := range strings.Fields(cleaned) {
		w := leadTrimRe.ReplaceAllString(raw, "")
		w = trailTrimRe.ReplaceAllString(w, "")
		if w != "" {
			out = append(out, w)
		}
	}
	return out
}

type VerbHead struct {
	Token string
	Lemma string
}

func FindVerbHead(tokens []string) *VerbHead {
	for _, tok := range tokens {
		if stopwords[tok] {
			continue
		}
		lemma := Lemmatize(tok)
		if _, ok := VerbLexicon[lemma]; ok {
			return &VerbHead{Token: tok, Lemma: lemma}
		}
	}
	return nil
}

func DetectAuthorization(text string) bool {
	for _, p := range authMarkers {
		if p.MatchString(text) {
			return true
		}
	}
	return false
}

func DetectEmergency(text string) bool {
	low := strings.ToLower(text)
	for _, m := range emergencyMarkers {
		if strings.Contains(low, m) {
			return true
		}
	}
	return false
}

func DetectBroadcast(text string) bool {
	low := strings.ToLower(text)
	for _, m := range broadcastMarkers {
		if strings.Contains(low, m) {
			return true
		}
	}
	return false
}

func DetectQuery(text string, verbLemma string) bool {
	if strings.HasSuffix(strings.TrimSpace(text), "?") {
		return true
	}
	low := strings.ToLower(text)
	for _, m := range queryMarkers {
		if strings.Contains(low, m) {
			return true
		}
	}
	if verbLemma != "" {
		if info, ok := VerbLexicon[verbLemma]; ok {
			if info.IsQuery {
				return true
			}
			if info.IsWrapper {
				wrappers := []string{"report", "show", "give", "fetch", "retrieve", "read", "what", "where"}
				for _, w := range wrappers {
					if verbLemma == w {
						return true
					}
				}
			}
		}
	}
	return false
}

func DetectNegation(text string) bool {
	for _, p := range negationMarkers {
		if p.MatchString(text) {
			return true
		}
	}
	return false
}

var glyphInjectionRe = regexp.MustCompile(`\b[A-Z\x{03a9}]:[A-Z][A-Z0-9_]*\b`)

func DetectGlyphInjection(text string) bool {
	return glyphInjectionRe.MatchString(text)
}

func DetectCodeInjection(text string) bool {
	for _, p := range injectionMarkers {
		if p.MatchString(text) {
			return true
		}
	}
	return false
}

func DetectEmail(text string) bool {
	return emailPattern.MatchString(text)
}

var idiomPunctStrip = regexp.MustCompile(`[.,!?']`)
var idiomPunctStripNoApos = regexp.MustCompile(`[.,!?]`)

func DetectIdiom(verbLemma, raw string) bool {
	if verbLemma == "" {
		return false
	}
	low := strings.ToLower(raw)
	tokens := strings.Fields(low)
	idx := -1
	for i, t := range tokens {
		if t == verbLemma {
			idx = i
			break
		}
	}
	if idx >= 0 && idx+1 < len(tokens) {
		next := idiomPunctStripNoApos.ReplaceAllString(tokens[idx+1], "")
		if idiomParticleAfterVerb[verbLemma+"|"+next] {
			return true
		}
	}
	for i := range tokens {
		clean := idiomPunctStrip.ReplaceAllString(tokens[i], "")
		if strings.HasPrefix(clean, verbLemma) && i+1 < len(tokens) {
			next := idiomPunctStripNoApos.ReplaceAllString(tokens[i+1], "")
			if idiomParticleAfterVerb[verbLemma+"|"+next] {
				return true
			}
		}
	}
	return false
}

// ─────────────────────────────────────────────────────────────────────────
// DIRECT OBJECT
// ─────────────────────────────────────────────────────────────────────────

var dobjKindMap = map[string]string{
	"drone": "drone", "uav": "drone", "node": "node", "sensor": "sensor",
	"patient": "patient", "vehicle": "vehicle", "vessel": "vehicle",
	"gateway": "gateway", "valve": "actuator", "door": "actuator",
	"pump": "actuator", "conveyor": "actuator", "camera": "peripheral",
	"microphone": "peripheral", "speaker": "peripheral", "flashlight": "peripheral",
	"torch": "peripheral", "haptic": "peripheral",
	"payment": "transaction", "key": "crypto_key",
	"temperature": "sensor_value", "humidity": "sensor_value",
	"pressure": "sensor_value",
	"oxygen": "vital", "vitals": "vital",
	"config": "config", "threshold": "config",
}

var multiWordObjBases = map[string]bool{
	"drone": true, "node": true, "sensor": true, "patient": true,
	"vehicle": true, "vessel": true, "gateway": true,
	"valve": true, "door": true, "agent": true, "key": true,
	"blood": true, "heart": true, "oxygen": true,
}

func FindDirectObject(tokens []string, verbIdx int) (string, string) {
	after := append([]string{}, tokens[verbIdx+1:]...)
	if len(after) > 0 {
		first := after[0]
		if first == "on" || first == "off" || first == "up" || first == "down" || first == "in" || first == "out" {
			after = after[1:]
		}
	}
	for len(after) > 0 {
		f := after[0]
		if f == "the" || f == "a" || f == "an" || f == "my" || f == "your" {
			after = after[1:]
			continue
		}
		break
	}
	if len(after) == 0 {
		return "", ""
	}
	obj := after[0]
	if len(after) >= 2 {
		cand := obj + " " + after[1]
		if multiWordObjBases[obj] {
			obj = cand
		}
	}
	first := strings.SplitN(obj, " ", 2)[0]
	if k, ok := dobjKindMap[first]; ok {
		return obj, k
	}
	if k, ok := dobjKindMap[obj]; ok {
		return obj, k
	}
	return obj, ""
}

// ─────────────────────────────────────────────────────────────────────────
// MAIN PARSE
// ─────────────────────────────────────────────────────────────────────────

func Parse(nl string) ParsedRequest {
	raw := strings.TrimSpace(nl)
	segments, chainOp := SplitChain(raw)
	if len(segments) > 1 {
		var sub []ParsedRequest
		for _, s := range segments {
			sub = append(sub, Parse(s))
		}
		whole := parseSingle(raw)
		whole.ChainSegments = sub
		whole.ChainOperator = chainOp
		return whole
	}
	return parseSingle(raw)
}

func parseSingle(nl string) ParsedRequest {
	raw := strings.TrimSpace(nl)
	tokens := Tokenize(raw)

	verbInfo := FindVerbHead(tokens)
	verbRaw := ""
	verbLemma := ""
	verbIdx := -1
	if verbInfo != nil {
		verbRaw = verbInfo.Token
		verbLemma = verbInfo.Lemma
		for i, t := range tokens {
			if t == verbRaw {
				verbIdx = i
				break
			}
		}
	}

	var directObject, dobjKind string
	if verbIdx >= 0 {
		directObject, dobjKind = FindDirectObject(tokens, verbIdx)
	}

	isAuth := DetectAuthorization(raw)
	isEmergency := DetectEmergency(raw)
	isBroadcast := DetectBroadcast(raw)
	isQuery := DetectQuery(raw, verbLemma)
	isNegated := DetectNegation(raw)
	hasGlyphInjection := DetectGlyphInjection(raw) || DetectCodeInjection(raw) ||
		DetectEmail(raw) || DetectIdiom(verbLemma, raw)

	slots := ExtractSlots(raw)
	scheduleValue := ""
	for _, sv := range slots {
		if sv.ValueType == "duration" || sv.ValueType == "time" {
			scheduleValue = sv.Value
			break
		}
	}

	conditions := ExtractConditions(raw)
	targets := ExtractTargets(raw)

	domain, nsHints := DetectDomain(raw)
	allHints := append([]string{}, nsHints...)
	if info, ok := VerbLexicon[verbLemma]; ok {
		for _, ns := range info.NsHints {
			present := false
			for _, h := range allHints {
				if h == ns {
					present = true
					break
				}
			}
			if !present {
				allHints = append(allHints, ns)
			}
		}
	}

	isPassthrough := verbInfo == nil && len(slots) == 0 && len(targets) == 0

	req := EmptyParsedRequest(raw)
	req.Verb = verbRaw
	req.VerbLemma = verbLemma
	req.DirectObject = directObject
	req.DirectObjectKind = dobjKind
	req.Targets = targets
	req.SlotValues = slots
	req.Conditions = conditions
	req.Schedule = scheduleValue
	req.AuthorizationRequired = isAuth
	req.IsEmergency = isEmergency
	req.IsBroadcast = isBroadcast
	req.IsQuery = isQuery
	req.IsPassthroughLikely = isPassthrough
	req.IsNegated = isNegated
	req.HasGlyphInjection = hasGlyphInjection
	req.NamespaceHints = allHints
	req.DomainHint = domain
	return req
}

// utf8Bytes returns the UTF-8 byte length of s.
func utf8Bytes(s string) int {
	return len(s) // Go strings are UTF-8 encoded by default.
}
