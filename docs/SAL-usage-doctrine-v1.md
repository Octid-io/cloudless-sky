# SAL Usage Doctrine v1.0

## Octid Semantic Mesh Protocol -- Composition and Selection Logic for LLM Agents

**Status:** Normative supplement to MCP server system prompt
**Scope:** Teaches an LLM how to SELECT opcodes from the ASD, not just how to FORMAT them
**Prerequisite:** Agent must have access to osmp_lookup, osmp_encode, osmp_decode, and osmp_discover tools
**Architect:** Clay Holberg
**Protocol:** OSMP v1.0 | Patent pending | Apache 2.0 with express patent grant

**Architectural Layer Separation:** This document governs agent-layer composition behavior. It does not modify protocol-layer decode properties. Decode remains inference-free table lookup per UTIL Claim 1. Composition uses the agent's native inference capability, constrained by these rules. The agent is a dictionary consumer, not a dictionary author. Dictionary authorship is a sovereign node operator function exercised through FNP, MDR registration, or local Omega registration. The agent composes from what exists in the local ASD at the moment of composition, no more, no less.

| Operation | Layer | Inference required? |
|---|---|---|
| Decode (SAL to meaning) | Protocol | No. Table lookup against ASD. |
| Lookup (is this opcode in the ASD?) | Protocol | No. Dictionary search. |
| Compose (NL to SAL) | Agent | Yes. LLM inference, constrained by grammar enforcement rules. |
| Selection (which opcode is correct?) | Agent | Yes. Domain context evaluation, constrained by namespace selection rules. |
| Boundary detection (SAL vs NL_PASSTHROUGH) | Agent | Yes. LLM evaluates lookup results and applies cascade rules. |

---

## Part I: The Usage Doctrine

Grammar tells you how to write a sentence. Usage tells you which sentence to write.

The SAL grammar (EBNF) defines legal instruction structure. The ASD dictionary defines the vocabulary. This doctrine defines the decision logic an LLM must follow to compose conformant SAL from arbitrary natural language input. Every composition decision follows this doctrine. No exceptions.

### Section 1: The Composition Decision Tree

When given natural language to encode as SAL, execute these steps in order. Do not skip steps. Do not reorder steps.

**STEP 1: DECOMPOSE**

Parse the natural language into semantic units:

| Unit Type | What to extract | Example from "If heart rate exceeds 120, file a casualty report and evacuate all nodes" |
|---|---|---|
| Actions | Imperative verbs and their objects | "file a casualty report", "evacuate" |
| Conditions | If/when/unless clauses, thresholds | "heart rate exceeds 120" |
| Targets | Who or what receives the action | "all nodes" |
| Parameters | Numeric values, codes, identifiers | "120" |
| Relationships | Logical connectives between actions | "if...then", "and" |

**STEP 2: CLASSIFY EACH SEMANTIC UNIT**

For each unit, determine its SAL role:

| If the unit is... | It maps to... |
|---|---|
| An action or instruction | An opcode candidate (search ASD) |
| A domain entity or measurement | A namespace + opcode candidate |
| A logical relationship between units | A glyph operator |
| A numeric value, code, or identifier | A slot value in brackets |
| A recipient or destination | A target after @ |
| Outside all of the above | A potential NL_PASSTHROUGH trigger |

**STEP 3: SEARCH THE ASD -- MANDATORY**

For every opcode candidate, call osmp_lookup. This is not optional. This is not a suggestion. You must confirm the opcode exists before using it. If you compose SAL containing an opcode you did not verify against the ASD, the instruction is non-conformant.

Three outcomes are possible:

| Outcome | Action |
|---|---|
| Exactly one match | Use it. Proceed to Step 5. |
| Multiple matches across namespaces | Proceed to Step 4 (Namespace Selection). |
| Zero matches | Proceed to Step 6 (Boundary Detection). |

**STEP 4: NAMESPACE SELECTION**

When the same concept maps to opcodes in multiple namespaces, the domain context of the natural language input determines which namespace is correct. The following table defines the selection hierarchy for the most common collision cases:

| Concept | Context Clue | Correct Namespace | Wrong Namespace | Why |
|---|---|---|---|---|
| temperature | patient, body, clinical, vital | H:TEMP | E:TH, W:TEMP, Z:TEMP | Clinical measurement is H namespace |
| temperature | room, sensor, device, ambient (indoor) | E:TH | H:TEMP, W:TEMP | Local sensor telemetry is E namespace |
| temperature | weather, outside, forecast, ambient (outdoor) | W:TEMP | E:TH, H:TEMP | External weather data is W namespace |
| temperature | model, sampling, inference, LLM | Z:TEMP | E:TH, H:TEMP, W:TEMP | Inference parameter is Z namespace |
| alert | patient, threshold, vitals, clinical | H:ALERT | L:ALERT, W:ALERT, U:ALERT | Clinical threshold crossing is H |
| alert | compliance, audit, log, regulation | L:ALERT | H:ALERT, W:ALERT | Compliance alert is L |
| alert | weather, storm, flood, fire (weather) | W:ALERT | H:ALERT, L:ALERT | Weather advisory is W |
| alert | operator, user, notification, display | U:ALERT | H:ALERT, L:ALERT | Human-facing notification is U |
| alert | municipal, city, emergency, public | M:A | H:ALERT, U:ALERT | Municipal alarm is M |
| status | compute, process, container, resource | C:STAT | R:STAT, J:STATUS | Compute resource is C |
| status | robot, drone, vehicle (physical agent) | R:STAT | C:STAT, V:STATUS | Physical agent is R |
| status | task, goal, plan, cognitive | J:STATUS | C:STAT, R:STAT | Agent execution state is J |
| status | vessel, ship, fleet, maritime | V:STATUS | R:STAT | Transport fleet is V |
| status | maintenance, repair, procedure | P:STAT | C:STAT | Procedure completion is P |
| stop | robot, motor, physical, movement | R:STOP | Z:STOP | Physical agent halt is R |
| stop | inference, generation, tokens, model | Z:STOP | R:STOP | Inference termination is Z |
| stop | emergency, immediate, all-override | R:ESTOP | R:STOP | Emergency overrides everything |
| wind | generation, turbine, power, energy | X:WIND | W:WIND | Energy generation is X |
| wind | weather, speed, direction, gust | W:WIND | X:WIND | Meteorological observation is W |
| store | memory, context, agent, episodic | Y:STORE | X:STORE | Agent memory is Y |
| store | battery, energy, grid, charge | X:STORE | Y:STORE | Energy storage is X |
| verify | signature, cryptographic, hash | S:VFY | A:VERIFY, Q:VERIFY | Cryptographic verification is S |
| verify | output quality, claim, grounding | Q:VERIFY | S:VFY, A:VERIFY | Quality verification is Q |
| verify | general agent output, request | A:VERIFY | S:VFY | General agent request is A |
| handoff | task, execution, agent, cognitive | J:HANDOFF | R:HANDOFF | Agent execution transfer is J |
| handoff | authority, control, physical | R:HANDOFF | J:HANDOFF | Physical authority transfer is R |
| embed | storage, memory, index | Y:EMBED | Z:EMBED | Store embedding is Y |
| embed | generate, create, compute | Z:EMBED | Y:EMBED | Generate embedding is Z |
| acknowledge | protocol, atomic policy, NACK complement, machine | A:ACK | U:ACK | Machine protocol acknowledgment is A |
| acknowledge | human, receipt, confirm, business communication | U:ACK | A:ACK | Human acknowledgment is U |
| acknowledge | no clear protocol or human context | NL_PASSTHROUGH | A:ACK, U:ACK | Ambiguous. Do not default to the shorter opcode. |

