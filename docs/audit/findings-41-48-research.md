# OSMP Dictionary & IP Findings Log (Sprint 4 Research Tangent)

**Status**: Research findings, NOT Sprint 4 audit fixes. These are forward-looking improvements and IP coordination tasks that surfaced during the Finding 33 ICD-10-CM work. Log here, act later in dedicated sprints after the Sprint 4 bundle lands.

---

## Finding 41 — SAIL intern table parameterization audit

**Severity**: Architectural (risk, not breakage)
**Priority**: Next audit pass (post Sprint 6)
**Status**: Hold for audit

**Context**: The SAIL codec builds its intern table dynamically from (1) opcode names in the base dictionary Section 3, (2) slot values from MDR dependency rule CSV Section B, and (3) bracket references from Section 5 dependency rules. Phase 1 is shared across all nodes (deterministic). Phases 2 and 3 parameterize the intern table on which MDR CSVs are loaded at codec construction time, which means two nodes with different MDR loadouts cannot round-trip SAIL byte streams.

Today this is narrow — Phase 2 only reads slot values from a handful of CSVs totaling a few hundred strings. But it's a latent brittleness that violates the isomorphism property SAIL promises. The decision not to extend this to dpack contents (discussed in the ICD conversation) was the right call for exactly this reason.

**Open question for the spec**: how should intern table coordination work across nodes? Options:

1. **Hash-based manifest**: each SAIL envelope carries an intern table hash in the header, decoder rejects mismatches
2. **FNP negotiation**: nodes exchange intern table manifests at session establishment and build a shared table
3. **Phase 1 only**: restrict the intern table to the base dictionary, forgoing Phase 2/3 savings in exchange for stable cross-node wire format

**Action**: Write up the tradeoffs in a new ADR, get an answer before any new MDR domain corpus ships.

---

## Finding 42 — Synonym-aware opcode rename sweep (revised with empirical data)

**Severity**: Design improvement
**Priority**: Dedicated v15 dictionary rename sprint, post Sprint 4 bundle
**Status**: Research complete, empirical validation pending

**Design principle (from the readability research)**: the ASD opcode table should follow a preference order when selecting names:

1. **Industry lingua franca** — the canonical shorthand the domain already uses (HR, BP, POS, GRID, STAT, CMD, CFG, ACK, REQ, RESP, INC). Mine these from training-data frequency patterns, not from explicit English expansion.
2. **Existing ASD canonical form** — if a word is already in the table in any namespace and means the same concept, reuse it (F:W → F:PAUSE because C:PAUSE already exists).
3. **Glyph operator** — if a concept is purely structural and the glyph table has it, use the glyph instead of an opcode (? for query).
4. **Full word only when no shorthand exists** — DISCOVER, PROCEED, SAFETY as fallbacks, and prefer DISC, CONT, SFTY when those are more canonical in the target domain.
5. **Single-letter opcodes reserved for cases where the letter IS the canonical symbol** in the domain (§ for human attestation).

**High-confidence rename list** (validated by single-model readability preview, needs multi-model empirical confirmation via `tools/opcode_readability_test.py`):

| Current | Rename to | Reason |
|---|---|---|
| `B:L` (life_safety) | `B:SFTY` | MISS — LEVEL/LOAD/LIGHTING won. SFTY is OSHA/fire-code canonical |
| `D:RT` (return_transmit) | `D:RETX` | MISS — collides with M:RT (route). RETX is networking canonical for retransmit |
| `A:AUTH` (authorization_assertion) | `A:AUTHZ` | IN_TOP3 — AuthN won over AuthZ. AUTHZ is OAuth/RBAC canonical spelling for the authorization distinction |
| `B:BS` (building_sector) | `B:SECT` | IN_TOP3 — BASE_STATION won. SECT is military/civil planning canonical |
| `E:OBS` (obstacle) | `E:OBS` kept + add `E:OBSV` | SPLIT — OBS IS canonical for obstacle in NOTAMs/SLAM but OBSERVATION came first in readability test. Keep both meanings as distinct opcodes |
| `M:MA` (municipal_alert) | merge into `M:ALERT` | IN_TOP3 + duplicate concept with M:A |
| `M:A` (alert_alarm) | keep as `M:ALERT` | Consolidation target for M:MA merger |
| `N:PR` (primary_relay) | `N:RELAY` | IN_TOP3 — PRIORITY won (collides with > glyph). RELAY is networking canonical |
| `O:AUTH` (authority_level) | `O:RANK` | IN_TOP3 — AUTHORIZATION won (collides with A:AUTH). RANK is military/command canonical |
| `R:DISP` (display_brightness) | merge into `R:SCRN` | Clay's call: SCRN[0]=off, SCRN[20]=20% brightness, SCRN[100]=max. One opcode covers on/off and brightness via slot value |

