# OSMP Rust SDK

Rust implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, composes, and validates agentic AI instructions using SAL (Semantic Assembly Language). 356 opcodes across 26 namespaces (v15.1) with the v16 namespace expansion (3-character primaries with v15 single-letter siblings) bundled in. Deterministic decode to structured instructions. No inference. Cross-SDK byte-identical with the Python, TypeScript, and Go SDKs.

## Status

**Pre-1.0** (`0.3.0`). Full wire-format parity with Python / TypeScript / Go: core encode/decode, ASD dictionary, v16 namespace mapping, SAL grammar, validator, macro registry, SALBridge, **FNP packet codec (40-byte ADV / 38-byte ACK with ADR-004 basis-manifest extended-form)**, overflow protocol (Tier 1/2/3 DAG), BAEL bridge-layer mode selector, D:PACK encode/decode, the EML universal-binary-operator math layer, the **89-macro EML MDR registry**, and the **unified wire codec** (`SAILCodec` binary + `SecCodec` ChaCha20-Poly1305 + Ed25519 envelope + `OSMPWireCodec` mode router across {Mnemonic, SAIL, SEC, SAILSEC}) all ship at parity. The remaining MDR domain-corpus resolve (ICD-10-CM / ISO 20022 / MITRE ATT&CK D:PACK/BLK lookup) and the full benchmark harness follow at `0.4.0`.

The SHA-256 ASD fingerprint is byte-identical with the other three SDKs: `9ecc507e2c24c4a7`. The `fingerprint_cross_sdk_identical` test in CI fails the build if Rust ever diverges.

## Install

```toml
[dependencies]
osmp = "0.3"
```

MSRV: Rust 1.70 (uses `std::sync::OnceLock`, stabilized in 1.70). Runtime crypto deps for the SEC envelope (`chacha20poly1305`, `ed25519-dalek`, `rand`) are pulled in transitively when the wire layer is constructed; the SAL text encoder/decoder requires only `sha2`, `serde`, `serde_json`, and `regex`.

## Quick Start

```rust
use osmp::AdaptiveSharedDictionary;

let asd = AdaptiveSharedDictionary::new();

// Lookup an opcode definition
let definition = asd.lookup("H", "HR"); // Some("heart_rate")

// Cross-SDK fingerprint
let fp = asd.fingerprint();
assert_eq!(fp, "9ecc507e2c24c4a7");
```

## Decode

```rust
use osmp::Decoder;

let dec = Decoder::new(None);
let result = dec.decode_frame("H:HR@NODE1>120").expect("valid SAL");

assert_eq!(result.namespace, "H");
assert_eq!(result.opcode, "HR");
assert_eq!(result.opcode_meaning.as_deref(), Some("heart_rate"));
assert_eq!(result.target.as_deref(), Some("NODE1>120"));
```

## Encode

```rust
use osmp::Encoder;

let enc = Encoder::new(None);
let sal = enc.encode_sequence(&["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"]);
// "H:HR@NODE1>120;H:CASREP;M:EVA@*"
```

## Validate

Eight deterministic rules enforced before any instruction hits the wire:

```rust
use osmp::{validate_composition, Severity};

let result = validate_composition("R:MOV@BOT1⚠", "", None, true, None);
assert!(!result.valid()); // ⚠ requires I:§ precondition
for issue in result.errors() {
    println!("{:?}: {}", issue.rule, issue.message);
}
```

The eight rules are: hallucinated opcode, namespace-as-target, R-namespace consequence class, I:§ precondition for ⚠/⊘, BAEL byte floor, slash rejection, mixed-mode, and regulatory dependency (REQUIRES rules from loaded MDR corpora).

## v16 Namespace Mapping

The v16 namespace expansion makes 3-character primaries the canonical form (e.g. `AGT` for agentic instead of `A`) while preserving v15 single-letter forms as deprecated siblings. The split letters C/D/K/Q resolve via the bridge composer disambiguation table (e.g. `C:ALLOC` → `CMP`, `C:QUOTA` → `RES`, `D:STAT` → `XFR`).

```rust
use osmp::disambiguate_to_v16;

assert_eq!(disambiguate_to_v16("A", "ACK"), Some("AGT"));
assert_eq!(disambiguate_to_v16("C", "ALLOC"), Some("CMP"));
assert_eq!(disambiguate_to_v16("D", "STAT"), Some("XFR"));
assert_eq!(disambiguate_to_v16("Q", "FLAG"), Some("QLT")); // default-to-QLT
assert_eq!(disambiguate_to_v16("AGT", "ACK"), Some("AGT")); // pass-through
```

## SALBridge — Propagation by Contact

When your agents communicate with non-OSMP peers, the bridge handles boundary translation. Outbound SAL is decoded to annotated natural language; inbound messages are scanned for SAL acquisition. Peers that learn SAL through contextual exposure transition from FALLBACK to ACQUIRED. **OSMP spreads by contact, not installation.**

```rust
use osmp::SALBridge;

let mut bridge = SALBridge::new("MY_NODE", None, true);
bridge.register_peer("GPT_AGENT", false);

// Outbound: SAL decoded to NL, annotated with SAL equivalent
let out = bridge.send("H:HR@NODE1>120", "GPT_AGENT");

// Inbound: scanned for SAL acquisition
let result = bridge.receive("A:ACK", "GPT_AGENT");
```

## EML — Universal Binary Operator Evaluator

