# Cloudless Sky

**Agentic AI mesh without the cloud.**

OSMP (Octid Semantic Mesh Protocol) is an open encoding standard for agentic AI instruction exchange. It works across any channel — from a 51-byte LoRa radio packet to a high-throughput cloud inference pipeline — using the same grammar, the same dictionary, and the same decode logic.

No cloud required. No inference at the decode layer. No central authority.

<p align="center">
  <img src="assets/octid-openclaw.png" alt="Octid and the OpenClaw community" width="480">
</p>

---

## The Problem

When AI agents communicate in JSON over HTTP, the cost compounds at every hop.

```json
{"action": "move", "agent": "BOT1", "waypoint": "WP1", "priority": "urgent"}
```

82 bytes of JSON envelope before you put any content in. Requires tokenization. Requires inference to parse. Fails completely at the 51-byte LoRa minimum payload.

## The Solution

```
R:MOV@BOT1:WPT:WP1↺
```

21 bytes. Decode is a table lookup. Fits a single LoRa packet at maximum-range spreading factor. No inference required at the receiving node. The LLM's existing NL→structured output capability handles the translation. The system prompt supplies the SAL grammar, the ASD, and examples from the canonical test vectors. No new tooling required on the generating side. What OSMP changes is the output format, and the decode layer: the receiving node does a table lookup, not inference.

---

## Integration Path

OSMP replaces JSON as the agent instruction serialization format. An LLM that currently outputs:

```
"If heart rate at node 1 exceeds 120, assemble casualty report
 and broadcast evacuation to all nodes."

→ 100 bytes. Requires tokenization. Requires inference to parse.
  Fails completely at 51-byte LoRa minimum payload.
```

can be configured via system prompt to output:

```
H:HR@NODE1>120→H:CASREP∧M:EVA@*

→ 35 bytes. 65% reduction. Decode is a table lookup.
  Fits a single LoRa packet at maximum-range spreading factor.
  No inference required at the receiving node.
```

---

## Measured Performance

<table>
<tr>
<td align="center"><h1>86.8%</h1><b>byte reduction vs JSON</b><br>29 real-world vectors from 5 frameworks</td>
<td align="center"><h1>70.5%</h1><b>byte reduction vs protobuf</b><br>compiled schemas, protoc 3.21.12</td>
<td align="center"><h1>76.0%</h1><b>fewer tokens (GPT-4)</b><br>cl100k_base tokenizer, 1,809 → 434</td>
</tr>
</table>

Compression claims are measured, not estimated. The [29-vector SAL vs JSON benchmark](benchmarks/sal-vs-json/) uses real wire-format payloads from MCP, OpenAI, Google A2A, CrewAI, and AutoGen. Full methodology and adversarial review in the [whitepaper](docs/SAL-efficiency-analysis.md).

---

## Quick Start

### MCP Server (any AI client)
```bash
pip install osmp-mcp
osmp-mcp
```

