# Structural Efficiency Analysis of Semantic Assembly Language for Agentic Instruction Encoding

## A Multi-Layer Comparison of SAL, JSON-RPC, and Binary Serialization Formats Across Wire, Token, and Grammar Dimensions

**Version 2.0 | March 2026**
**Octid Semantic Mesh Protocol (OSMP) v1.0 | Cloudless Sky Project**
**Author: Clay Holberg**
**Contact: ack@octid.io | octid.io**
**Repository: github.com/octid-io/cloudless-sky**
**License: Apache 2.0 with express patent grant**

---

## Abstract

This paper presents a multi-layer efficiency analysis comparing Semantic Assembly Language (SAL), the instruction encoding format of the Octid Semantic Mesh Protocol (OSMP), against JSON-RPC, MessagePack (self-describing binary), and Protocol Buffers (schema-based binary). The primary evidence base is a 29-vector empirical benchmark drawn from five production frameworks (MCP, OpenAI, Google A2A, CrewAI, Microsoft AutoGen), measured across three dimensions: byte reduction, LLM token economics (GPT-4 cl100k_base tokenizer), and binary serialization comparison (MessagePack and Protocol Buffers). Supplementary analysis includes a 1,000-point grammar-level structural overhead sweep and Shannon entropy measurement of structural token streams.

Principal findings: SAL achieves 75.6% mean token reduction (measured with the GPT-4 cl100k_base tokenizer), 86.5% mean byte reduction over JSON, 69.8% over Protocol Buffers, and 84.1% over MessagePack. Protocol Buffers achieves 55.4% reduction over JSON, confirming that schema-based binary formats capture a significant portion of JSON's overhead. SAL's additional reduction over protobuf derives from semantic content compression (replacing natural language descriptions with opcode lookups), not from superior structural encoding alone. The paper includes an adversarial prosecution section, explicit methodological assumptions, and honest disclosure of cases where SAL underperforms protobuf on numeric-heavy payloads.

All methodologies, data, source code, and test vectors are published in the open repository. The protocol has zero production deployments, zero third-party adoption, no independent audit, and no formal verification. This paper measures encoding properties, not production readiness.

---

## 1. Introduction

The dominant serialization format for agent-to-agent communication in 2026 is JSON, transmitted via JSON-RPC 2.0 (in MCP and Google A2A) or as structured function call objects (in OpenAI, CrewAI, and AutoGen). JSON is a self-describing key-value format designed for human developer readability. It has achieved ubiquitous adoption because developers can read, write, and debug it without specialized tools.

This design carries a cost. Every JSON message includes key names that repeat with every transmission, nesting braces, quoted string delimiters, type discriminators, and protocol envelopes. These structural elements consume bytes on the wire and tokens in LLM context windows. Schema-based binary formats (Protocol Buffers, Apache Avro, FlatBuffers) address part of this overhead by externalizing field names into a shared schema compiled at both endpoints. Self-describing binary formats (MessagePack, CBOR) address a smaller portion by using compact type headers while preserving key names. None of these, by themselves, replace verbose natural-language instruction content with a constrained operational vocabulary.

OSMP's Semantic Assembly Language (SAL) operates at a different layer. It is not a compression algorithm applied to JSON or a binary encoding of JSON's structure. It is a domain-specific instruction language that replaces natural language content with opcode lookups against a shared dictionary (the ASD). This means SAL compresses both structure and content, but at the cost of a stronger dependency: the ASD must be present at both endpoints, and the instruction domain must be covered by the ASD's vocabulary.

OSMP originated from a design exercise exploring the minimum viable encoding for AI agent communication under extreme bandwidth constraints. LoRa radio, the physical layer underlying both the LoRaWAN enterprise network protocol and the Meshtastic peer-to-peer mesh protocol, imposes payload floors ranging from 11 bytes (US915 DR0 under LoRaWAN) to 51 bytes (EU868 DR0) to 255 bytes (standard Meshtastic LongFast deployment). A standard JSON-RPC 2.0 tools/call envelope is 82 bytes before content, exceeding these floors. The protocol was designed from the minimum constraint upward. This paper measures whether the encoding properties that enable constrained-channel operation also produce meaningful efficiency gains on unconstrained cloud infrastructure.

### 1.1 Scope and Limitations

OSMP v1.0 is a working protocol with a reference implementation, three SDK implementations (Python, TypeScript, Go), 231 passing tests, an MCP server on PyPI (pip install osmp-mcp), and a static website. It has zero production deployments, zero third-party adoption metrics, and no independent audit. The analysis measures encoding properties, not production readiness. These are different questions.

SAL does not replace JSON for arbitrary data serialization, and it does not replace Protocol Buffers for general-purpose schema-driven messaging. It replaces verbose text-based encodings for agentic instructions where the semantic content maps to a defined set of operational codes. Free-form data remains in its native format. The efficiency claims apply to the instruction encoding domain.

### 1.2 Methodological Disclosure

This paper was authored by the protocol's inventor. It has been subjected to independent adversarial review, and the prosecution section (Section 10) incorporates findings from that review. However, the data, models, and analysis originate from the same source as the protocol itself. Independent replication using the published code and test vectors is encouraged.

---

## 2. Protocol Overview

### 2.1 Encoding Architecture

A SAL instruction is a human-readable character sequence comprising four layers:

1. **Namespace prefix** (1 byte): A single uppercase Latin letter identifying the semantic domain (A through Z, 26 standard namespaces).
2. **Opcode** (2-6 bytes): An alphanumeric code representing a semantic primitive drawn from an authoritative domain vocabulary.
3. **Glyph operators** (1-3 bytes each): Unicode formal logic symbols representing logical, sequential, or compositional relationships.
4. **Slot values** (variable): Typed operand positions carrying parameters, targets, and domain codes.

Example: `H:TRIAGE?I` (10 bytes) encodes "triage classification: immediate." The equivalent JSON-RPC tool call requires approximately 140-170 bytes depending on framework.