**Global Namespace Discrimination Principles:**

These principles override the collision table when the table doesn't have a specific entry. They're the rules behind the table, not exceptions to it.

**Principle 1: Operational event vs. external data product.** Four namespaces report about the physical world, but from different vantage points. Confusing them is the most common namespace crosswire.

| Namespace | Vantage | Ask yourself |
|---|---|---|
| E (Environmental/Sensor) | Local instrument reading. Your sensor, your node, right now. | "Is a sensor I control producing this data?" |
| W (Weather/External) | External data product. NWS, NOAA, WMO, METAR. Published by an authority, received by you. | "Am I receiving this from an external weather service?" |
| B (Building) | Event in a structure. Fire alarm, HVAC fault, access point breach. | "Is something happening to or inside a building?" |
| M (Municipal) | Operational response to an event. Evacuation, incident command, alert to the public. | "Is this an emergency management action or public alert?" |

A building is on fire: B:BA (building alert) + M:EVA (evacuation). The National Weather Service issues a fire weather watch: W:FIRE. A temperature sensor on your node reads 38C: E:TH. The NWS publishes an ambient temperature advisory: W:TEMP. This principle applies to every hazard type (fire, flood, wind, structural) not just the ones in the collision table.

**Principle 2: Definition match, not mnemonic match.** When an English word in the natural language input matches an opcode mnemonic, the match is only valid if the ASD definition's operational context matches the natural language usage context. If the definition context diverges from the usage context, the mnemonic match is a false positive and the opcode must not be used.

This is a composition gate, not a suggestion. Examples:

| English word | Mnemonic match | ASD definition context | NL usage context | Valid match? |
|---|---|---|---|---|
| "acknowledge" | A:ACK | Protocol-level machine acknowledgment, NACK complement, Atomic policy | Human business communication ("acknowledge receipt") | No. False positive. |
| "order" | K:ORD | Financial order entry, ISO 20022/FIX/SWIFT | Food ordering | No. False positive. |
| "summarize" | A:SUM | Condense information, agent output compression | Condense information | Yes. Contexts align. |
| "sign" | S:SIGN | Cryptographic digital signature | Legal document signing | No. False positive. |
| "stop" | R:STOP | Physical agent halt | "Stop talking" | No. False positive. |
| "cost" | Z:COST | Inference cost report (API billing) | General cost calculation | No. False positive. |
| "observation" | E:OBS | Obstacle detection (physical obstruction) | Sensor observation / measurement | No. False positive. OBS is obstacle, not observation. |

Mnemonic similarity is not definition match. The abbreviation may look like your word but mean something different. E:OBS does not mean "observation." It means "obstacle." A:CMP does not mean "compute." It means "compress/compare." Read the definition every time.

The test: read the ASD definition out loud. Does it describe what the human actually meant? If not, the opcode does not apply, regardless of how closely the mnemonic matches.

**Selection rules when the table and principles above do not cover the case:**

1. **Specificity wins.** If one namespace is domain-specific to the context and another is general-purpose, use the domain-specific one. H (clinical) is more specific than A (agentic) for health concepts. K (financial) is more specific than A for transaction concepts.

2. **The namespace description is the tiebreaker.** Each namespace has a domain label in the ASD. If the natural language input falls squarely within one domain label and only tangentially within another, use the squarely matching one.

3. **When genuinely ambiguous, prefer the namespace that produces the shorter encoding.** If "alert" could be H:ALERT or U:ALERT and context does not clearly favor one, both are valid. Choose the one that produces fewer bytes. If equal, use whichever namespace appears first alphabetically.

4. **Never cross namespaces within a single frame.** A frame_id is one namespace prefix, one colon, one opcode. The target after @ is a node_id or wildcard, never another namespace:opcode. Chain separate frames with operators.

**STEP 5: COMPOSE THE INSTRUCTION**

Assemble the SAL instruction using these composition rules:

| Natural Language Pattern | SAL Operator | Example |
|---|---|---|
| "if X then Y" / "when X, Y" / "X triggers Y" | → (THEN) | H:HR@NODE1>120→H:CASREP |
| "X and Y" / "X plus Y" / "both X and Y" | ∧ (AND) | H:CASREP∧M:EVA@* |
| "X or Y" / "either X or Y" | ∨ (OR) | R:RTH@⌂∨R:LAND |
| "X then Y then Z" (ordered, non-conditional) | ; (SEQUENCE) | S:ENC;D:PUSH@NODE2;L:AUDIT |
| "X and Y simultaneously" / "at the same time" | ∥ (PARALLEL) | A∥[?WEA∧?NEWS] |
| "if and only if" / "exactly when" | ↔ (IFF) | K:PAY@RECV↔I:§ |
| "unless X" / "except when X" | ¬→ (UNLESS) | R:↺MOV@WPT1¬→E:OBS |
| "for all" / "every" / "each" | ∀ (FOR-ALL) | ∀R:STAT? |
| "any" / "at least one" / "there exists" | ∃ (EXISTS) | ∃N:INET |
| "approximately" / "about" / "roughly" | ~ (APPROX) | E:TH~22 |
| "every N minutes/hours" / "recurring" | ⟳ (REPEAT-EVERY) | E:EQ@4A?TH:0⟳[300] |
| "not X" / "excluding X" | ¬ (NOT) | ¬H:TRIAGE:B |
| "ranked" / "in priority order" | ⊕ (PRIORITY-ORDER) | R:RTH@⌂⊕R:LAND⊕R:STOP |
| "prefer X over Y" / "X first, then Y" | > (PRIORITY) | R:RTH@⌂>R:LAND |

**Composition ordering rules:**

1. **Conditions precede actions.** The condition frame appears left of →, the action frame appears right. "If heart rate exceeds 120, evacuate" is `H:HR@NODE1>120→M:EVA@*`, not `M:EVA@*→H:HR@NODE1>120`.

2. **Qualifiers precede the qualified.** Identity verification precedes the action it gates. `I:§→R:⚠MOV` means "human confirms, then hazardous move." Not the reverse.

3. **Layer 2 accessors are standalone frames, not target parameters.** H:ICD[J083] is its own frame in a chain. It is never a target: `H:ICD[J083]→H:CASREP→M:EVA@MEDEVAC` is correct. `H:CASREP@H:ICD[J083]` is wrong. The @ operator takes a node_id or wildcard, never a namespace:opcode.

4. **R namespace instructions require consequence class designators.** Every R namespace instruction must carry ⚠ (HAZARDOUS), ↺ (REVERSIBLE), or ⊘ (IRREVERSIBLE). Omitting this makes the instruction malformed. ⚠ and ⊘ require I:§ as a structural precondition. Exception: R:ESTOP requires no consequence class and no I:§.

5. **One semantic declaration per frame.** If you need to assert two things, use two frames joined by an operator. Do not overload a single frame with multiple semantic claims.

**STEP 6: BOUNDARY DETECTION -- WHEN NOT TO COMPOSE SAL**

This is the most critical step. The failure mode that prompted this doctrine is an LLM attempting to compose SAL for concepts outside the ASD vocabulary. The "order me some tacos" test: the correct encoding is NL_PASSTHROUGH. The incorrect response is any SAL composition, including K:ORD (which is financial order entry, not food ordering).

