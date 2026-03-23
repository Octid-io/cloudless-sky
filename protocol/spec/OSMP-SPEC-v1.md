# OSMP Protocol Specification v1.0
## Octid Semantic Mesh Protocol — Cloudless Sky Project

**Status:** Draft for community review  
**Docket:** OSMP-001-UTIL (patent pending)  
**Inventor:** Clay Holberg  
**License:** Apache 2.0

---

## Abstract

The Octid Semantic Mesh Protocol (OSMP) is a bandwidth-agnostic application-layer wire protocol for semantic instruction encoding in agentic AI systems. OSMP enables AI-to-AI and human-to-AI instruction exchange across any communication channel — from 51-byte LoRa radio payloads to high-bandwidth cloud infrastructure — using a composable domain-specific symbolic instruction format (Semantic Assembly Language, or SAL), an adaptive shared compression dictionary (Adaptive Shared Dictionary, or ASD), and a capability negotiation and session handshake protocol (Frame Negotiation Protocol, or FNP).

OSMP achieves mean 60.8% UTF-8 byte reduction relative to natural language equivalents across the 55-vector canonical test suite (range varies by instruction complexity; up to 82.1% on short imperative instructions). Decode is a table lookup operation requiring no neural inference at the receiving node. Any device capable of string processing can participate as a sovereign OSMP node.

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
| ⟳ | U+27F3 | REPEAT-EVERY | Interval and recurrence composition | every, repeat at interval, recur |
| ≠ | U+2260 | NOT-EQUAL | Slot value exclusion filter | not equal to, excluding, other than |
| ⊕ | U+2295 | PRIORITY-ORDER | Strict ranked execution across parallel instructions when resources are constrained | prioritize, ranked order, prefer |

### 3.3 Compound Operator

| Glyph | Unicode | Name | Function |
|---|---|---|---|
| ¬→ | U+00AC + U+2192 | UNLESS | Negated conditional |

### 3.4 Compression Properties

TCL glyph substitution alone reduces character count 5-25% depending on instruction type prior to opcode encoding. Combined with full OSMP encoding: **mean 60.8% UTF-8 byte reduction** across the 55-vector canonical test suite (range 0.0% to 82.1%). On the 20 representative instruction types in the provisional filing Datasets A-D (longer, more complex instructions averaging 115 bytes NL), the range is 68.3%-87.5%.

Measurement basis: UTF-8 byte count (`len(s.encode('utf-8'))` in Python). All numbers are independently reproducible by running the benchmark against the canonical test vectors.

Two-tier corpus compression (D:PACK): SAL first tier + lossless dictionary-based compression second tier. Two profiles are defined: D:PACK/LZMA for companion devices with adequate SRAM for full-corpus decompression, and D:PACK/BLK (zstd, block-level random access) for microcontroller targets where full-corpus decompression exceeds available SRAM. On a 5,000-byte partial medical domain corpus, this architecture achieved 72.7% total reduction and 3.7x compression multiplier versus natural language + LZMA baseline, with the SAL tier contributing a larger proportion on the small sample. At full scale on CMS FY2026 ICD-10-CM (74,719 clinical descriptions, 5.4MB raw): D:PACK/LZMA produced a 505KB binary (91.1% reduction); D:PACK/BLK produced a 477KB binary (91.4% reduction, dict-free) with single-code resolution requiring only 38KB of SRAM versus 6,177KB for the LZMA profile. On ISO 20022 eRepository (66,956 financial definitions, 8.7MB raw), D:PACK/BLK achieved 86.5% total reduction in a 1.21MB binary (dict-free); D:PACK/LZMA achieved 87.2% in a 1.14MB binary. The SAL first tier contributes 8-16% depending on corpus repetitiveness; the second tier contributes the dominant share. The primary value of the two-tier architecture at full scale is edge-local deployment: entire domain code libraries in microcontroller flash for infrastructure-denied operations without network dependency.

### 3.5 Six-Category Typed Symbol Architecture

The OSMP glyph system comprises six functionally distinct symbol categories. Categories 2 through 6 may not be substituted for Category 1 operators within instruction grammar; cross-category substitution produces a grammatically invalid, non-executable instruction.

