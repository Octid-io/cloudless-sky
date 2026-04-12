# Cloudless Sky

**Agentic AI mesh without the cloud.**

OSMP (Octid Semantic Mesh Protocol) is an open encoding standard for agentic AI instruction exchange. It works across any channel -- from a 51-byte LoRa radio packet to a high-throughput cloud inference pipeline -- using the same grammar, the same dictionary, and the same decode logic.

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



---

## Using OSMP in Your Agent

Installing the SDK gives you encode, decode, and validate. Making your agents speak SAL requires wiring those into your agent loop. Here is the end-to-end pattern.

### Step 1: Give Your LLM the Composition Doctrine

The LLM needs to know the SAL grammar, the opcode dictionary, and the composition rules before it can compose SAL.

**Path A (MCP):** This happens automatically. When an MCP-native agent connects to the OSMP server, it reads the `osmp://system_prompt` resource (~390 tokens, under 0.3% of a 200K context window). The agent learns the grammar, the dictionary, and the composition rules on connect. No manual prompt engineering required.

**Path B (SDK):** Add the [Usage Doctrine](docs/SAL-usage-doctrine-v1.md) to your LLM's system prompt. The doctrine teaches the LLM when to compose SAL, when to fall back to natural language, and how to select the right opcode for a given intent.

### Step 2: Compose

The LLM composes a SAL instruction from natural language input. It uses the dictionary to select opcodes and the grammar to structure them.

```
Natural language: "If heart rate exceeds 120, file a casualty report and evacuate all nodes."
LLM output:       H:HR@NODE1>120→H:CASREP∧M:EVA@*
```

### Step 3: Validate Before Transmitting

Every composed instruction passes through the validator before it hits the wire. Eight rules. No exceptions.

```python
from osmp import encode, decode, validate

sal = "H:HR@NODE1>120→H:CASREP∧M:EVA@*"
result = validate(sal, nl="If heart rate exceeds 120, file casualty report and evacuate all nodes.")

if result.valid:
    transmit(sal)  # your transport layer
else:
    for issue in result.issues:
        print(f"{issue.rule}: {issue.message}")
```

The validator catches hallucinated opcodes, missing consequence classes, namespace-as-target errors, byte inflation (BAEL floor guarantee), and regulatory dependency violations.

### Step 4: Decode at the Receiving Node

The receiving node decodes by dictionary lookup. No inference. No model. No ambiguity.

```python
from osmp import decode

sal = receive()  # your transport layer
text = decode(sal)
# "H:heart_rate →NODE1>120; H:casualty_report; M:evacuation →*"
# The agent acts on the decoded instruction.
```

The decode is identical across all three SDKs. Python, TypeScript, and Go produce field-for-field identical results from the same SAL input.

### Mixed Environments: The SALBridge

Not every agent in your system will speak OSMP. The SALBridge handles the boundary.

```python
from osmp import bridge

b = bridge("MY_NODE")
b.register_peer("GPT_AGENT", attempt_fnp=False)

# Outbound: SAL decoded to natural language, annotated with SAL equivalent
out = b.send("H:HR@NODE1>120;H:CASREP", "GPT_AGENT")
# "heart_rate at NODE1 exceeds 120; casualty_report
#  [SAL: H:HR@NODE1>120;H:CASREP]"

# Inbound: scanned for SAL acquisition
result = b.receive("A:ACK", "GPT_AGENT")
```

The bridge annotates outbound messages with SAL equivalents, seeding the remote agent's context window. When the remote agent starts producing valid SAL through exposure, the bridge detects it and transitions from FALLBACK to ACQUIRED. OSMP spreads by contact, not installation.

The MCP server includes five bridge tools (`osmp_bridge_register`, `osmp_bridge_send`, `osmp_bridge_receive`, `osmp_bridge_status`, `osmp_bridge_comparison`) for agents operating in mixed environments.
---

## Where OSMP Sits

OSMP is not a framework. It is an encoding layer. MCP, A2A, and ACP define how agents discover and invoke each other. OSMP defines how the instructions themselves are encoded once composed. An MCP client using OSMP encodes its tool calls in SAL instead of JSON. The framework stays the same. The wire format changes.

