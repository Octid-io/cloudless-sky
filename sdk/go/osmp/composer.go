// SALComposer — Deterministic NL-to-SAL composition pipeline.
//
// The composer NEVER generates SAL text via inference. It decomposes
// NL into intent, looks up opcodes in the ASD, assembles using grammar
// rules, and validates the result.
//
// Patent pending | License: Apache 2.0
package osmp

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
	"unicode"
)

// ComposedIntent holds structured intent extracted from natural language.
type ComposedIntent struct {
	Actions    []string
	Conditions []string
	Targets    []string
	Parameters map[string]string
	Raw        string
}

// Composer is the deterministic NL-to-SAL composition pipeline.
type Composer struct {
	asd           *AdaptiveSharedDictionary
	macroRegistry *MacroRegistry
	keywordIndex  map[string][][2]string // keyword -> [(ns, op), ...]
	phraseIndex   map[string][2]string   // phrase -> (ns, op)
	phrasesSorted []string               // sorted longest-first
}

// chainSeparators map NL separator patterns to the SAL operator that joins
// composed segments. Order matters: longer / more-specific patterns first.
// Mirrors Python `_CHAIN_SEPARATORS` in protocol.py (lines 2495-2505).
var chainSeparators = []struct {
	re *regexp.Regexp
	op string
}{
	{regexp.MustCompile(`(?i),\s+then\s+`), ";"},
	{regexp.MustCompile(`(?i),\s+and\s+then\s+`), ";"},
	{regexp.MustCompile(`(?i)\s+then\s+`), ";"},
	{regexp.MustCompile(`(?i)\s+next\s+`), ";"},
	{regexp.MustCompile(`(?i),\s+and\s+`), "\u2227"},
}

// chainTrailingPunctRe strips trailing , ; . from a chain segment after split.
var chainTrailingPunctRe = regexp.MustCompile(`[.,;]+$`)

var (
	sensingNS = map[string]bool{"E": true, "H": true, "W": true, "G": true, "X": true, "S": true, "D": true, "Z": true}
	actionNS  = map[string]bool{"U": true, "M": true, "R": true, "B": true, "J": true, "A": true, "K": true}

	conditionMap = map[string]string{
		"above": ">", "over": ">", "exceeds": ">", "greater than": ">",
		"more than": ">", "higher than": ">",
		"below": "<", "under": "<", "less than": "<", "lower than": "<",
		"equals": "=", "equal to": "=", "is": "=",
		"not": "\u00ac",
	}

	skipWords = map[string]bool{
		"the": true, "and": true, "for": true, "from": true, "with": true,
		"that": true, "this": true, "when": true, "then": true, "turn": true,
		"get": true, "set": true, "put": true, "make": true, "give": true,
		"take": true, "show": true, "tell": true, "let": true, "use": true,
		"try": true, "see": true, "ask": true, "how": true, "what": true,
		"where": true, "who": true, "why": true, "can": true, "will": true,
		"has": true, "have": true, "does": true, "did": true, "are": true,
		"was": true, "been": true, "being": true, "many": true, "much": true,
		"some": true, "any": true, "all": true, "each": true, "every": true,
		"other": true, "about": true, "into": true, "over": true, "after": true,
		"before": true, "between": true, "but": true, "only": true, "just": true,
		"also": true, "too": true, "very": true, "really": true, "it": true,
		"its": true, "me": true, "my": true, "your": true, "our": true,
		"their": true, "him": true, "her": true, "his": true, "them": true,
		"going": true, "goes": true, "went": true,
		"you": true, "need": true, "want": true, "know": true, "like": true,
		"think": true, "would": true, "post": true, "photo": true,
		"caption": true, "book": true, "order": true, "send": true,
		// Generic referent nouns — objects of actions, not actions themselves
		"payload": true, "data": true, "message": true, "request": true,
		"response": true, "content": true, "file": true, "item": true,
		"value": true, "result": true, "thing": true,
	}

	targetFalsePositives = map[string]bool{
		"THE": true, "A": true, "AN": true, "THIS": true, "THAT": true,
		"MY": true, "YOUR": true, "IT": true, "THEM": true, "HIM": true,
		"HER": true, "ME": true, "EVERYTHING": true, "TEMPERATURE": true,
		"IS": true, "SOME": true, "ALL": true,
	}

	condRe    = regexp.MustCompile(`(?i)(above|over|below|under|exceeds?|greater than|less than|higher than|lower than)\s+(\d+\.?\d*)`)
	paramRe   = regexp.MustCompile(`(?i)(?:temperature|top.?p|top.?k|max.?tokens?)\s+(\d+\.?\d*)`)
	icdRe     = regexp.MustCompile(`(?i)(?:code|icd|diagnosis|icd-10)\s+([A-Z]\d{2}\.?\d*)`)
	targetRe  = regexp.MustCompile(`(?i)(?:^|\W)(?:on|at|to|@)\s+(\w+)`)
)