**Rule 6.1: The Core Action Test.** Identify the core imperative action in the natural language. Search the ASD for that action. If no opcode maps to the core action, the entire instruction is NL_PASSTHROUGH. Do not compose SAL around the periphery of an instruction whose core action is unmapped.

| Natural Language | Core Action | ASD Match? | Correct Encoding |
|---|---|---|---|
| "Order me some tacos" | order food | No. K:ORD is financial order entry. | NL_PASSTHROUGH |
| "Book a flight to Denver" | book a flight | No. No travel booking opcode. | NL_PASSTHROUGH |
| "Send an email to the team" | send email | No. No email opcode. | NL_PASSTHROUGH |
| "Summarize the quarterly report" | summarize | Yes. A:SUM. | A:SUM[quarterly report] |
| "Check the patient's heart rate" | check heart rate | Yes. H:HR. | H:HR@PATIENT1? or ?H:HR@PATIENT1 |
| "Encrypt the payload" | encrypt | Yes. S:ENC. | S:ENC |
| "Evacuate all building sectors" | evacuate | Yes. M:EVA. | M:EVA@* |

**Rule 6.2: Domain Coverage Test.** If the core action maps to an opcode but the domain qualifier does not, encode only what maps. Use string literals in slot brackets for unmapped qualifiers.

| Natural Language | Mapped | Unmapped | Correct Encoding |
|---|---|---|---|
| "Set inference temperature to 0.7" | Z:TEMP (inference temperature) | 0.7 (numeric value) | Z:TEMP:0.7 (value goes in slot) |
| "Navigate to waypoint BRAVO" | R:WPT (waypoint) | BRAVO (identifier) | R:WPT[BRAVO] (identifier in brackets) |
| "Log compliance event for HIPAA Section 164.312" | L:AUDIT (audit log entry) | HIPAA section ref | L:AUDIT[HIPAA-164.312] |

**Rule 6.3: The Lookup Cascade and Omega Resolution.** The agent's composition scope is exactly the current dictionary state of the node it's running on. The agent is a dictionary consumer, not a dictionary author. The cascade:

1. Agent invokes osmp_lookup against the full local ASD. The ASD includes all tiers: Tier 1 (A-Z standard namespaces), Tier 2 (registered double-Latin prefixes), and any Omega entries the sovereign node operator has previously registered. The agent does not distinguish between tiers during lookup. An opcode is an opcode regardless of its tier provenance.

2. If lookup resolves at any tier: compose using the returned opcodes. The entry's provenance (Tier 1, Tier 2, or Omega) is invisible to the composition logic. An Omega entry that exists in the local ASD resolves and composes identically to a Tier 1 entry.

3. If lookup resolves nothing at any tier: the agent evaluates the operational context.

   a. If the concept is operationally critical (recurring, bandwidth-relevant, domain-specific) and the session has HITL capability, the agent MAY surface a vocabulary gap proposal to the human operator: "No ASD entry covers [concept]. This appears to be a recurring [domain] operation. Would you like me to propose an Omega entry for this?" If the human approves, the agent drafts the entry following the Omega MDR Guide (opcode, definition, slot values, namespace alignment), the human reviews and confirms the draft, the entry registers in the local ASD, and ADP proliferates it through the mesh. The agent then composes against the newly registered entry. The agent never writes to the ASD without human approval. The human confirmation is a structural precondition, not a courtesy notification.

   b. If the human declines the proposal, or no HITL is available, or the concept is casual, one-off, or not bandwidth-critical: NL_PASSTHROUGH.

4. The agent never composes against an opcode that does not exist in the ASD at the moment of composition. The agent never hypothesizes an Omega entry into existence. The agent never emits an Omega-prefixed opcode that it did not discover via lookup or that was not just registered through the HITL approval gate.

| Scenario | Resolution | Path |
|---|---|---|
| "Check heart rate" (H:HR exists in ASD) | Compose H:HR | Lookup hit at Tier 1 |
| "Report soil moisture" (sovereign node operator previously registered Omega:SOIL) | Compose Omega:SOIL | Lookup hit at Omega tier |
| "Report soil moisture" (no Omega:SOIL registered, recurring sensor op, HITL available) | Agent proposes Omega entry, human approves, register, compose | HITL Omega proposal |
| "Report soil moisture" (no Omega:SOIL registered, no HITL available) | NL_PASSTHROUGH | Cascade exhausted |
| "Order me some tacos" (no entry at any tier, not operationally critical) | NL_PASSTHROUGH | No domain mapping, no proposal warranted |
| One-off conversational remark | NL_PASSTHROUGH | Casual, no recurrence |
| Mid-operation vocabulary gap (e.g., air tanker coordination not in ASD) | Agent proposes Omega entry, human approves | HITL Omega proposal for operational need |

**Constraint on in-flight Omega entries:** Entries created through the HITL Omega proposal during operations carry a provisional status. They resolve normally on lookup, compose normally, and proliferate normally via ADP. But they surface for review in post-mission debrief. The sovereign node operator can then promote them to permanent, revise them, or deprecate them. This closes the quality loop on entries drafted under operational time pressure.

**Rule 6.4: The Byte Check.** After composing SAL, count the UTF-8 bytes. If the SAL encoding is longer than or equal to the natural language, use NL_PASSTHROUGH. BAEL exists to guarantee that OSMP encoding never inflates the message. This rule has no exceptions.

```
SAL_bytes = len(sal_string.encode('utf-8'))
NL_bytes = len(nl_string.encode('utf-8'))
if SAL_bytes >= NL_bytes:
    use NL_PASSTHROUGH
```

**Rule 6.5: The Semantic Fidelity Test.** After composing SAL, decode it back to natural language using the ASD. If the decoded meaning diverges from the original intent, the encoding is wrong. Either recompose or use NL_PASSTHROUGH. An instruction that decodes to something other than what was intended is worse than NL_PASSTHROUGH, because it will be executed as decoded, not as intended.

### Section 2: Prohibited Composition Patterns

These patterns are always wrong. If you find yourself composing one, stop and reconsider.

**PROHIBIT-01: Hallucinated Opcodes.** Never use an opcode that does not appear in the ASD. If osmp_lookup returns zero results for your opcode candidate, the opcode does not exist. Do not invent opcodes. Do not assume opcodes exist because they seem logical. The ASD is the single source of truth. Examples of hallucinated opcodes: K:TACO, R:FLY, U:EMAIL, D:DOWNLOAD, A:SEARCH.

**PROHIBIT-02: Namespace as Target.** The @ operator takes a node_id or the * wildcard. It never takes a namespace:opcode. `H:CASREP@H:ICD[J083]` is wrong. `H:ICD[J083]→H:CASREP` is correct.

**PROHIBIT-03: Slash as Operator.** The / character is not a SAL operator. Never use it. If you mean "or", use ∨. If you mean namespace separation, use :. There is no context in which / is valid SAL.

**PROHIBIT-04: Forced Fit.** If the natural language concept does not map to the ASD, do not force it into the closest-sounding opcode. K:ORD is "financial order entry" drawn from ISO 20022/FIX/SWIFT. It is not "order food." A:SUM is "summarize" (as in condense information). It is not "sum" (as in arithmetic addition). S:SIGN is "cryptographic signature." It is not "sign a document" in the legal sense. Read the definition in the ASD, not just the mnemonic.

**PROHIBIT-05: Mixed-Mode Frames.** A SAL instruction is either FULL_OSMP or NL_PASSTHROUGH. You cannot embed natural language inside a SAL frame or embed a SAL opcode inside a natural language sentence. The BAEL mode flag applies to the entire payload.

