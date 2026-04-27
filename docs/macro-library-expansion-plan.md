# Macro Library Expansion Plan

**Status:** Draft proposal, 2026-04-24
**Author:** CTO/CLC thread
**Owner:** Clay Holberg
**Companion artifact:** Worker doctrine cascade (`octid-worker/encode.js`, deployed alongside this proposal)

---

## Context

OSMP-SPEC §11.4 establishes a composition priority hierarchy:

1. **Macro invocation** — pre-validated multi-step SAL chain template, zero composition error surface
2. **Individual opcode composition** — grammar-constrained, inference-dependent
3. **Natural language passthrough** — no compression, no encoding

The protocol's native answer to compose-rate brittleness is macros. An agent that hits a registered macro collapses composition to slot-fill; the chain structure is pre-validated by whoever registered the macro, and the LLM cannot make a structural error in the chain. Composition errors are bounded to slot-value typos, which are recoverable.

The current macro library has **16 entries**, all in the Meshtastic mesh telemetry domain (`mdr/meshtastic/meshtastic-macros.json`). This is a starter set, not a coverage target. For the cascade architecture to deliver high compose rate across realistic NL inputs, the macro corpus needs aggressive expansion across the 26 standard namespaces.

This document proposes the expansion workstream structure, prioritization, and acceptance criteria.

---

## Workstream structure

### Phase 1 — Domain audit (per domain)

For each priority domain, produce a workflow inventory:
- Source standards and protocols (e.g., ICD-10 for clinical, ISO 20022 for financial)
- 20-50 recurring multi-step workflows that an agent would commonly execute
- Existing single-frame patterns that are sub-units of those workflows

Output: `mdr/<domain>/workflow-inventory.md` (markdown, free-form)

### Phase 2 — Macro design

For each workflow in the inventory:
- Draft the chain template using existing ASD opcodes only
- Define typed slots with namespace constraints where applicable
- Define trigger phrases (3-7 natural-language patterns that should match this workflow)
- Compute the inherited consequence class (per macro_registry logic)

Output: `mdr/<domain>/<domain>-macros.json` (corpus file matching the existing schema)

### Phase 3 — Validation gauntlet

Every macro MUST pass:
1. `MacroRegistry.register(template)` — ASD opcode existence, slot/placeholder pairing, CC inheritance
2. `validate_composition(macro.chain_template)` after slot-fill with sample values
3. SAL → decode → semantic check (does the decoded NL match the workflow intent?)
4. Cross-SDK round-trip (Python, TS, Go all produce byte-identical compact + expanded forms)

Output: macro test fixtures in `tests/macros/<domain>_test.py` (and TS/Go equivalents)

### Phase 4 — Corpus integration

- Add to MDR registry with version pin (`<corpus_id>:<version>`)
- Update Worker's inlined copy (or move to wrangler bundle if size warrants)
- Update SDK examples and documentation

### Phase 5 — Coverage measurement

After each domain ships, run the cascade against a corpus of 50-100 representative NL inputs in that domain and measure:
- **Macro hit rate**: % that resolve to `A:MACRO[id]`
- **Single-opcode compose rate**: % that resolve via individual opcode composition
- **Passthrough rate**: % that fall to NL_PASSTHROUGH

Target: macro hit rate >= 60% per domain after the first pass; >= 80% after iteration.

---

## Prioritized domain queue

The order is set by a combination of (a) agent-relevance, (b) availability of authoritative source standards, (c) demonstration value for prospects, and (d) presence of canonical embodiments already in the spec.

