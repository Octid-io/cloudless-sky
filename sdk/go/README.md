# OSMP Go SDK

Go implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Semantic Assembly Language). 342 opcodes across 26 namespaces. Inference-free decode by table lookup. ASD compiled-in; D:PACK/BLK via `klauspost/compress/zstd`.

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

## Test

```
cd sdk/go
go test ./osmp/ -v
```

## License

Apache 2.0. Patent pending. Filed March 17, 2026.

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
