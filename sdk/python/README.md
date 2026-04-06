# OSMP Python SDK

Reference implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Semantic Assembly Language). 342 opcodes across 26 namespaces. Inference-free decode by table lookup.

## Install

```
pip install osmp
```

Zero dependencies beyond Python standard library (optional `zstandard` for D:PACK).

## Tier 1: Two Functions, Zero Setup

```python
from osmp import encode, decode

sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
# "H:HR@NODE1>120;H:CASREP;M:EVA@*"

text = decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
# "heart_rate at NODE1 priority 120; casualty_report; evacuation at broadcast"
```

Three lines. No instantiation. Module-level singleton, cached on first call.

### Additional Tier 1 Functions

```python
from osmp import validate, lookup, byte_size

result = validate("R:MOV@BOT1⚠")
print(result.valid)    # False -- ⚠ requires I:§ precondition

definition = lookup("R:WPT")
# "waypoint"

print(byte_size("H:HR@NODE1>120"))
# 15
```

## Tier 2: Class-Based Interface

For configuration beyond defaults (custom ASD floor, pre-loaded dependency rules, direct ASD access):

```python
from osmp.core import OSMP

o = OSMP()
sal = o.encode(["H:HR@NODE1>120", "H:CASREP"])
text = o.decode(sal)
result = o.validate(sal)
definition = o.lookup("H", "HR")
```

## Tier 3: Full Protocol Access

Direct access to encoder, decoder, ASD, and all protocol internals:

```python
from osmp.protocol import SALEncoder, SALDecoder, AdaptiveSharedDictionary, validate_composition

asd = AdaptiveSharedDictionary()
enc = SALEncoder(asd)
dec = SALDecoder(asd)

sal = enc.encode_frame("R", "MOV", target="BOT1", cc="↺")
result = dec.decode_frame(sal)
# result.namespace = "R"
# result.opcode = "MOV"
# result.opcode_meaning = "move"
# result.consequence_class_name = "REVERSIBLE"
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

```python
from osmp.protocol import BlockCompressor

bc = BlockCompressor()
bc.load("mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack")
result = bc.resolve("J93.0")
# "Spontaneous tension pneumothorax"
```

Three corpora bundled: ICD-10-CM (74,719 codes), ISO 20022 (47,835 codes), MITRE ATT&CK (1,661 codes).

## MCP Server

The MCP server is a separate package that wraps this SDK:

```
pip install osmp-mcp
osmp-mcp
```

Nine tools for AI client integration. Connect from Claude Code (`claude mcp add osmp -- osmp-mcp`), Claude Desktop, Cursor, or any MCP-compatible client.

## License

Apache 2.0. Patent pending. Filed March 17, 2026.
