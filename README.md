# Cloudless Sky

**Agentic AI mesh without the cloud.**

OSMP (Octid Semantic Mesh Protocol) is an open encoding standard for agentic AI instruction exchange. It works across any channel — from a 51-byte LoRa radio packet to a high-throughput cloud inference pipeline — using the same grammar, the same dictionary, and the same decode logic.

No cloud required. No inference at the decode layer. No central authority.

---

## The Problem

When AI agents communicate in JSON over HTTP, the cost compounds at every hop.

```
"If heart rate at node 1 exceeds 120, assemble casualty report
 and broadcast evacuation to all nodes."

→ 100 bytes. Requires tokenization. Requires inference to parse.
  Fails completely at 51-byte LoRa minimum payload.
```

## The Solution

```
H:HR@NODE1>120→H:CASREP∧M:EVA@*

→ 35 bytes. 65% reduction. Decode is a table lookup.
  Fits a single LoRa packet at maximum-range spreading factor.
  No inference required at the receiving node.
```

OSMP replaces JSON as the serialization format for agentic instruction exchange. An LLM that currently outputs JSON can be configured via system prompt to output SAL instead — no new tooling required on the generating side, because LLMs already handle NL→structured output. What OSMP changes is the output format, and the decode layer: the receiving node does a table lookup, not inference.

---

## Benchmark

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

## Quick Start

```bash
git clone https://github.com/octid-io/cloudless-sky
cd cloudless-sky
python3 sdk/python/src/osmp.py
```

No dependencies beyond Python standard library.

### pip
```bash
pip install osmp-protocol
```

### npm
```bash
npm install osmp-protocol
```

### Go
```go
import "github.com/octid-io/cloudless-sky/sdk/go/osmp"
```

---

## SDK Status

All three SDKs are independently verified against the same 55-vector canonical test suite. Wire compatibility is confirmed: Python, TypeScript, and Go produce field-for-field identical decode results on 86 test instructions covering every namespace, every operator, and every edge case documented in the spec.

| SDK | Target | Conformance | Notes |
|---|---|---|---|
| **Python** | Reference implementation | CONFORMANT ✓ 60.8% | Single source of truth for all SDK behavior |
| **TypeScript** | OpenClaw / web agent integrations | CONFORMANT ✓ 60.8% | `npm install osmp-protocol` |
| **Go** | PicoClaw / constrained hardware | CONFORMANT ✓ 60.8% | ASD compiled-in; no filesystem or network dependency |

---

## What OSMP Delivers Today

Everything here is operational from the floor ASD without MDR, cloud access, or additional tooling.

**Instruction encoding across all 26 standard namespaces** — 339 opcodes drawn from authoritative sources: IEC 61850 (energy), ICD-10/SNOMED CT/CPT (clinical), ISO 20022/FIX/SWIFT (financial), ISO 10218-1:2025 (robotics), FEMA ICS/NIMS (emergency management), BDI/PDDL/HTN (cognitive AI), OpenAI/Anthropic APIs (model operations).

**Four AI-native namespaces** — J (Cognitive Execution State), Q (Quality/Evaluation/Grounding), Y (Memory + Retrieval), Z (Model/Inference Operations). No prior agent communication protocol defines these. They encode what agents do internally, not just what they communicate between themselves. The J→Y→Z→Q chain encodes the full AI cognitive pipeline as a single transmissible SAL instruction sequence, decodable by ASD lookup without neural inference.

**Two-tier corpus compression** -- `D:PACK` applies OSMP encoding followed by lossless dictionary-based compression for at-rest storage. Two profiles: D:PACK/LZMA (full-corpus, companion device) and D:PACK/BLK (zstd block-level, microcontroller target with single-code random access in 38KB SRAM). `D:UNPACK` retrieves semantic content by ASD lookup against the SAL intermediate representation. Two complete D:PACK/BLK builds demonstrate the architecture at scale: the CMS FY2026 ICD-10-CM code set (74,719 clinical descriptions, 5.4MB raw) produces a 473KB binary (91.5% total reduction), and the ISO 20022 eRepository (66,956 financial message element definitions, 8.7MB raw) produces a 1.04MB binary (88.3% total reduction). Both artifacts fit in ESP32 flash and enable edge-local domain code resolution without network access.

**H namespace Layer 2 accessors** — `H:ICD[R00.1]`, `H:SNOMED[concept_id]`, `H:CPT[99213]` are fully functional today with native code values in brackets. Slot values from open-ended external registries are exempt from the single-character encoding rule. MDR increases compression density of these codes; it does not gate functionality.

**R:ESTOP hard exception** — executes immediately on receipt of any single fragment, regardless of loss tolerance policy, fragment completeness, or I:§ authorization state. Asymmetric harm: unnecessary stop is recoverable; failure to stop a physical agent in emergency is not. This is intentional and documented in spec §8.2. Do not modify.

**Overflow Protocol** — Tier 1 (single packet, ≤51 bytes at LoRa SF12) and Tier 2 (sequential burst). Three loss tolerance policies: Φ (Fail-Safe), Γ (Graceful Degradation, default), Λ (Atomic — required for K and H namespace instructions with irreversible consequences).

**BAEL floor guarantee** — the protocol never makes an instruction longer than its natural language input. When the encoded form exceeds the natural language form, BAEL selects NL_PASSTHROUGH and transmits the original with a flags bit. Compression is never negative.