### 2.2 Adaptive Shared Dictionary (ASD)

The ASD is the shared reference enabling positional encoding without self-description. It contains 339 opcodes across 26 namespaces, drawn from authoritative domain standards (ICD-10, ISO 20022, MITRE ATT&CK, IEEE 1451, RFC 5424, FIPS 140-3, and others). Three MDR corpora extend the ASD with 124,215 resolvable domain codes.

Both sender and receiver must possess the ASD. This is architecturally analogous to protobuf's requirement for compiled .proto schemas at both endpoints, and to MCP's tools/list schema discovery step. The ASD shifts schema from per-message to per-session. Unlike protobuf schemas, the ASD also provides semantic vocabulary compression: opcode names replace natural language descriptions.

### 2.3 Decode Property

SAL decoding is performed by table lookup against the ASD. No neural inference, statistical model, or training history is required. Any device capable of string processing and dictionary lookup can decode SAL instructions. This enables deployment on constrained hardware (ESP32, LoRaWAN end devices, Meshtastic nodes) where language model inference is computationally infeasible.

---

## 3. Methodology

### 3.1 Content-Structure Decomposition

The analysis separates encoded messages into two byte classes:

**Content bytes (C):** The semantic payload. A location name, an ICD-10 code, an account number.

**Structural bytes (S):** Everything the grammar requires that is not content. In JSON: key names, braces, quotes, colons, commas, type discriminators, protocol envelopes. In SAL: namespace prefix, assign colon, target operator, slot brackets, composition operators. In protobuf: field tags, wire type indicators, varint length prefixes.

The overhead ratio for a grammar G is: R(G, M) = S_G / (S_G + C).

**Explicit assumptions and limitations of this decomposition:**

1. Key names are classified as structural because SAL and protobuf both eliminate them through positional/field-number encoding. This is a modeling choice, not an objective fact. In JSON, key names carry semantic information to human readers and have real engineering value for debugging, interoperability, and evolvability. The decomposition treats this value as zero for purposes of wire/token cost measurement.

2. The ASD and protobuf schemas are treated as session-level costs amortized across all messages, not charged per-message. This is defensible for persistent connections but overstates the advantage for short-lived or ad hoc exchanges where dictionary/schema negotiation occurs frequently.

3. SAL's opcode substitution compresses content, not just structure. When SAL replaces "Transferred to flights_refunder" with `J:HANDOFF@flights_refunder`, the content is shorter because the opcode carries semantic meaning that the natural language description spelled out. This is vocabulary-level compression, distinct from structural overhead reduction. Both contribute to SAL's total byte savings, but they are different mechanisms.

4. This decomposition does not measure dictionary lifecycle costs (version negotiation, synchronization, cache invalidation, governance). Those are real system costs not captured by per-message encoding measurement.

### 3.2 Measurement Dimensions

**Primary evidence:**

| Layer | Measures | Data Points | Method |
|-------|---------|-------------|--------|
| Byte reduction | SAL vs JSON vs MessagePack vs Protocol Buffers | 29 | Direct measurement + protobuf compiled schemas (protoc 3.21.12) |
| Token economics | LLM context window consumption | 29 | GPT-4 cl100k_base tokenizer (tiktoken) |
| Batch compression | All formats with best second-pass compression | 29 (batched) | gzip for JSON/MsgPack, lossless block for SAL |

**Supplementary analysis:**

| Layer | Measures | Data Points | Method |
|-------|---------|-------------|--------|
| Grammar structural overhead | Structural bytes per grammar, content held constant | 1,000 | Analytical sweep (n, k, d) |
| Shannon entropy | Information density of structural token streams | 2 corpora (500 msg each) | Byte-level entropy |

### 3.3 Empirical Validation

Twenty-nine test vectors sourced from official documentation of five production frameworks:

| Framework | Version | Vectors | Source |
|-----------|---------|---------|--------|
| MCP | 2025-11-25 spec | 7 | modelcontextprotocol.io |
| OpenAI | Responses API / Chat Completions | 7 | developers.openai.com |
| Google A2A | v0.2.5 spec | 5 | a2a-protocol.org |
| CrewAI | 0.86+ | 5 | docs.crewai.com |
| Microsoft AutoGen | 0.4 AgentChat | 5 | microsoft.github.io/autogen |

Every JSON payload is drawn from published documentation. Source URLs are recorded per vector and published in the repository.

### 3.4 What This Analysis Does Not Measure

Parse speed, implementation complexity, ecosystem maturity, developer experience, production reliability, dictionary lifecycle costs, failure mode behavior, or security properties. These matter and are out of scope.

---

## 4. Layer 1: Grammar-Level Structural Analysis

### 4.1 Structural Models

**JSON-RPC (MCP pattern).** The minimum structural envelope for a JSON-RPC 2.0 tools/call message is 82 bytes:

    {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"","arguments":{}}}

This is the exact minified string. The 82 bytes are structural: they must be present regardless of what content fills the empty name and arguments fields. Each parameter adds approximately 5 bytes of structural tokens (quotes, colon, comma) plus the key name (average 6 bytes). Each instruction in a chain requires its own complete envelope.

**SAL.** The minimum structural frame is 2 bytes (namespace prefix + assign colon). Target adds 1 byte. Slot list adds 3 bytes plus 1 byte per separator. Chain operators add 1-3 bytes per join. No envelope. No key names.

**Protocol Buffers.** Field tag (1-2 bytes per field) + varint length prefix for strings (1 byte for lengths under 128). No key names, no braces, no quotes. Protobuf's structural overhead is the lightest of the three formats for a given number of fields.

### 4.2 Parameter Space Sweep

Structural byte models swept across: n = [1..20] parameters, k = [1..10] chain length, d = [1..5] nesting depth. Total: 1,000 data points.

The sweep is synthetic. It is not measured from real agent traffic distributions. It shows the grammar's behavior across the composition space, not the frequency-weighted behavior of production deployments.