**Category 1 -- Logical and Compositional Operators (18 total):**
∧ ∨ ¬ → ↔ ∀ ∃ @ ∥ > ~ * : ; ? ⟳ ≠ ⊕ (plus compound ¬→). These bind, negate, sequence, quantify, and compose instruction elements across all namespaces.

**Category 2 -- Consequence Class Designators:**
⚠ (U+26A0, HAZARDOUS), ↺ (U+21BA, REVERSIBLE), ⊘ (U+2298, IRREVERSIBLE), § (U+00A7, HUMAN-AUTHORIZED in I namespace). These classify the physical-world impact of R namespace instructions and occupy the mandatory consequence class slot in R namespace instruction frames. An R namespace instruction without a valid Category 2 designator in the required frame position is malformed and non-executable.

**Category 3 -- Outcome State Designators:**
⊤ (U+22A4, PASS/TRUE), ⊥ (U+22A5, FAIL/FALSE). Formal logical constants predating OSMP; adopted for pre-existing definitions, not arbitrary assignment.

**Category 4 -- Parameter and Slot Designators:**
Δ (U+0394, DELTA), ⌂ (U+2302, HOME), ⊗ (U+2297, ABORT/CANCEL), τ (U+03C4, TIMEOUT), ∈ (U+2208, SCOPE/WITHIN), ∖ (U+2216, MISSING -- set minus, for NACK fragment identification).

**Category 5 -- Loss Tolerance Policy Designators:**
Φ (U+03A6, FAIL-SAFE -- fundamental invariant, silent discard on incomplete receipt), Γ (U+0393, GRACEFUL-DEGRADATION -- graduated threshold, execute satisfiable subset; default policy), Λ (U+039B, ATOMIC -- indivisible function, all-or-nothing execution). Greek uppercase letters whose pre-existing mathematical meanings map directly to their policy semantics. Configuration syntax: `N:CFG@[nodeID]:FRAG[Φ|Γ|Λ]:τ[n]`.

**Category 6 -- Dictionary Update Mode Designators:**
+ (U+002B, ADDITIVE -- append entry, preserve prior), ← (U+2190, REPLACE -- supersede and retire prior, mandatory retransmit), † (U+2020, DEPRECATE -- mark retired, preserve backward compatibility). Used exclusively in dictionary delta payload mode fields. REPLACE operations require mandatory FLAGS[C] (criticality override) to ensure retransmit-on-loss; graceful degradation is not permitted for dictionary replacement operations.

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

