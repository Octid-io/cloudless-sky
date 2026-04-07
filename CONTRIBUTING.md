# Contributing to Cloudless Sky / OSMP

Thank you for your interest in contributing to OSMP. This document explains how contributions work, what we are looking for, and how to get a contribution accepted.

---

## The Spec Is Authoritative

The protocol specification at `protocol/spec/OSMP-SPEC-v1.0.2.md` is the source of truth. The formal grammar at `protocol/grammar/SAL-grammar.ebnf` is the canonical SAL definition. The test vectors at `protocol/test-vectors/canonical-test-vectors.json` define what "correct" means.

If there is a conflict between an SDK implementation and the spec, the spec wins. If there is a conflict between the spec and intuition, open an issue — do not resolve it by changing the implementation.

If you are building a new SDK or parser implementation, the EBNF grammar file is the complete and sufficient specification for SAL syntax. You do not need to read the prose spec to implement a conformant parser — the grammar file is machine-readable and can be used directly with standard EBNF parser generators.

---

## SDK Status

The following SDKs are shipped and conformant against the 55-vector canonical test suite:

| SDK | Package | Conformance | Notes |
|---|---|---|---|
| **Python** | `pip install osmp-protocol` | CONFORMANT ✓ 60.8% | Reference implementation. Single source of truth for all SDK behavior. |
| **TypeScript** | `npm install osmp-protocol` | CONFORMANT ✓ 60.8% | OpenClaw / web agent integrations. |
| **Go** | `github.com/octid-io/cloudless-sky/sdk/go` | CONFORMANT ✓ 60.8% | PicoClaw / constrained hardware. ASD compiled-in; no filesystem or network dependency. |

---

## Meshtastic Integration

OSMP integration with Meshtastic operates at two levels. Understanding the distinction determines which language you need.

### Companion Device Integration (Python -- operational today)

A companion device (phone, laptop, Raspberry Pi, server) runs the OSMP Python SDK and connects to a Meshtastic radio over serial, TCP, or BLE using the Meshtastic Python library (`pip install meshtastic`). The companion device encodes OSMP instructions, sends them through `interface.sendText()` or `interface.sendData()`, and decodes received payloads on arrival. The Meshtastic radio is a dumb transport. OSMP handles the payload. Meshtastic handles the RF and mesh routing. No new code required.

```python
import meshtastic, meshtastic.serial_interface
from osmp import SALEncoder, SALDecoder

interface = meshtastic.serial_interface.SerialInterface()
encoded = "H:HR@NODE1>120→H:CASREP∧M:EVA@*"
interface.sendText(encoded)  # Meshtastic carries the OSMP payload
```

This path works today with existing SDKs and existing Meshtastic hardware.

### Firmware-Level Sovereign Node (C++ -- contribution target)

A Meshtastic device (ESP32 or nRF52) running OSMP encode/decode natively in firmware, operating as a sovereign OSMP node without a companion device. The microcontroller maintains its own ASD, encodes and decodes SAL instructions on-chip, and participates in the mesh as an autonomous agent node.

This is a different and more advanced deployment scenario. It requires a C++ OSMP encoder/decoder that compiles for ESP32 and nRF52 targets, with the ASD basis compiled into flash. The C++ implementation does not modify Meshtastic firmware; it produces payloads compatible with the Meshtastic SDK message API.

**Target:** Meshtastic module API compatible. ESP32 and nRF52 compatible. ASD compiled into flash as a constant table.

---

## D:PACK Corpus Compression

D:PACK is the two-tier corpus compression system. The first tier applies SAL encoding to domain text. The second tier applies lossless dictionary-based compression to the SAL output. Two profiles exist:

**D:PACK/LZMA** -- Full-corpus decompression at node startup. Requires multi-MB SRAM. Suitable for companion devices (phones, laptops, servers). Legacy profile.

**D:PACK/BLK** -- Block-level random access using zstd, dict-free. Resolves a single code by decompressing one ~32KB block. Peak SRAM: ~38KB. Suitable for ESP32-class microcontrollers. Active profile. Dict-free format is universal across all three SDKs (Python, TypeScript, Go).

Both profiles produce binaries stored in `mdr/` subdirectories.

### MDR Directory Structure