| Order | Namespace | Domain | Source standards | Why first |
|---|---|---|---|---|
| 1 | H | Clinical | ICD-10, SNOMED CT, CPT, START/SALT triage, 9-line MEDEVAC | Spec §11 canonical embodiment is MEDEVAC; corpus audience overlap with hospitals/EMS demos |
| 2 | R | Robotic | ISO 10218-1/2, ROS2 conventions | Highest-stakes namespace; consequence-class machinery exercised; covers the patent's R-namespace claims |
| 3 | I | Identity / auth | W3C DID, OAuth 2.0, NIST SP 800-63, FinCEN CIP | Gates on K and R chains; KYC/AML/biometric flows are common composite patterns |
| 4 | K | Financial | ISO 20022, FIX, SWIFT message categories | Compliance-gated trade is a spec example; high enterprise relevance |
| 5 | S | Cryptographic | RFC 8446, RFC 7748, RFC 8017, FIPS 140-3 | Common chains: keygen → sign → push, encrypt → seal → transmit |
| 6 | L | Compliance / audit | RFC 5424, OCSF 1.0, HIPAA §164.312, PCI DSS Req. 10 | Crosscutting; pairs with K and H workflows |
| 7 | J | Cognitive execution | BDI architecture, AgentSpeak, PDDL, ReAct | Agent-to-agent handoff, replan, decompose patterns |
| 8 | Y | Memory + retrieval | MemGPT, Voyager, RAG, Mem0 | Agent memory workflows: store → embed → retrieve → forget |
| 9 | Z | Inference ops | OpenAI/Anthropic/Vertex AI APIs, vLLM, Ollama | Model invocation chains: model → temp → topp → infer → tokens |
| 10 | W | Weather | WMO No. 306, NOAA CAP, ICAO METAR/TAF | METAR queries, alert chains; clean external-data namespace |
| 11 | V | Maritime | NMEA 0183/2000, ITU-R M.1371-5 (AIS), SAE J1939 | Fleet ops, AIS reports, port arrivals |
| 12 | X | Energy | IEC 61850, IEC 61970-301, OpenADR, IEEE 1547 | Grid status, demand response, load shedding |

The remaining namespaces (B, C, D, E, F, G, M, N, O, P, Q, T, U) get coverage in a second pass once the priority dozen are stable.

---

## Acceptance criteria for "compose rate at 99%"

The 99% claim is meaningful only against a defined input distribution. The proposed measurement protocol:

1. **Test corpus**: 50 NL inputs per priority domain, totaling 600 inputs across the first 12 domains. Inputs are written by domain experts (or by Clay for v1) and reflect realistic agent instructions in that domain.
2. **Pipeline**: Run each input through the deployed Worker cascade (Haiku + ASD + macros + tools).
3. **Scoring**: For each input, the output is one of:
   - `A:MACRO[id]` (macro hit) — pass if the macro's workflow matches the input intent
   - Individual opcode composition — pass if the SAL is grammatically valid, semantically correct (decoded matches intent), and uses no hallucinated opcodes
   - `NL_PASSTHROUGH` with reason — pass if the input genuinely has no opcode coverage (e.g., "order me tacos")
   - Wrong SAL composition — fail
4. **Aggregate**: % pass across all 600. Target: 99%.

Expected distribution at the end of the workstream:
- Macro hit: 60-70%
- Individual opcode: 20-25%
- Correct passthrough: 5-10%
- Failure: <= 1%

The 99% claim collapses to two empirical numbers: (a) macro corpus coverage of recurring workflows, (b) cascade reliability when macros don't apply. Both are measurable, neither is currently measured.

---

## Open questions for Clay

1. **Domain priority confirmation.** The order above is my read of agent-relevance + standard availability. If you want a different order (e.g., financial before robotic for a specific prospect), say so before Phase 1 work begins on a domain.
2. **Test corpus authorship.** The 50-input-per-domain corpus needs domain expertise. For v1 you're the canonical author. Want to build it during macro design (your input shapes the macros) or after (macros are designed, then corpus tests them)?
3. **MDR governance.** Today macros land via PR review against the cloudless-sky repo. Should there be a more formal MDR registration flow (e.g., spec-revision-style with versioned corpora and ADP distribution), or stay informal until enterprise pilots demand it?
4. **Worker inline vs CDN.** Current Worker inlines the corpus (~5KB for Meshtastic). At ~150-300 macros across all domains the inline grows to ~50-100KB — still fine for a single-file paste. Beyond that, move to wrangler bundling or CDN fetch with cold-start cache. At what point do we switch?

---

## What this workstream is NOT

- Not the worker rewrite (workstream a, completed).
- Not a replacement for the doctrine cascade — macros sit ATOP the cascade as the preferred resolution path, the cascade still runs for everything else.
- Not a replacement for the SDK's keyword/phrase composer — that's the fallback when no macro fits and the Worker isn't in the loop (e.g., MCP-direct usage).
- Not a substitute for measurement. The 99% claim still requires the input-corpus + harness work described in §"Acceptance criteria" above.

---

## Next concrete deliverable

Phase 1 audit for Domain 1 (Clinical / H namespace). Output: `mdr/clinical/workflow-inventory.md` with 30-50 recurring clinical agent workflows, each annotated with the candidate opcodes from H, I, M, T, L namespaces. Estimated artifact size: a few hundred lines of structured markdown. Sign-off from Clay before Phase 2 begins on this domain.