**Results (SAL vs JSON-RPC only; protobuf is measured empirically in Section 6):**

| Metric | Uniform | Frequency-Weighted |
|--------|---------|-------------------|
| Structural advantage (SAL over JSON-RPC) | 92.9% | 93.1% |
| JSON overhead ratio (structure / total) | 75.1% | 86.2% |
| SAL overhead ratio (structure / total) | 19.3% | 31.7% |

The near-identity of uniform and weighted results reflects that JSON's overhead scales linearly with every composition parameter while SAL's scales sublinearly. This stability is a property of the model, not an empirical discovery.

---

## 5. Layer 2: Token Economics

### 5.1 Why Tokens, Not Bytes, Are the Cost Layer

When Agent A sends a tool call to Agent B in a cloud environment:

1. **Wire layer:** JSON serialized, optionally gzipped, transmitted over HTTP. Bandwidth is effectively free. Gzip achieves 70-85% compression on repetitive JSON structural tokens.

2. **Token layer:** The full, uncompressed JSON text is placed into the LLM's context window. Every key name, brace, quote, and envelope token consumes API metering and context capacity. Gzip does not operate at this layer. The LLM never sees compressed bytes.

Empirical studies of production multi-agent systems reveal that 53-86% of tokens are consumed by communication overhead rather than useful work. The AgentTaxo study measured token duplication rates across frameworks: 72% in MetaGPT, 86% in CAMEL, and 53% in AgentVerse [12]. AgentPrune demonstrated comparable performance at 87% cost reduction by pruning redundant communication [13]. OPTIMA achieved up to 90% token reduction through optimized multi-agent communication training [14].

### 5.2 Empirical Token Measurement

All 29 vectors tokenized with GPT-4 cl100k_base (tiktoken). Measured counts, not estimates.

| Metric | JSON | SAL | Reduction |
|--------|------|-----|-----------|
| Total tokens (29 vectors) | 1,809 | 441 | 75.6% |
| Mean tokens per instruction | 62.4 | 15.2 | 75.6% |

**Token economics at representative LLM input pricing ($2.50 / 1M tokens):**

At 10,000 inter-agent messages per day across a deployment: approximately $430/year in input token savings. At 50,000 messages per day: approximately $2,150/year. These figures cover input tokens only, at a single price point, for a single tokenizer. Output tokens (priced higher) and context window capacity freed for reasoning are not quantified here.

### 5.3 The Gzip Boundary

| Layer | Gzip | SAL |
|-------|------|-----|
| Wire (HTTP transport) | 70-85% compression | 86.5% byte reduction |
| Token (LLM context window) | No effect | 75.6% token reduction |

On unconstrained cloud channels, the wire efficiency argument alone does not justify a protocol change when gzip is available. The token economics argument is structurally independent of gzip because gzip operates below the LLM layer.

On constrained channels (LoRaWAN end devices, Meshtastic mesh nodes, BLE, ESP32), gzip is unavailable: the device lacks memory for streaming decompression, and compressed output may still exceed the payload floor.

---

## 6. Layer 3: Binary Serialization Comparison

### 6.1 Format Classification

Binary serialization formats fall into two architectural classes:

**Self-describing formats (MessagePack, CBOR, BSON):** Replace JSON's text syntax with binary type headers and compact encodings, but preserve key names, nesting structure, and per-message schema. The receiver needs no prior knowledge of the message structure.

