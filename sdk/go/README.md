# OSMP Go SDK

Go implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Semantic Assembly Language). 352 opcodes across 26 namespaces. Deterministic decode to structured instructions. No inference. ASD compiled-in; D:PACK/BLK via `klauspost/compress/zstd`.

## Install

```
go get github.com/octid-io/cloudless-sky/sdk/go/osmp
```

## Tier 1: Package-Level Functions, Zero Setup

```go
import "github.com/octid-io/cloudless-sky/sdk/go/osmp"

sal := osmp.Encode([]string{"H:HR@NODE1>120", "H:CASREP", "M:EVA@*"})
// "H:HR@NODE1>120;H:CASREP;M:EVA@*"

text := osmp.Decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
// "H:heart_rate →NODE1 >120; H:casualty_report; M:evacuation →*"
```

No constructors. Singleton ASD initialized on first call via `sync.Once`. Thread-safe.

### Additional Tier 1 Functions

```go
result := osmp.Validate("R:MOV@BOT1⚠")
fmt.Println(result.Valid)   // false -- ⚠ requires I:§ precondition

definition := osmp.Lookup("R:WPT")
// "waypoint"

fmt.Println(osmp.ByteSize("H:HR@NODE1>120"))
// 15
```

## Tier 2: Struct-Based Interface

For explicit ASD control, custom dependency rules, or concurrent instances with different configurations:

```go
asd := osmp.NewASD()
enc := osmp.NewEncoder(asd)
dec := osmp.NewDecoder(asd)

sal := enc.EncodeSequence([]string{"H:HR@NODE1>120", "H:CASREP"})
result, err := dec.DecodeFrame("H:HR@NODE1>120")
// result.Namespace = "H"
// result.Opcode = "HR"
// result.OpcodeMeaning = "heart_rate"
// result.Target = "NODE1"
```

## Composition Validation

Eight deterministic rules enforced before any instruction hits the wire:

1. **Hallucination check** -- every opcode must exist in the ASD
2. **Namespace-as-target** -- `@` must not be followed by `NS:OPCODE`
3. **R namespace consequence class** -- mandatory except `R:ESTOP`
4. **I:§ precondition** -- ⚠ and ⊘ require `I:§` in the chain
5. **Byte check** -- SAL bytes must not exceed NL bytes (exception: R safety chains)
6. **Slash rejection** -- `/` is not a SAL operator
7. **Mixed-mode check** -- no natural language embedded in SAL frames
8. **Regulatory dependency** -- REQUIRES rules from loaded MDR corpora

## Domain Code Resolution

```go
bc := osmp.NewBlockCompressor()
err := bc.Load("mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack")
result, err := bc.Resolve("J93.0")
// "Spontaneous tension pneumothorax"
```

Three corpora bundled: ICD-10-CM (74,719 codes), ISO 20022 (47,835 codes), MITRE ATT&CK (1,661 codes).

## EML — Universal Binary Operator Evaluator