// Curated triggers discovered through cross-model composition testing.
var curatedTriggers = map[string][2]string{
	"flow authorization": {"F", "AV"}, "authorization proceed": {"F", "AV"},
	"emergency route": {"M", "RTE"}, "municipal route": {"M", "RTE"},
	"incident route": {"M", "RTE"}, "network status": {"N", "STS"},
	"node status": {"N", "STS"}, "vessel heading": {"V", "HDG"},
	"ship heading": {"V", "HDG"}, "maritime heading": {"V", "HDG"},
	"restart process": {"C", "RSTRT"}, "restart service": {"C", "RSTRT"},
	"data query": {"D", "Q"}, "query data": {"D", "Q"},
	"audit query": {"L", "QUERY"}, "query audit": {"L", "QUERY"},
	"robot heading": {"R", "HDNG"}, "vehicle heading": {"R", "HDNG"},
	"robot status": {"R", "STAT"}, "device status": {"R", "STAT"},
	"robot waypoint": {"R", "WPT"}, "attest payload": {"S", "ATST"},
	"attestation": {"S", "ATST"}, "page out memory": {"Y", "PAGEOUT"},
	"store to memory": {"Y", "STORE"}, "save to memory": {"Y", "STORE"},
	"generate key": {"S", "KEYGEN"}, "generate keys": {"S", "KEYGEN"},
	"key pair": {"S", "KEYGEN"}, "create keypair": {"S", "KEYGEN"},
	"sign payload": {"S", "SIGN"}, "digital signature": {"S", "SIGN"},
	"push to node": {"D", "PUSH"}, "send to node": {"D", "PUSH"},
	"transfer task": {"J", "HANDOFF"}, "hand off": {"J", "HANDOFF"},
	"task handoff": {"J", "HANDOFF"}, "verify identity": {"I", "ID"},
	"identity check": {"I", "ID"}, "run inference": {"Z", "INF"},
	"invoke model": {"Z", "INF"}, "building fire": {"B", "ALRM"},
	"fire alarm": {"B", "ALRM"},
	// Operational abbreviations (mesh radio shorthand)
	"temp report": {"E", "TH"}, "temp check": {"E", "TH"},
	"battery level": {"X", "STORE"}, "battery status": {"X", "STORE"},
	"battery report": {"X", "STORE"}, "signal strength": {"O", "LINK"},
	"link quality": {"O", "LINK"}, "gps fix": {"E", "GPS"},
	"position report": {"G", "POS"}, "node info": {"N", "STS"},
	"mesh status": {"O", "MESH"}, "air quality": {"E", "EQ"},
	"wind speed": {"W", "WIND"}, "heart rate check": {"H", "HR"},
	"blood pressure check": {"H", "BP"}, "vitals check": {"H", "VITALS"},
	"oxygen level": {"H", "SPO2"},
}

