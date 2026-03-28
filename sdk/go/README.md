# OSMP Go SDK

Go implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Structured Agent Language). 342 opcodes across 26 namespaces. Inference-free decode by table lookup.

## Install

```
go get github.com/octid-io/cloudless-sky/sdk/go/osmp
```

## Encode

```go
import "github.com/octid-io/cloudless-sky/sdk/go/osmp"

enc := osmp.NewEncoder()
sal := enc.Encode("H", "HR", "NODE1", map[string]string{"threshold": "130"})
// "H:HR@NODE1[130]"
```

## Decode

```go
dec := osmp.NewDecoder(nil)
result, err := dec.DecodeFrame("H:HR@NODE1[130]")
// result.Namespace = "H"
// result.Opcode = "HR"
// result.OpcodeMeaning = "heart_rate"
// result.Target = "NODE1"
```

## Validate Composition

Always validate before emitting composed SAL:

```go
result := osmp.ValidateComposition("R:MOV@BOT1", "Move the robot to BOT1", nil, true)
fmt.Println(result.Valid)   // false
fmt.Println(result.Errors()) // [CONSEQUENCE_CLASS_OMISSION: R:MOV requires ⚠/↺/⊘]

ok := osmp.ValidateComposition("I:§→R:MOV@BOT1⚠", "Move the robot to BOT1", nil, true)
fmt.Println(ok.Valid)       // true
```

Seven rules enforced:

1. **Hallucination check** — every opcode must exist in the ASD
2. **Namespace-as-target** — `@` must not be followed by `NS:OPCODE`
3. **R namespace consequence class** — mandatory except `R:ESTOP`
4. **I:§ precondition** — `⚠` and `⊘` require `I:§` in the chain
5. **Byte check** — SAL bytes must not exceed NL bytes (exception: R safety chains)
6. **Slash rejection** — `/` is not a SAL operator
7. **Mixed-mode check** — no natural language embedded in SAL frames

## Dictionary Lookup

```go
asd := osmp.NewASD()
definition := asd.Lookup("R", "WPT")
// "waypoint"
```

## Domain Code Resolution

```go
bc := osmp.NewBlockCompressor()
err := bc.Load("mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack")
result, err := bc.Resolve("J93.0")
// "Spontaneous tension pneumothorax"
```

Three corpora bundled: ICD-10-CM (74,719 codes), ISO 20022 (47,835 codes), MITRE ATT&CK (1,661 codes).

## Benchmark

```go
report, err := osmp.RunBenchmark("protocol/test-vectors/canonical-test-vectors.json")
fmt.Printf("Mean reduction: %.1f%%\n", report.MeanReductionPct)
fmt.Printf("Conformant: %v\n", report.Conformant)
```

## Test

```
cd sdk/go
go test ./osmp/ -v
```

## License

Apache 2.0. Patent pending (Application #64/007,684).