A companion math-evaluation subpackage. Based on Odrzywołek (2026, [arXiv:2603.21852](https://arxiv.org/abs/2603.21852)): a single binary operator `eml(x, y) = exp(x) − ln(y)`, together with the constant 1, generates the standard calculator function basis — exp, ln, sin, cos, sqrt, arithmetic, and more — as compact expression trees.

Byte-exact evaluation across Python, Go, and TypeScript on every IEEE-754-conformant platform. Full sin(x) or sqrt(x) approximation fits in fewer than 100 bytes on the wire.

```go
import "github.com/octid-io/cloudless-sky/sdk/go/osmp/eml"

// The operator itself
eml.Eml(2.0, 1.0)  // exp(2) - ln(1) = 7.389056...

// Build an expression tree: exp(x) = eml(x, 1)
tree := eml.Branch(eml.VarX(), eml.Leaf(1.0))
tree.Evaluate(2.0)  // 7.389056...
```

### Pre-Built Corpus

Sixteen single-variable base functions and four multi-variable arithmetic compounds ship pre-verified:

```go
import (
    "math"
    "github.com/octid-io/cloudless-sky/sdk/go/osmp/eml"
)

// Base corpus (single variable x)
chain, _ := eml.GetBaseChain("ln(x)")
chain.Evaluate([]float64{math.E})    // 1.0
chain.Evaluate([]float64{math.E * math.E})  // 2.0

// Arithmetic compounds (multi-variable)
eml.CompoundXPlusY().Evaluate([]float64{2.0, 3.0})              // 5.0
eml.CompoundXTimesY().Evaluate([]float64{2.0, 3.0})             // 6.0
eml.CompoundLinearCalibration().Evaluate([]float64{2.0, 3.0, 1.0}) // 7.0
```

Available base names: `exp(x)`, `ln(x)`, `identity`, `zero`, `exp(x)-ln(x)`, `exp(x)-x`, `e-x`, `exp(exp(x))`, `e-exp(x)`, `1-ln(x)`, `e/x`, `exp(x)-1`, `exp(x)-e`, `e^e/x`, `ln(ln(x))`, `exp(exp(exp(x)))`.

### Wire Format

Three wire encodings ship:

```go
// Paper tree form: pre-order tagged traversal, 4-byte float32 or 8-byte float64 leaves
tree := eml.Branch(eml.Leaf(1.0), eml.Branch(eml.Branch(eml.Leaf(1.0), eml.VarX()), eml.Leaf(1.0))) // ln(x)
wire := eml.EncodeTree(tree, false)        // bytes
decoded, _ := eml.DecodeTree(wire)
decoded.Evaluate(math.E)  // 1.0

// Restricted chain form (bit-packed, single variable)
chain, _ := eml.GetBaseChain("ln(x)")
wire, _ = eml.EncodeChainRestricted(chain, true)   // self-describing, 2 bytes
decoded2, _ := eml.DecodeChainRestricted(wire, true, 0, "x")
decoded2.Evaluate([]float64{math.E})  // 1.0
```

A wide multi-variable form (`EncodeChainWide` / `DecodeChainWide`) handles compounds with up to 15 variables and 15 levels in a single-byte header.

### Cross-Device Determinism

```go
fp, _ := eml.CorpusFingerprint()
// e9a4a71383f14624472fe0602ca5e0ff1959e00b09725a62d584e1361f842c1b
```

Identical fingerprint across Python, Go, and TypeScript on every IEEE-754-conformant platform.

### Precision Modes

Two modes toggled via `SetPrecisionMode`:

- **`eml.Fast`** (default) — fdlibm-derived, 1-ULP accurate, ships publicly.
- **`eml.Precision`** — crlibm-derived, correctly-rounded, audit-grade. For regulated industries (medical IEC 62304, aerospace DO-178C, nuclear IEC 61513), audit-grade finance, and cryptographic protocol-frame hash inputs. **Available under commercial license** — contact `licensing@octid.io` or see [PATENTS.md](../../PATENT-NOTICE.md).

```go
if err := eml.SetPrecisionMode(eml.Precision); err != nil {
    // err == eml.ErrPrecisionPackNotInstalled
    fmt.Println(err)
    // "precision mode requires the commercial precision pack;
    //  contact licensing@octid.io or see PATENTS.md"
}
```

## Test

```
cd sdk/go
go test ./osmp/ -v
```

## License

Apache 2.0. Patent pending.

## SALBridge: Mixed Environment Integration

```go
b := osmp.NewSALBridge("MY_NODE")
b.RegisterPeer("GPT_AGENT", false)

// Outbound: SAL decoded to annotated NL
out := b.Send("H:HR@NODE1>120", "GPT_AGENT")

// Inbound: scanned for SAL acquisition
result := b.Receive("A:ACK", "GPT_AGENT")

// Metrics
metrics := b.GetMetrics("GPT_AGENT")
```
