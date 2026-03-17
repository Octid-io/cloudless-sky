# OSMP Protocol Specification v1.0
## Octid Semantic Mesh Protocol — Cloudless Sky Project

**Status:** Draft for community review  
**Docket:** OSMP-001-UTIL (patent pending)  
**Inventor:** Clay Holberg  
**License:** Apache 2.0

---

## Abstract

The Octid Semantic Mesh Protocol (OSMP) is a bandwidth-agnostic application-layer wire protocol for semantic instruction encoding in agentic AI systems. OSMP enables AI-to-AI and human-to-AI instruction exchange across any communication channel — from 51-byte LoRa radio payloads to high-bandwidth cloud infrastructure — using a composable domain-specific symbolic instruction format (Semantic Assembly Language, or SAL), an adaptive shared compression dictionary (Adaptive Shared Dictionary, or ASD), and a capability negotiation and session handshake protocol (Frame Negotiation Protocol, or FNP).

OSMP achieves 68.3%–87.5% UTF-8 byte reduction relative to natural language equivalents across representative agentic instruction types. Decode is a table lookup operation requiring no neural inference at the receiving node. Any device capable of string processing can participate as a sovereign OSMP node.

---

## 1. Design Principles

**1.1 Inference-free decode.** An OSMP-encoded instruction is decoded by table lookup against the shared dictionary and grammar specification. No model, no inference step, no ambiguity resolution. The instruction is the intent.

**1.2 Sovereignty.** Every node maintains its own Local Context Store and executes SAL encoding and decoding locally without dependency on any central server or cloud infrastructure. Nodes retain the right to define proprietary namespace extensions without requiring approval from any central authority.

**1.3 Bandwidth agnosticism.** Compression properties developed under the 51-byte LoRa minimum constraint floor produce compounding efficiency gains at all bandwidth levels including cloud scale. The same encoding that fits a single LoRa packet reduces tokenization cost, context window consumption, storage, and network egress in high-throughput AI systems.

**1.4 Human inspectability.** OSMP-encoded instructions are human-readable at every transmission point without specialized decoding hardware. Any operator can inspect instruction traffic at the encoding layer.

**1.5 Lossless semantics.** Every SAL substitution maps a natural language phrase or operational code to a single symbolic element with one-to-one formal equivalence. No semantic information is discarded. Recovery is by table lookup with no statistical inference.

---

## 2. Architecture Overview

OSMP comprises seven components:

| Component | Full Name | Function |
|---|---|---|
| SAL | Semantic Assembly Language | Domain-specific symbolic instruction format |
| ASD | Adaptive Shared Dictionary | Adaptive shared compression dictionary |
| FNP | Frame Negotiation Protocol | Capability negotiation and session handshake |
| SNA | Sovereign Node Architecture | Autonomous edge node architecture |
| TCL | Translational Compression Layer | Semantic serialization and transcoding layer |
| OP | Overflow Protocol | Message fragmentation, priority, and graceful degradation |
| BAEL | Bandwidth-Agnostic Efficiency Layer | Adaptive encoding layer adjusting compression parameters based on negotiated channel capacity |

---

## 3. Semantic Assembly Language (SAL)

### 3.1 Instruction Structure

A SAL instruction is composed of:

```
[NAMESPACE_PREFIX]:[OPCODE][@TARGET][?QUERY][SLOT:VALUE][OPERATOR][NAMESPACE_PREFIX]:[OPCODE]...
```

**Example:**
```
EQ@4A?TH:0∧?HU:0
```
Natural language equivalent: "Node 4A, report temperature and humidity at offset zero."
UTF-8 bytes: 12 vs 57 (78.9% reduction)

### 3.2 Glyph Operators

Glyph operators are single Unicode characters with formal logical equivalences. Decode is by table lookup — no inference required.

| Glyph | Unicode | Name | Function | Natural Language Equivalents |
|---|---|---|---|---|
| ∧ | U+2227 | AND | Both conditions apply simultaneously | and, also, &, as well as |
| ∨ | U+2228 | OR | Either condition satisfies | or, either, alternatively |
| ¬ | U+00AC | NOT | Negation or exclusion | not, except, excluding, without |
| → | U+2192 | THEN | Sequential or conditional dependency | then, if...then, when...then, therefore |
| ↔ | U+2194 | IFF | Biconditional | if and only if, iff, exactly when |
| ∀ | U+2200 | FOR-ALL | Applies to all matching nodes or items | for all, every, each |
| ∃ | U+2203 | EXISTS | At least one matching node satisfies | any, there exists, at least one |
| @ | U+0040 | TARGET | Node or location targeting | at, on, directed to |
| ∥ | U+2225 | PARALLEL | Parallel execution | simultaneously, in parallel, concurrently |
| > | U+003E | PRIORITY | Execution weight or preference ordering | first, prefer, prioritize |
| ~ | U+007E | APPROX | Fuzzy or approximate match | approximately, about, roughly |
| * | U+002A | WILDCARD | Matches all values — broadcast semantics | all, any value, broadcast |
| : | U+003A | ASSIGN | Slot value assignment | equals, is set to, assign |
| ; | U+003B | SEQUENCE | Ordered sequential execution | then next, followed by, in sequence |
| ? | U+003F | QUERY | Request for value or status | what is, query, retrieve |