**PROHIBIT-06: Consequence Class Omission on R Namespace.** Every R namespace instruction except R:ESTOP must carry a consequence class designator (⚠, ↺, or ⊘). `R:MOV@WPT1` is malformed. `R:↺MOV@WPT1` or `R:⚠MOV@WPT1` is correct.

**PROHIBIT-07: Unauthorized Hazardous Action.** R namespace instructions carrying ⚠ (HAZARDOUS) or ⊘ (IRREVERSIBLE) require I:§ as a structural precondition. `R:⚠MOV@WPT1` without preceding `I:§→` is incomplete. The complete instruction is `I:§→R:⚠MOV@WPT1`.

**PROHIBIT-08: Autonomous Omega Creation.** The agent never emits an Omega-prefixed opcode that does not exist in the local ASD at the moment of composition. The agent is a dictionary consumer, not a dictionary author. If the agent determines that a concept warrants an Omega entry, it proposes the entry to the human operator through the HITL gate. The human approves, the entry registers, and only then does the agent compose against it. The agent never bypasses this gate by emitting `Ω:ANYTHING` speculatively. Emitting an unregistered Omega opcode is functionally identical to hallucinating an opcode: the receiving node cannot decode it. The Omega prefix provides no protection against this failure.

### Section 3: Disambiguation Heuristics

When multiple valid SAL encodings exist for the same natural language and the selection rules in Step 4 do not resolve the ambiguity, apply these heuristics in priority order:

1. **Prefer the encoding that produces fewer UTF-8 bytes.** OSMP exists to compress. The shorter encoding is preferred, all else equal.

2. **Prefer Layer 1 opcodes over Layer 2 accessors.** Layer 1 opcodes resolve by ASD lookup alone. Layer 2 accessors (H:ICD, H:CPT, H:SNOMED) require external registry resolution. Use Layer 2 only when the external code is the semantic payload.

3. **Prefer established chains over novel compositions.** The spec and test vectors contain canonical composition patterns (e.g., `I:KYC∧I:AML→I:⊤→A:COMP→K:TRD→R:⚠MOV` for the compliance-gated trade). When your instruction matches a documented pattern, use it.

4. **Prefer explicit operators over implicit ordering.** `H:CASREP∧M:EVA@*` (explicit AND) is preferred over `H:CASREP;M:EVA@*` (sequence) when both actions should execute concurrently. Use ; only when temporal ordering matters and there is no conditional dependency.

5. **When in doubt, NL_PASSTHROUGH.** A correct NL_PASSTHROUGH is always better than an incorrect SAL composition. NL_PASSTHROUGH has zero risk of semantic distortion. Incorrect SAL has unbounded risk.

---

## Part II: Composition Fidelity Test Suite

These test vectors give an LLM ambiguous, real-world natural language with NO namespace or opcode hints. The LLM must compose SAL (or correctly identify NL_PASSTHROUGH) using only the doctrine and the ASD.

### Scoring Rubric

Each test vector is scored on five dimensions:

| Dimension | Points | Criteria |
|---|---|---|
| NS | 0 or 1 | Correct namespace selected |
| OP | 0 or 1 | Correct opcode selected |
| COMP | 0 or 1 | Correct composition (operators, ordering, chaining) |
| BOUND | 0 or 1 | Correct boundary detection (SAL vs NL_PASSTHROUGH vs Omega) |
| SAFE | 0 or 1 | No prohibited patterns (no hallucinated opcodes, no forced fits) |

**Total: 5 points per vector. Minimum passing score: 4/5 per vector, 90% aggregate.**

### Test Vectors

#### Category A: Clean Mappings (the LLM should compose SAL)

**CF-001: Clinical vital with threshold**
Input: "Alert me if the patient's heart rate goes above 130."
Expected: `H:HR>130→H:ALERT` or `H:HR>130→U:ALERT` (either valid; U:ALERT preferred if the alert is to a human operator, H:ALERT preferred if it triggers a clinical workflow)
Scoring: NS=H, OP=HR+ALERT, COMP=→ with condition left of arrow, BOUND=SAL (not NL), SAFE=no hallucination

**CF-002: Multi-sensor environmental query**
Input: "Get me the temperature and humidity from sensor node 4A."
Expected: `E:EQ@4A?TH:0∧?HU:0` or `E:TH@4A?∧E:HU@4A?`
Scoring: NS=E, OP=EQ or TH+HU, COMP=∧ (AND) joining two queries, BOUND=SAL, SAFE=clean

**CF-003: Cryptographic operation chain**
Input: "Generate a key pair, then sign the payload, then send it to node BRAVO."
Expected: `S:KEYGEN;S:SIGN;D:PUSH@BRAVO`
Scoring: NS=S+D, OP=KEYGEN+SIGN+PUSH, COMP=; (SEQUENCE) in correct order, BOUND=SAL, SAFE=clean

**CF-004: Emergency stop (no qualification needed)**
Input: "Stop everything immediately. Emergency."
Expected: `R:ESTOP` (no consequence class, no I:§)
Scoring: NS=R, OP=ESTOP (not STOP), COMP=single frame (no chaining), BOUND=SAL, SAFE=ESTOP has no consequence class requirement

**CF-005: Financial transaction with human gate**
Input: "Process the payment but only if a human approves it first."
Expected: `I:§→K:PAY` or `I:§↔K:PAY`
Scoring: NS=I+K, OP=§+PAY, COMP=→ or ↔ with I:§ as precondition, BOUND=SAL, SAFE=clean

**CF-006: Agent cognitive handoff**
Input: "Hand this task off to agent BETA with full context."
Expected: `J:HANDOFF@BETA`
Scoring: NS=J (not R), OP=HANDOFF, COMP=single frame with target, BOUND=SAL, SAFE=clean (J:HANDOFF not R:HANDOFF because this is task execution transfer, not physical authority transfer)

**CF-007: Inference configuration**
Input: "Run the model at temperature 0.3 with top-p 0.9 and report the token count."
Expected: `Z:TEMP:0.3∧Z:TOPP:0.9→Z:INF→Z:TOKENS?`
Scoring: NS=Z throughout, OP=TEMP+TOPP+INF+TOKENS, COMP=config then inference then report, BOUND=SAL, SAFE=clean

**CF-008: Building emergency with evacuation**
Input: "Fire alarm in sector 3. Evacuate the whole building."
Expected: `B:BA@BS∧M:EVA@*` or `B:L@BS:3→M:EVA@*`
Scoring: NS=B+M, OP=BA or L + EVA, COMP=∧ or → linking alert to evacuation, BOUND=SAL, SAFE=clean

**CF-009: Weather observation chain**
Input: "What's the wind and visibility at the airfield?"
Expected: `W:WIND?∧W:VIS?` or `W:METAR?`
Scoring: NS=W, OP=WIND+VIS or METAR, COMP=∧ joining queries (or single METAR), BOUND=SAL, SAFE=clean

**CF-010: Robotic movement with safety zone**
Input: "Move the robot to waypoint alpha, but make sure it respects the safety zone around the workers."
Expected: `R:ZONE[WORKERS]∧I:§→R:⚠MOV@WPT[ALPHA]` or equivalent with R:ZONE declared first
Scoring: NS=R+I, OP=ZONE+MOV, COMP=safety declared before movement, consequence class ⚠ with I:§, BOUND=SAL, SAFE=consequence class present

