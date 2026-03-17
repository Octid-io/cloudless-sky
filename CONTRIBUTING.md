# Contributing to Cloudless Sky / OSMP

Thank you for your interest in contributing to OSMP. This document explains how contributions work, what we are looking for, and how to get a contribution accepted.

---

## The Spec Is Authoritative

The protocol specification at `protocol/spec/OSMP-SPEC-v1.md` is the source of truth. The formal grammar at `protocol/grammar/SAL-grammar.ebnf` is the canonical SAL definition. The test vectors at `protocol/test-vectors/canonical-test-vectors.json` define what "correct" means.

If there is a conflict between an SDK implementation and the spec, the spec wins. If there is a conflict between the spec and intuition, open an issue — do not resolve it by changing the implementation.

---

## What We Need Most

### TypeScript SDK — highest priority

An OSMP TypeScript SDK for OpenClaw and web integrations.

**Target package:** `osmp-protocol` on npm  
**Reference:** The Python SDK at `sdk/python/src/osmp.py` is the complete reference implementation. All behavior is specified there. The TypeScript SDK should expose the same API surface in idiomatic TypeScript.

**What to build:**
- `OSMPEncoder` class with `encodeFrame()`, `encodeCompound()`, `encodeParallel()`, `encodeSequence()`
- `OSMPDecoder` class with `decodeFrame()` returning a typed `DecodedInstruction` object
- `AdaptiveSharedDictionary` class with `lookup()`, `applyDelta()`, `fingerprint()`
- `OverflowProtocol` class with `fragment()` and `receive()`
- Benchmark runner that executes against the canonical test vectors and reports conformance

**Conformance requirement:** Mean UTF-8 byte reduction ≥60% across all test vectors, zero decode errors.

**How to measure:** `Buffer.byteLength(str, 'utf8')` — same measurement basis as Python `len(s.encode('utf-8'))`.

### Go SDK — second priority

An OSMP Go SDK for PicoClaw and constrained hardware deployments.

**Target module:** `github.com/octid-io/cloudless-sky/sdk/go`  
**Key constraint:** The Go implementation should produce a self-contained binary with minimal external dependencies. The ASD basis set should be embeddable as a compiled-in constant, not a runtime file load, for constrained hardware targets.

### C++ Meshtastic Integration — third priority

Not firmware. An OSMP encoder/decoder that produces payloads compatible with the Meshtastic SDK message API. The Meshtastic transport layer is unchanged — OSMP encodes the payload that Meshtastic carries.

**Target:** Meshtastic module API compatible. ESP32 and nRF52 compatible.

### Kotlin (Android) and Swift (iOS) — community contribution

Mobile SDK implementations for the Meshtastic Android and iOS apps.

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
3-byte glyphs: ∧ ∨ → ↔ ∀ ∃ ∥ ⚠ ↺ ⊘ ⊤ ⊥ ⌂ ⊗ ∈ ∖  
2-byte glyphs: § τ Δ ¬  
Note: ¬ (U+00AC NOT SIGN) is 2 UTF-8 bytes (0xC2 0xAC). Earlier versions of this document incorrectly listed it as 3-byte.
2-byte glyphs: § τ Δ  
1-byte glyphs: @ > ~ * : ; ?  
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