A companion math-evaluation submodule. Based on Odrzywołek (2026, [arXiv:2603.21852](https://arxiv.org/abs/2603.21852)): a single binary operator `eml(x, y) = exp(x) − ln(y)`, together with the constant 1, generates the standard calculator function basis as compact expression trees.

Byte-exact evaluation across Python, TypeScript, Go, and Rust on every IEEE-754-conformant platform.

```rust
use osmp::{eml, eml_macro_count, eml_mdr_lookup};

// The operator itself
let v = eml(2.0, 1.0); // exp(2) - ln(1) = 7.389056...

// 89-macro registry (cross-SDK byte-identical with Python / TS / Go)
assert_eq!(eml_macro_count(), 89);

// Look up a macro by 3-character shorthand ID
if let Some(m) = eml_mdr_lookup("EXP") {
    println!("{} ({:?}): {}", m.shorthand_id, m.function_class, m.description);
}
```

### Precision Modes

Two modes:

- **Fast** (default) — fdlibm-derived, 1-ULP accurate, ships publicly. Correct for LoRa/BLE/edge-ML, drone swarm coordination, and general scientific computation.
- **Precision** — crlibm-derived, correctly-rounded, audit-grade. For regulated industries (medical IEC 62304, aerospace DO-178C, nuclear IEC 61513), audit-grade finance, and cryptographic protocol-frame hash inputs. **Available under commercial license** — contact `ack@octid.io`.

```rust
use osmp::eml::{eml_precise, EmlError};

match eml_precise(2.0, 1.0) {
    Ok(v) => println!("precision result: {v}"),
    Err(EmlError::PrecisionUnavailable) => {
        println!("precision mode requires the commercial precision pack");
    }
}
```

## Wire Codec — Four Modes

Four wire modes selectable per message via `WireMode`:

| Mode | Byte | Description |
|---|---|---|
| `Mnemonic` | `0x00` | UTF-8 SAL text (human-readable) |
| `SAIL` | `0x01` | Binary SAIL (single-byte tokens + intern table) |
| `SEC` | `0x02` | SAL text + ChaCha20-Poly1305 + Ed25519 envelope |
| `SAILSEC` | `0x03` | Binary SAIL + ChaCha20-Poly1305 + Ed25519 envelope |

`OSMPWireCodec` routes per-mode encode and decode. Cross-SDK byte-identical with Python `wire.py`, Go `wire.go`, and TypeScript `osmp_wire.ts`.

```rust
use osmp::{OSMPWireCodec, WireMode};

// Loopback codec — fresh keys generated; pass Some(&seed)/Some(&key) for fixed identity.
let mut codec = OSMPWireCodec::new(&[0x00, 0x01], None, None).expect("construct");

// Mnemonic — pass-through UTF-8.
let m = codec.encode("H:HR@NODE1", WireMode::Mnemonic).unwrap();

// SAIL — binary SAL, one-byte tokens + intern table built from the v15 ASD basis.
let s = codec.encode("H:HR@NODE1\u{2192}H:CASREP", WireMode::SAIL).unwrap();
let back = codec.decode(&s, WireMode::SAIL).unwrap();
assert_eq!(back, "H:HR@NODE1\u{2192}H:CASREP");

// SEC — 87 bytes overhead for 2-byte node_id (89 for 4-byte).
let envelope = codec.encode("H:HR@NODE1", WireMode::SEC).unwrap();
let plain = codec.decode(&envelope, WireMode::SEC).unwrap();

// SAILSEC — binary + envelope; minimal wire form for HAZARDOUS payloads.
let sec_sail = codec.encode("R:MOV@BOT1\u{26A0}", WireMode::SAILSEC).unwrap();
```

The SEC envelope derives its 12-byte ChaCha20-Poly1305 nonce from the envelope header padded with the canonical salt `b"OSMP-SEC-v1\x00"` (byte-identical across all four SDKs). Ed25519 signs `header || ciphertext || auth_tag`.

## FNP — Frame Negotiation Protocol

Two-message handshake completing in 78 bytes total (40-byte ADV + 38-byte ACK), designed for the LoRa SF12 51-byte payload floor. ADR-004 extended-form ADV (msg_type `0x81`) carries an 8-byte basis fingerprint at offset 32 for `EstablishedSAIL` capability grading.

```rust
use osmp::{AdaptiveSharedDictionary, FNPSession, FNPState, FNP_CAP_FLOOR};

let asd = AdaptiveSharedDictionary::new();
let mut a = FNPSession::new_with_version(&asd, "NODE_A", 1, FNP_CAP_FLOOR);
let mut b = FNPSession::new_with_version(&asd, "NODE_B", 1, FNP_CAP_FLOOR);

let adv = a.initiate().expect("A initiates");           // 40 bytes
let ack = b.receive(&adv).unwrap().expect("B replies"); // 38 bytes
assert_eq!(b.state, FNPState::EstablishedSAIL);

a.receive(&ack).unwrap();
assert_eq!(a.state, FNPState::EstablishedSAIL);
```

ADR-004 basis-manifest mode is enabled by passing `FNPSessionOptions { basis_fingerprint: Some(vec![..; 8]), .. }` to `FNPSession::new_with_options`.

## Test

```
cd sdk/rust
cargo test
cargo clippy --all-targets -- -D warnings
```

The cross-SDK fingerprint test is the runtime gate for byte-identical compatibility with Python, TypeScript, and Go.

## License

Apache 2.0.