| Layer | What it does | Components |
|---|---|---|
| **Application** | Agent framework and LLM composition | MCP, A2A, ACP, CrewAI, AutoGen, LangGraph |
| **Encoding** | Instruction serialization (OSMP replaces JSON here) | SAL (human-readable), SAIL (binary), Composition Validator, ASD, BAEL |
| **Transport** | Byte delivery | HTTP, LoRa, BLE, WiFi, Meshtastic, satellite, serial, MQTT, TCP/UDP |

Today, every framework above the line serializes to JSON-RPC over HTTP. That works when your transport is an unconstrained internet connection. It fails at 51 bytes. OSMP replaces that serialization step. JSON-RPC requires HTTP. Protocol Buffers require a schema compiler and a reliable transport. SAL and SAIL encode to raw bytes that fit any channel, from a 51-byte LoRa packet at maximum-range spreading factor to a high-throughput cloud pipeline. Two agents using different frameworks that share the OSMP grammar and dictionary can communicate with no modification to either framework.

## SAL and SAIL

**SAL** (Semantic Assembly Language) is the human-readable encoding. Unicode glyphs. Inspectable at every hop.

**SAIL** (Semantic Assembly Isomorphic Language) is the binary encoding. Opaque bytes. Maximum compression for constrained channels.

SAL and SAIL are isomorphic. Every valid SAL instruction has exactly one SAIL encoding. Every valid SAIL payload decodes to exactly one SAL instruction. The decode path is encoding-agnostic: the same dictionary lookup, the same result.

BAEL selects the wire mode automatically based on channel capacity and instruction safety classification:

| Channel | Consequence | Wire Mode |
|---|---|---|
| Constrained (LoRa, BLE) | HAZARDOUS/IRREVERSIBLE | SAIL + SEC (binary, signed) |
| Constrained | REVERSIBLE | SAIL (binary, unsigned) |
| Unconstrained (HTTP, WiFi) | HAZARDOUS/IRREVERSIBLE | SAL + SEC (readable, signed) |
| Unconstrained | REVERSIBLE | SAL (readable, unsigned) |

SEC is the security envelope: node ID + monotonic sequence counter + AEAD tag + Ed25519 signature. 87 bytes of fixed overhead. Designed for mesh networks with no certificate authority and no internet connectivity.

---

## Measured Performance

<table>
<tr>
<td align="center"><h1>86.8%</h1><b>byte reduction vs JSON</b><br>29 real-world vectors from 5 frameworks</td>
<td align="center"><h1>84.5%</h1><b>byte reduction vs MessagePack</b><br>binary serialization baseline</td>
<td align="center"><h1>70.5%</h1><b>byte reduction vs protobuf</b><br>compiled schemas, protoc 3.21.12</td>
<td align="center"><h1>76.0%</h1><b>fewer tokens (GPT-4)</b><br>cl100k_base tokenizer, 1,809 → 434</td>
</tr>
</table>

Compression claims are measured, not estimated. The [29-vector SAL vs JSON benchmark](benchmarks/sal-vs-json/) uses real wire-format payloads from MCP, OpenAI, Google A2A, CrewAI, and AutoGen. Full methodology and adversarial review in the [whitepaper](docs/SAL-efficiency-analysis.md).

### Behavioral Compliance

Smaller on the wire means nothing if the LLM can't use it correctly. Cross-model testing confirms it can.

| Model | JSON Compliance | SAL Compliance | Delta | Wire Reduction |
|---|---|---|---|---|
| Claude Sonnet 4 | 90% | 95% | +5% | 72% |
| GPT-4o | 85% | 88% | +3% | 72% |
| GPT-4o-mini | 88% | 88% | 0% | 72% |

SAL delivers 88-95% behavioral compliance across three models at 72% less wire cost. JSON delivers 85-90% at full cost. SAL's advantage is concentrated in safety classification: JSON models identify the correct consequence class 75% of the time. SAL models identify it 100% of the time, across every model tested. The glyph is a universal signal.

---

## Quick Start