**FNP fingerprinting** — SHA-256 dictionary fingerprint for session handshake verification. Two nodes with matching fingerprints share identical ASD state.

**Sovereign namespace extension** — `Ω:` (U+03A9) allows any implementing party to define proprietary namespace extensions without central approval or registration.

---

## What Requires MDR or Future Work

**MDR (Managed Dictionary Registry)** — not yet published. When published, MDR will map ICD-10 diagnosis codes, SNOMED CT concept identifiers, ISO 20022 financial instrument identifiers, and other open-ended registry values into compact SAL tokens, increasing first-tier compression density. The SDK is structurally ready for MDR deltas via `applyDelta()`. The extended mapping tables are not yet published.

**Overflow Protocol Tier 3** — DAG decomposition for instructions with conditional branches and dependency chains. Spec-defined and patent-covered; implementation is a contribution target.

**FNP full handshake** — the two-message capability advertisement + acknowledgment protocol (≤40 bytes each, within LoRa MTU). Fingerprint computation is implemented; the handshake state machine is a contribution target.

**C++ firmware-level OSMP nodes** — OSMP integration with Meshtastic via the Python SDK and Meshtastic Python library is operational today (see CONTRIBUTING.md). The C++ contribution target is a firmware-level encoder/decoder enabling ESP32 and nRF52 Meshtastic devices to operate as sovereign OSMP nodes without a companion device, with the ASD compiled into flash.

---

## Architecture

| Component | Function |
|---|---|
| **SAL** — Semantic Assembly Language | Domain-specific symbolic instruction format |
| **ASD** — Adaptive Shared Dictionary | 339-opcode version-pinned compression dictionary |
| **FNP** — Frame Negotiation Protocol | Capability negotiation and session handshake |
| **SNA** — Sovereign Node Architecture | Autonomous edge node, air-gapped operation |
| **TCL** — Translational Compression Layer | Semantic serialization and transcoding |
| **OP** — Overflow Protocol | Message fragmentation, priority, graceful degradation |
| **BAEL** — Bandwidth-Agnostic Efficiency Layer | Adaptive encoding across any channel capacity |

---

## Why OSMP Is Different From Every Other Agent Protocol

| Protocol | Transport | Offline | Compression | Inference-Free Decode |
|---|---|---|---|---|
| MCP (Anthropic) | HTTP/JSON | ✗ | ✗ | ✗ |
| A2A (Google/Linux Foundation) | HTTPS/JSON | ✗ | ✗ | ✗ |
| ACP (IBM) | REST/HTTP | ✗ | ✗ | ✗ |
| **OSMP** | **Any channel** | **✓** | **60.8% mean** | **✓** |

MCP, A2A, and ACP are framework-layer protocols. OSMP is an encoding-layer protocol. It operates beneath any of them. Two agents using different frameworks that share the OSMP grammar and dictionary can communicate with no modification to either framework.

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

## Integration Path

OSMP replaces JSON as the agent instruction serialization format. An LLM that currently outputs:

```json
{"action": "move", "agent": "BOT1", "waypoint": "WP1", "priority": "urgent"}
```

can be configured via system prompt to output:

```
R:MOV@BOT1:WPT:WP1↺
```

The LLM's existing NL→structured output capability handles the translation. The system prompt supplies the SAL grammar, the ASD, and examples from the canonical test vectors. No new tooling required on the generating side. What changes is that the receiving node decodes by table lookup instead of inference — enabling LoRa transport, offline operation, and any-device participation.

---

## Repository Structure

```
cloudless-sky/
  protocol/
    spec/           ← OSMP-SPEC-v1.md — authoritative protocol specification
    grammar/        ← SAL-grammar.ebnf — formal grammar (EBNF)
    test-vectors/   ← canonical-test-vectors.json — 55-vector conformance suite
  sdk/
    python/         ← Reference implementation (pip: osmp-protocol)
    typescript/     ← OpenClaw/web SDK (npm: osmp-protocol)
    go/             ← PicoClaw/constrained hardware SDK
  tests/
    tier1/          ← Unit tests per SDK (Python 122, TypeScript 112, Go 10)
    tier2/          ← Cross-SDK wire compatibility (86-instruction corpus)
  docs/
    adr/            ← Architecture Decision Records
```

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The spec is authoritative. All SDK implementations are validated against the canonical test vectors. A conformant implementation must achieve ≥60% mean UTF-8 byte reduction with zero decode errors.

Meshtastic integration via the Python SDK and Meshtastic Python library is operational today with no additional code required. See CONTRIBUTING.md for details.

Wanted: C++ firmware-level encoder/decoder (ESP32/nRF52 sovereign nodes), Kotlin/Swift mobile SDKs, Tier 3 DAG fragmentation, FNP handshake state machine.

---

## Patent Notice

The OSMP architecture is covered by pending US patent application OSMP-001-UTIL (inventor: Clay Holberg, priority date March 17, 2026). A continuation-in-part (OSMP-001-CIP) extends coverage to cloud-scale AI orchestration, non-RF channels, and the AI-native namespace architecture. Apache 2.0 includes an express patent grant for implementations of this specification. See [`PATENT-NOTICE.md`](PATENT-NOTICE.md).

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

---

*Cloudless Sky is a project of Octid.*