**Schema-based formats (Protocol Buffers, FlatBuffers, Apache Avro, Cap'n Proto):** Externalize field names into a shared schema (.proto file, .avsc file) compiled at both endpoints. The wire message contains field numbers and wire types, not field names. The receiver recovers names and types from the compiled schema. This is architecturally analogous to SAL's use of the ASD.

Previous versions of this analysis compared SAL only to MessagePack. That comparison is incomplete because it understates what schema-based formats achieve. Protocol Buffers is included here as the strongest binary comparator.

### 6.2 Four-Way Comparison

All 29 JSON payloads encoded in MessagePack (msgpack.packb) and Protocol Buffers (compiled .proto schemas with protoc 3.21.12, optimal field numbering using fields 1-15 for single-byte tags). Protobuf schemas were designed generously: low field numbers, compact types, well-structured messages.

| Format | Total Bytes | Reduction vs JSON |
|--------|------------|-------------------|
| JSON (minified) | 6,896 | baseline |
| MessagePack (self-describing) | 5,848 | 15.2% |
| Protocol Buffers (schema-based) | 3,075 | 55.4% |
| SAL (semantic instruction encoding) | 928 | 86.5% |

**Cross-format comparisons:**

| Comparison | Reduction |
|------------|-----------|
| SAL vs Protocol Buffers | 69.8% |
| SAL vs MessagePack | 84.1% |
| Protobuf vs MessagePack | 47.3% |

### 6.3 Where SAL Loses

On vector DOM-04 (scale service to 5 replicas with resource limits), protobuf produces 27 bytes while SAL produces 52 bytes. SAL is 92.6% larger. This occurs because the payload is dominated by short numeric values (replicas: 5, cpu: "2000m", memory: "4Gi") that protobuf encodes as 1-2 byte varints while SAL transmits as UTF-8 text. When payloads are predominantly numeric with short string values and no natural language content to compress, protobuf will outperform SAL on wire bytes.

### 6.4 Why the Gap Exists

Protobuf and SAL share the same architectural bet: externalize schema/dictionary, amortize it across the session. Both eliminate key names from the wire. Why does SAL still beat protobuf by 69.8% overall?

The answer is content compression, not structural encoding. Protobuf transmits the semantic content in full: the string "Transferred to flights_refunder, adopting the role of flights_refunder immediately." is 85 bytes in protobuf (tag + length prefix + 83 bytes UTF-8 content). SAL replaces this with `J:HANDOFF@flights_refunder` (26 bytes) because the opcode `HANDOFF` carries the semantic meaning that the natural language description spelled out.

This is not a fair structural comparison. It is a vocabulary comparison. Protobuf faithfully serializes whatever content the application provides. SAL replaces the content with a domain-specific code. The reduction comes from the domain vocabulary, not from superior encoding mechanics.

On pure structural overhead (tags, length prefixes, type indicators vs namespace prefix, colons, brackets), protobuf and SAL are comparable for low field counts. SAL's advantage grows with content length because opcode substitution compresses content linearly with description verbosity. Protobuf's advantage grows with numeric-heavy payloads where varint encoding is maximally compact.

**Methodological note:** The protobuf sizes in this analysis were verified against compiled .proto schemas using protoc 3.21.12 with Python serialization. The analytical wire format estimates (used for initial comparison) differed from compiled serializer output by 6 bytes total across all 29 vectors (3,081 analytical vs 3,075 compiled, a 0.2% delta). Three vectors produced compiled output 2 bytes smaller than estimated due to proto3 default value omission. All other vectors were byte-identical. The compiled results are used in this paper. The .proto schemas and serialization code are published in the repository.

**Defensible summary:** Against the benchmark set used here, compiled-schema Protocol Buffers captures much of JSON's structural inefficiency, reducing total bytes by 55.4% versus minified JSON. SAL remains smaller by a further 69.8% relative to compiled protobuf, but that remaining gap is attributable primarily to domain-specific semantic abbreviation via a shared dictionary rather than to structural encoding alone.

### 6.5 System Complexity

JSON-RPC is self-describing: the grammar is the full system. Protobuf requires grammar + schema compiler + .proto files at both endpoints. SAL requires grammar + ASD + MDR corpora at both endpoints. Protobuf and SAL are comparable in total system complexity; both trade per-message simplicity for per-session dependency. JSON trades per-session simplicity for per-message overhead.

### 6.6 Two-Tier Encoding: Per-Message and Batch Transmission

The results in Sections 6.2 through 6.4 measure raw SAL, the human-readable UTF-8 text as it appears at encode and decode time. The OSMP specification also defines a two-tier encoding architecture in which SAL-encoded instructions undergo lossless block compression prior to wire transmission. The first tier is the semantic encoding (natural language to SAL via the ASD). The second tier is lossless compression of the SAL byte stream for transport. The human-readable form is recoverable at the receiver by reversing the second tier and resolving the first tier by dictionary lookup.

**Per-message results.** On the 29 benchmark vectors, the second-tier compression does not reduce byte count below the raw SAL size for any individual message. The overhead of the compression frame header exceeds the savings achievable on payloads of 10-65 bytes. The protocol's mode selection mechanism correctly selects uncompressed SAL for all 29 individual messages. This is the compression floor guarantee operating as designed: the two-tier architecture never increases byte count over the single-tier encoding.

**Batch transmission results.** Multi-agent workflows frequently produce compound instruction sequences transmitted as a group. When all 29 benchmark instructions are encoded as a single batch (simulating a compound workflow or Overflow Protocol sequential burst), second-pass lossless compression is applied to all formats to ensure symmetric comparison. Results:

| Format + Best Compression | Batch Size (29 instructions) |
|--------------------------|------------------------------|
| SAL + lossless block compression | 640 bytes |
| Protocol Buffers + gzip | 1,751 bytes |
| JSON (minified) + gzip | 2,623 bytes |
| MessagePack (array) + gzip | 2,698 bytes |

SAL's batch compression reduces the combined payload from 956 raw bytes to 640 bytes, a 33.1% compression over the already-compact SAL encoding. Protobuf's concatenated binary stream compresses from 3,075 raw bytes to 1,751 under gzip (43.1% compression), confirming that protobuf's binary does contain exploitable redundancy in batch. JSON + gzip achieves 62.1% compression from 6,924 raw bytes to 2,623. Compressed SAL remains 63.4% smaller than compressed protobuf, 75.6% smaller than compressed JSON, and 76.3% smaller than compressed MessagePack. All formats receive their best available second-pass lossless compression in this comparison.

The batch compression ratio improves with message count because SAL's structural tokens (namespace prefixes, colons, operators, bracket patterns) are highly repetitive across instructions in the same domain. Protobuf's binary encoding, already compact per-message, offers less redundancy for a second-pass compressor to exploit.

**Per-vector scoreboard: raw SAL vs Protocol Buffers.** Without any second-tier compression, SAL produces a smaller encoding than Protocol Buffers on 28 of 29 vectors. The single vector where protobuf wins (DOM-04: Kubernetes scaling with resource limits, protobuf 27 bytes, SAL 52 bytes) is a numeric-heavy payload with short string values and no natural language content to compress. On that class of payload, protobuf's binary numeric encoding (variable-length integers) is more compact than SAL's text representation of the same values. This is a consequence of SAL's human-readability constraint: the wire format is inspectable text, which costs bytes on numeric fields that protobuf encodes as binary.

**Traffic-weighted representation.** The 28-of-29 scoreboard is a vector count, not a traffic-weighted result. If numeric-only payloads (where protobuf is competitive or superior) represent a large fraction of production agent traffic, the effective advantage would be lower than the per-vector count implies. Among the message types documented in production multi-agent frameworks (tool calls, task delegations, handoffs, configuration exchange), the dominant pattern is text-heavy with natural language descriptions, method names, and context strings. Numeric-only patterns are more characteristic of sensor telemetry than agent-to-agent instruction exchange. The scoreboard reflects this instruction-class distribution, but it is based on 29 selected vectors, not measured traffic distributions.

**Interpretation.** The two-tier architecture does not change SAL's per-message competitive position against protobuf. Raw SAL already wins 28 of 29 vectors on semantic compression alone. The second tier matters for compound instruction chains where batch compression of the SAL stream yields further reduction. When all formats receive their best second-pass compression, SAL (640 bytes) remains 63.4% smaller than compressed protobuf (1,751 bytes) and 75.6% smaller than gzipped JSON (2,623 bytes). This is the pattern that occurs in production multi-agent workflows: not single isolated instructions, but sequences of related instructions with shared namespace context, repeated targets, and structural regularity.

---

## 7. Supplementary: Shannon Entropy Analysis

### 7.1 Method and Limitations

Two corpora of 500 messages each were generated: one of JSON-RPC structural tokens and one of SAL structural tokens. Content values replaced with fixed-length placeholders. Byte-level Shannon entropy computed.

**Limitations:** These corpora are not like-for-like. JSON's corpus includes repeated field names because JSON is self-describing. SAL's corpus excludes the ASD that gives its symbols meaning. The comparison measures entropy of the wire format only, not entropy of the full encoding system including external dependencies. Results should be interpreted within this constraint.

### 7.2 Results

| Metric | JSON structural | SAL structural |
|--------|----------------|----------------|
| Corpus size | 80,070 bytes | 16,306 bytes |
| Entropy | 4.20 bits/byte | 3.60 bits/byte |
| Total structural information | 336,558 bits | 58,640 bits |

### 7.3 Interpretation

SAL's per-byte entropy is lower than JSON's (3.60 vs 4.20 bits/byte). Each SAL structural byte is individually more redundant. But SAL produces 4.9x fewer structural bytes, yielding 5.7x lower total structural information cost.

SAL achieves this by eliminating entire categories of structural tokens (quotes at 26% of JSON's stream, key names at ~30%, envelope tokens). This elimination mechanism differs from compression: gzip can exploit redundancy within JSON's structural stream, but cannot remove the grammar's requirement for key names, quotes, and envelopes. Schema-based formats like protobuf CAN remove field names, which is why protobuf's structural overhead is substantially lower than JSON's. SAL's remaining advantage over protobuf comes from content vocabulary compression, not structural elimination.

---

## 8. Empirical Validation: 29-Vector Benchmark

| Framework | Vectors | Mean Byte Reduction vs JSON | Mean Token Reduction | Mean Byte Reduction vs Protobuf |
|-----------|---------|----------------------------|---------------------|-------------------------------|
| MCP | 7 | 87.2% | 72.7% | 51.3% |
| OpenAI | 7 | 85.5% | 72.2% | 59.2% |
| Google A2A | 5 | 86.1% | 75.1% | 61.3% |
| CrewAI | 5 | 84.0% | 68.5% | 77.6% |
| AutoGen | 5 | 85.8% | 81.6% | 77.8% |
| Cross-domain | 7 | 87.5% | 74.8% | 50.5% |

CrewAI and AutoGen show the largest SAL-vs-protobuf gap because their payloads contain long natural language strings (task descriptions, agent backstories, conversation histories) that protobuf transmits verbatim while SAL replaces with opcodes. MCP and OpenAI show the smallest gap because their tool call payloads are more structured with shorter string values.

---

## 9. Four-Mode Communication Architecture

OSMP operates across four communication modes. The encoding format does not change between modes; the binding constraint and the economic argument differ.

### 9.1 Mode 1: Edge-to-Edge (Binding Constraint: Physics)

**The LoRa Layer Stack.** LoRa is a physical radio modulation technique (chirp spread spectrum, Semtech). Two protocol ecosystems sit on top of it:

**LoRaWAN** is a MAC/network protocol managed by the LoRa Alliance (500+ member companies). Star-of-stars topology: end devices communicate through gateways to centralized network servers. Millions of devices deployed globally for metering, tracking, agriculture, and industrial monitoring.

**Meshtastic** is a peer-to-peer mesh protocol on the same LoRa hardware. Decentralized, no gateway or server dependency. Community-oriented with active AI integration efforts (MESH-API, DEF CON 700+ node mesh demonstration).

OSMP operates at the application layer, above both. The payload encoding goes inside either protocol's frame.

**Payload floors by transport and region:**

| Transport / Config | Application Payload |
|-------------------|-------------------|
| LoRaWAN US915 DR0 (SF12) | 11 bytes |
| LoRaWAN EU868 DR0 (SF12) | 51 bytes |
| LoRaWAN US/EU DR3+ (SF9) | 125+ bytes |
| Meshtastic LongFast (default) | 228-255 bytes |

At 11 bytes, `H:TRIAGE?I` (10 bytes) fits. A bare `{"a":1}` is 7 bytes. A JSON-RPC envelope (82 bytes) is physically impossible below DR3. A protobuf-encoded minimal tool call (approximately 35 bytes) exceeds the EU DR0 floor. Among the formats compared in this analysis, SAL produces the most compact multi-field instructions at 11-51 byte floors.

**Existing application-layer encodings.** The closest standardized application-layer encoding in LoRaWAN is CayenneLPP (Cayenne Low Power Payload), a binary TLV format supporting approximately 20 sensor data types. CayenneLPP is built into The Things Stack as a native payload formatter. It handles sensor telemetry compactly: a temperature reading is 4 bytes (channel + type + value).

CayenneLPP cannot express conditional logic, multi-step workflows, cross-domain composition, or any form of agentic instruction. When a LoRaWAN deployment needs to send instructions rather than readings, custom binary byte layouts with device-specific payload formatters are the norm. There is no dominant standardized, semantically composable instruction encoding for these channels comparable to what CayenneLPP provides for telemetry.

OSMP targets this instruction-encoding space. A SAL payload formatter for The Things Stack would be a JavaScript function performing ASD lookup, enabling any LoRaWAN network server to decode OSMP instructions without per-device custom code. On Meshtastic, SAL instructions are UTF-8 text through the existing message channel. This does not mean no other instruction-layer solutions exist; custom TLV protocols, domain-specific command encodings, and proprietary control payloads are widely used. What does not exist is a cross-domain standard with a published dictionary and open implementations.

The constrained-channel claim should be scoped precisely: OSMP does not replace CayenneLPP for compact numeric telemetry (where CayenneLPP's binary encoding is more compact per reading). It addresses the instruction encoding space that CayenneLPP does not cover.

**The numeric tax on biometric telemetry.** The tradeoff between SAL's human-readable encoding and binary numeric encoding can be quantified on real clinical data. Human vital signs occupy narrow numeric ranges that rarely exceed three digits:

| Vital Sign | Clinical Range | SAL Encoding | SAL Bytes | Binary (protobuf-equivalent) | Binary Bytes | Delta |
|-----------|---------------|-------------|-----------|------------------------------|-------------|-------|
| Heart rate | 40-200 bpm | `H:HR[72]` | 8 | channel + type + varint | 4 | +4 |
| SpO2 | 70-100% | `H:SPO2[97]` | 10 | channel + type + varint | 4 | +6 |
| Respiratory rate | 8-40 /min | `H:RR[16]` | 8 | channel + type + varint | 4 | +4 |
| Temperature | 90-110 F | `H:TEMP[101]` | 11 | channel + type + varint | 4 | +7 |
| Blood pressure | 60-250 mmHg | `H:BP[120/80]` | 12 | channel + type + 2x varint | 4 | +8 |
| Glucose | 40-500 mg/dL | `H:GLUC[95]` | 10 | channel + type + varint | 4 | +6 |
| Triage classification | I/D/M/B/X | `H:TRIAGE?I` | 10 | channel + type + enum | 3 | +7 |

A complete vitals panel (7 readings): SAL costs 69 bytes. Binary costs 27 bytes. The numeric tax is 42 bytes total, averaging 6 bytes per reading.

**What the tax buys.** The same device, in the same grammar, on the same channel, without switching protocols, can also express:

| Instruction | SAL Encoding | Bytes | Fits EU DR0 (51B) |
|------------|-------------|-------|-------------------|
| Threshold-triggered clinical alert | `H:HR<60→H:ALERT[BRADYCARDIA]∧H:ICD[R001]` | 44 | Yes |
| Triage + MEDEVAC request | `H:TRIAGE?I∧H:ICD[J939]→H:CASREP@coord⚠` | 44 | Yes |
| Composite vitals in one frame | `H:HR[72]∧H:SPO2[97]∧H:RR[16]∧H:BP[120]` | 44 | Yes |
| GPS-tagged triage | `E:GPS[40.7128,-74.006]∧H:TRIAGE?I` | 35 | Yes |

None of these can be expressed in CayenneLPP at any byte count. A protobuf encoding could serialize equivalent data structures, but the .proto schema defining those structures must be designed, agreed upon by sender and receiver, compiled, deployed to both endpoints, and versioned. SAL carries the semantics in the encoding itself, resolvable by any node with the ASD.

The complete sense-decide-act loop (sensor reading, threshold evaluation, alert composition, coordination request, command response) runs in one grammar with zero translation boundaries between stages. A deployment using CayenneLPP for telemetry plus custom binary for thresholds plus JSON for cloud coordination maintains three encoding formats with translation logic at every boundary. Each boundary is code to write, test, maintain, and debug. On a constrained device in a disconnected environment, each boundary is also a failure surface.

42 bytes of numeric tax per vitals panel. One protocol for the entire operational loop. That is the tradeoff.

### 9.2 Mode 2: Edge-to-Cloud (Binding Constraint: Asymmetric Encoding)

The edge node encodes in SAL and transmits via LoRaWAN gateway, Meshtastic mesh relay, cellular, or satellite. The cloud node decodes by ASD lookup. A triage classification with ICD-10 diagnosis, GPS coordinates, and MEDEVAC request encodes in approximately 38 bytes, transmissible at any LoRaWAN data rate or over Meshtastic.

The H namespace contains 16 clinical opcodes. The ICD-10-CM MDR corpus contains 74,719 codes resolvable at the edge by table lookup. Decode is deterministic: `H:ICD[J939]` resolves to "Pneumothorax, unspecified" by dictionary lookup. Deterministic decode is not the same as semantic adequacy: if the opcode inventory lacks a needed clinical concept, the decode is exact but incomplete. The ASD covers the ICD-10-CM code set; concepts outside that set require Frame Negotiation Protocol extension.

### 9.3 Mode 3: Cloud-to-Cloud (Binding Constraint: Token Economics)

Bandwidth is free. Gzip handles wire compression. But the LLM reads full uncompressed text as tokens. An agent encountering OSMP via the MCP server discovers eight tools and six resources, learns the grammar through tool use, and produces instructions at 75.6% fewer tokens (measured, Section 5.2).

The tradeoff: SAL instructions are not self-describing. A developer debugging a multi-agent system must consult the ASD to read `H:TRIAGE?I` where JSON shows `"triage_category":"immediate"` directly. For deployments where API cost at scale is the binding constraint, this tradeoff is favorable. For prototyping where cost is immaterial and debuggability is paramount, JSON's self-description has higher immediate value.

### 9.4 Mode 4: Enterprise Compliance (Binding Constraint: Regulatory Interoperability)

Instructions carrying regulatory code references (ICD-10, CFR, NFPA, ISO 20022) must be machine-readable and unambiguous across organizational boundaries. SAL's domain code accessor pattern (`H:ICD[J939]`, `K:PAY[ISO20022:MsgId]`) enables compliance logging where the instruction constitutes an auditable record. Any party with the ASD decodes to full regulatory meaning without proprietary tooling.

---

## 10. Limitations and Counterarguments

### 10.1 Protocol Buffers Is the Missing Strong Comparator (Verdict: Addressed)

Previous versions of this analysis used MessagePack as a binary proxy. That was weak. Protocol Buffers achieves 55.4% reduction over JSON by externalizing field names via compiled schemas. SAL's remaining 69.8% advantage over protobuf derives primarily from semantic content compression (opcode substitution), not structural encoding superiority. On numeric-heavy payloads where there is no natural language to compress, protobuf outperforms SAL (DOM-04: protobuf 27 bytes, SAL 52 bytes). Section 6.3 reports this honestly.

### 10.2 JSON Key Names Carry Information (Verdict: Valid, Acknowledged)

Key names have real engineering value: debugging, interoperability, evolvability, auditability, and safety inspection. The content-structure decomposition treats this value as zero for wire/token measurement purposes. That is a modeling choice stated explicitly in Section 3.1, not an objective fact.

### 10.3 Gzip Narrows the Wire Gap (Verdict: Valid on Wire, Inapplicable on Tokens)

Correct at the wire layer. Inapplicable at the token layer. On constrained channels, gzip is unavailable. See Section 5.3.

### 10.4 SAL Requires a Shared Dictionary (Verdict: Valid Architectural Tradeoff)

The ASD is a hard dependency. If the receiver lacks it, the message is unintelligible. JSON is self-contained. Protobuf requires compiled schemas, a comparable dependency. The ASD goes further than protobuf schemas by also compressing content, which tightens the coupling: a missing opcode is not just a missing field name but a missing concept.

Dictionary lifecycle costs (versioning, synchronization, governance, backward compatibility) are real system costs not measured in this per-message encoding analysis. These costs should not be dismissed as "amortized"; they are engineering burden that scales with deployment complexity.

### 10.5 Dictionary Governance and Version Drift (Verdict: Valid, Unquantified)

If sender and receiver ASD versions diverge, instructions may contain opcodes unknown to the receiver. The protocol addresses this through the Frame Negotiation Protocol (requesting definitions for unknown opcodes) and loss tolerance policies (fail-safe, graceful degradation, atomic). These mechanisms exist in the specification but are untested in production. The failure mode behavior under dictionary divergence is a first-order engineering concern for any deployment.

### 10.6 Semantic Loss from Constrained Opcode Inventories (Verdict: Valid)

339 opcodes across 26 namespaces cannot express every possible agent instruction. If the instruction domain falls outside the ASD vocabulary, SAL cannot encode it without sovereign extension (the Omega namespace) or MDR registration. Deterministic decode is not semantic adequacy: an exact decode of a limited vocabulary may lose nuance present in the original natural language instruction.

### 10.7 Content Compression Conflated with Grammar Compression (Verdict: Addressed in Methodology)

SAL's total byte reduction combines structural overhead reduction and vocabulary-level content compression. Section 3.1 states this explicitly. Section 6.4 separates the two mechanisms and explains why SAL's advantage over protobuf is primarily content compression.

### 10.8 Benchmark Selection Bias (Verdict: Partially Valid)

The 29 test vectors are drawn from tool-call and task-delegation patterns, which are verbose JSON-RPC wrappers. This is the dominant inter-agent communication pattern in the five frameworks tested, but it is not the only pattern. Short status messages, numeric sensor data, and binary payloads would show smaller SAL advantages or protobuf superiority (as DOM-04 demonstrates).

### 10.9 Glyph Operators Cost 3 Bytes (Verdict: Edge Case)

Unicode composition operators (3 bytes each in UTF-8) matter near LoRaWAN payload floors and are negligible for typical cloud messages where the envelope savings (82 bytes) dominate.

### 10.10 SAL Scope Is Limited to Instructions (Verdict: By Design)

SAL does not replace JSON or protobuf for arbitrary data. It replaces verbose text-based encodings where agent instructions are the payload.

### 10.11 Shannon Entropy Comparison Is Not Like-for-Like (Verdict: Valid, Scoped)

JSON's structural corpus includes self-describing tokens; SAL's excludes the external ASD. The comparison measures wire format entropy, not full system entropy. Section 7.1 states this limitation. The finding that SAL eliminates structural token categories is valid within this scope; the claim should not be extended to full-system information-theoretic superiority.

### 10.12 Unicode and Transport Fragility (Verdict: Acknowledged)

SAL depends on UTF-8 preservation through the transport layer. Systems that strip, transliterate, or corrupt multi-byte UTF-8 sequences will damage glyph operators. This is a deployment constraint documented in the protocol specification (malformed fragments treated as missing under loss tolerance policy) but not stress-tested in production.

### 10.13 Parser Complexity and Implementation Burden (Verdict: Unquantified)

This analysis measures encoding efficiency, not decoding complexity. SAL parsing requires Unicode-aware tokenization, namespace resolution, glyph operator recognition, and ASD lookup. JSON parsing is a solved problem with mature libraries in every language. Protobuf parsing is handled by generated code from compiled schemas. The implementation burden of a new parser for a new format is a real adoption cost not measured here.

### 10.14 Misdecode Risk Under Partial Vocabulary Overlap (Verdict: Acknowledged)

If sender and receiver have overlapping but non-identical ASD versions, an opcode may resolve to different definitions at each endpoint. The protocol specifies Frame Negotiation Protocol for unknown opcodes and loss tolerance policies for unresolvable instructions, but the behavior under partial overlap (where both sides have the opcode but with different semantic definitions due to version drift) is a failure mode that has not been tested. Silent semantic divergence is potentially worse than a clean unknown-opcode error.

### 10.15 Protobuf Comparison Verified Against Compiled Schemas (Verdict: Resolved)

The Protocol Buffers byte counts were initially computed analytically from wire format encoding rules. They have since been verified against compiled .proto schemas using protoc 3.21.12 with Python serialization. The compiled output differed from the analytical estimate by 6 bytes total across 29 vectors (0.2%). The compiled results are used in this paper. The .proto schemas are published in the repository.

---

## 11. Current State of the Protocol

| Component | Status |
|-----------|--------|
| Specification | OSMP v1.0, SAL EBNF grammar, semantic dictionary v12 |
| Patent | Provisional filed March 17, 2026 (#64/007,684); non-provisional in progress |
| Python SDK (reference) | 167 tests passing |
| TypeScript SDK | 52 tests passing |
| Go SDK | 12 tests passing |
| MCP Server | PyPI v1.0.12, 8 tools, 6 resources, 3 MDR corpora |
| Canonical benchmark | 55 vectors, 60.8% mean SAL-vs-NL reduction, CONFORMANT |
| Website | octid.io (static, Netlify) |
| License | Apache 2.0 with express patent grant |
| Production deployments | **Zero** |
| Third-party adoption | **Zero** |
| Independent audit | **None** |
| Formal verification | **None** |

---

## 12. Conclusion

SAL, JSON, Protocol Buffers, and MessagePack encode the same semantic content using different architectural models:

| Format | Model | Key Names | Content | Schema Dependency |
|--------|-------|-----------|---------|-------------------|
| JSON-RPC | Self-describing text | Per-message | Verbatim | None |
| MessagePack | Self-describing binary | Per-message | Verbatim | None |
| Protocol Buffers | Schema-based binary | Externalized | Verbatim | .proto schema |
| SAL | Semantic instruction encoding | Externalized | Opcode-compressed | ASD dictionary |

The benchmark results reported here follow from these architectural differences:

| Dimension | JSON | MessagePack | Protobuf | SAL |
|-----------|------|-------------|----------|-----|
| Byte reduction vs JSON (per-message) | -- | 15.2% | 55.4% | 86.5% |
| Batch (29 msgs, each format best-compressed) | gzip: 2,623B | gzip: 2,698B | gzip: 1,751B | 640B |
| Token reduction vs JSON | -- | not measured | not applicable (binary) | 75.6% |
| Per-vector wins vs protobuf (29 vectors) | -- | -- | 1 | 28 |
| Schema/dictionary dependency | None | None | Compiled schema | ASD + MDR |

SAL's per-message advantage over protobuf (69.8% byte reduction) derives primarily from semantic content compression: opcodes replacing natural language descriptions. This is a vocabulary optimization, not a structural encoding improvement. On numeric-heavy payloads with no natural language content, protobuf outperforms SAL (1 of 29 vectors). On batch transmission, with all formats receiving their best available second-pass compression, compressed SAL (640 bytes) remains 63.4% smaller than compressed protobuf (1,751 bytes) and 75.6% smaller than gzipped JSON (2,623 bytes).

SAL's token reduction (75.6%) is structurally independent of gzip and binary serialization because LLMs consume uncompressed text. This reduction applies wherever agent instructions pass through LLM context windows as text, which includes cloud-to-cloud multi-agent deployments where inter-agent messages are tokenized at each receiving agent.

On constrained channels (LoRaWAN, Meshtastic), SAL produces multi-field instructions within payload floors (11-51 bytes) where JSON-RPC envelopes and protobuf tool calls do not fit.

The protocol exists as open-source software with published code, test vectors, and benchmarks. It has no production deployments and no third-party adoption. The encoding properties measured here are empirically verifiable by any party using the published materials.

---

## Appendix A: Reproduction

All code and data at github.com/octid-io/cloudless-sky/benchmarks/sal-vs-json/:

    python3 benchmark.py              # 29-vector empirical benchmark
    python3 grammar-analysis.py       # 1,000-point structural sweep
    python3 protobuf-comparison.py    # Four-way format comparison

Protocol Buffers schemas: benchmark.proto (compiled with protoc 3.21.12). Two-tier batch compression results in dpack-comparison.json. Dependencies: tiktoken, msgpack, protobuf, grpcio-tools (pip install). Additional dependencies for two-tier analysis are listed in the repository.

---

## Appendix B: References

[1] Shannon, C.E. (1948). "A Mathematical Theory of Communication." Bell System Technical Journal, 27(3), 379-423.

[2] Chomsky, N. (1956). "Three models for the description of language." IRE Transactions on Information Theory, 2(3), 113-124.

[3] Hernandez-Barrera, M. et al. (2025). "Human languages trade off complexity against efficiency." PLOS Complex Systems.

[4] RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format.

[5] JSON-RPC 2.0 Specification. jsonrpc.org.

[6] Model Context Protocol Specification, v2025-11-25. modelcontextprotocol.io.

[7] Agent2Agent Protocol Specification, v0.2.5. a2a-protocol.org.

[8] OpenAI Function Calling Guide. developers.openai.com.

[9] CrewAI Documentation. docs.crewai.com.

[10] Microsoft AutoGen Documentation. microsoft.github.io/autogen.

[11] Van Gassen, E. (2026). "Semantic Compression of LLM Instructions via Symbolic Metalanguages." arXiv:2601.07354.

[12] Xu, H. et al. (2025). "On the Limits of Multi-Agent LLM Systems." ICLR 2025 Workshop. (AgentTaxo: 53-86% token duplication across MetaGPT, CAMEL, AgentVerse.)

[13] Zhang, Z. et al. (2025). "AgentPrune: Compressing Multi-Agent Systems Through Pruning Redundant Communication." ICLR 2025.

[14] Li, X. et al. (2025). "OPTIMA: Optimizing Multi-Agent Communication with Efficiency Training." ACL Findings 2025.

[15] Protocol Buffers Encoding Guide. protobuf.dev/programming-guides/encoding.

[16] LoRa Alliance. LoRaWAN Regional Parameters v1.0.3 (2018).

[17] myDevices. Cayenne Low Power Payload (CayenneLPP). docs.mydevices.com/docs/lorawan/cayenne-lpp.

[18] Semtech. "Packet Size Considerations." lora-developers.semtech.com.

---

*OSMP is patent pending (Application #64/007,684, filed March 17, 2026). This paper describes measurement methodology and competitive analysis applied to the disclosed protocol. The analytical frameworks (Shannon entropy, grammar production comparison, token cost measurement) are measurement tools, not protocol extensions. The benchmark results, format comparisons, and economic projections are analytical work product not present in the patent application. Readers should not treat this paper as a definitive scope statement regarding the patent's disclosure.*