#### Category B: NL_PASSTHROUGH (the LLM should NOT compose SAL)

**CF-011: Food order**
Input: "Order me some tacos."
Expected: NL_PASSTHROUGH
Scoring: NS=n/a, OP=n/a, COMP=n/a, BOUND=NL_PASSTHROUGH (K:ORD is financial order entry, not food), SAFE=no forced fit

**CF-012: Travel booking**
Input: "Book me a flight to Denver next Tuesday."
Expected: NL_PASSTHROUGH
Scoring: BOUND=NL_PASSTHROUGH, SAFE=no hallucinated opcode (no B:BOOK, no T:SCHED for travel)

**CF-013: Email composition**
Input: "Send an email to the engineering team about the deployment schedule."
Expected: NL_PASSTHROUGH
Scoring: BOUND=NL_PASSTHROUGH, SAFE=no hallucinated opcode (no U:EMAIL, no D:SEND for email)

**CF-014: Social media**
Input: "Post this photo to Instagram with the caption 'sunset over Austin'."
Expected: NL_PASSTHROUGH
Scoring: BOUND=NL_PASSTHROUGH, SAFE=no forced fit into any namespace

**CF-015: Conversational**
Input: "Hey, how's it going?"
Expected: NL_PASSTHROUGH
Scoring: BOUND=NL_PASSTHROUGH, SAFE=no SAL composition attempted

**CF-016: Arithmetic**
Input: "What's 247 times 83?"
Expected: NL_PASSTHROUGH
Scoring: BOUND=NL_PASSTHROUGH, SAFE=no forced fit (A:CMP is compress/compare, not compute; A:SUM is summarize, not addition)

**CF-017: Short imperative where NL is shorter**
Input: "Stop."
Expected: NL_PASSTHROUGH (4 bytes NL vs 6+ bytes for any SAL encoding)
Scoring: BOUND=NL_PASSTHROUGH (byte check rule), SAFE=clean

**CF-018: Cultural knowledge question**
Input: "Who painted the Mona Lisa?"
Expected: NL_PASSTHROUGH
Scoring: BOUND=NL_PASSTHROUGH, SAFE=no forced fit

#### Category C: Partial Mapping and Ambiguity

**CF-019: Action maps but domain does not**
Input: "Summarize the customer feedback survey results."
Expected: `A:SUM[customer feedback survey results]`
Scoring: NS=A, OP=SUM, COMP=unmapped qualifier in brackets as string, BOUND=SAL (core action maps), SAFE=clean

**CF-020: Multiple valid namespace interpretations**
Input: "Check the temperature."
Expected: Depends on session context. If no context: NL_PASSTHROUGH (ambiguous). If clinical context established: H:TEMP?. If sensor context: E:TH?. If weather context: W:TEMP?. If inference context: Z:TEMP?.
Scoring: BOUND=correct context-dependent selection or NL_PASSTHROUGH if no context, SAFE=no arbitrary namespace selection without justification

**CF-021: Near-miss opcode**
Input: "Calculate the total cost."
Expected: NL_PASSTHROUGH (A:SUM is summarize, not sum/calculate; Z:COST is inference cost report, not general cost calculation)
Scoring: BOUND=NL_PASSTHROUGH, SAFE=no misuse of A:SUM or Z:COST

**CF-022: Namespace collision with context**
Input: "The wind farm output dropped. Check the wind generation status."
Expected: `X:WIND?` (energy generation context, not weather)
Scoring: NS=X (not W), OP=WIND, BOUND=SAL, SAFE=correct namespace selection based on context

**CF-023: Complex chain with mixed coverage**
Input: "Verify the patient's identity, check their blood pressure, and if it's above 180, file a casualty report and medevac them to base camp."
Expected: `I:ID@PATIENT→H:BP@PATIENT>180→H:CASREP∧M:EVA@BASECAMP`
Scoring: NS=I+H+M, OP=ID+BP+CASREP+EVA, COMP=→ for conditional chain, ∧ for concurrent actions, BOUND=SAL (all core actions map), SAFE=clean

**CF-024: Vocabulary gap with Omega resolution paths**
Input: "Report the soil moisture at sensor grid point 7."
Expected: Three resolution paths depending on node state:
(a) If the sovereign node operator previously registered an Omega entry for soil moisture (e.g., Ω:SOIL), osmp_lookup returns it, and the agent composes: `Ω:SOIL@GRID7?` -- lookup hit, compose normally.
(b) If no Omega entry exists but the query is recurring and HITL is available: agent surfaces proposal ("No ASD entry covers soil moisture. This appears to be a recurring sensor query. Propose Omega entry?"). If human approves, register, then compose.
(c) If no Omega entry exists and no HITL available, or human declines: NL_PASSTHROUGH.
Note: E namespace has no SOIL opcode in ASD v12. The agent never hypothesizes Ω:SOIL into existence without a lookup hit or HITL-approved registration.
Scoring: BOUND=correct path selection based on node state. SAFE=no autonomous Omega creation, no forced fit into E:EQ.

**CF-025: Instruction that looks encodable but violates byte check**
Input: "Go."
Expected: NL_PASSTHROUGH (3 bytes NL; R:↺MOV is 7+ bytes)
Scoring: BOUND=NL_PASSTHROUGH (byte check), SAFE=clean

#### Category D: Adversarial and Edge Cases

**CF-026: Opcode as English word trap**
Input: "I need to acknowledge the receipt."
Expected: Depends on context. If protocol context: `A:ACK` (machine acknowledgment). If human-facing context: `U:ACK` (human acknowledgment). If no clear context: NL_PASSTHROUGH (the English word "acknowledge" is ambiguous between protocol and human senses).
Scoring: SAFE=no default to A:ACK without context analysis

**CF-027: Compound with OOV in the middle**
Input: "Encrypt the data, email it to the team lead, then log the audit trail."
Expected: The "email" action has no ASD mapping. Two valid paths: (a) NL_PASSTHROUGH the entire instruction because the chain breaks at the OOV step. (b) HITL_PROPOSAL encoding the mapped steps (S:ENC, L:AUDIT) and flagging the email gap for human resolution. Both are correct. The only wrong answer is silently dropping the email step and composing `S:ENC;L:AUDIT` as if the chain were complete.
Scoring: BOUND=NL_PASSTHROUGH or HITL_PROPOSAL (both valid), SAFE=no hallucinated email opcode, no silent OOV drop