Namespace addressing operates in three tiers: Tier 1 comprises the 26 single-letter standard prefixes (A-Z) defined above. Tier 2 comprises 351 order-invariant two-character MDR-registered prefixes (AB=BA canonical form, AA-ZZ all valid), providing domain-specific extension capacity without Ω sovereign scope. Tier 3 is the unlimited Ω sovereign extension space, available to any implementing party without registration.

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
Behavior: Instruction tree decomposed into a directed acyclic graph (DAG) of executable units. Each unit carries dependency pointer. Receiving node uses dependency-resolution buffer to reconstruct execution order via topological sort (Kahn's algorithm). Executes maximal subset resolvable under received fragments.

Fragment header remains 6 bytes (shared with Tier 2). The DEP byte encodes single-parent dependencies directly. Root convention: DEP == FRAG_IDX (self-reference) signals no dependency; this is unambiguous because a fragment cannot depend on itself. Tier 2 fragments (DEP=0x00 on fragment 0) remain valid under this convention.

Multi-parent dependencies (diamond joins): FLAGS bit 3 (0x08, EXTENDED_DEP) signals that the first 4 bytes of payload are a big-endian u32 dependency bitmap, where bit N indicates dependency on fragment N. The DEP header byte carries the primary parent for legacy readers. The 32-bit bitmap supports up to 32 fragments per message; practical DAG depth is 3-8 nodes.

Execution order under loss tolerance:
- **Φ (Fail-Safe):** All fragments required; discard on incomplete receipt.
- **Γ (Graceful Degradation):** Execute the maximal subgraph whose full ancestor chains are present (topological sort of resolvable subset).
- **Λ (Atomic):** All fragments required; NACK on incomplete receipt.

R:ESTOP exception: Any fragment containing R:ESTOP executes immediately on receipt, regardless of DAG position, dependency state, or loss tolerance policy.

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

### 8.4 BAEL -- Bandwidth-Agnostic Efficiency Layer

BAEL dynamically selects among three encoding representation modes based on minimum byte count, providing a compression floor guarantee: OSMP encoding never increases byte count over natural language input.

**Mode 1 -- FULL_OSMP (FLAGS=0x00):** Namespace-prefixed opcodes connected by glyph operators, decoded by ASD lookup. Standard encoding mode.

**Mode 2 -- TCL_ONLY (FLAGS=0x02):** Glyph substitution of logical operators only, without full opcode encoding. Selected when TCL-only encoding produces fewer bytes than full OSMP encoding.

**Mode 3 -- NL_PASSTHROUGH (FLAGS=0x04):** Natural language transmitted as-is, signaled by bit 2 in the fragment header FLAGS field. Selected when natural language byte count is less than or equal to the byte count of any available OSMP encoding.

Mode selection is governed by O namespace operational context instructions (`O:CHAN`, `O:FLOOR`) transmitted as co-equal structural elements of the instruction stream, grounding BAEL channel adaptation in explicit addressable instruction state rather than abstract layer behavior.

The NL_PASSTHROUGH mode ensures that very short natural language instructions (e.g., "Stop") are never inflated by encoding overhead. A receiving node checks bit 2 of the FLAGS field; if set, the payload is interpreted as natural language without ASD lookup.

---

## 9. Frame Negotiation Protocol (FNP)

FNP establishes session state between two sovereign nodes in two packets totaling 78 bytes. It negotiates three properties: dictionary alignment, namespace intersection, and channel capacity.

### 9.1 Message 1: Capability Advertisement (40 bytes)

| Offset | Size | Field | Description |
|---|---|---|---|
| 0 | 1B | msg_type | 0x01 (ADV) |
| 1 | 1B | protocol_version | 0x01 |
| 2 | 8B | fingerprint | First 8 bytes of SHA-256(canonical ASD JSON) |
| 10 | 2B | asd_version | ASD version, big-endian u16 |
| 12 | 4B | namespace_bitmap | Bit 0=A, bit 1=B, ..., bit 25=Z, bit 26=Omega. Big-endian u32 |
| 16 | 1B | channel_capacity | 0x00=51B (LoRa floor), 0x01=255B, 0x02=512B (BLE), 0x03=unconstrained |
| 17 | 23B | node_id | UTF-8, null-padded |

### 9.2 Message 2: Capability Acknowledgment (38 bytes)

| Offset | Size | Field | Description |
|---|---|---|---|
| 0 | 1B | msg_type | 0x02 (ACK) or 0x03 (NACK) |
| 1 | 1B | match_status | 0x00=exact, 0x01=version mismatch, 0x02=fingerprint mismatch |
| 2 | 8B | echo_fingerprint | Fingerprint from received ADV (echo for verification) |
| 10 | 8B | own_fingerprint | Responder's own ASD fingerprint |
| 18 | 4B | common_namespaces | Intersection of both namespace bitmaps. Big-endian u32 |
| 22 | 1B | neg_capacity | Negotiated capacity = min(adv, own). LCD of the link. |
| 23 | 15B | node_id | UTF-8, null-padded |

### 9.3 Fingerprint Computation

The ASD fingerprint is the first 8 bytes of SHA-256 over the canonical JSON serialization of the ASD data. Canonical JSON matches Python `json.dumps(data, sort_keys=True)`: keys sorted alphabetically, separators `", "` and `": "`, non-ASCII escaped to `\uXXXX`. All three SDKs (Python, TypeScript, Go) produce identical fingerprints for identical dictionary state.

### 9.4 Channel Capacity Negotiation

The session byte budget is the minimum of what both nodes declare. An ESP32 on LoRa (0x00, 51B) meeting a phone on BLE (0x02, 512B) negotiates down to 51B. BAEL selects encoding mode within this budget for every subsequent instruction. The mesh scales within the most constrained link, not the most capable one.

| Class | Value | Bytes | Channel |
|---|---|---|---|
| FLOOR | 0x00 | 51 | LoRa SF12 BW125kHz |
| STANDARD | 0x01 | 255 | LoRa SF11 BW250kHz / Meshtastic LongFast |
| BLE | 0x02 | 512 | Bluetooth Low Energy |
| UNCONSTRAINED | 0x03 | 0 (no limit) | WiFi, HTTP, cloud |

### 9.5 State Machine

```
IDLE -> initiate() -> ADV_SENT
ADV_SENT -> receive ACK (match) -> ESTABLISHED
ADV_SENT -> receive ACK (mismatch) -> SYNC_NEEDED
ADV_SENT -> timeout -> IDLE
IDLE -> receive ADV -> send ACK -> ESTABLISHED or SYNC_NEEDED
```

ESTABLISHED: dictionaries match, session active. SYNC_NEEDED: fingerprint or version mismatch detected, delta synchronization required (see section 10).

### 9.6 Gossip Propagation

Negotiated session parameters propagate to adjacent nodes via gossip protocol, extending vocabulary expansion without per-pair handshake overhead.

---

## 10. Dictionary Synchronization

### 10.1 Delta Packetization

Dictionary updates are deconstructed into independently parseable delta units, each carrying a version pointer and position index. Reuses Overflow Protocol tier 2 fragment header structure.

### 10.2 Update Resolution Modes

Dictionary delta operations use Category 6 glyph designators (see §3.5) as mode fields in delta payloads. Each mode has a CRDT analog governing conflict resolution in distributed dictionary synchronization.

| Mode | Glyph | CRDT Analog | Behavior | Criticality Flag |
|---|---|---|---|---|
| ADDITIVE | + (U+002B, 1 byte) | Grow-only set (G-Set) | New entry appended; existing entry preserved; version pointer incremented | Standard |
| REPLACE | ← (U+2190, 3 bytes) | Last-write-wins register (LWW-Register) | New entry supersedes existing; prior definition retired | Mandatory FLAGS[C] -- retransmit on loss, no graceful degradation |
| DEPRECATE | † (U+2020, 3 bytes) | Tombstone (2P-Set) | Entry marked retired; resolution preserved for backward compatibility; staleness flag logged | Standard |

REPLACE operations must use FLAGS[C] (criticality override in the fragment header). A REPLACE delta lost in transit and not retransmitted leaves the receiving node with a stale dictionary entry, which is a semantic correctness violation. Graceful degradation is not permitted for REPLACE operations; the criticality flag forces Atomic execution policy for that specific delta regardless of the node's standing loss tolerance policy.

### 10.3 Guaranteed Minimum Operational Vocabulary Floor

A version-pinned subset of the ASD basis set unconditionally present on every sovereign node regardless of dictionary synchronization state, network connectivity, or duration of off-grid operation. Instructions authored exclusively against floor-version glyphs are **baseline-layer instructions** guaranteed executable at any node in any synchronization state.

### 10.4 ASD Distribution Protocol (ADP)

The ADP extends FNP binary handshake with SAL-level instructions for dictionary synchronization over mesh and gossip channels where binary FNP is not the transport. ADP instructions are A namespace opcodes using existing Category 6 glyph designators for delta operations.

#### 10.4.1 Version Scheme

ASD versions use the existing FNP `asd_version` u16 field (Section 9.1, offset 10) interpreted as u8.u8: upper byte is MAJOR, lower byte is MINOR. MAJOR increments on breaking changes (REPLACE or RETRACT). MINOR increments on additive changes (ADD, DEPRECATE, EXTEND) and resets to 0 on MAJOR bump. The wire format is unchanged; the interpretation is a display convention.

Breaking-change detection from version number alone: compare upper bytes. If `(new >> 8) > (old >> 8)`, the version gap contains at least one REPLACE operation requiring session renegotiation.

SAL display: `2.7` (u16 value 0x0207). Range: 0.0 through 255.255.

MDR corpora carry separate version identifiers using the source authority's own version scheme (e.g., ICD-10-CM uses calendar year, MITRE ATT&CK uses major.minor).

#### 10.4.2 ADP Instructions

Seven SAL instruction patterns using two new A namespace opcodes (A:ASD, A:MDR) and the existing A:ACK:

| Instruction | Pattern | Example | Bytes | EU DR0 |
|---|---|---|---|---|
| Version identity | `A:ASD[M.m]` or `A:ASD[M.m:NsM.m:...]` | `A:ASD[2.7:H2.3:K1.0]` | 10-51 | Yes |
| Version query | `A:ASD?` | `A:ASD?` | 6 | Yes |
| Version alert | `A:ASD[M.m]⚠` | `A:ASD[2.7]⚠` | 13 | Yes |
| Delta request | `A:ASD:REQ[from→to]` | `A:ASD:REQ[2.5→2.7]` | 20 | Yes |
| Delta payload | `A:ASD:DELTA[from→to:Ns{mode}[OP]:...]` | `A:ASD:DELTA[2.5→2.7:H+[LACTATE]]` | 34-51 | Yes (single op) |
| Micro-delta request | `A:ASD:DEF?[NS:OP]` | `A:ASD:DEF?[H:LACTATE]` | 21 | Yes |
| Micro-delta response | `A:ASD:DEF[NS:OP:def:layer]` | `A:ASD:DEF[H:LACTATE:lactate_level:1]` | 36 | Yes |
| Hash verification | `A:ASD:HASH[M.m:hex]` | `A:ASD:HASH[2.7:a3f8b1c2]` | 24 | Yes |
| MDR identity | `A:MDR[corpus:ver:...]` | `A:MDR[ICD:2026:ATT:15.1]` | 24 | Yes |
| MDR request | `A:MDR:REQ[corpus:from→to]` | `A:MDR:REQ[ICD:2025→2026]` | 26 | Yes |
| Acknowledge | `A:ACK[ASD:M.m]` | `A:ACK[ASD:2.7]` | 14 | Yes |

Delta payloads use Category 6 glyph designators as mode operators within the payload: `+` (ADDITIVE), `←` (REPLACE), `†` (DEPRECATE). Multi-operation deltas exceeding 51 bytes route to the Overflow Protocol for fragmentation.

#### 10.4.3 Exchange Sequences

**Sequence 1: Version Match (no sync needed)**

```
Node A → B:  A:ASD[2.7:H2.3:K1.0]
Node B → A:  A:ASD[2.7:H2.3:K1.0]
(Match. Session proceeds.)
```

**Sequence 2: Additive Delta (safe mid-session)**

```
Node A → B:  A:ASD[2.7:H2.3:K1.0]
Node B → A:  A:ASD[2.5:H2.1:K1.0]
(K matches. H mismatch. Only H delta needed.)
Node B → A:  A:ASD:REQ[H2.1→H2.3]
Node A → B:  A:ASD:DELTA[2.5→2.7:H+[LACTATE]:H+[HRV]]
Node B:      (apply, verify)
Node B → A:  A:ACK[ASD:2.7]
```

**Sequence 3: Task-Relevant Micro-Delta**

```
Node A → B:  H:LACTATE[4.2]
Node B:      (H:LACTATE not in local ASD. Held in semantic pending queue.)
Node B → A:  A:ASD:DEF?[H:LACTATE]
Node A → B:  A:ASD:DEF[H:LACTATE:lactate_level:1]
Node B:      (apply definition, resolve pending instruction)
```

**Sequence 4: Mesh Broadcast Discovery**

```
Node A → *:  A:ASD?
Node B → A:  A:ASD[2.7]
Node C → A:  A:ASD[2.3]
Node D → A:  A:ASD[1.4]
(Node A now knows the mesh version landscape.)
```

**Sequence 5: Trickle Charge (idle bandwidth, background sync)**

```
(No active instruction traffic.)
Node D → A:  A:ASD:REQ[1.4→2.7]
Node A → D:  A:ASD:DELTA[1.4→1.5:H+[LACTATE]:H+[HRV]]
(Mission traffic arrives. Delta pauses.)
...
(Idle again. Resume.)
Node A → D:  A:ASD:DELTA[1.5→1.6:E+[SOIL]:E+[PH]]
...
Node A → D:  A:ASD:DELTA[2.6→2.7:H+[GCS]]
Node D → A:  A:ASD:HASH[2.7:a3f8b1c2]
Node A → D:  A:ACK[ASD:HASH]
```

**Sequence 6: Breaking Change**

```
Node A → B:  A:ASD:DELTA[2.7→3.0:H←[TRIAGE]]
(← signals REPLACE. Breaking change. FLAGS[C] mandatory.)
Node B:      (Active session uses H:TRIAGE. Queue delta. Do not apply.)
(Session ends.)
Node B:      (Apply delta. Renegotiate version on next session.)
```

#### 10.4.4 Semantic Pending Queue

When a node receives an instruction referencing an opcode not present in its local ASD, the instruction is held in a semantic pending queue rather than discarded or failed. The pending queue is architecturally distinct from a retransmit buffer: semantic resolution is pending receipt of a defining delta unit, not retransmission of a lost packet.

Upon receipt of a defining delta (via A:ASD:DELTA or A:ASD:DEF), the node re-evaluates all pending instructions. Instructions whose unresolved opcodes are now defined are released from the queue and executed. Instructions with remaining unresolved opcodes stay pending.

The micro-delta request (`A:ASD:DEF?[NS:OP]`) is the trigger mechanism: when a node queues an instruction as pending, it simultaneously requests the specific opcode definition from the sending node.

Patent ref: OSMP-001-UTIL Claim 20 (semantic dependency resolution buffer).

#### 10.4.5 Priority Hierarchy

ADP traffic is subordinate to mission traffic. An ASD update never blocks, delays, or degrades an active instruction exchange. Priority levels (lower number = higher priority):

| Priority | Traffic Class | Description |
|---|---|---|
| 0 | Mission | Any non-ADP instruction (H, K, E, M, etc.) |
| 1 | Micro-delta | Task-relevant single opcode definition (A:ASD:DEF) |
| 2 | Background delta | Namespace delta payload (A:ASD:DELTA) |
| 3 | Trickle charge | Version queries, delta requests, announcements |

Priority enforcement is implementation-defined. The protocol specifies the ordering; the scheduling algorithm is left to the implementing party. On constrained channels, priority 2 and 3 traffic transmits only in idle bandwidth gaps between mission instructions.

### 10.5 Two-Tier Corpus Compression (D:PACK / D:UNPACK)

`D:PACK` applies OSMP SAL encoding as a first-tier semantic compression pass, followed by a lossless dictionary-based compressor as a second-tier byte-level pass, for at-rest corpus storage. The result is a two-tier encoded corpus in which the semantic structure of the original content is preserved in the SAL intermediate representation.

`D:UNPACK` retrieves semantic content from a two-tier encoded corpus by ASD lookup against the SAL intermediate representation. The resolution path depends on the compression profile used to produce the binary.

Both opcodes are defined in the D namespace of the ASD floor vocabulary and are operational today without MDR.

#### 10.5.1 Compression Profiles

D:PACK defines two binary profiles addressing different deployment targets. Both profiles share the same first-tier SAL encoding. The second tier differs in algorithm, binary structure, and resolution strategy.

**D:PACK/LZMA** (full-corpus, companion-device profile)

Binary magic: `DPAK`. Second-tier algorithm: LZMA (Lempel-Ziv-Markov chain Algorithm). The corpus and index are each LZMA-compressed as monolithic blobs. At node startup the LZMA second tier is decompressed once into a memory-resident SAL corpus; subsequent lookups resolve by offset seek into the SAL layer and ASD expansion, with no per-lookup decompression cost. This is the zero-unpack semantic resolution property: once the SAL intermediate is resident, any code resolves to actionable clinical context by table lookup in constant time.

Deployment target: companion device with adequate SRAM for full-corpus decompression (approximately 6.2MB resident for ICD-10-CM: 4.7MB corpus + 1.4MB index).

Binary structure (DPAK v1):
- Header (48 bytes): magic (4) + version u32 BE (4) + index compressed size u32 BE (4) + corpus compressed size u32 BE (4) + SHA-256 (32)
- Index section: LZMA-compressed JSON mapping {mdr_token: [byte_offset, byte_length]}
- Corpus section: LZMA-compressed concatenated SAL text with single-byte separators

**D:PACK/BLK** (block-level, microcontroller profile)

Binary magic: `DBLK`. Second-tier algorithm: Zstandard (zstd) with optional trained dictionary. The corpus is partitioned into fixed-target blocks (default 32KB decompressed), each independently compressed. A block table in the binary header maps MDR token ranges to block offsets, enabling single-code resolution by decompressing only the containing block.

Deployment target: ESP32-class microcontroller (520KB SRAM, 4-16MB flash). The entire binary resides in flash; resolution requires loading the block table (6.3KB for ICD-10-CM) and decompressing one block into an SRAM buffer.

Binary structure (DBLK v1):
- Header (24 bytes): magic (4) + version u16 BE (2) + flags u16 BE (2, bit 0 = has trained dictionary) + block count u32 BE (4) + dictionary offset u32 BE (4) + dictionary size u32 BE (4) + blocks offset u32 BE (4)
- Block table (block_count * 44 bytes): first code (32 bytes, null-padded UTF-8) + block offset u32 BE (4, relative to blocks section) + compressed size u32 BE (4) + entry count u16 BE (2) + reserved (2)
- Dictionary section (optional, default 32KB trained zstd dictionary)
- Block data section (concatenated zstd-compressed blocks)

Each decompressed block contains sorted lines of the form `MDR_TOKEN\tSAL_TEXT`, separated by newlines.

Resolution path (D:PACK/BLK):
1. Binary search block table by first_code to identify target block
2. Read compressed block from flash (2-10KB typical)
3. Decompress single block into SRAM buffer (32-39KB typical)
4. Linear scan within decompressed block for target MDR token
5. Return SAL text

BAEL integration: when the Bandwidth-Agnostic Efficiency Layer selects D:PACK for corpus storage, the profile is selected based on the node's O namespace channel capacity declaration. Nodes declaring constrained-memory operation use D:PACK/BLK; nodes declaring companion-device capacity use D:PACK/LZMA. Profile selection is a deployment-time decision, not a per-message decision.

ESP32 SRAM budget (C implementation, D:PACK/BLK, dict-free):
- Block table: 6.3 KB (146 blocks for ICD-10-CM)
- zstd decompression context: approximately 32 KB
- Decompression window buffer: 38.2 KB (matches content size)
- Output buffer: 40 KB
- Total: approximately 117 KB (22% of 520KB SRAM)

#### 10.5.2 Empirical Results

On a 5,000-byte partial medical domain corpus, D:PACK achieved 72.7% total reduction and 3.7x compression multiplier versus natural language + LZMA baseline.

Full-scale results on the CMS FY2026 ICD-10-CM code set (74,719 clinical descriptions, 5.4MB raw):

| Profile | Binary size | Reduction vs raw | Corpus | Index/Table | Dict | Resolution memory |
|---|---|---|---|---|---|---|
| D:PACK/LZMA | 505 KB | 91.1% | 282 KB | 211 KB | n/a | 6,177 KB (full decompress) |
| D:PACK/BLK | 477 KB | 91.4% | 471 KB (146 blocks) | 6.3 KB | n/a | 38 KB (single block) |

The D:PACK/BLK dict-free profile is 3.3% smaller than D:PACK/LZMA on ICD-10-CM and 5.5% larger on ISO 20022. The dict-free format eliminates trained dictionary overhead, enabling a single binary readable by all three SDKs (Python, TypeScript, Go) with no native decompression dependencies in the TypeScript path. The primary advantage of the BLK profile is not total size but resolution memory: 38 KB versus 6,177 KB (ICD-10-CM) or 9,941 KB (ISO 20022), enabling on-device code resolution at microcontroller scale without full-corpus decompression.

On the complete ISO 20022 eRepository (66,956 financial message element definitions, 8.7MB raw), D:PACK/BLK achieved 86.5% total reduction in a 1,207KB dict-free binary (201 blocks); D:PACK/LZMA achieved 87.2% in a 1,143KB binary (843KB corpus + 327KB index). The SAL first tier contributed 15.8% on clinical text and 8.4% on financial text; the second tier contributed the dominant share on both corpora.

The primary value of the two-tier architecture at full scale is edge-local deployment: entire domain code libraries in microcontroller flash for infrastructure-denied operations without network dependency.

---

## 11. Example Instructions

| ID | Description | Encoded | Natural Language | NL Bytes | OSMP Bytes | Reduction |
|---|---|---|---|---|---|---|
| EQ | Environmental query | `EQ@4A?TH:0` | Node 4A, report temperature at offset zero. | 43 | 10 | 76.7% |
| BA | Building alert broadcast | `BA@BS!` | Alert all building sector nodes. | 32 | 6 | 81.2% |
| AR | Agentic request | `AR@EP:1` | Request emergency protocol, priority 1. | 39 | 7 | 82.1% |
| MEDEVAC | Biometric threshold alert | `H:HR@NODE1>120→H:CASREP∧M:EVA@*` | If heart rate at node 1 exceeds 120, assemble casualty report and broadcast evacuation to all nodes. | 100 | 35 | 65.0% |
| PARALLEL | Multi-query | `A∥[?WEA∧?NEWS∧?CAL]` | Simultaneously query weather, news, and calendar. | 49 | 25 | 49.0% |
| FINANCIAL | Atomic payment | `K:PAY@RECV↔I:§→K:XFR[AMT]` | Execute payment to receiver if and only if human operator confirmation received, then transfer asset. | 101 | 30 | 70.3% |

---

## 12. Compression Data

| Metric | Value | Basis |
|---|---|---|
| UTF-8 compression range (provisional) | 68.3% -- 87.5% | 20 instruction types in provisional filing Datasets A-D |
| UTF-8 compression range (55-vector suite) | 0.0% -- 82.1% | 55 canonical test vectors, full range |
| Mean UTF-8 reduction (55-vector suite) | 60.8% | Conformance benchmark, independently reproducible |
| Token compression range | 55.2% -- 79.2% | cl100k approximation, provisional Datasets A-D |
| LoRa floor | 51 bytes | SF12 BW125kHz maximum-range spreading factor |
| Standard deployment | 255 bytes | SF11 BW250kHz / Meshtastic LongFast |
| Two-tier corpus reduction (partial) | 72.7% | 5,000-byte partial medical corpus, SAL + LZMA |
| Two-tier multiplier (partial) | 3.7x | vs. natural language + LZMA baseline on partial corpus |
| D:PACK/LZMA binary (ICD-10-CM) | 505 KB | CMS FY2026, 74,719 codes, 5.4MB raw, SAL + LZMA |
| D:PACK/LZMA reduction (ICD-10-CM) | 91.1% | vs. raw description text |
| D:PACK/LZMA resolution memory | 6,177 KB | Full corpus + index decompressed into SRAM |
| D:PACK/BLK binary (ICD-10-CM) | 477 KB | CMS FY2026, 74,719 codes, SAL + zstd dict-free, 146 blocks |
| D:PACK/BLK reduction (ICD-10-CM) | 91.4% | vs. raw description text |
| D:PACK/BLK resolution memory | 38 KB | Single block decompress, ESP32 target |
| D:PACK/BLK resolve latency | 0.1 -- 0.3 ms | Single-code, Python reference SDK |
| D:PACK/BLK format | dict-free | Universal format, all SDKs, no trained dictionary |
| D:PACK/BLK vs LZMA size | -3.3% (ICD), +5.5% (ISO) | BLK smaller on ICD, larger on ISO; tradeoff is resolution memory |
| Two-tier corpus reduction (full ISO 20022, BLK) | 86.5% | ISO 20022 eRepository, 66,956 definitions, 8.7MB raw, SAL + zstd dict-free |
| Two-tier corpus reduction (full ISO 20022, LZMA) | 87.2% | ISO 20022 eRepository, 66,956 definitions, 8.7MB raw, SAL + LZMA |
| D:PACK/BLK binary (ISO 20022) | 1,207 KB | Full ISO 20022 data dictionary (201 blocks, dict-free) |
| D:PACK/LZMA binary (ISO 20022) | 1,143 KB | Full ISO 20022 data dictionary (843KB corpus + 327KB index) |
| SAL first-tier contribution (clinical) | 15.8% | Highly repetitive clinical description text |
| SAL first-tier contribution (financial) | 8.4% | Financial message element definitions |

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
- Implement ASD Distribution Protocol (ADP) SAL-level synchronization per Section 10.4
- Implement the semantic pending queue per Section 10.4.4
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