**Net opcode count change**: -3 to -4 (342 → 338 or 339)
- Remove: D:Q, F:Q, O:TYPE, M:MA (merged), R:DISP (merged)
- Add: E:OBSV (split from E:OBS)
- Rename-only: the rest

**Whitepaper & patent coordination required**: 342 appears in the whitepaper, MCP `osmp://about` resource, system prompt, patent claims (if any claim the count), and test assertions. A rename sprint MUST coordinate with whitepaper revision and any necessary CIP amendment in a single patent prosecution pass.

---

## Finding 43 — Y:STAT → Y:UTIL (semantic correctness fix)

**Severity**: Minor, but the meaning is wrong for the name
**Priority**: Include in v15 rename sprint
**Status**: Ready

The current Y:STAT maps to "report_memory_utilization" — but STAT is the canonical shorthand for STATUS, not for UTIL. A memory subsystem reporting "stat" would naturally mean "status of memory" (healthy, degraded, error). Reporting "util" would mean "how much memory is in use" (percentage, bytes, free/used). These are different concepts.

**Rename**: Y:STAT → Y:UTIL. UTIL is Unix-canonical for utilization (iostat `%util` column, CPU util, GPU util, disk util). Frees the Y:STAT slot for actual memory status reporting if that concept is ever needed.

---

## Finding 44 — Q opcodes redundant with `?` glyph operator

**Severity**: Structural redundancy
**Priority**: Include in v15 rename sprint
**Status**: Ready, with caveat

The glyph operator table already defines `?` as the canonical QUERY marker. Having `D:Q`, `F:Q`, and `N:Q` as separate opcodes meaning "query" duplicates the glyph.

**Action**:
- **Remove** `D:Q` and `F:Q`. Queries on data transfer become `D:PULL?` or `D:STAT?` using the glyph as a suffix modifier on the actual action
- **Rename** `N:Q` to `N:DISC`. Peer discovery is semantically distinct from generic query — it's an active probe (mDNS, DHCP-DISCOVER, Bluetooth, WiFi probe request), not a passive question. DISC is the networking lingua franca for this concept.

**Caveat**: The single-model readability preview showed `N:Q` correctly reads as QUERY with namespace context. The removal argument is about structural elegance (one canonical way to express a concept), not about readability. Multi-model empirical validation before execution.

---

## Finding 45 — "Frequency-Aligned Lingua Franca" design principle

**Severity**: Strategic / IP
**Priority**: Patent attorney coordination required BEFORE any action
**Status**: IP research task, do NOT include in code or bundle

**The thesis**: OSMP's ASD opcode table is deliberately aligned to the statistical mode of human shorthand as reflected in LLM training distributions. As model families train on increasingly similar internet crawls, they converge toward a shared vocabulary of shorthand. Aligning a protocol's symbol table to that convergence point gives the protocol forward-compatibility across model generations — no fine-tuning required, no model-specific adapters. The bridge function is what makes this work: it translates between OSMP-native agents and non-OSMP peers, and the bridge efficiency is maximized when the opcodes are already recognizable to the peer's base model.

### Finding 45a — Prior art and FTO search

**Task**: Before any whitepaper amendment or CIP claim based on the Frequency-Aligned Lingua Franca principle, run a formal prior art and Freedom-to-Operate search.

**Search targets**:
- USPTO/EPO/WIPO: "protocol opcode natural language alignment", "agent communication protocol lingua franca", "LLM-friendly API design"
- Academic: ACL/EMNLP papers on prompt engineering conventions, vocabulary alignment, API design for LLM consumption
- Adjacent prior art to rule out: OpenAI Function Calling spec, Anthropic Tool Use / MCP spec, JSON-RPC, LangChain agent spec, BabyAGI, AutoGPT, any "structured prompt" or "tool calling schema" patents
- Adjacent fields for obviousness: compiler design symbol tables, DSL design, API documentation conventions

**Novelty frame to test**: NOT "using shorthand in protocols" (obvious) but **"deliberately aligning a protocol symbol table to the statistical mode of a target model's training distribution, as a deployment strategy that substitutes for model fine-tuning in environments where fine-tuning is unavailable."** The substitution-for-fine-tuning angle is the potentially novel element.

**Budget**: Attorney hours, ~4-8 hours for a preliminary search.

### Finding 45b — Audit existing prov/util for over-claimed opcodes