### 3.3 Compound Operator

| Glyph | Unicode | Name | Function |
|---|---|---|---|
| ¬→ | U+00AC + U+2192 | UNLESS | Negated conditional |

### 3.4 Compression Properties

TCL glyph substitution alone reduces character count 5–25% depending on instruction type prior to opcode encoding. Combined with full OSMP encoding: **68.3%–87.5% UTF-8 byte reduction** across 20 representative instruction types.

Measurement basis: UTF-8 byte count (`len(s.encode('utf-8'))` in Python).

Two-tier corpus compression: SAL first tier + LZMA second tier achieves **72.7% total reduction** and **3.7x compression multiplier** versus natural language + LZMA baseline on a partial medical domain dictionary. This is a conservative lower bound; a complete domain MDR achieves higher substitution density.

---

## 4. Namespace Architecture

### 4.1 Standard Namespaces

| Prefix | Domain | Authoritative Sources |
|---|---|---|
| A | Agentic / OSMP-Native | OSMP-defined; no external standard |
| B | Building / Construction | IBC, NFPA fire and safety codes |
| C | Compute / Resource Management | POSIX.1-2017, Kubernetes ResourceQuota API, cgroups v2, OCI Runtime Spec |
| D | Data / Query / File Transfer | OSMP-defined retrieval and transfer primitives |
| E | Environmental / Sensor | IEEE 1451 (smart sensor interface), NMEA 0183 sensor sentences |
| F | Federal / Regulatory | CFR titles; **F does not cover financial — that is K namespace** |
| G | Geospatial / Navigation | OpenStreetMap, USGS topographic data, USFS trail identifiers, ICAO location codes |
| H | Health / Clinical | ICD-10, SNOMED CT, CPT, START/SALT triage, 9-liner MEDEVAC format |
| I | Identity / Permissioning | W3C DID, OAuth 2.0, NIST SP 800-63, FinCEN CIP |
| J | Cognitive Execution State *(AI-native)* | BDI architecture (Rao & Georgeff 1995), AgentSpeak, PDDL, HTN planning, ReAct (Yao et al. ICLR 2023) |
| K | Financial / Transaction | ISO 20022, FIX protocol, SWIFT message categories |
| L | Logging / Audit / Compliance | RFC 5424 (syslog), NIST SP 800-92, OCSF 1.0, HIPAA 45 CFR §164.312(b), PCI DSS Req. 10 |
| M | Municipal Operations | FEMA ICS codes, NIMS, municipal emergency management frameworks |
| N | Network / Routing | OSMP-defined mesh coordination primitives |
| O | Operational Context / Environment | FEMA ICS/NIMS, DEFCON/FPCON (DoD), EMCON (NATO), OPCON/TACON (JP 1), MIL-STD-2525D, Semtech SX127x, Meshtastic channel presets, 3GPP |
| P | Procedural / Maintenance | iFixit repair guide identifiers, CPT-adjacent maintenance procedure codes |
| Q | Quality / Evaluation / Grounding *(AI-native)* | Reflexion (Shinn et al. NeurIPS 2023), RAGAS, HELM (Stanford CRFM 2022), Constitutional AI (Anthropic 2022), LangSmith |
| R | Robotic / Physical Agent | ISO 10218-1:2025, ISO 10218-2:2025, ROS2 opcode conventions |
| S | Security / Cryptographic | FIPS 140-3, RFC 8446 (TLS 1.3), RFC 8017 (RSA/PKCS#1), RFC 7748 (X25519), RFC 9580 (OpenPGP), NIST SP 800-131A |
| T | Time / Scheduling | ISO 8601:2019, RFC 5545 (iCalendar), RFC 3339, NTP RFC 5905, IEEE 1588 (PTP) |
| U | User / Human Interaction | OSMP-defined structural communicative act primitives; decoded by ASD lookup, no FIPA-ACL inference required |
| V | Vehicle / Transport Fleet | ITU-R M.1371-5 (AIS), NMEA 0183/IEC 61162-1, NMEA 2000/IEC 61162-3, SAE J1939, ICAO Doc 9684 |
| W | Weather / Environmental (External) | WMO No. 306 (BUFR/GRIB), NOAA CAP/OASIS CAP 1.2, ICAO METAR/TAF (Doc 8896), NWS product codes |
| X | Energy / Power Systems | IEC 61850, IEC 61970-301 (CIM), IEC 61968, OpenADR 2.0, IEEE 1547, DNP3 |
| Y | Memory + Retrieval *(AI-native)* | MemGPT (Packer et al. 2023), Voyager (Wang et al. 2023), RAG (Lewis et al. NeurIPS 2020), FAISS, Mem0, LangChain |
| Z | Model / Inference Operations *(AI-native)* | OpenAI Chat Completions API, Anthropic Messages API, Google Vertex AI API, vLLM, Ollama |
| Ω: | Sovereign Extension | Any implementing party may define additional namespaces without central authority approval. Ω (U+03A9, OMEGA, 2 UTF-8 bytes) — the glyph for the beyond-standard sovereign space. |

The four AI-native namespaces — J, Q, Y, Z — have no analog in any prior agent communication protocol. They encode the complete AI agent cognitive processing pipeline. The J→Y→Z→Q chain composes the full pipeline as a single transmissible SAL instruction sequence decodable by ASD lookup without neural inference.

### 4.2 Selected Namespace Opcodes

**A namespace (Agentic):**
`SUM` (summarize) | `CMP` (compress/compare) | `COMP` (compliance gate assertion — used in cross-namespace authorization chain I:KYC∧I:AML→I:⊤→A:COMP→K:TRD→R:⚠MOV) | `MEM` (memory operation) | `TXN` (transaction gate) | `ERR` (error handler) | `AUTH` (authorization assertion) | `DA` (delegate to agent) | `PROPOSE` / `ACCEPT` / `REJECT` (inter-agent negotiation primitives decoded by ASD lookup — not FIPA-ACL performatives)

**E namespace (Environmental):**
`TH` (temperature) | `PU` (pressure) | `OBS` (obstacle) | `E:GPS[lat,lon]` (GPS coordinates) | `UV` (ultraviolet index)

**N namespace (Network):**
`Q` (query/discovery) | `S` (status) | `CFG` (configure) | `PR` (primary relay) | `BK` (backup node) | `CMD` (command node)

**R namespace (Robotic):**
`MOV` (move) | `STOP` (stop) | `ESTOP` (emergency stop — overrides ALL policies) | `ZONE` (safety zone) | `TKOF` (takeoff) | `LAND` (landing) | `WPT` (waypoint) | `RTH` (return to home/⌂) | `HDNG` (heading) | `DPTH` (depth)

**H namespace (Health):**
`HR` (heart rate) | `SPO2` (oxygen saturation) | `BP` (blood pressure) | `ECG` (electrocardiogram) | `TEMP` (body temperature) | `TRIAGE` (triage classification) | `VITALS` (composite vital signs) | `CASREP` (casualty report) | `ICD[code]` | `CPT[code]` | `SNOMED[code]`

---

## 5. Consequence Class Designators (R Namespace)

R namespace instructions carry mandatory consequence class designators. An R namespace instruction without a valid consequence class designator in the required frame position is **malformed**.

| Glyph | Unicode | Name | Function | I:§ Required |
|---|---|---|---|---|
| ⚠ | U+26A0 | HAZARDOUS | Physical instruction with irreversible consequences requiring human authorization | Yes |
| ↺ | U+21BA | REVERSIBLE | Physical instruction that can be aborted or reversed | No |
| ⊘ | U+2298 | IRREVERSIBLE | Physical instruction producing permanent state change | Yes |

**I:§ — Human Confirmation Opcode:** U+00A7, 2 UTF-8 bytes. Required precondition for ⚠ and ⊘ R instructions. This is a safety interlock available to deployers — it is not mandated for all agentic action. Routine autonomous operation under established mandate does not require per-instruction human confirmation.

**R:ESTOP exception:** R:ESTOP overrides ALL execution policies including Atomic. Executes on receipt of any single fragment without complete fragment receipt, I namespace authorization, or node standing policy. Asymmetric harm justification: unnecessary stop is recoverable; failure to stop a physical agent in emergency is not.

**ITAR Scope Limitation:** The R namespace is directed to civilian operation only. Nothing herein covers weapons engagement, targeting systems, lethal autonomous action, or any subject matter controlled under ITAR (22 CFR Parts 120-130) or EAR (15 CFR Parts 730-774).

---

## 6. Outcome State Designators (I Namespace)

| Glyph | Unicode | Name | Function |
|---|---|---|---|
| ⊤ | U+22A4 | PASS/TRUE | Successful verification outcome |
| ⊥ | U+22A5 | FAIL/FALSE | Failed verification outcome |

Example: `I:KYC@SUBJ→I:⊤∨I:⊥`

---

## 7. Parameter and Slot Designators

| Glyph | Unicode | Name | Function |
|---|---|---|---|
| Δ | U+0394 | DELTA | Difference, spacing, or offset parameter |
| ⌂ | U+2302 | HOME | Origin or home position reference |
| ⊗ | U+2297 | ABORT/CANCEL | Abort condition trigger or comms-denial state |
| τ | U+03C4 | TIMEOUT | Time constant or timeout duration |
| ∈ | U+2208 | SCOPE/WITHIN | Set membership for scope or permission boundary |
| ∖ | U+2216 | MISSING | Set minus; missing fragment indicator in NACK payloads |

---

## 8. Overflow Protocol (OP)

### 8.1 Fragmentation Tiers

**Tier 1 — Single Packet (No Fragmentation)**
Condition: Complete encoded instruction fits within single packet.
LoRa constraint floor: ≤51 bytes at SF12 BW125kHz. Standard deployment (SF11 BW250kHz / Meshtastic LongFast): 255 bytes.

**Tier 2 — Sequential Burst**
Condition: Total instruction size known at transmit time; exceeds single packet; no conditional branching.
Behavior: Split into sequenced fragments. Each fragment independently parseable. Partial execution possible on packet loss.

Fragment header fields:
| Field | Size | Description |
|---|---|---|
| MSG_ID | 2B | Message identifier |
| FRAG_IDX | 1B | Fragment index |
| FRAG_CT | 1B | Total fragment count |
| FLAGS | 1B | T (terminal) / C (criticality override) |
| DEP | 1B | Dependency pointer |

**Tier 3 — DAG Decomposition**
Condition: Instruction set contains conditional branches or dependency chains.
Behavior: Instruction tree decomposed into a directed acyclic graph (DAG) of executable units. Each unit carries dependency pointer. Receiving node uses dependency-resolution buffer to reconstruct execution order. Executes maximal subset resolvable under received fragments.

### 8.2 Loss Tolerance Policies

| Code | Name | Behavior | Config Syntax |
|---|---|---|---|
| Φ | Fail-Safe | Incomplete receipt after timeout → silent discard. No partial execution. | `N:CFG@[nodeID]:FRAG[Φ]:τ[n]` |
| Γ | Graceful Degradation | Execute maximum subset of received fragments whose dependencies are satisfied. | `N:CFG@[nodeID]:FRAG[Γ]:τ[n]` |
| Λ | Atomic | No fragment executes unless ALL fragments received within timeout. Incomplete receipt produces NACK: `A:NACK[MSG:[id]∖[missing_indices]]` | `N:CFG@[nodeID]:NS[namespace_list]:FRAG[Λ]:τ[n]` |

**Per-message override:** FLAGS[C] bit overrides node standing policy for that individual message.

**Canonical AT candidates:** K namespace (financial) and H namespace (clinical) — irreversible consequences of partial execution.

### 8.3 CDSAFE — Comms-Denial Safe State

On comms-denial timeout expiry, node executes pre-encoded safe state instruction from Local Context Store.

Config: `N:CFG@[nodeID]:COMMS[⊗]:τ[n]:EXEC[instruction]`

Example: `R:RTH@⌂` for UAV, `R:SRFC` for UUV.

---

## 9. Frame Negotiation Protocol (FNP)

FNP enables dynamic vocabulary expansion within constrained-bandwidth channel limits. Complete vocabulary negotiation within LoRa payload constraints across two messages.

**Message 1 — Capability Advertisement (≤40 bytes):**
Transmitting node declares current ASD version, supported namespace prefixes, and available capability slots.

**Message 2 — Capability Acknowledgment (≤40 bytes):**
Receiving node confirms shared vocabulary intersection, negotiated ASD version, and session parameters.

Post-handshake: both nodes operate against the negotiated ASD version for the session duration.

**Gossip propagation:** Negotiated session parameters propagate to adjacent nodes via gossip protocol, extending vocabulary expansion without per-pair handshake overhead.

---

## 10. Dictionary Synchronization

### 10.1 Delta Packetization

Dictionary updates are deconstructed into independently parseable delta units, each carrying a version pointer and position index. Reuses Overflow Protocol tier 2 fragment header structure.

### 10.2 Update Resolution Modes

| Mode | Behavior | Criticality Flag |
|---|---|---|
| + | New entry appended; existing entry preserved; version pointer incremented | Standard |
| ← | New entry supersedes existing; prior definition retired | Mandatory FLAGS[C] — retransmit on loss, no graceful degradation |
| † | Entry marked retired; resolution preserved for backward compatibility; staleness flag logged | Standard |

### 10.3 Guaranteed Minimum Operational Vocabulary Floor

A version-pinned subset of the ASD basis set unconditionally present on every sovereign node regardless of dictionary synchronization state, network connectivity, or duration of off-grid operation. Instructions authored exclusively against floor-version glyphs are **baseline-layer instructions** guaranteed executable at any node in any synchronization state.

---

## 11. Example Instructions

| ID | Description | Encoded | Natural Language | NL Bytes | OSMP Bytes | Reduction |
|---|---|---|---|---|---|---|
| EQ | Environmental query | `EQ@4A?TH:0` | Node 4A, report temperature at offset zero. | 47 | 10 | 78.7% |
| BA | Building alert broadcast | `BA@BS!` | Alert all building sector nodes. | 32 | 6 | 81.3% |
| AR | Agentic request | `AR@EP:1` | Request emergency protocol, priority 1. | 38 | 7 | 81.6% |
| MEDEVAC | Biometric threshold alert | `H:HR@NODE1>120→H:CASREP∧M:EVA@*` | If heart rate at node 1 exceeds 120, assemble casualty report and broadcast evacuation to all nodes. | 103 | 24 | 76.7% |
| PARALLEL | Multi-query | `A∥[?WEA∧?NEWS∧?CAL]` | Simultaneously query weather, news, and calendar. | 52 | 22 | 57.7% |
| FINANCIAL | Atomic payment | `K:PAY@RECV:I:§↔K:XFR[amount]` | Execute payment to receiver if and only if human confirmation received, then transfer asset. | 94 | 31 | 67.0% |

---

## 12. Compression Data

| Metric | Value | Basis |
|---|---|---|
| UTF-8 compression range | 68.3% – 87.5% | 20 representative instruction types, Spec §II.D / Exhibit A |
| Token compression range | 55.2% – 79.2% | cl100k approximation |
| LoRa floor | 51 bytes | SF12 BW125kHz maximum-range spreading factor |
| Standard deployment | 255 bytes | SF11 BW250kHz / Meshtastic LongFast |
| Two-tier corpus reduction | 72.7% | 5000-byte medical corpus, partial MDR, LZMA second tier |
| Two-tier compression multiplier | 3.7x | vs. natural language + LZMA baseline |

---

## 13. Conformance

A conformant OSMP implementation MUST:

1. Implement all glyph operators defined in Section 3.2 with their specified Unicode code points
2. Implement at least one standard namespace from Section 4.1
3. Implement the guaranteed minimum operational vocabulary floor per Section 10.3
4. Implement Overflow Protocol Tier 1 and at least one of Tier 2 or Tier 3
5. Implement at least one loss tolerance policy from Section 8.2
6. Produce UTF-8 byte reduction ≥60% on the standard benchmark instruction set (see test vectors)
7. Decode any conformant OSMP instruction by table lookup without neural inference

A conformant implementation MAY:

- Implement sovereign namespace extensions (Ω: prefix, U+03A9, 2 UTF-8 bytes)
- Implement FNP dynamic vocabulary expansion
- Implement dictionary delta synchronization
- Implement the full namespace suite

---

## 14. Test Vectors

See `/protocol/test-vectors/` for the canonical test vector suite. Every conformant implementation must pass all test vectors before submission to the community registry.

---

## 15. Patent Notice

This protocol specification is provided under Apache 2.0 license. The underlying architecture is covered by pending US patent application OSMP-001-UTIL (inventor: Clay Holberg), filed March 16, 2026, with priority date August 7, 2025. A continuation-in-part application (OSMP-001-CIP) extends coverage to cloud-scale AI orchestration, non-RF channels, and the AI-native namespace architecture. Apache 2.0 includes an express patent grant for implementations of this specification.

---

## 16. Contributing

See `CONTRIBUTING.md`. SDK implementations in any language are welcome. All implementations must pass the canonical test vector suite in `/protocol/test-vectors/`. Architecture decisions are documented in `/docs/adr/`.