```python
from osmp import encode, decode

sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
# "H:HR@NODE1>120;H:CASREP;M:EVA@*"

text = decode(sal)
# "H:heart_rate →NODE1>120; H:casualty_report; M:evacuation →*"
```

Three lines. Zero setup. Zero dependencies. The SDK handles dictionary initialization internally.

### Install

Four production paths. All four are real integration options, not tiers.

**Python SDK** (reference implementation, zero dependencies)
```bash
pip install osmp
```
```python
from osmp import encode, decode
```
Wire encode/decode into your agent framework's serialization pipeline. Add the [Usage Doctrine](docs/SAL-usage-doctrine-v1.md) to your LLM's system prompt. The agent composes SAL instead of JSON. The receiving node decodes by dictionary lookup.

**TypeScript SDK**
```bash
npm install osmp-protocol
```
```typescript
import { encode, decode } from "osmp-protocol";
```

**Go SDK**
```go
import "github.com/octid-io/cloudless-sky/sdk/go/osmp"

sal := osmp.Encode([]string{"H:HR@NODE1>120", "H:CASREP", "M:EVA@*"})
text := osmp.Decode(sal)
```

**MCP Server** (Claude Desktop, Cursor, Claude Code, any MCP client)
```bash
pip install osmp-mcp
osmp-mcp
```
The MCP server is not an evaluation tool. It is a production integration. The agent connects, reads the `osmp://system_prompt` resource, learns the SAL grammar and dictionary, and composes SAL natively from that point forward. The server stays running as the encode/decode/validate layer underneath. Nine tools, three MDR corpora, composition doctrine included. Connect from Claude Code: `claude mcp add osmp -- osmp-mcp`. Listed on the [MCP Registry](https://registry.modelcontextprotocol.io) as `io.github.Octid-io/osmp`.

The three SDKs are for agents and frameworks that manage their own transport (CrewAI, AutoGen, LangGraph, custom orchestrators, embedded nodes). The MCP server is for agents that already speak MCP. Both approaches run OSMP in production. The difference is who manages the connection.

For platform-specific install notes (Termux, Raspberry Pi, constrained hardware), see [KNOWN-ISSUES.md](KNOWN-ISSUES.md).

---



## SDK Status

All three SDKs are independently verified against the canonical test suite. Wire compatibility is confirmed: Python, TypeScript, and Go produce field-for-field identical decode results across every namespace, every operator, and every edge case documented in the spec. D:PACK/BLK resolve is verified across all 124,215 domain codes (74,719 ICD-10-CM + 47,835 ISO 20022 + 1,661 MITRE ATT&CK) in all three SDKs.

| SDK | Install | API | Notes |
|---|---|---|---|
| **Python** | `pip install osmp` | `from osmp import encode, decode` | Reference implementation |
| **TypeScript** | `npm install osmp-protocol` | `import { encode, decode }` | `fzstd` for D:PACK/BLK |
| **Go** | `go get .../sdk/go/osmp` | `osmp.Encode()` / `osmp.Decode()` | ASD compiled-in |
| **MCP Server** | `pip install osmp-mcp` | 9 tools via MCP protocol | Wraps Python SDK |

### Benchmark

```
$ python3 -m osmp.protocol

OSMP BENCHMARK — Cloudless Sky Protocol v1.0
SDK: Python (reference)

  ID         NL Bytes OSMP Bytes  Reduction
  ✓ TV-001         43         10      76.7%
  ✓ TV-013        100         35      65.0%
  ✓ TV-015        101         30      70.3%
  ...

  CONFORMANT ✓
```

Run it yourself. The numbers are real and independently reproducible across all three SDKs. The measured wire-format comparisons (86.8% vs JSON, 70.5% vs protobuf, 76.0% fewer tokens) use the [29-vector benchmark suite](benchmarks/sal-vs-json/).

---

## Architecture

| Component | Function |
|---|---|
| **ADP** — ASD Distribution Protocol | Dictionary delta synchronization across nodes |
| **ASD** — Adaptive Shared Dictionary | 342-opcode version-pinned compression dictionary |
| **BAEL** — Bandwidth-Agnostic Efficiency Layer | Adaptive encoding across any channel capacity |
| **FNP** — Frame Negotiation Protocol | Capability negotiation, session handshake, FALLBACK/ACQUIRED states for non-OSMP peers |
| **MDR** — Managed Dictionary Registry | Domain-specific controlled vocabulary corpora (ICD-10-CM, ISO 20022, MITRE ATT&CK) packaged as D:PACK/BLK binaries for edge-local resolution without network access |
| **OP** — Overflow Protocol | Message fragmentation, priority, graceful degradation |
| **SAIL** — Semantic Assembly Isomorphic Language | Binary wire encoding, isomorphic to SAL |
| **SAL** — Semantic Assembly Language | Human-readable symbolic instruction format |
| **SEC** — Security Envelope | AEAD + Ed25519 authentication for mesh networks |
| **SNA** — Sovereign Node Architecture | Autonomous edge node, air-gapped operation |
| **TCL** — Translational Compression Layer | Semantic serialization and transcoding |

---

## What OSMP Delivers Today

Everything here is operational from the floor ASD without MDR, cloud access, or additional tooling.

**Instruction encoding across all 26 standard namespaces** — 342 opcodes drawn from authoritative sources: IEC 61850 (energy), ICD-10/SNOMED CT/CPT (clinical), ISO 20022/FIX/SWIFT (financial), ISO 10218-1:2025 (robotics), FEMA ICS/NIMS (emergency management), BDI/PDDL/HTN (cognitive AI), OpenAI/Anthropic APIs (model operations).

**Four AI-native namespaces** — J (Cognitive Execution State), Q (Quality/Evaluation/Grounding), Y (Memory + Retrieval), Z (Model/Inference Operations). No prior agent communication protocol defines these. They encode what agents do internally, not just what they communicate between themselves. The J→Y→Z→Q chain encodes the full AI cognitive pipeline as a single transmissible SAL instruction sequence, decodable by ASD lookup without neural inference.

**Two-tier corpus compression** -- `D:PACK` applies OSMP encoding followed by lossless dictionary-based compression for at-rest storage. Two profiles: D:PACK/LZMA (full-corpus, companion device) and D:PACK/BLK (zstd block-level, microcontroller target with single-code random access in 38KB SRAM). `D:UNPACK` retrieves semantic content by ASD lookup against the SAL intermediate representation. Three complete D:PACK/BLK dict-free builds demonstrate the architecture at scale: the CMS FY2026 ICD-10-CM code set (74,719 clinical descriptions, 5.4MB raw) produces a 477KB binary (91.4% total reduction), the ISO 20022 eRepository (47,835 unique financial definitions extracted from 66,956 source rows, 8.7MB raw) produces a 1.2MB binary (86.5% total pipeline reduction), and the MITRE ATT&CK Enterprise v18.1 knowledge base (1,661 techniques, malware, tools, and threat groups, 82KB raw) produces a 20KB binary (75.3% reduction). All artifacts fit in ESP32 flash and enable edge-local domain code resolution without network access.

**Layer 2 accessors** — Bracket-enclosed slot values drawn from external open-ended registries: `H:ICD[R00.1]`, `H:SNOMED[concept_id]`, `H:CPT[99213]`, `K:ISO[MessageDefinitionIdentifier]`. Layer 2 slot values are exempt from the single-character encoding rule and are fully functional today with native code values in brackets. MDR corpus compression increases storage density of these codes; it does not gate the accessor pattern itself.

**Three MDR domain corpora shipped** — ICD-10-CM (74,719 clinical codes, H namespace), ISO 20022 (47,835 financial definitions, K namespace), and MITRE ATT&CK Enterprise v18.1 (1,661 entries, S namespace). All three are D:PACK/BLK dict-free binaries resolvable by all three SDKs without network access. See D:PACK section above for sizes and reduction figures.

**R:ESTOP hard exception** — executes immediately on receipt of any single fragment, regardless of loss tolerance policy, fragment completeness, or I:§ authorization state. Asymmetric harm: unnecessary stop is recoverable; failure to stop a physical agent in emergency is not. This is intentional and documented in spec §8.2. Do not modify.

**Overflow Protocol** — Tier 1 (single packet, ≤51 bytes at LoRa SF12), Tier 2 (sequential burst), and Tier 3 (DAG decomposition for conditional branches and dependency chains). Three loss tolerance policies: Φ (Fail-Safe), Γ (Graceful Degradation, default), Λ (Atomic -- required for K and H namespace instructions with irreversible consequences). Tier 3 decomposes compound SAL instructions into a directed acyclic graph of executable units with dependency pointers, resolves execution order via topological sort, and applies loss tolerance to the maximal resolvable subgraph under partial receipt. Multi-parent dependencies (diamond joins) use a FLAGS bit 3 extended dependency bitmap. Fragment header stays at 6 bytes across all three tiers.

**BAEL floor guarantee** — the protocol never makes an instruction longer than its natural language input. When the encoded form exceeds the natural language form, BAEL selects NL_PASSTHROUGH and transmits the original with a flags bit. Compression is never negative.

**SAL/SAIL isomorphic encoding** — every SAL instruction compiles to a SAIL binary representation and every SAIL payload decompiles back to the identical SAL instruction. The mapping is bijective: no information is lost in either direction. A developer composes and debugs in SAL (human-readable), deploys in SAIL (binary, maximum compression), and can always decompile the wire payload back to readable SAL for inspection. The encoding a node transmits and the encoding an operator reads are the same instruction in two forms.

**FNP handshake and SALBridge** — Two-message capability advertisement + acknowledgment (40B + 38B = 78 bytes total). Negotiates dictionary alignment, namespace intersection, and channel capacity in two LoRa packets. Implemented in all three SDKs with byte-identical wire format. Channel capacity negotiation selects the LCD of both nodes, so the mesh scales within the most constrained link. When FNP detects a non-OSMP peer (timeout or invalid response), the session transitions to FALLBACK. The SALBridge then handles boundary translation: outbound SAL is decoded to annotated natural language, inbound messages are scanned for SAL acquisition. Peers that learn SAL through contextual exposure transition to ACQUIRED. Regression detection drops acquired peers back to FALLBACK if they stop producing valid SAL.

**ADP dictionary synchronization** — The ASD Distribution Protocol keeps dictionaries aligned across nodes after initial FNP handshake. Delta-based updates decompose dictionary changes into independently parseable units, each carrying a version pointer and a tripartite resolution flag (additive, superseding replacement with mandatory retransmission, or deprecation). Nodes apply deltas as they arrive and operate in a partially updated but internally consistent state during synchronization. Instructions referencing opcodes whose defining delta has not yet arrived are held in a semantic pending queue and resolved on receipt. MAJOR.MINOR version signaling detects breaking changes. The guaranteed minimum operational vocabulary floor ensures every node can decode baseline instructions regardless of synchronization state. Implemented in the Python SDK with 69 tests passing.

**Sovereign namespace extension** — `Ω:` (U+03A9) allows any implementing party to define proprietary namespace extensions without central approval or registration.

---

## What Requires Future Work

**C++ firmware-level OSMP nodes** — OSMP integration with Meshtastic via the Python SDK and Meshtastic Python library is operational today (see CONTRIBUTING.md). The C++ contribution target is a firmware-level encoder/decoder enabling ESP32 and nRF52 Meshtastic devices to operate as sovereign OSMP nodes without a companion device, with the ASD compiled into flash.

**Additional MDR namespaces** — SNOMED CT, RxNorm, LOINC, and other open registries are future namespace targets.

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
    spec/           <- OSMP-SPEC-v1.0.2.md -- authoritative protocol specification
    grammar/        <- SAL-grammar.ebnf -- formal grammar (EBNF)
    test-vectors/   <- canonical-test-vectors.json -- conformance suite
  sdk/
    python/
      osmp/         <- Package: pip install osmp (encode, decode, validate)
      src/          <- Reference single-file implementation
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

Patent pending. Priority date March 17, 2026. Apache 2.0 includes an express patent grant for implementations of this specification. See [`PATENT-NOTICE.md`](PATENT-NOTICE.md).

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

---

*Cloudless Sky is a project of Octid.*