// NewComposer creates a SALComposer with the default ASD.
func NewComposer(asd *AdaptiveSharedDictionary) *Composer {
	if asd == nil {
		asd = NewASD()
	}
	c := &Composer{
		asd:          asd,
		keywordIndex: make(map[string][][2]string),
		phraseIndex:  make(map[string][2]string),
	}
	c.buildKeywordIndex()
	c.buildPhraseIndex()
	return c
}

// NewComposerWithMacros creates a Composer with an attached macro registry.
// The composer prefers macro matches over individual opcode composition;
// see MacroRegistry semantics in macro.go.
func NewComposerWithMacros(asd *AdaptiveSharedDictionary, registry *MacroRegistry) *Composer {
	c := NewComposer(asd)
	c.macroRegistry = registry
	return c
}

// MacroRegistry returns the attached registry, or nil if none.
func (c *Composer) MacroRegistry() *MacroRegistry { return c.macroRegistry }

// SetMacroRegistry attaches or replaces the macro registry post-construction.
func (c *Composer) SetMacroRegistry(registry *MacroRegistry) {
	c.macroRegistry = registry
}

// sortedNamespaces returns the ASDFloorBasis namespaces in deterministic
// (alphabetical) order. Go's `range map` is intentionally randomized; without
// a stable iteration order the keyword index's first-match policy becomes
// non-deterministic, which breaks both reproducibility and cross-SDK parity.
func sortedNamespaces() []string {
	out := make([]string, 0, len(ASDFloorBasis))
	for ns := range ASDFloorBasis {
		out = append(out, ns)
	}
	sort.Strings(out)
	return out
}

// sortedOpcodes returns the opcodes for a single namespace in alphabetical
// order. Same rationale as sortedNamespaces.
func sortedOpcodes(ns string) []string {
	ops := ASDFloorBasis[ns]
	out := make([]string, 0, len(ops))
	for op := range ops {
		out = append(out, op)
	}
	sort.Strings(out)
	return out
}

func (c *Composer) buildKeywordIndex() {
	for _, ns := range sortedNamespaces() {
		for _, op := range sortedOpcodes(ns) {
			defn := ASDFloorBasis[ns][op]
			words := strings.Fields(strings.ReplaceAll(strings.ToLower(defn), "_", " "))
			for _, w := range words {
				if len(w) > 2 {
					c.keywordIndex[w] = append(c.keywordIndex[w], [2]string{ns, op})
				}
			}
		}
	}
}

func (c *Composer) buildPhraseIndex() {
	for _, ns := range sortedNamespaces() {
		for _, op := range sortedOpcodes(ns) {
			defn := ASDFloorBasis[ns][op]
			phrase := strings.ReplaceAll(strings.ToLower(defn), "_", " ")
			if strings.Contains(phrase, " ") {
				c.phraseIndex[phrase] = [2]string{ns, op}
			}
		}
	}
	for phrase, nsOp := range curatedTriggers {
		c.phraseIndex[phrase] = nsOp
	}
	c.phrasesSorted = make([]string, 0, len(c.phraseIndex))
	for p := range c.phraseIndex {
		c.phrasesSorted = append(c.phrasesSorted, p)
	}
	sort.Slice(c.phrasesSorted, func(i, j int) bool {
		return len(c.phrasesSorted[i]) > len(c.phrasesSorted[j])
	})
}

// LookupByKeyword finds opcodes matching a keyword. Iteration order is
// stable (alphabetical by namespace, then by opcode) so the first-match
// policy in Compose() produces deterministic, reproducible output.
func (c *Composer) LookupByKeyword(keyword string) [][3]string {
	kw := strings.ToLower(strings.TrimSpace(keyword))
	var results [][3]string
	seen := map[string]bool{}

	// Direct opcode match
	for _, ns := range sortedNamespaces() {
		for _, op := range sortedOpcodes(ns) {
			if kw == strings.ToLower(op) {
				key := ns + ":" + op
				if !seen[key] {
					results = append(results, [3]string{ns, op, ASDFloorBasis[ns][op]})
					seen[key] = true
				}
			}
		}
	}
	// Keyword index
	for _, pair := range c.keywordIndex[kw] {
		key := pair[0] + ":" + pair[1]
		if !seen[key] {
			defn := c.asd.Lookup(pair[0], pair[1])
			results = append(results, [3]string{pair[0], pair[1], defn})
			seen[key] = true
		}
	}
	// Fuzzy substring
	if len(results) == 0 {
		for _, ns := range sortedNamespaces() {
			for _, op := range sortedOpcodes(ns) {
				defn := ASDFloorBasis[ns][op]
				if strings.Contains(strings.ToLower(defn), kw) {
					results = append(results, [3]string{ns, op, defn})
				}
			}
		}
	}
	return results
}

