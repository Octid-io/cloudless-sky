# OSMP Python SDK

Reference implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Structured Agent Language). 342 opcodes across 26 namespaces. Inference-free decode by table lookup.

## Install

The SDK is bundled with the MCP server:

```
pip install osmp-mcp
```

Or import directly from the repo:

```python
import sys
sys.path.insert(0, "sdk/python/src")
from osmp import SALEncoder, SALDecoder, AdaptiveSharedDictionary, validate_composition
```

## Encode

```python
enc = SALEncoder()
sal = enc.encode(namespace="H", opcode="HR", target="NODE1", slots={"threshold": "130"})
# "H:HR@NODE1[130]"
```

## Decode

```python
dec = SALDecoder()
result = dec.decode_frame("H:HR@NODE1[130]")
# result.namespace = "H"
# result.opcode = "HR"
# result.opcode_meaning = "heart_rate"
# result.target = "NODE1"
```

## Validate Composition

Always validate before emitting composed SAL:

```python
from osmp import validate_composition

result = validate_composition("R:MOV@BOT1", nl="Move the robot to BOT1")
print(result.valid)   # False
print(result.errors)  # [CONSEQUENCE_CLASS_OMISSION: R:MOV requires ⚠/↺/⊘]

result = validate_composition("I:§→R:MOV@BOT1⚠", nl="Move the robot to BOT1")
print(result.valid)   # True
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

```python
asd = AdaptiveSharedDictionary()
definition = asd.lookup("R", "WPT")
# "waypoint"
```

## Domain Code Resolution

```python
from osmp import BlockCompressor

bc = BlockCompressor()
bc.load("mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack")
result = bc.resolve("J93.0")
# "Spontaneous tension pneumothorax"
```

Three corpora bundled: ICD-10-CM (74,719 codes), ISO 20022 (47,835 codes), MITRE ATT&CK (1,661 codes).

## Benchmark

```python
from osmp import run_benchmark

report = run_benchmark("protocol/test-vectors/canonical-test-vectors.json")
print(f"Mean reduction: {report.mean_reduction_pct:.1f}%")
print(f"Conformant: {report.conformant}")
```

## License

Apache 2.0. Patent pending (Application #64/007,684).
