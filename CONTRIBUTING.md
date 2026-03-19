# Contributing to Cloudless Sky / OSMP

Thank you for your interest in contributing to OSMP. This document explains how contributions work, what we are looking for, and how to get a contribution accepted.

---

## The Spec Is Authoritative

The protocol specification at `protocol/spec/OSMP-SPEC-v1.md` is the source of truth. The formal grammar at `protocol/grammar/SAL-grammar.ebnf` is the canonical SAL definition. The test vectors at `protocol/test-vectors/canonical-test-vectors.json` define what "correct" means.

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

## What We Need Most

### C++ Firmware-Level Encoder/Decoder -- highest priority

See Meshtastic Integration above. The companion device path is operational. The firmware-level sovereign node path requires a C++ SDK.

### Kotlin (Android) and Swift (iOS) -- second priority

Mobile SDK implementations enabling phones to function as sovereign OSMP nodes. Relevant for both the Meshtastic mobile apps and standalone OSMP mesh participation.

### Tier 3 DAG Fragmentation -- contribution target

Overflow Protocol Tier 3: DAG decomposition for instructions with conditional branches and dependency chains. Spec-defined (§8.1) and patent-covered. The Python reference implements Tier 1 and Tier 2; Tier 3 is architecturally specified but not yet implemented.

### FNP Handshake State Machine -- contribution target

The two-message capability advertisement + acknowledgment protocol (40 bytes each, within LoRa MTU). FNP fingerprint computation (SHA-256) is implemented in all three SDKs; the handshake state machine managing the negotiation lifecycle is a contribution target.

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

**FNP handshake completion within 80-byte total budget**  
Analog: CoAP option encoding (RFC 7252 §3.1). Two messages, fixed field positions, no dynamic allocation. Capability advertisement and acknowledgment must each fit within available channel MTU.

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