// stripPunct removes leading/trailing punctuation from a word.
func stripPunct(s string) string {
	return strings.TrimFunc(s, func(r rune) bool {
		return unicode.IsPunct(r)
	})
}

// ExtractIntentKeywords parses NL into a ComposedIntent using keyword matching.
func (c *Composer) ExtractIntentKeywords(nlText string) ComposedIntent {
	raw := strings.TrimSpace(nlText)
	rawLower := strings.ToLower(raw)
	rawWords := strings.Fields(rawLower)
	words := make([]string, 0, len(rawWords))
	for _, w := range rawWords {
		w = stripPunct(w)
		if w != "" {
			words = append(words, w)
		}
	}

	intent := ComposedIntent{
		Parameters: make(map[string]string),
		Raw:        raw,
	}

	// Numeric conditions
	for _, m := range condRe.FindAllStringSubmatch(raw, -1) {
		opWord := strings.ToLower(m[1])
		salOp, ok := conditionMap[opWord]
		if !ok {
			salOp = ">"
		}
		intent.Conditions = append(intent.Conditions, salOp+m[2])
	}

	// Parametric values
	for _, m := range paramRe.FindAllStringSubmatch(raw, -1) {
		key := strings.ToLower(strings.Fields(m[0])[0])
		intent.Parameters[key] = m[1]
	}

	// ICD codes
	for _, m := range icdRe.FindAllStringSubmatch(raw, -1) {
		intent.Parameters["icd"] = strings.ReplaceAll(m[1], ".", "")
	}

	// Targets
	for _, m := range targetRe.FindAllStringSubmatch(raw, -1) {
		intent.Targets = append(intent.Targets, strings.ToUpper(m[1]))
	}

	// Phase 1: Phrase matching
	type span struct{ start, end int }
	var matchedSpans []span
	for _, phrase := range c.phrasesSorted {
		escaped := regexp.QuoteMeta(phrase)
		re := regexp.MustCompile(`(?i)(?:\A|\W)` + escaped + `(?:\z|\W)`)
		loc := re.FindStringIndex(rawLower)
		if loc == nil {
			continue
		}
		// Adjust for the leading \W match
		idx := loc[0]
		end := loc[1]
		if idx < len(rawLower) && !isWordChar(rune(rawLower[idx])) {
			idx++
		}
		if end > 0 && end <= len(rawLower) && !isWordChar(rune(rawLower[end-1])) {
			end--
		}
		overlaps := false
		for _, s := range matchedSpans {
			if !(end <= s.start || idx >= s.end) {
				overlaps = true
				break
			}
		}
		if !overlaps {
			matchedSpans = append(matchedSpans, span{idx, end})
			intent.Actions = append(intent.Actions, phrase)
		}
	}

	// Build consumed positions
	consumed := map[int]bool{}
	for _, sp := range matchedSpans {
		pos := 0
		for i, w := range words {
			wIdx := strings.Index(rawLower[pos:], w)
			if wIdx >= 0 {
				wIdx += pos
				if wIdx >= sp.start && wIdx+len(w) <= sp.end {
					consumed[i] = true
				}
				pos = wIdx + len(w)
			}
		}
	}

	// Build set of all 2-char opcode names for short-word matching
	shortOpcodes := map[string]bool{}
	for _, ops := range ASDFloorBasis {
		for op := range ops {
			if len(op) <= 2 {
				shortOpcodes[strings.ToLower(op)] = true
			}
		}
	}

	// Phase 2: Single-word fallback
	for i, word := range words {
		if consumed[i] {
			continue
		}
		// Allow short words (2 chars) if they're exact opcode names
		if len(word) == 2 && !shortOpcodes[word] {
			continue
		}
		if len(word) < 2 {
			continue
		}
		if skipWords[word] {
			continue
		}
		if len(word) > 2 || shortOpcodes[word] {
			if len(c.LookupByKeyword(word)) > 0 {
				intent.Actions = append(intent.Actions, word)
			}
		}
	}

	return intent
}