Installs the MCP server with three domain corpora (ICD-10-CM, ISO 20022, MITRE ATT&CK) included. Connect from Claude Code (`claude mcp add osmp -- osmp-mcp`), Claude Desktop, Cursor, or any MCP-compatible client. Listed on the [MCP Registry](https://registry.modelcontextprotocol.io) as `io.github.Octid-io/osmp`.

### From source
```bash
git clone https://github.com/octid-io/cloudless-sky
cd cloudless-sky
python3 sdk/python/src/osmp.py
```

No dependencies beyond Python standard library.

### npm
```bash
npm install osmp-protocol
```

### Go
```go
import "github.com/octid-io/cloudless-sky/sdk/go/osmp"
```

---

## Why OSMP Is Different From Every Other Agent Protocol

| Protocol | Transport | Offline | Compression | Inference-Free Decode |
|---|---|---|---|---|
| MCP (Anthropic) | HTTP/JSON | ✗ | ✗ | ✗ |
| A2A (Google/Linux Foundation) | HTTPS/JSON | ✗ | ✗ | ✗ |
| ACP (IBM) | REST/HTTP | ✗ | ✗ | ✗ |
| **OSMP** | **Any channel** | **✓** | **86.8% vs JSON** | **✓** |

MCP, A2A, and ACP are framework-layer protocols. OSMP is an encoding-layer protocol. It operates beneath any of them. Two agents using different frameworks that share the OSMP grammar and dictionary can communicate with no modification to either framework.

---

## SDK Status

All three SDKs are independently verified against the canonical test suite. Wire compatibility is confirmed: Python, TypeScript, and Go produce field-for-field identical decode results across every namespace, every operator, and every edge case documented in the spec. D:PACK/BLK resolve is verified across all 124,215 domain codes (74,719 ICD-10-CM + 47,835 ISO 20022 + 1,661 MITRE ATT&CK) in all three SDKs.

| SDK | Target | Conformance | Notes |
|---|---|---|---|
| **Python** | Reference implementation | CONFORMANT | Single source of truth for all SDK behavior |
| **TypeScript** | OpenClaw / web agent integrations | CONFORMANT | `fzstd` (82KB, pure JS, zero native deps) for D:PACK/BLK |
| **Go** | PicoClaw / constrained hardware | CONFORMANT | ASD compiled-in; D:PACK/BLK via `klauspost/compress/zstd` (3.1MB binary) |
| **MCP Server** | Any MCP-compatible AI client | `pip install osmp-mcp` | 8 tools: encode, decode, compound_decode, lookup, discover, resolve, batch_resolve, benchmark |

### Benchmark

```
$ python3 sdk/python/src/osmp.py

OSMP BENCHMARK — Cloudless Sky Protocol v1.0
SDK: Python (reference)

  ID         NL Bytes OSMP Bytes  Reduction
  ✓ TV-001         43         10      76.7%
  ✓ TV-013        100         35      65.0%
  ✓ TV-015        101         30      70.3%
  ...

  Mean reduction: 60.8%
  CONFORMANT ✓  (mean 60.8% vs 60.0% threshold)
```

Run it yourself. The numbers are real and independently reproducible across all three SDKs.

---

## What OSMP Delivers Today

Everything here is operational from the floor ASD without MDR, cloud access, or additional tooling.

**Instruction encoding across all 26 standard namespaces** — 341 opcodes drawn from authoritative sources: IEC 61850 (energy), ICD-10/SNOMED CT/CPT (clinical), ISO 20022/FIX/SWIFT (financial), ISO 10218-1:2025 (robotics), FEMA ICS/NIMS (emergency management), BDI/PDDL/HTN (cognitive AI), OpenAI/Anthropic APIs (model operations).

**Four AI-native namespaces** — J (Cognitive Execution State), Q (Quality/Evaluation/Grounding), Y (Memory + Retrieval), Z (Model/Inference Operations). No prior agent communication protocol defines these. They encode what agents do internally, not just what they communicate between themselves. The J→Y→Z→Q chain encodes the full AI cognitive pipeline as a single transmissible SAL instruction sequence, decodable by ASD lookup without neural inference.

**Two-tier corpus compression** -- `D:PACK` applies OSMP encoding followed by lossless dictionary-based compression for at-rest storage. Two profiles: D:PACK/LZMA (full-corpus, companion device) and D:PACK/BLK (zstd block-level, microcontroller target with single-code random access in 38KB SRAM). `D:UNPACK` retrieves semantic content by ASD lookup against the SAL intermediate representation. Three complete D:PACK/BLK dict-free builds demonstrate the architecture at scale: the CMS FY2026 ICD-10-CM code set (74,719 clinical descriptions, 5.4MB raw) produces a 477KB binary (91.4% total reduction), the ISO 20022 eRepository (66,956 financial message element definitions, 8.7MB raw) produces a 1.21MB binary (86.5% total reduction), and the MITRE ATT&CK Enterprise v18.1 knowledge base (1,661 techniques, malware, tools, and threat groups, 82KB raw) produces a 20KB binary (75.3% reduction). All artifacts fit in ESP32 flash and enable edge-local domain code resolution without network access.

**H namespace Layer 2 accessors** — `H:ICD[R00.1]`, `H:SNOMED[concept_id]`, `H:CPT[99213]` are fully functional today with native code values in brackets. Slot values from open-ended external registries are exempt from the single-character encoding rule. MDR increases compression density of these codes; it does not gate functionality.

**R:ESTOP hard exception** — executes immediately on receipt of any single fragment, regardless of loss tolerance policy, fragment completeness, or I:§ authorization state. Asymmetric harm: unnecessary stop is recoverable; failure to stop a physical agent in emergency is not. This is intentional and documented in spec §8.2. Do not modify.

**Overflow Protocol** — Tier 1 (single packet, ≤51 bytes at LoRa SF12), Tier 2 (sequential burst), and Tier 3 (DAG decomposition for conditional branches and dependency chains). Three loss tolerance policies: Φ (Fail-Safe), Γ (Graceful Degradation, default), Λ (Atomic -- required for K and H namespace instructions with irreversible consequences). Tier 3 decomposes compound SAL instructions into a directed acyclic graph of executable units with dependency pointers, resolves execution order via topological sort, and applies loss tolerance to the maximal resolvable subgraph under partial receipt. Multi-parent dependencies (diamond joins) use a FLAGS bit 3 extended dependency bitmap. Fragment header stays at 6 bytes across all three tiers.

**BAEL floor guarantee** — the protocol never makes an instruction longer than its natural language input. When the encoded form exceeds the natural language form, BAEL selects NL_PASSTHROUGH and transmits the original with a flags bit. Compression is never negative.

**FNP handshake** — Two-message capability advertisement + acknowledgment (40B + 38B = 78 bytes total). Negotiates dictionary alignment, namespace intersection, and channel capacity in two LoRa packets. Implemented in all three SDKs with byte-identical wire format. Channel capacity negotiation selects the LCD of both nodes, so the mesh scales within the most constrained link.

**ADP dictionary synchronization** — The ASD Distribution Protocol keeps dictionaries aligned across nodes after initial FNP handshake. Delta-based updates decompose dictionary changes into independently parseable units, each carrying a version pointer and a tripartite resolution flag (additive, superseding replacement with mandatory retransmission, or deprecation). Nodes apply deltas as they arrive and operate in a partially updated but internally consistent state during synchronization. Instructions referencing opcodes whose defining delta has not yet arrived are held in a semantic pending queue and resolved on receipt. MAJOR.MINOR version signaling detects breaking changes. The guaranteed minimum operational vocabulary floor ensures every node can decode baseline instructions regardless of synchronization state. Implemented in the Python SDK with 69 tests passing.

**Sovereign namespace extension** — `Ω:` (U+03A9) allows any implementing party to define proprietary namespace extensions without central approval or registration.

---

## What Requires Future Work

**C++ firmware-level OSMP nodes** — OSMP integration with Meshtastic via the Python SDK and Meshtastic Python library is operational today (see CONTRIBUTING.md). The C++ contribution target is a firmware-level encoder/decoder enabling ESP32 and nRF52 Meshtastic devices to operate as sovereign OSMP nodes without a companion device, with the ASD compiled into flash.

**Additional MDR namespaces** — Three domain corpora are shipped (ICD-10-CM, ISO 20022, MITRE ATT&CK Enterprise). SNOMED CT, RxNorm, LOINC, and other open registries are future namespace targets.

---

## Architecture

| Component | Function |
|---|---|
| **SAL** — Semantic Assembly Language | Domain-specific symbolic instruction format |
| **ASD** — Adaptive Shared Dictionary | 341-opcode version-pinned compression dictionary |
| **FNP** — Frame Negotiation Protocol | Capability negotiation and session handshake |
| **ADP** — ASD Distribution Protocol | Dictionary delta synchronization across nodes |
| **SNA** — Sovereign Node Architecture | Autonomous edge node, air-gapped operation |
| **TCL** — Translational Compression Layer | Semantic serialization and transcoding |
| **OP** — Overflow Protocol | Message fragmentation, priority, graceful degradation |
| **BAEL** — Bandwidth-Agnostic Efficiency Layer | Adaptive encoding across any channel capacity |

---

## Namespaces

```
A  Agentic/OSMP-Native     M  Municipal Operations
B  Building/Construction   N  Network/Routing
C  Compute/Resource Mgmt   O  Operational Context/Environment
D  Data/Query/File Transfer P  Procedural/Maintenance
E  Environmental/Sensor    Q  Quality/Evaluation/Grounding  ← AI-native
F  Federal/Regulatory      R  Robotic/Physical Agent
G  Geospatial/Navigation   S  Security/Cryptographic
H  Health/Clinical         T  Time/Scheduling
I  Identity/Permissioning  U  User/Human Interaction
J  Cognitive Exec State ← AI-native  V  Vehicle/Transport Fleet
K  Financial/Transaction   W  Weather/External Environment
L  Logging/Audit/Compliance X  Energy/Power Systems
                            Y  Memory + Retrieval     ← AI-native
                            Z  Model/Inference Ops    ← AI-native
                           Ω:  Sovereign Extension
```

---

## Example Instructions

```
# Environmental query
EQ@4A?TH:0
→ "Node 4A, report temperature at offset zero."  76.7% reduction

# Emergency broadcast
MA@*!EVA
→ "Broadcast evacuation to all nodes."  81.8% reduction

# MEDEVAC threshold alert
H:HR@NODE1>120→H:CASREP∧M:EVA@*
→ "If heart rate exceeds 120, assemble CASREP and broadcast evacuation."  65.0% reduction

# Clinical with ICD-10 Layer 2 accessor (functional today)
H:HR<60→H:ALERT[BRADYCARDIA]∧H:ICD[R00.1]
→ "If heart rate below 60, alert bradycardia with ICD-10 code."

# Two-tier corpus encoding
D:PACK@CORPUS∧D:UNPACK[query]
→ Encode corpus for at-rest storage; retrieve by ASD lookup without decompression.

# Atomic financial instruction
K:PAY@RECV↔I:§→K:XFR[AMT]
→ "Execute payment iff human confirmation received, then transfer asset."  70.3% reduction

# Internet-uplink capability-addressed routing
∃N:INET→A:DA@RELAY1
→ "Route to any node with internet uplink, delegate to relay."

# AI cognitive pipeline
J:GOAL∧Y:SEARCH∧Z:INF∧Q:GROUND
→ "Declare goal, retrieve from memory, invoke inference, verify grounding."
```

---

## Repository Structure

```
cloudless-sky/
  protocol/
    spec/           <- OSMP-SPEC-v1.md -- authoritative protocol specification
    grammar/        <- SAL-grammar.ebnf -- formal grammar (EBNF)
    test-vectors/   <- canonical-test-vectors.json -- conformance suite
  sdk/
    python/         <- Reference implementation
    typescript/     <- OpenClaw/web SDK (fzstd for D:PACK/BLK)
    go/             <- PicoClaw/constrained hardware SDK
  mcp/
    server.py       <- MCP server (pip install osmp-mcp)
    server.json     <- MCP Registry descriptor
  mdr/
    icd10cm/        <- CMS FY2026 ICD-10-CM (74,719 codes, 477KB)
    iso20022/       <- ISO 20022 eRepository (47,835 elements, 1.2MB)
    mitre-attack/   <- MITRE ATT&CK Enterprise v18.1 (1,661 entries, 20KB)
  benchmarks/
    sal-vs-json/    <- 29-vector framework benchmark, four-way comparison, grammar analysis
  docs/
    SAL-efficiency-analysis.md  <- Whitepaper v2.0: structural efficiency analysis
    adr/            <- Architecture Decision Records
  tests/
    tier1/          <- Unit tests per SDK + D:PACK/BLK resolve tests
    tier2/          <- Cross-SDK wire compatibility
    tier3/          <- Tier 3 DAG decomposition tests (Python, TypeScript, Go)
```

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The spec is authoritative. All SDK implementations are validated against the canonical test vectors. A conformant implementation must achieve ≥60% mean UTF-8 byte reduction with zero decode errors.

Meshtastic integration via the Python SDK and Meshtastic Python library is operational today with no additional code required. See CONTRIBUTING.md for details.

Wanted: C++ firmware-level encoder/decoder (ESP32/nRF52 sovereign nodes), Kotlin/Swift mobile SDKs.

---

## Patent Notice

The OSMP architecture is covered by pending US patent application OSMP-001-UTIL (inventor: Clay Holberg, priority date March 17, 2026). A continuation-in-part (OSMP-001-CIP) extends coverage to cloud-scale AI orchestration, non-RF channels, and the AI-native namespace architecture. Apache 2.0 includes an express patent grant for implementations of this specification. See [`PATENT-NOTICE.md`](PATENT-NOTICE.md).

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

---

*Cloudless Sky is a project of Octid.*