**Task**: Before any claim amendment, grep UTIL v20 and CIP v15 for specific opcode strings appearing as "novel" or "inventive" elements. If any opcode is claimed as unique and it's actually just mined from common shorthand (HR, BP, STAT, CMD, ACK, etc.), that claim is vulnerable to anticipation or 103 obviousness.

**Specific opcodes to check**: E:OBS, M:MA, M:IT, N:PR, N:S, D:RT, O:AUTH, any single-letter opcode, any opcode using domain-lingua-franca shorthand (HR, BP, POS, STAT, CMD, ACK, CFG, REQ, RESP, ENV).

**Action**: Separate the claims that are about the GRAMMAR (deterministic parsing, consequence class requirement, dependency rule logic, bridge function architecture) from claims that are about the SYMBOLS (specific opcode letters). Grammar claims are strong. Symbol claims are the risk. Symbol claims should be broadened to claim the pattern of selection (frequency-aligned choice), not the specific letters, OR dropped entirely.

### Finding 45c — Reframe claims around the bridge function

**Proposal**: The novel element worth claiming is the **SALBridge** — the boundary translator that enables OSMP-to-non-OSMP interoperation without model cooperation. Frame the symbol table alignment as a design optimization of the bridge efficiency, not as a separable invention. Questions for the patent attorney:

1. Is the bridge function novel given the known prior art on agent-to-agent translation layers?
2. Can the claims cover "bi-directional protocol translation between a semantic assembly language and arbitrary natural-language-capable peers" without tripping over existing translation patents?
3. Does claiming frequency-aligned symbol selection as a dependent claim (optimization of bridge efficiency) make the bridge claim stronger or weaker?

**Status**: Attorney conversation, not engineering work.

---

## Finding 46 — F namespace fundamentally mismatched to food/ag lingua franca

**Severity**: Architectural
**Priority**: HOLD for research, ACT in the v15 rename sprint
**Status**: Research hold

**Evidence from readability preview**:

| Current | Model's first guess | Current meaning |
|---|---|---|
| `F:PRO` | PRODUCE | proceed_protocol |
| `F:Q` | QUALITY | query_request |
| `F:W` | WATER | wait |
| `F:AV` | (not tested but likely AVIAN/AUDIOVISUAL) | authorization |

The F namespace has 4 opcodes and **all 4 appear to be misaligned** to what an agricultural practitioner would expect. The F namespace as currently designed is a thin wrapper around generic protocol operations with a food prefix, not a real domain vocabulary.

**Research task**: Before acting, survey actual food/ag operational vocabulary:
- USDA, FDA food safety reporting codes
- FAO agricultural terminology
- Precision agriculture protocol vocabulary (John Deere, Climate Fieldview, Trimble)
- Farm management software data schemas
- Food traceability standards (GS1, HACCP codes)

**Proposed redesign** (pending research validation):
- Remove: F:PRO, F:Q, F:W, F:AV (the generic protocol ops — move those operations to D/A/I namespaces if still needed)
- Add real domain opcodes:
  - `F:PRODUCE` — production output metric
  - `F:QUAL` — quality grade (fresh, graded, spoiled)
  - `F:WATER` — irrigation state / water schedule
  - `F:YIELD` — yield per unit area
  - `F:HARVEST` — harvest event / schedule
  - `F:IRRIGATE` — irrigation command
  - `F:PEST` — pest detection / pesticide application
  - `F:SOIL` — soil sensor reading
  - `F:CROP` — crop identity / growth stage

**Action sequence**: Research first (not audit fix), then propose redesign in a new ADR, then execute in v15 rename sprint as a coordinated namespace refactor alongside Finding 42.

---

## Finding 47 — Multi-model empirical validation of readability tests

**Severity**: Research infrastructure
**Priority**: Before v15 rename sprint
**Status**: Tool ready, needs API keys and real run

**Context**: `tools/opcode_readability_test.py` exists in the working copy as of this session (Finding 45 tangent). It supports Anthropic and OpenAI providers, CSV output, dry-run mode, filtering by namespace / opcode / flagged-subset, and a semantic-judgment pass (opt-in via `--semantic-judgment`) that fixes false positives and negatives in the string-token classifier.

**The preview run was single-model (Sonnet 4.6, sample-of-1 via inline simulation).** Before acting on Finding 42 renames, a real multi-model run is required.