func isWordChar(r rune) bool {
	return unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_'
}

// Compose produces valid SAL from natural language, or "" if composition fails.
//
// First tries chain-split: if the NL contains sequential separators ("then",
// "next", ", and"), split into segments and compose each. This produces
// proper ; (SEQUENCE) or ∧ (AND) chains instead of flat keyword-matched SAL.
// Falls back to single-segment composition if no chain detected.
//
// Mirrors Python `compose` at protocol.py lines 2553-2576.
func (c *Composer) Compose(nlText string, intent *ComposedIntent) string {
	if intent == nil {
		if chainSAL := c.tryChainSplit(nlText); chainSAL != "" {
			result := ValidateComposition(chainSAL, nlText, c.asd, true, nil)
			if result.Valid {
				return chainSAL
			}
			// Chain validation failed → fall through to single-compose
		}
	}
	return c.composeImpl(nlText, intent)
}

// composeSingle is the chain-split entry point per segment. Kept separate
// to make the recursion stop at one level (mirrors Python `_compose_single`).
func (c *Composer) composeSingle(nlText string) string {
	return c.composeImpl(nlText, nil)
}

// tryChainSplit splits NL on chain separators and composes each segment.
// Returns "" if no separator matches OR any segment fails to compose.
// Mirrors Python `_try_chain_split` at protocol.py lines 2507-2546.
func (c *Composer) tryChainSplit(nlText string) string {
	nlLower := strings.ToLower(nlText)
	if strings.Contains(nlLower, " if ") || strings.HasPrefix(nlLower, "if ") {
		return "" // conditional chains handled by existing logic
	}

	for _, sep := range chainSeparators {
		raw := sep.re.Split(nlText, -1)
		if len(raw) < 2 {
			continue
		}
		segments := make([]string, 0, len(raw))
		for _, s := range raw {
			seg := chainTrailingPunctRe.ReplaceAllString(strings.TrimSpace(s), "")
			if seg != "" {
				segments = append(segments, seg)
			}
		}
		if len(segments) < 2 {
			continue
		}

		composed := make([]string, 0, len(segments))
		for _, seg := range segments {
			if len([]byte(seg)) < 4 {
				return ""
			}
			segSAL := c.composeSingle(seg)
			if segSAL == "" {
				return "" // any segment fails → whole chain fails
			}
			composed = append(composed, segSAL)
		}
		if len(composed) >= 2 {
			return strings.Join(composed, sep.op)
		}
		return ""
	}
	return ""
}