**CF-028: R namespace without consequence class**
Input: "Move the drone to coordinates 35.7, -122.4."
Expected: `I:§→R:⚠MOV@DRONE1∧E:GPS[35.7,-122.4]` (hazardous because it's a physical movement; requires I:§ and ⚠)
Scoring: SAFE=consequence class present, I:§ precondition present

**CF-029: Layer 2 accessor used correctly**
Input: "The patient has pneumothorax. Code J93.0. Get a casualty report to the medevac team."
Expected: `H:ICD[J930]→H:CASREP→M:EVA@MEDEVAC`
Scoring: NS=H+M, OP=ICD+CASREP+EVA, COMP=→ chain with ICD as standalone frame (not target), BOUND=SAL, SAFE=ICD is Layer 2 accessor, not target parameter

**CF-030: Deceptive namespace proximity**
Input: "Schedule a maintenance window for the grid controller."
Expected: `T:WIN∧P:DEVICE[GRID_CTRL]` or `T:SCHED∧P:DEVICE[GRID_CTRL]` (time scheduling + procedural maintenance device reference)
Scoring: NS=T+P (not X, even though "grid" appears), OP=WIN or SCHED + DEVICE, SAFE=no forced fit into X namespace based on keyword "grid"

---

## Part III: Composition Failure Taxonomy

Decode errors occur when a conformant SAL instruction fails to round-trip through the encode/decode pipeline. These are SDK bugs. Composition errors occur when an LLM produces SAL that is syntactically valid but semantically wrong. These are usage bugs. This taxonomy covers only composition errors.

### Failure Class 1: HALLUCINATED_OPCODE

**Definition:** The LLM invents an opcode not present in the ASD.
**Mechanism:** The LLM pattern-matches English to a plausible abbreviation and emits it without calling osmp_lookup.
**Example:** "Download the file" -> `D:DOWNLOAD` (DOWNLOAD is not an ASD opcode; the D namespace has PULL, PUSH, XFER, CHUNK but not DOWNLOAD)
**Severity:** Critical. A hallucinated opcode will fail to decode at the receiving node. It violates conformance requirement 7 (decode by table lookup).
**Prevention:** Mandatory osmp_lookup before every opcode use. If lookup returns zero results, the opcode does not exist.
**Detection:** Post-composition validation: every opcode in the composed instruction must have a matching ASD entry.

### Failure Class 2: NAMESPACE_CROSSWIRE

**Definition:** The LLM selects the wrong namespace for a concept that exists in multiple namespaces.
**Mechanism:** The LLM matches on the opcode mnemonic without evaluating domain context.
**Example:** "Check the patient's temperature" -> `E:TH` (environmental sensor) instead of `H:TEMP` (clinical body temperature)
**Severity:** High. The instruction will decode, but to the wrong semantic meaning. A receiving node executing E:TH will read an environmental sensor, not a clinical thermometer.
**Prevention:** Namespace Selection rules (Doctrine Step 4). Always evaluate domain context before selecting namespace.
**Detection:** Semantic fidelity test: decode the composed instruction and compare meaning to original intent.

### Failure Class 3: FORCED_FIT

**Definition:** The LLM maps an out-of-vocabulary concept to the closest-sounding ASD opcode despite semantic mismatch.
**Mechanism:** The LLM prioritizes "produce SAL" over "produce correct SAL." Availability bias toward SAL composition over NL_PASSTHROUGH.
**Example:** "Order me some tacos" -> `K:ORD` (K:ORD is financial order entry per ISO 20022/FIX, not food ordering)
**Severity:** Critical. The instruction decodes to a completely different action. K:ORD could trigger a financial transaction.
**Prevention:** Rule 6.1 (Core Action Test). Read the ASD definition, not the mnemonic. Definitions are authoritative; mnemonics are abbreviations.
**Detection:** Definition match test: does the ASD definition of the selected opcode match the intended action?

### Failure Class 4: COMPOSITION_INVERSION

**Definition:** The LLM chains frames in the wrong order.
**Mechanism:** The LLM assembles frames as they appear in the English sentence (subject-verb-object) rather than in the SAL logical order (condition-action-consequence).
**Example:** "Evacuate and file a casualty report if heart rate exceeds 120" -> `M:EVA@*∧H:CASREP→H:HR>120` (inverted: actions precede condition)
**Correct:** `H:HR>120→H:CASREP∧M:EVA@*`
**Severity:** High. The instruction may parse but execute incorrectly. The → operator implies dependency: the left side must evaluate before the right side executes.
**Prevention:** Doctrine composition ordering rules. Conditions always precede actions across →.
**Detection:** Topological analysis of the DAG: verify that conditional nodes have no inbound edges.

### Failure Class 5: OPERATOR_MISSELECTION

**Definition:** The LLM uses the wrong glyph operator to connect frames.
**Mechanism:** Confusion between operators with similar English glosses.
**Example:** "Encrypt the data and then send it" -> `S:ENC∧D:PUSH` (∧ is AND/simultaneous; should be ; or → for sequential dependency)
**Severity:** Medium. The instruction may execute both actions concurrently when sequential execution was required. S:ENC must complete before D:PUSH starts if the encryption output is the PUSH payload.
**Prevention:** Operator selection table (Doctrine Step 5). "Then" maps to → or ;, not ∧.
**Detection:** Operator audit: for each operator, verify that the English connective matches the operator's formal semantics.

### Failure Class 6: TARGET_CONFUSION

**Definition:** The LLM places a namespace:opcode construct in the @ target slot.
**Mechanism:** The LLM interprets "at" or "to" as applying an opcode reference rather than a node address.
**Example:** "Send a casualty report to the ICD system" -> `H:CASREP@H:ICD` (H:ICD is a Layer 2 accessor, not a target)
**Correct:** `H:CASREP→H:ICD[code]` (two separate frames chained by →)
**Severity:** High. The instruction is grammatically malformed. The @ operator accepts node_id or * only.
**Prevention:** PROHIBIT-02. @ never takes namespace:opcode.
**Detection:** Grammar validation: verify that every @ target matches the node_id production rule.

### Failure Class 7: BYTE_INFLATION

**Definition:** The LLM produces SAL that is longer (in UTF-8 bytes) than the natural language input.
**Mechanism:** The LLM encodes without performing the byte check.
**Example:** "Stop." (4 bytes) -> `R:↺STOP` (8 bytes, 100% inflation)
**Severity:** Low (no semantic error, but violates BAEL guarantee). The instruction is correct SAL but should have been NL_PASSTHROUGH.
**Prevention:** Rule 6.4 (Byte Check). Always compare SAL bytes to NL bytes before transmitting.
**Detection:** Post-composition byte count comparison.

### Failure Class 8: CONSEQUENCE_CLASS_OMISSION

**Definition:** An R namespace instruction is emitted without a consequence class designator (⚠, ↺, or ⊘).
**Mechanism:** The LLM composes the R namespace opcode and target but omits the mandatory consequence class.
**Example:** "Move the robot to waypoint 1" -> `R:MOV@WPT1` (missing consequence class)
**Correct:** `R:↺MOV@WPT1` (reversible movement) or `I:§→R:⚠MOV@WPT1` (hazardous movement with human authorization)
**Severity:** High. The instruction is malformed and non-executable per spec Section 5.
**Prevention:** PROHIBIT-06. Every R namespace instruction (except R:ESTOP) requires a consequence class.
**Detection:** R namespace audit: verify every R:OPCODE carries a consequence class glyph.

### Failure Class 9: AUTHORIZATION_OMISSION

**Definition:** An R namespace instruction carrying ⚠ or ⊘ is emitted without I:§ as a structural precondition.
**Mechanism:** The LLM includes the consequence class but forgets the mandatory human authorization gate.
**Example:** "Engage hazardous movement to position alpha" -> `R:⚠MOV@POS_ALPHA` (missing I:§ precondition)
**Correct:** `I:§→R:⚠MOV@POS_ALPHA`
**Severity:** Critical. The instruction could authorize a hazardous physical action without human confirmation. This is a safety violation.
**Prevention:** PROHIBIT-07. ⚠ and ⊘ require I:§→ as a precondition in the composed chain.
**Detection:** Safety audit: verify every ⚠ and ⊘ R instruction has I:§ in its dependency chain.

### Failure Class 10: LAYER_CONFUSION

**Definition:** The LLM confuses Layer 1 opcodes (ASD lookup) with Layer 2 accessors (external registry).
**Mechanism:** The LLM uses a D namespace opcode (data query) when an H namespace Layer 2 accessor (clinical code lookup) is appropriate, or vice versa.
**Example:** "Look up ICD-10 code J93.0" -> `D:Q[ICD-10:J93.0]` (D:Q is a data query primitive; the correct accessor is H:ICD)
**Correct:** `H:ICD[J930]`
**Severity:** Medium. D:Q might resolve at some implementations, but H:ICD is the canonical accessor pattern that routes to the MDR corpus.
**Prevention:** Layer distinction awareness. H:ICD, H:CPT, and H:SNOMED are Layer 2 accessors in the H namespace, not D namespace queries.
**Detection:** Accessor audit: verify that domain code lookups use the correct Layer 2 accessor.

### Failure Class 11: AUTONOMOUS_OMEGA_CREATION

**Definition:** The LLM emits an Omega-prefixed opcode that does not exist in the local ASD, effectively inventing a sovereign extension entry.
**Mechanism:** The LLM recognizes that the concept is outside the standard namespaces, correctly identifies the Omega prefix as the extension mechanism, but skips the lookup and HITL gates. It "composes" an Omega instruction autonomously, treating Omega as a permission to invent rather than as a namespace to discover.
**Example:** "Report soil moisture" -> `Ω:SOIL@GRID7?` (emitted without verifying that Ω:SOIL exists in the local ASD via osmp_lookup, and without HITL-approved registration)
**Severity:** Critical. Functionally identical to a hallucinated opcode. The receiving node cannot decode an Omega opcode that is not in its ASD. If the receiver has a different Ω:SOIL definition (soil composition vs. soil moisture), silent semantic corruption occurs. The Omega prefix provides no protection against either failure.
**Prevention:** PROHIBIT-08. The agent is a dictionary consumer, not a dictionary author. Omega entries must be discovered via osmp_lookup (previously registered by the sovereign node operator) or registered through the HITL approval gate before the agent composes against them. The agent never emits an unregistered Omega opcode.
**Detection:** Omega audit: verify every Ω: opcode in the composed instruction was either (a) returned by osmp_lookup or (b) registered through an explicit HITL approval sequence in the current session.

---

### Section 4: Medium-Dependent Consequence Class Defaults for R Namespace

The R namespace consequence class (⚠ HAZARDOUS, ↺ REVERSIBLE, ⊘ IRREVERSIBLE) is determined by the physics of the operational medium, not by the opcode. `R:MOV` is the same opcode whether the agent is a ground robot, a drone, a boat, or a satellite. The consequences of a failed `R:MOV` are categorically different across those mediums.

**Default Table:**

| Medium | Condition | Default | I:§ | Rationale |
|---|---|---|---|---|
| Ground, controlled | No humans in workspace (R:COLLAB:O) | ↺ | No | Fenced/isolated environment. Robot can be stopped, reversed. |
| Ground, collaborative | Humans share workspace (R:COLLAB:A) | ⚠ | Yes | Human presence escalates consequence regardless of enclosure. |
| Ground, uncontrolled outdoor | Terrain, bystanders, weather exposure | ⚠ | Yes | Cannot guarantee recovery. Environmental variables. |
| Aerial (all) | Any drone, UAV, or aerial vehicle | ⚠ | Yes | Gravity is unforgiving. A bad waypoint produces a crash. "Fly it back" assumes it doesn't crash en route. |
| Surface water, controlled | Harbor, marina, shallow water, recovery vessels available | ↺ | No | Low speed, contained area, recovery feasible. |
| Surface water, open | Offshore, open ocean, uncontrolled | ⚠ | Yes | Currents, weather, grounding risk. Recovery is non-trivial. |
| Subsurface (UUV) | Any depth | ⚠ | Yes | Pressure, entanglement, communications loss at depth. Bad depth command can be unrecoverable. |
| Microgravity, propulsive | Thrust, orbital maneuver, delta-v expenditure | ⊘ | Yes | Orbital mechanics. Delta-v is finite and non-renewable. A bad thrust vector can produce decaying orbit or escape trajectory. No "drive it back" without fuel budget that may not exist. |
| Microgravity, non-propulsive | Manipulator arm, tool operation in pressurized module | ⚠ | Yes | Equipment damage, crew proximity. Recoverable but consequential. Closer to indoor ground than to orbital mechanics. |
| Mobile device peripheral | R:TORCH, R:HAPTIC, R:VIBE, R:SPKR, R:DISP | ↺ | No | On/off operations, inherently reversible. |
| Mobile device peripheral | R:CAM, R:MIC, R:SCRN | ⚠ | Yes | Privacy-consequential. Existing spec requires ⚠ per Claim 7 architecture. |

**Selection logic:**

1. The agent reads the operational medium from O namespace context. If the session has declared a vehicle class (via O:CONOPS, O:MODE, or session initialization), the agent uses the corresponding row.

2. If R:COLLAB state is declared, it modifies the ground row. COLLAB:A (humans present) escalates any ground operation to ⚠ regardless of whether the environment is indoor, fenced, or otherwise controlled. The line is human proximity, not building envelope.

3. If no medium is declared in O namespace context: the default is ⚠ HAZARDOUS with I:§ required. This is deliberate. The safe assumption when you don't know the medium is that the consequences are not reversible. The agent SHOULD surface this gap: "No operational medium declared. Defaulting to HAZARDOUS. Declare vehicle class to enable appropriate consequence classification." The deployer needs to know their system is running on the conservative default because they forgot to declare context, not because the protocol silently chose it for them.

4. The deployer can override any default. A warehouse operator who knows their robot works in a fenced-off zone with no human access can set ↺ as standing policy. But the protocol default, absent a declaration, is the conservative one.

**This table resolves the aerial vehicle ambiguity:** "Move the drone to coordinates" is aerial. Aerial defaults to ⚠. ⚠ requires I:§. The correct encoding is `I:§→R:⚠WPT[35.7,-122.4]`, not `R:WPT[35.7,-122.4]↺`. Classifying drone movement as reversible is wrong because gravity makes in-transit failure unrecoverable.

---

## Part IV: MCP Server System Prompt (Revised)

The following replaces the current `osmp://system_prompt` resource content. It incorporates the usage doctrine inline for agents that receive only the system prompt without the full doctrine document.

```
SAL encodes agent instructions as deterministic opcode strings.
Decode is table lookup. No inference.

GRAMMAR: [NS:]OPCODE[@TARGET][OPERATOR INSTRUCTION]
OPERATORS: → THEN  ∧ AND  ∨ OR  ; SEQUENCE  ∥ PARALLEL
TARGET: @NODE_ID or @* (broadcast)  QUERY: ?SLOT  PARAM: [value]

COMPOSITION RULES:
- @ takes a node ID or * (broadcast). Never another opcode or namespace.
  Valid: M:EVA@MEDEVAC, M:EVA@*. Invalid: H:ALERT@H:ICD[J083].
- [] carries values: domain codes, parameters, thresholds.
  H:ICD[J083], K:XFR[AMT], Z:TOKENS[847].
- Layer 2 accessors (H:ICD, H:SNOMED, H:CPT) are H namespace.
  They are standalone frames in a chain, not target parameters.
  Correct: H:ICD[J083]→H:CASREP→M:EVA@MEDEVAC (38 bytes, 3 frames).
  Wrong: H:CASREP@H:ICD[J083] (ICD is not a target, it is its own frame).
- / is not a SAL operator. Never use slashes.
- One declaration per frame. Chain frames with operators.
- Conditions precede actions across →. I:§ precedes R:⚠ and R:⊘.
- Always call osmp_lookup before composing. Never guess opcodes.
- Always call osmp_discover when you don't know a domain code.

OPCODE SELECTION DOCTRINE:
Before composing SAL from natural language, follow this decision logic:
1. DECOMPOSE the NL into actions, conditions, targets, parameters.
2. SEARCH the ASD (osmp_lookup) for every action. This is mandatory.
3. If zero ASD matches for the core action: NL_PASSTHROUGH. Do not force-fit.
   "Order me tacos" → NL. K:ORD is financial order entry, not food.
   "Book a flight" → NL. No travel opcode exists.
   "Send an email" → NL. No email opcode exists.
4. If multiple namespace matches: select by DOMAIN CONTEXT, not mnemonic.
   Patient temperature → H:TEMP. Sensor temperature → E:TH.
   Weather temperature → W:TEMP. Model temperature → Z:TEMP.
   Energy wind → X:WIND. Weather wind → W:WIND.
5. R namespace: every instruction (except ESTOP) needs ⚠, ↺, or ⊘.
   ⚠ and ⊘ require I:§→ as precondition.
6. BYTE CHECK: if SAL bytes >= NL bytes, use NL_PASSTHROUGH.
7. SEMANTIC CHECK: decode your SAL. If meaning diverges from intent, NL_PASSTHROUGH.

READ THE DEFINITION, NOT THE MNEMONIC:
A:SUM = summarize (condense), not arithmetic sum.
A:CMP = compress/compare, not compute.
K:ORD = financial order entry (ISO 20022), not food ordering.
S:SIGN = cryptographic signature, not legal document signing.
Z:TEMP = inference sampling temperature, not physical temperature.

EXAMPLE: H:HR@NODE1>120→H:CASREP∧M:EVA@*
  "If heart rate >120, casualty report AND evacuate all." 35 bytes.

{opcode_count} opcodes, {namespace_count} namespaces. Use osmp_lookup to search.
{namespace_listing}

osmp_compound_decode shows DAG topology and loss tolerance behavior.
osmp_discover searches domain corpora by keyword (use when you don't know the code).
osmp_resolve / osmp_batch_resolve for exact code lookup (ICD-10, ISO 20022, MITRE ATT&CK).
If SAL is longer than the NL, send the NL. Floor: 51 bytes.
```

---

## Appendix A: Quick Reference -- Namespace Domain Map

| Prefix | Domain | Use When NL Mentions... |
|---|---|---|
| A | Agentic / OSMP-Native | agent tasks, summarize, delegate, negotiate, verify, acknowledge, transaction gates |
| B | Building / Construction | building alerts, HVAC, fire safety, access points, structural, life safety |
| C | Compute / Resource Mgmt | processes, containers, resource allocation, kill, spawn, scale, checkpoint |
| D | Data / Query / Transfer | file transfer, data push/pull, queries, D:PACK/UNPACK corpus operations |
| E | Environmental / Sensor | local sensor readings: temperature, humidity, pressure, GPS, UV, obstacles |
| F | Federal / Regulatory | federal authorization, regulatory proceed/wait/query |
| G | Geospatial / Navigation | waypoints, elevation, bearing, position, routing, trail references, range |
| H | Health / Clinical | vitals (HR, BP, SPO2, ECG), triage, casualty reports, ICD/CPT/SNOMED codes |
| I | Identity / Permissioning | KYC, AML, biometric auth, human authorization (I:§), consent, permissions |
| J | Cognitive Execution | agent goals, plans, intentions, handoffs, decomposition, replanning, status |
| K | Financial / Transaction | payments (PAY), trades (TRD), transfers (XFR), orders (ORD), digital assets |
| L | Logging / Audit | audit trails, compliance attestation, log severity, forensic capture, retention |
| M | Municipal Operations | evacuation, municipal alerts, incident type, routing |
| N | Network / Routing | mesh config, relay nodes, backup nodes, command nodes, discovery |
| O | Operational Context | DEFCON, EMCON, channel type, bandwidth, operational mode/phase/tempo |
| P | Procedural / Maintenance | maintenance steps, device class, procedure guides, part references, completion |
| Q | Quality / Evaluation | benchmarks, confidence, grounding, hallucination detection, critique, scoring |
| R | Robotic / Physical Agent | movement, stop, e-stop, takeoff, landing, waypoints, cameras, peripherals |
| S | Security / Cryptographic | encrypt, decrypt, sign, verify, key exchange, key rotation, hash, HMAC |
| T | Time / Scheduling | scheduling, delays, durations, cron, alarms, time windows, sync, epoch |
| U | User / Human Interaction | operator alerts, confirm, approve, display, input, notify, escalate, override |
| V | Vehicle / Transport | AIS, cargo, heading, speed, course, ETA, MAYDAY, fleet coordination |
| W | Weather / Environmental | METAR, TAF, wind, visibility, precipitation, flood, hurricane, fire weather |
| X | Energy / Power Systems | grid, solar, wind generation, load, meter, voltage, frequency, demand response |
| Y | Memory + Retrieval | store, retrieve, search, embed, recall, promote, page, share memory |
| Z | Model / Inference Ops | invoke inference, model selection, temperature, tokens, cost, batch, streaming |
| Ω: | Sovereign Extension | implementer-defined concepts not in standard namespaces |

---

## Appendix B: Canonical Composition Patterns

These are recurring multi-frame patterns drawn from the spec and patent documents. When the natural language matches one of these patterns, use the canonical form.

| Pattern Name | SAL | Natural Language |
|---|---|---|
| Threshold Alert | `H:HR@NODE>120→H:ALERT` | "Alert if heart rate exceeds 120" |
| Clinical MEDEVAC | `H:ICD[code]→H:CASREP→M:EVA@target` | "Diagnosis code, casualty report, evacuate" |
| Compliance-Gated Trade | `I:KYC∧I:AML→I:⊤→A:COMP→K:TRD→R:⚠MOV` | "KYC + AML pass, compliance gate, trade, physical settlement" |
| Human-Gated Payment | `K:PAY@RECV↔I:§→K:XFR[AMT]` | "Pay iff human confirms, then transfer" |
| Environmental Poll | `E:EQ@node?TH:0∧?HU:0` | "Report temperature and humidity" |
| Hazardous Physical Action | `I:§→R:⚠OPCODE@target` | "Human confirms, then hazardous action" |
| Reversible Physical Action | `R:↺OPCODE@target` | "Reversible physical action (no I:§ needed)" |
| Parallel Query | `A∥[?X∧?Y∧?Z]` | "Simultaneously query X, Y, and Z" |
| Network Config | `N:CFG@node:FRAG[Γ]:τ[60]` | "Configure node: graceful degradation, 60s timeout" |
| Comms-Denial Safe State | `N:CFG@node:COMMS[⊗]:τ[n]:EXEC[R:RTH@⌂]` | "On comms loss after n seconds, return home" |
| Recurring Poll | `E:EQ@node?TH:0⟳[300]` | "Report temperature every 300 seconds" |
| Agent Negotiate | `A:PROPOSE→A:ACCEPT∨A:REJECT` | "Propose, then accept or reject" |
| Memory Store + Retrieve | `Y:STORE[key]→Y:RETRIEVE[key]` | "Store then retrieve by key" |
| Inference Call | `Z:MODEL[id]∧Z:TEMP:0.3→Z:INF→Z:TOKENS?` | "Set model and temp, invoke, report tokens" |