```
mdr/
  icd10cm/
    MDR-ICD10CM-FY2026-blk.dpack      BLK profile (74,719 codes, 477KB)
  iso20022/
    MDR-ISO20022-DEFINITIONS-FULL.csv  Source: ISO 20022 eRepository extraction
    MDR-ISO20022-MSG-FULL.csv          Source: message type catalog
    MDR-ISO20022-K-ISO-blk.dpack       BLK profile (47,835 unique definitions, 1.2MB)
  mitre-attack/
    MDR-MITRE-ATTACK-ENT-v18.1-blk.dpack  BLK profile (1,661 entries, 20KB)
```

### DBLK Binary Format (v1)

The BLK profile uses the following binary layout. Implementations that read DBLK files must handle this format exactly.

Header (24 bytes): magic "DBLK" (4) + version u16 BE (2) + flags u16 BE (2, bit 0 = has trained dictionary) + block count u32 BE (4) + dictionary offset u32 BE (4) + dictionary size u32 BE (4) + blocks offset u32 BE (4).

Block table (block_count * 44 bytes): first code (32 bytes, null-padded UTF-8) + block offset u32 BE (4, relative to blocks section) + compressed size u32 BE (4) + entry count u16 BE (2) + reserved (2).

Dictionary section (optional, supported by format but not used in shipped binaries; dict-free is the universal format).

Block data section (concatenated zstd-compressed blocks).

Each decompressed block contains sorted lines: `KEY\tVALUE\n`. Resolution path: binary search block table by first_code, decompress one block, linear scan for target key. When the first_code field truncates a long key (>32 bytes), the binary search may overshoot by one block; implementations must check the previous block as a fallback.

### SDK D:PACK Status

| SDK | Pack (write) | Resolve (read) | Class |
|---|---|---|---|
| **Python** | Yes | Yes | `BlockCompressor` in `osmp.py` |
| **TypeScript** | No | Contribution target | -- |
| **Go** | No | Contribution target | -- |

Pack (building DBLK binaries from source CSVs) is Python-only. Resolve (reading a single code from a DBLK binary) is the useful operation for deployed nodes and should be implemented in all SDKs. The Python `BlockCompressor` class is the reference implementation.

### D:PACK/BLK Verified Numbers

All numbers measured from source artifacts with zero round-trip errors:

| Corpus | Entries | Raw | BLK Binary | Reduction |
|---|---|---|---|---|
| ICD-10-CM (H:ICD) | 74,719 | 5.4 MB | 477 KB | 91.4% |
| ISO 20022 (K:ISO) | 47,835 | 8.7 MB | 1,207 KB | 86.5% |
| MITRE ATT&CK Enterprise (S:ATT) | 1,661 | 82 KB | 20 KB | 75.3% |

---

## What We Need Most

### D:PACK/BLK Resolve for TypeScript and Go -- shipped

Read-only DBLK binary resolution is implemented and verified across all 124,215 codes (74,719 ICD-10-CM + 47,835 ISO 20022 + 1,661 MITRE ATT&CK) in all three SDKs. TypeScript uses `fzstd` (82KB, pure JS, zero native deps). Go uses `github.com/klauspost/compress/zstd` (decode-only, 3.1MB compiled binary). Dict-free binaries only in the TypeScript path; Go supports both. Pack (write) stays Python-only. Tier 1 unit tests: `tests/tier1/test_dpack.ts` and `tests/tier1/dpack_test.go` (14 hardcoded codes).

### C++ Firmware-Level Encoder/Decoder -- highest priority

See Meshtastic Integration above. The companion device path is operational. The firmware-level sovereign node path requires a C++ SDK.

### Kotlin (Android) and Swift (iOS) -- second priority

Mobile SDK implementations enabling phones to function as sovereign OSMP nodes. Relevant for both the Meshtastic mobile apps and standalone OSMP mesh participation.

### Tier 3 DAG Fragmentation -- shipped (Python, TypeScript, Go)

Overflow Protocol Tier 3: DAG decomposition for instructions with conditional branches and dependency chains. Spec-defined (§8.1) and patent-covered. All three SDKs implement DAGFragmenter and DAGReassembler. DAGFragmenter decomposes compound SAL into a directed acyclic graph, assigns DEP pointers (self-reference for roots, direct pointer for single-parent, FLAGS bit 3 extended bitmap for multi-parent). DAGReassembler resolves execution order via topological sort under all three loss tolerance policies. R:ESTOP hard exception fires immediately regardless of DAG state. Python: 45 tests. TypeScript: 52 assertions. Go: 12 tests. Fragment header format is byte-identical across all three SDKs.

### FNP Handshake State Machine -- shipped