// composeImpl is the core composition logic. Mirrors Python `_compose_impl`
// at protocol.py lines 2578-2812. The macro priority check is the first step
// after the BAEL byte pre-check (lines 2595-2602).
func (c *Composer) composeImpl(nlText string, intent *ComposedIntent) string {
	if intent == nil {
		i := c.ExtractIntentKeywords(nlText)
		intent = &i
	}

	// BAEL byte pre-check
	if len([]byte(nlText)) < 6 {
		return ""
	}

	// Step 1: Macro priority check (composition priority hierarchy)
	if c.macroRegistry != nil {
		rawLower := strings.ToLower(intent.Raw)
		for _, m := range c.macroRegistry.ListMacros() {
			for _, trigger := range m.Triggers {
				if trigger == "" {
					continue
				}
				if strings.Contains(rawLower, strings.ToLower(trigger)) {
					return fmt.Sprintf("A:MACRO[%s]", m.MacroID)
				}
			}
		}
	}

	// Step 2: ASD lookup
	type nsOp = [2]string
	var resolved []nsOp
	hasPhraseMatch := false
	contains := func(list []nsOp, ns, op string) bool {
		for _, p := range list {
			if p[0] == ns && p[1] == op {
				return true
			}
		}
		return false
	}

	for _, action := range intent.Actions {
		if pair, ok := c.phraseIndex[action]; ok {
			if !contains(resolved, pair[0], pair[1]) {
				resolved = append(resolved, pair)
			}
			hasPhraseMatch = true
			continue
		}
		matches := c.LookupByKeyword(action)
		if len(matches) > 0 {
			ns, op := matches[0][0], matches[0][1]
			if !contains(resolved, ns, op) {
				resolved = append(resolved, nsOp{ns, op})
			}
		}
	}

	// Parameter-driven injection
	if intent.Parameters["icd"] != "" && !contains(resolved, "H", "ICD") {
		resolved = append([]nsOp{{"H", "ICD"}}, resolved...)
	}
	if intent.Parameters["temperature"] != "" && !contains(resolved, "Z", "TEMP") {
		resolved = append(resolved, nsOp{"Z", "TEMP"})
	}
	if intent.Parameters["top-p"] != "" && !contains(resolved, "Z", "TOPP") {
		resolved = append(resolved, nsOp{"Z", "TOPP"})
	}

	if len(resolved) == 0 {
		return ""
	}

	// Confidence gate
	if !hasPhraseMatch && len(intent.Conditions) == 0 {
		isStrong := func(ns, op string) bool {
			defn := ASDFloorBasis[ns][op]
			defnClean := strings.ReplaceAll(strings.ToLower(defn), "_", " ")
			for _, action := range intent.Actions {
				if strings.ToUpper(action) == op {
					return true
				}
				if strings.ToLower(action) == defnClean && len(action) >= 4 {
					return true
				}
				// Action is a prefix of a definition word (e.g., "temp" starts "temperature")
				for _, dw := range strings.Fields(defnClean) {
					if len(action) >= 4 && strings.HasPrefix(dw, strings.ToLower(action)) && len(dw) >= len(action)+2 {
						return true
					}
				}
				if len(op) >= 3 && strings.HasPrefix(strings.ToUpper(action), op) && len(action) >= len(op)+3 {
					return true
				}
			}
			return false
		}

		defnMatchesContext := func(ns, op string) bool {
			defn := ASDFloorBasis[ns][op]
			defnWords := strings.Fields(strings.ReplaceAll(strings.ToLower(defn), "_", " "))
			if len(defnWords) <= 1 {
				return true
			}
			nlLower := strings.ToLower(nlText)
			qualifiers := []string{}
			for _, w := range defnWords {
				if len(w) > 3 {
					qualifiers = append(qualifiers, w)
				}
			}
			exactMatches := 0
			prefixMatches := 0
			for _, qw := range qualifiers {
				if strings.Contains(nlLower, qw) {
					exactMatches++
				} else {
					for _, nlWord := range strings.Fields(nlLower) {
						if len(nlWord) >= 4 && strings.HasPrefix(qw, nlWord) {
							prefixMatches++
							break
						}
					}
				}
			}
			if exactMatches >= 2 {
				return true
			}
			if exactMatches >= 1 && prefixMatches >= 1 {
				return true
			}
			if prefixMatches >= 1 && len(defnWords) <= 2 {
				return true
			}
			return false
		}

		if len(resolved) == 1 {
			if !isStrong(resolved[0][0], resolved[0][1]) {
				return ""
			}
			if !defnMatchesContext(resolved[0][0], resolved[0][1]) {
				return ""
			}
		} else if len(resolved) == 2 {
			strong := 0
			for _, p := range resolved {
				if isStrong(p[0], p[1]) {
					strong++
				}
			}
			if strong == 0 {
				return ""
			}
		} else if len(resolved) >= 3 {
			strong := 0
			for _, p := range resolved {
				if isStrong(p[0], p[1]) {
					strong++
				}
			}
			nlWordCount := len(strings.Fields(nlText))
			if strong == 0 && nlWordCount < 8 {
				return ""
			}
		}
	}

	// OOV chain gap detection
	if len(resolved) > 0 && !hasPhraseMatch {
		chainSplitRe := regexp.MustCompile(`(?i),\s+then\s+|,\s+and\s+then\s+|\bthen\b|,\s+`)
		segments := chainSplitRe.Split(strings.ToLower(nlText), -1)
		if len(segments) >= 3 {
			unresolved := 0
			for _, seg := range segments {
				s := strings.TrimSpace(seg)
				if s == "" || len(s) < 5 {
					continue
				}
				segHasMatch := false
				for _, p := range resolved {
					defn := ASDFloorBasis[p[0]][p[1]]
					defnWords := strings.Fields(strings.ReplaceAll(strings.ToLower(defn), "_", " "))
					for _, w := range defnWords {
						if len(w) > 3 && strings.Contains(s, w) {
							segHasMatch = true
							break
						}
					}
					if segHasMatch {
						break
					}
				}
				if !segHasMatch {
					unresolved++
				}
			}
			if unresolved > 0 {
				return ""
			}
		}
	}

	// Sort sensing before action
	if len(intent.Conditions) > 0 && len(resolved) > 1 {
		var sensing, acting, other []nsOp
		for _, p := range resolved {
			if sensingNS[p[0]] {
				sensing = append(sensing, p)
			} else if actionNS[p[0]] {
				acting = append(acting, p)
			} else {
				other = append(other, p)
			}
		}
		resolved = append(append(sensing, other...), acting...)
	}

	// Grammar assembly
	frames := make([]string, 0, len(resolved))
	for _, p := range resolved {
		ns, op := p[0], p[1]
		frame := ns + ":" + op

		if ns == "H" && op == "ICD" && intent.Parameters["icd"] != "" {
			frame += "[" + intent.Parameters["icd"] + "]"
		} else if ns == "Z" && op == "TEMP" && intent.Parameters["temperature"] != "" {
			frame += ":" + intent.Parameters["temperature"]
		} else if ns == "Z" && op == "TOPP" && intent.Parameters["top-p"] != "" {
			frame += ":" + intent.Parameters["top-p"]
		}

		validTargets := []string{}
		for _, t := range intent.Targets {
			if !targetFalsePositives[t] {
				validTargets = append(validTargets, t)
			}
		}
		if len(validTargets) > 0 {
			frame += "@" + validTargets[0]
		}
		if ns == "R" && op != "ESTOP" {
			frame += "\u21ba"
		}
		frames = append(frames, frame)
	}

	if len(intent.Conditions) > 0 && len(frames) > 0 {
		frames[0] += intent.Conditions[0]
	}

	var sal string
	if len(frames) == 1 {
		sal = frames[0]
	} else if len(intent.Conditions) > 0 {
		sal = strings.Join(frames, "\u2192")
	} else {
		sal = strings.Join(frames, "\u2227")
	}

	result := ValidateComposition(sal, nlText, c.asd, true, nil)
	if result.Valid {
		return sal
	}

	if len(intent.Conditions) > 0 && len(frames) > 1 {
		parts := make([]string, len(resolved))
		for i, p := range resolved {
			parts[i] = p[0] + ":" + p[1]
		}
		simple := strings.Join(parts, "\u2227")
		r2 := ValidateComposition(simple, nlText, c.asd, true, nil)
		if r2.Valid {
			return simple
		}
	}

	return ""
}

// ComposeOrPassthrough composes SAL or returns the original NL.
// Returns (output, isSAL).
func (c *Composer) ComposeOrPassthrough(nlText string, intent *ComposedIntent) (string, bool) {
	sal := c.Compose(nlText, intent)
	if sal != "" {
		return sal, true
	}
	return nlText, false
}
