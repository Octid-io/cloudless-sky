<div align="center">

<img src="assets/octid-openclaw.png" alt="OSMP — Cloudless Sky" width="100%">

# Cloudless Sky

**Agentic AI mesh without the cloud.**

[![PyPI version](https://img.shields.io/pypi/v/osmp?label=osmp&color=blue)](https://pypi.org/project/osmp/)
[![PyPI version](https://img.shields.io/pypi/v/osmp-mcp?label=osmp-mcp&color=blue)](https://pypi.org/project/osmp-mcp/)
[![npm version](https://img.shields.io/npm/v/osmp-protocol?color=red)](https://www.npmjs.com/package/osmp-protocol)
[![crates.io](https://img.shields.io/crates/v/osmp?color=orange)](https://crates.io/crates/osmp)
[![CI](https://github.com/Octid-io/cloudless-sky/actions/workflows/test.yml/badge.svg)](https://github.com/Octid-io/cloudless-sky/actions)
[![License](https://img.shields.io/badge/license-Apache_2.0-green)](LICENSE)

</div>

---

OSMP (Octid Semantic Mesh Protocol) is an open encoding standard for agentic AI instruction exchange. It works across any channel — from a 51-byte LoRa radio packet to a high-throughput cloud inference pipeline — using the same grammar, the same dictionary, and the same decode logic.

**No cloud required. No inference at the decode layer. No central authority.**

## Install

```bash
pip install osmp                  # Python SDK
pip install osmp-mcp              # MCP server (Claude Desktop, Cursor, Claude Code)
npm install osmp-protocol         # TypeScript SDK
cargo add osmp                    # Rust SDK
go get github.com/octid-io/cloudless-sky/sdk/go/osmp
```

## 30-Second Example

```python
from osmp import encode, decode

sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
# "H:HR@NODE1>120;H:CASREP;M:EVA@*"

text = decode(sal)
# "(clinical) heart rate above 120 at NODE1, then [clinical] casualty report,
#  then [emergency] evacuation at all nodes"
```

35 bytes on the wire. Decoded by dictionary lookup, not inference. Fits a single LoRa packet at maximum-range spreading factor. The same input produces field-for-field identical output in Python, TypeScript, Go, and Rust.

---

## Why OSMP

When AI agents communicate in JSON over HTTP, the cost compounds at every hop.

```json
{"action": "move", "agent": "BOT1", "waypoint": "WP1", "priority": "urgent"}
```

82 bytes of envelope before any content. Tokenization required. Inference required to parse. Fails completely at the 51-byte LoRa minimum payload.

```
R:MOV@BOT1:WPT:WP1↺
```

21 bytes. Deterministic decode. Fits a single LoRa packet. No inference at the receiving node — the structured instruction is recovered by dictionary lookup.

What OSMP changes is the output format and the decode layer. Frameworks above it (MCP, A2A, ACP, CrewAI, AutoGen, LangGraph) stay the same. Transports below it (HTTP, LoRa, BLE, WiFi, Meshtastic, satellite) stay the same. The serialization step changes, and the decode becomes inference-free.

---

## How Agents Use It

Two paths. Both run OSMP in production.

### Path A — MCP (zero-config)

The agent connects to the OSMP MCP server and reads the `osmp://system_prompt` resource (~390 tokens, under 0.3% of a 200K context window). It learns the grammar, the dictionary, and the composition rules on connect.

```bash
claude mcp add osmp -- osmp-mcp
```

The agent then calls `osmp_compose` with natural-language instructions. The deterministic pipeline returns SAL or `NL_PASSTHROUGH` if no opcode matches.

### Path B — SDK (your own transport)

Add the [Usage Doctrine](docs/SAL-usage-doctrine-v1.md) to your LLM's system prompt. The model composes SAL via `SALComposer.compose()` (or your language's equivalent). Wire `encode` / `decode` / `validate` into your agent loop.

```python
from osmp import encode, decode, validate

sal = "H:HR@NODE1>120→H:CASREP∧M:EVA@*"
result = validate(sal, nl="If heart rate exceeds 120, file casualty report and evacuate all nodes.")

if result.valid:
    transmit(sal)  # your transport layer
```

The validator catches hallucinated opcodes, missing consequence classes, namespace-as-target errors, byte inflation, and regulatory dependency violations. Eight rules. No exceptions.

---

## Mixed Environments — The SALBridge

Not every agent in your system speaks OSMP. The bridge handles the boundary.

```python
from osmp import bridge

b = bridge("MY_NODE")
b.register_peer("GPT_AGENT", attempt_fnp=False)

# Outbound: SAL decoded to NL, annotated with SAL equivalent
out = b.send("H:HR@NODE1>120;H:CASREP", "GPT_AGENT")
# "heart_rate at NODE1 exceeds 120; casualty_report
#  [SAL: H:HR@NODE1>120;H:CASREP]"
```

The bridge annotates outbound messages with SAL, seeding the remote agent's context window. When the remote agent starts producing valid SAL through exposure, the bridge transitions from FALLBACK to ACQUIRED.

**OSMP does not spread by installation. It spreads by contact.**

---

## Performance

<table>
<tr>
<td align="center"><h2>86.8%</h2><b>byte reduction vs JSON</b><br>29 real-world vectors from 5 frameworks</td>
<td align="center"><h2>84.5%</h2><b>vs MessagePack</b><br>binary serialization baseline</td>
<td align="center"><h2>70.5%</h2><b>vs protobuf</b><br>compiled schemas, protoc 3.21.12</td>
<td align="center"><h2>76.0%</h2><b>fewer GPT-4 tokens</b><br>cl100k_base, 1,809 → 434</td>
</tr>
</table>

Compression claims are measured, not estimated. The [29-vector benchmark](benchmarks/sal-vs-json/) uses real wire-format payloads from MCP, OpenAI, Google A2A, CrewAI, and AutoGen. Full methodology and adversarial review in the [whitepaper](docs/SAL-efficiency-analysis.md).

### Behavioral Compliance

Smaller on the wire means nothing if the LLM can't use it correctly. Cross-model testing confirms it can.

| Model | JSON Compliance | SAL Compliance | Wire Reduction |
|---|---|---|---|
| Claude Sonnet 4 | 90% | 95% | 72% |
| GPT-4o | 85% | 88% | 72% |
| GPT-4o-mini | 88% | 88% | 72% |

SAL's advantage concentrates in safety classification: JSON models identify the correct consequence class 75% of the time. SAL models identify it 100%, across every model tested. The glyph is a universal signal.

---

## SDKs

All four SDKs are independently verified against the canonical test suite. The SHA-256 ASD fingerprint (`9ecc507e2c24c4a7`) is byte-identical across SDKs and gates cross-SDK drift in CI.

| SDK | Install | Reference |
|---|---|---|
| **Python** | `pip install osmp` | [sdk/python/](sdk/python/) — reference implementation |
| **TypeScript** | `npm install osmp-protocol` | [sdk/typescript/](sdk/typescript/) — `fzstd` for D:PACK/BLK |
| **Go** | `go get .../sdk/go/osmp` | [sdk/go/](sdk/go/) — ASD compiled-in |
| **Rust** | `cargo add osmp` | [sdk/rust/](sdk/rust/) — pre-1.0; ASD core + v16 + EML |
| **MCP Server** | `pip install osmp-mcp` | [osmp_mcp/](osmp_mcp/) — 19 tools, wraps Python SDK |

D:PACK/BLK resolve is verified across all 124,215 domain codes (74,719 ICD-10-CM + 47,835 ISO 20022 + 1,661 MITRE ATT&CK) in Python, TypeScript, and Go.

---

## EML — Mathematics on the Wire

OSMP encodes instructions. **EML encodes mathematics.** Both ship in the same package.

EML is a companion evaluator based on Odrzywołek (2026, [arXiv:2603.21852](https://arxiv.org/abs/2603.21852)): a single binary operator `eml(x, y) = exp(x) − ln(y)`, together with the constant 1, generates the standard calculator function basis — exp, ln, sin, cos, sqrt, arithmetic — as compact expression trees.

A full sin(x) or sqrt(x) approximation fits in fewer than 100 bytes on the wire. The receiving node decodes the tree and evaluates it deterministically by composing `eml` in a loop — no math library dependency, byte-exact identical output across all four SDKs.

```python
from osmp.eml import get_base_chain, compound_linear_calibration
import math

get_base_chain("ln(x)").evaluate(math.e)              # 1.0
compound_linear_calibration().evaluate([2.0, 3.0, 1.0])  # a·x + b = 7.0
```

A constrained-channel instruction can carry its own math: a 51-byte LoRa frame can ship an OSMP instruction *and* the calibration polynomial, exponential decay curve, or sensor coefficient needed to interpret it — on any receiver, without firmware updates.

**Two modes:**
- **Fast** (default) — fdlibm-derived, 1-ULP accurate. Correct for LoRa/BLE/edge-ML, drone swarm coordination, general scientific computation. **Ships publicly.**
- **Precision** — crlibm-derived, correctly-rounded, audit-grade. For regulated industries (medical IEC 62304, aerospace DO-178C, nuclear IEC 61513), audit-grade finance, cryptographic protocol-frame hash inputs. **Available under commercial license** — contact `ack@octid.io`.

Cross-SDK fingerprint: `e9a4a71383f14624472fe0602ca5e0ff1959e00b09725a62d584e1361f842c1b`. Identical across Python / TypeScript / Go / Rust.

---

## Architecture

| Component | Function |
|---|---|
| **SAL** — Semantic Assembly Language | Human-readable symbolic instruction format |
| **SAIL** — Semantic Assembly Isomorphic Language | Binary wire encoding, isomorphic to SAL |
| **ASD** — Adaptive Shared Dictionary | 356-opcode version-pinned compression dictionary |
| **ADP** — ASD Distribution Protocol | Dictionary delta synchronization across nodes |
| **BAEL** — Bandwidth-Agnostic Efficiency Layer | Adaptive encoding across any channel capacity |
| **FNP** — Frame Negotiation Protocol | Capability negotiation, FALLBACK/ACQUIRED states for non-OSMP peers |
| **MDR** — Managed Dictionary Registry | Domain corpora (ICD-10-CM, ISO 20022, MITRE ATT&CK) as D:PACK/BLK binaries |
| **OP** — Overflow Protocol | Message fragmentation, priority, graceful degradation |
| **SALBridge** | Boundary translation for non-OSMP peers; propagation by contact |
| **SEC** — Security Envelope | AEAD + Ed25519 authentication for mesh networks |
| **SNA** — Sovereign Node Architecture | Autonomous edge node, air-gapped operation |
| **TCL** — Translational Compression Layer | Semantic serialization and transcoding |

Every layer is implemented in all four SDKs (Python reference; TypeScript, Go, and Rust are pure derivations) with byte-identical wire format.

---

## Where OSMP Sits

| Layer | What it does | Components |
|---|---|---|
| **Application** | Agent framework and LLM composition | MCP, A2A, ACP, CrewAI, AutoGen, LangGraph |
| **Encoding** | Instruction serialization (OSMP replaces JSON here) | SAL, SAIL, Composition Validator, ASD, BAEL |
| **Transport** | Byte delivery | HTTP, LoRa, BLE, WiFi, Meshtastic, satellite, serial, MQTT, TCP/UDP |

OSMP is not a framework. It is an encoding layer. Two agents using different frameworks that share the OSMP grammar and dictionary can communicate with no modification to either framework.

---

## Namespaces

```
A  Agentic / OSMP-Native     N  Network / Routing
B  Building / Construction   O  Operational Context
C  Compute / Resource Mgmt   P  Procedural / Maintenance
D  Data / Query / Transfer   Q  Quality / Eval / Grounding ← AI-native
E  Environmental / Sensor    R  Robotic / Physical Agent
F  Federal / Regulatory      S  Security / Cryptographic
G  Geospatial / Navigation   T  Time / Scheduling
H  Health / Clinical         U  User / Human Interaction
I  Identity / Permissioning  V  Vehicle / Transport Fleet
J  Cognitive Exec State ← AI-native  W  Weather / External Env
K  Financial / Transaction   X  Energy / Power Systems
L  Logging / Audit           Y  Memory + Retrieval ← AI-native
M  Municipal Operations      Z  Model / Inference Ops ← AI-native
                             Ω  Sovereign Extension
```

Four AI-native namespaces (J/Q/Y/Z) encode what agents do internally, not just what they communicate. The J→Y→Z→Q chain encodes the full AI cognitive pipeline as a transmissible instruction sequence, decodable by ASD lookup without neural inference.

The v16 release (Q4 2026) makes 3-character primaries (e.g., `AGT`, `HLT`, `ENV`) the canonical form, with v15 single-letter forms preserved as deprecated siblings. See [docs/adr/ADR-001-asd-generated-from-canonical-dictionary.md](docs/adr/ADR-001-asd-generated-from-canonical-dictionary.md) for the dictionary discipline.

---

## Example Instructions

```
# Environmental query
EQ@4A?TH:0
→ "Node 4A, report temperature at offset zero."          76.7% reduction

# Emergency broadcast
M:EVA@*
→ "Broadcast evacuation to all nodes."                   81.8% reduction

# MEDEVAC threshold alert
H:HR@NODE1>120→H:CASREP∧M:EVA@*
→ "If heart rate exceeds 120, assemble CASREP and broadcast evacuation."  65.0%

# Clinical with ICD-10 Layer 2 accessor
H:HR<60→H:ALERT[BRADYCARDIA]∧H:ICD[R00.1]
→ "If heart rate below 60, alert bradycardia with ICD-10 code."

# Atomic financial instruction
K:PAY@RECV↔I:§→K:XFR[AMT]
→ "Execute payment iff human confirmation received, then transfer asset."  70.3%

# Internet-uplink capability-addressed routing
∃N:INET→A:DA@RELAY1
→ "Route to any node with internet uplink, delegate to relay."

# AI cognitive pipeline
J:GOAL∧Y:SEARCH∧Z:INF∧Q:GROUND
→ "Declare goal, retrieve from memory, invoke inference, verify grounding."
```

---

## What's Built Today

<details>
<summary><b>Click to expand the deliverables list</b></summary>

- **Instruction encoding across all 26 standard namespaces** — 356 opcodes drawn from authoritative sources: IEC 61850 (energy), ICD-10/SNOMED CT/CPT (clinical), ISO 20022/FIX/SWIFT (financial), ISO 10218-1:2025 (robotics), FEMA ICS/NIMS (emergency management), BDI/PDDL/HTN (cognitive AI), OpenAI/Anthropic APIs (model operations). Registered macro architecture with 16 Meshtastic macros (pre-validated multi-opcode chain templates invoked via `A:MACRO[name]`).

- **Four AI-native namespaces** — J (Cognitive Execution State), Q (Quality/Evaluation/Grounding), Y (Memory + Retrieval), Z (Model/Inference Operations). No prior agent communication protocol defines these.

- **Two-tier corpus compression** — `D:PACK` applies OSMP encoding followed by lossless dictionary-based compression for at-rest storage. Two profiles: D:PACK/LZMA (full-corpus) and D:PACK/BLK (zstd block-level, microcontroller target with single-code random access in 38KB SRAM). `D:UNPACK` retrieves semantic content by ASD lookup against the SAL intermediate representation.

- **Three MDR domain corpora** — CMS FY2026 ICD-10-CM (74,719 codes, 477KB), ISO 20022 eRepository (47,835 definitions, 1.2MB), MITRE ATT&CK Enterprise v18.1 (1,661 entries, 20KB). All three are D:PACK/BLK dict-free binaries resolvable across SDKs without network access.

- **Layer 2 accessors** — Bracket-enclosed slot values from external open-ended registries: `H:ICD[R00.1]`, `H:SNOMED[concept_id]`, `H:CPT[99213]`, `K:ISO[MessageDefinitionIdentifier]`. Layer 2 slot values are exempt from the single-character encoding rule.

- **R:ESTOP hard exception** — executes immediately on receipt of any single fragment, regardless of loss tolerance policy, fragment completeness, or `I:§` authorization state. Asymmetric harm: unnecessary stop is recoverable; failure to stop a physical agent in emergency is not.

- **Overflow Protocol** — Tier 1 (single packet, ≤51 bytes at LoRa SF12), Tier 2 (sequential burst), Tier 3 (DAG decomposition for conditional branches and dependency chains). Three loss tolerance policies: Φ (Fail-Safe), Γ (Graceful Degradation, default), Λ (Atomic — required for K and H namespace instructions with irreversible consequences).

- **BAEL floor guarantee** — the protocol never makes an instruction longer than its natural language input. When the encoded form exceeds the natural language form, BAEL selects NL_PASSTHROUGH and transmits the original with a flags bit. Compression is never negative.

- **SAL/SAIL isomorphic encoding** — every SAL instruction compiles to a SAIL binary representation and every SAIL payload decompiles back to the identical SAL instruction. Bijective: no information lost in either direction.

- **FNP handshake and SALBridge — propagation by contact** — Two-message capability advertisement + acknowledgment (40B + 38B = 78 bytes total). Negotiates dictionary alignment, namespace intersection, and channel capacity in two LoRa packets. When FNP detects a non-OSMP peer, the session transitions to FALLBACK. The SALBridge handles boundary translation; peers that learn SAL through contextual exposure transition to ACQUIRED.

- **ADP dictionary synchronization** — The ASD Distribution Protocol keeps dictionaries aligned across nodes after initial FNP handshake. Delta-based updates with version pointers and tripartite resolution flags (additive, superseding replacement, deprecation).

- **Sovereign namespace extension** — `Ω:` (U+03A9) allows any implementing party to define proprietary namespace extensions without central approval.

</details>

---

## Documentation

- **[Spec](protocol/spec/OSMP-SPEC-v1.0.2.md)** — authoritative protocol specification
- **[Grammar](protocol/grammar/SAL-grammar.ebnf)** — formal grammar (EBNF)
- **[Dictionary](protocol/OSMP-semantic-dictionary-v15.csv)** — canonical opcode source of truth
- **[Usage Doctrine](docs/SAL-usage-doctrine-v1.md)** — composition rules for LLM system prompts
- **[Efficiency Analysis](docs/SAL-efficiency-analysis.md)** — whitepaper, methodology, adversarial review
- **[Architecture Decision Records](docs/adr/)** — design rationale (ADRs 1–5)
- **[Contributing](CONTRIBUTING.md)** — opcode-addition process, SDK conformance, test discipline
- **[Patent Notice](PATENT-NOTICE.md)** — Apache 2.0 patent grant scope and commercial-mode disclosure
- **[Known Issues](KNOWN-ISSUES.md)** — platform-specific install notes (Termux, Raspberry Pi, constrained hardware)

---

## Roadmap

Current focus: full Rust SDK feature parity (decoder/encoder/bridge/FNP shipped at 0.1.0; MDR resolve, full benchmark harness, and Pangram handshake to follow).

Open contributions welcome:
- **C++ firmware-level encoder/decoder** — sovereign OSMP nodes on ESP32 / nRF52 with the ASD compiled into flash. Today, OSMP integration with Meshtastic via the Python SDK and Meshtastic Python library is operational; the C++ contribution target eliminates the companion-device dependency.
- **Kotlin and Swift mobile SDKs** — feature parity with the four shipped SDKs.
- **Additional MDR namespaces** — SNOMED CT, RxNorm, LOINC are future namespace targets.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The spec is authoritative. All SDK implementations are validated against the canonical test vectors. A conformant implementation must achieve ≥60% mean UTF-8 byte reduction with zero decode errors.

Wanted: C++ firmware encoders, Kotlin/Swift mobile SDKs, and MDR corpora for additional regulated domains.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

Patent pending. See [PATENT-NOTICE.md](PATENT-NOTICE.md).

---

<div align="center">

*Cloudless Sky is a project of [Octid](https://octid.io).*

</div>