Two-message capability advertisement + acknowledgment (40B ADV + 38B ACK = 78 bytes). Negotiates dictionary alignment, namespace intersection, and channel capacity. Implemented in all three SDKs (Python, TypeScript, Go) with byte-identical wire format verified against Python reference packets. See spec section 9 for wire format and state machine.

---

## Contribution Process

1. Fork the repository
2. Build your implementation against the spec
3. Run the canonical test vectors: your implementation must achieve ≥60% mean UTF-8 byte reduction with zero decode errors
4. Add an Architecture Decision Record to `docs/adr/` explaining any non-obvious implementation decisions and the analog from existing systems you used to resolve them
5. Open a pull request with benchmark output included in the PR description

---

## Architecture Decision Records

Every non-obvious implementation decision should have an ADR. The format is simple:

```
# ADR-XXX: [Decision Title]

## Context
What problem were you solving?

## Decision
What did you decide?

## Analog
What existing solved problem did you draw from? Link to the reference implementation.

## Consequences
What does this decision make easier or harder?
```

This is not bureaucracy. It is the thing that makes a protocol engineer trust the implementation when they read it.

---

## Conformance Test

Every SDK must include a conformance runner. The Python reference shows the exact format. A conformant implementation prints:

```
CONFORMANT ✓  (mean XX.X% vs 60.0% threshold)
```

Pull requests that do not include conformance output will not be merged.

---

## Edge Cases Worth Getting Right

These are the implementation nuances documented during the design of the Python reference. Each has an analog from production systems noted.

**DAG dependency resolution under partial fragment receipt**  
Analog: QUIC stream receive buffer (RFC 9000 §2.2). Execute maximal resolvable subset. Buffer unresolvable fragments. Do not fail on partial receipt under Graceful Degradation policy.

**Dictionary delta additive vs replace under partial sync**  
Analog: CRDT primitives (Shapiro et al., INRIA-00555588). ADDITIVE = grow-only set. REPLACE = last-write-wins register with mandatory criticality flag. DEPRECATE = tombstone record. REPLACE operations must use FLAGS[C] — retransmit on loss, never graceful degrade.

**FNP handshake completion within 78 bytes (40B ADV + 38B ACK)**  
Analog: CoAP option encoding (RFC 7252 §3.1). Two messages, fixed field positions, no dynamic allocation. Capability advertisement and acknowledgment each fit within LoRa floor MTU. Implemented in all three SDKs.

**Guaranteed minimum vocabulary floor under extended off-grid operation**  
Analog: Nix derivation pinning. The floor version is compiled in. It does not depend on filesystem state, network state, or synchronization state. Every glyph in the floor version resolves correctly at any time.

**R:ESTOP execution regardless of fragment completeness**  
This is intentional. If a fragment payload contains R:ESTOP, execute immediately. Do not check policy. Do not wait for complete receipt. Asymmetric harm: unnecessary stop is recoverable, failure to stop a physical agent in emergency is not. This is not a bug to fix.

**Multi-byte glyph byte counting**  
UTF-8 byte counts for glyphs vary. Do not assume one character = one byte.  
3-byte glyphs: ∧ ∨ → ↔ ∀ ∃ ∥ ⚠ ↺ ⊘ ⊤ ⊥ ⌂ ⊗ ∈ ∖ ⟳ ≠ ⊕  
2-byte glyphs: § τ Δ ¬ Φ Γ Λ  
Note: ¬ (U+00AC NOT SIGN) is 2 UTF-8 bytes (0xC2 0xAC). Earlier versions of this document incorrectly listed it as 3-byte.
1-byte glyphs: @ > ~ * : ; ? +  
Use `Buffer.byteLength(str, 'utf8')` in TypeScript, `len(str.encode('utf-8'))` in Python.

**D:PACK/BLK block table binary search truncation fallback**  
The block table first_code field is 32 bytes. Keys longer than 32 bytes are truncated in the block table. When two adjacent blocks share a 32-byte prefix (common in ISO 20022 with long type names like `AcceptorCompletionAdviceResponse`), the binary search may land one block too far. If the target key is not found in the candidate block, check the previous block before returning not-found. The Python reference implements this in `BlockCompressor.resolve()`.

---

## What We Will Not Merge

- Implementations that change the wire format of any existing conformant instruction
- Implementations that add inference at the decode layer
- Implementations that require central server connectivity for basic encode/decode
- Implementations that fail the canonical test vector suite
- R namespace implementations that remove the consequence class requirement
- Any modification to the guaranteed minimum vocabulary floor that reduces the set of guaranteed opcodes

---

## Questions

Open a GitHub issue. Tag it with the appropriate SDK label.