**Required runs**:
1. Sonnet 4.6 with `--semantic-judgment` against all flagged opcodes (50+) — canonical baseline
2. Haiku 4.5 same — intra-family check
3. GPT-4o same — cross-family check (requires OPENAI_API_KEY which doesn't exist in working copy)
4. Gemini same if possible — third family
5. Aggregate: for each opcode, compute the agreement rate across all models. An opcode that's AGREE across all 3-4 models is validated canonical. An opcode that MISSes in multiple models is a strong rename candidate. An opcode with mixed results needs manual review.

**Output artifact**: `reports/opcode-readability-v14-aggregated.csv` with columns (namespace, opcode, current_meaning, sonnet_classification, haiku_classification, gpt4o_classification, gemini_classification, aggregate_score, rename_suggestion).

**Cost estimate**: ~50 opcodes × 4 models × 2 API calls (guess + semantic judgment) = ~400 API calls total. Under $5 across all providers.

**Reusability**: The harness becomes permanent infrastructure. Every new opcode addition or rename triggers a re-run. Every new model release triggers a re-run. The harness IS the empirical backstop for the Frequency-Aligned Lingua Franca principle.

---

## Finding 48 — Bridge `_is_pure_sal` substring-match bug (CRITICAL, fixed in Sprint 4)

**Severity**: Cross-SDK functional bug
**Priority**: FIXED in Sprint 4 (Python and TypeScript)
**Status**: Resolved with regression tests

**Context**: The bridge has two responsibilities for inbound messages: (1) detect SAL fragments via `_detect_sal_frames`, and (2) decide whether the message is "pure SAL" (route to `result.sal`) or "mixed-mode" (route to `result.nl` with detected frames listed in `result.detected_frames`). Finding 48 is a bug in the second decision.

**The bug**: Both `bridge.py:_is_pure_sal` (Python) and `bridge.ts:isPureSal` (TypeScript) used substring search (`re.search()` in Python, `regex.test()` in JavaScript) to verify each frame was valid SAL. Substring search returns True if the regex matches anywhere in the string, so a natural language message like `"authorize via I:§ before proceeding"` passed the check because it contains `I:§`. The result: the bridge classified the entire NL message as pure SAL, routed it to `result.sal`, and emptied `result.detected_frames`. Mixed-mode routing was completely broken for any message containing a SAL substring.

The Python composition validator returned a `MIXED_MODE` warning for these cases but `result.valid` stayed True (warnings aren't errors), so the secondary validation pass didn't catch the issue either.

**How it surfaced**: While writing the Finding 37 TypeScript bridge integration tests, the smoking-gun assertion `bridge.receive("authorize via I:§ before proceeding", peerId).detectedFrames.includes("I:§")` failed. Direct testing of the regex layer showed the regex matched `I:§` correctly. Side-by-side reproduction in Python confirmed both SDKs had identical broken behavior.

**Why the existing tests missed it**: The Sprint 2 Finding 13 regression tests in `tests/test_bridge_frame_detection.py` tested `_detect_sal_frames` directly (the regex layer) but never tested the end-to-end `bridge.receive()` path. Unit tests at the regex layer don't catch bugs in consumers of the regex.

**The fix** (applied in both SDKs):

1. Strip every full SAL frame (with `@target`, `?query`, `:slot`, `[bracket]`, and consequence class glyph tail) from the message using a comprehensive frame-with-tail regex
2. Strip chain operators (`→ ∧ ∨ ↔ ∥ ⟳ ≠ ⊕ ¬ ;`), parentheses, and whitespace
3. If any residue remains, the message is NOT pure SAL (NL prose remained after stripping)
4. Second pass: every recognized frame must validate cleanly under composition rules with NO `MIXED_MODE` warnings (warnings now treated as failures for the pure-SAL classification gate)

**Files changed**:
- `sdk/python/osmp/bridge.py` — `_is_pure_sal` rewritten, added `_NS_PATTERN`/`_OPCODE_PATTERN` imports
- `sdk/typescript/src/bridge.ts` — `isPureSal` rewritten, added `NS_PATTERN`/`OPCODE_PATTERN` imports
- `tests/test_bridge_pure_sal.py` — NEW, 15 regression tests covering NL+SAL rejection, pure SAL recognition, edge cases, marker test
- `sdk/typescript/tests/bridge.test.ts` — Already in Finding 37 work, contains the cross-SDK equivalent bridge integration tests including the I:§ smoking gun

**Test results**: Both SDKs now correctly classify mixed-mode messages and route them through the right code path. Python: **513 tests passing** (498 + 15 new). TypeScript: **89 tests passing** including the bridge integration suite.

**Lesson**: End-to-end integration tests catch a different class of bugs than unit tests. The Sprint 2 work for Finding 13 had thorough regex-layer unit tests but no integration tests, which let this consumer-side bug ship undetected for the entire interval between Sprint 2 and Sprint 4. The TypeScript test infrastructure work for Finding 37 was indirectly the audit step that surfaced it. **Going forward, every cross-SDK behavioral fix should include both a regex-layer test AND an integration test through the consumer.**

