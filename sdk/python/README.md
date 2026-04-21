# OSMP Python SDK

Reference implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, composes, and validates agentic AI instructions using SAL (Semantic Assembly Language). 352 opcodes across 26 namespaces. SALComposer for deterministic NL-to-SAL composition (95.7% opcode coverage). MacroRegistry for pre-validated chain templates (16 Meshtastic macros shipped). Deterministic decode to structured instructions. No inference.

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
# "(clinical) [clinical] heart rate above 120 at NODE1, then [clinical] casualty report, then [emergency] evacuation at all nodes"
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

## EML — Universal Binary Operator Evaluator

A companion math-evaluation layer. Based on Odrzywołek (2026, [arXiv:2603.21852](https://arxiv.org/abs/2603.21852)): a single binary operator `eml(x, y) = exp(x) − ln(y)`, together with the constant 1, generates the standard calculator function basis — exp, ln, sin, cos, sqrt, arithmetic, and more — as compact expression trees.

The receiver evaluates a pre-built tree by composing `eml` in a loop. No math library dependency. A full sin(x) or sqrt(x) approximation fits in fewer than 100 bytes on the wire, byte-exact across Python, Go, and TypeScript.

```python
from osmp.eml import eml, EMLNode, leaf, var_x, node

# The operator itself: eml(x, y) = exp(x) - ln(y)
eml(2.0, 1.0)  # exp(2) - ln(1) = 7.389056...

# Build an expression tree: exp(x) = eml(x, 1)
tree = node(var_x(), leaf(1.0))
tree.evaluate(2.0)  # 7.389056...
```

### Pre-Built Corpus

Sixteen single-variable base functions and four multi-variable arithmetic compounds ship pre-verified:

```python
from osmp.eml import get_base_chain, compound_x_plus_y, compound_x_times_y, compound_linear_calibration
import math

# Base corpus (single variable x)
chain = get_base_chain("ln(x)")
chain.evaluate(math.e)       # 1.0
chain.evaluate(math.e ** 2)  # 2.0

# Arithmetic compounds (multi-variable)
compound_x_plus_y().evaluate([2.0, 3.0])                # 5.0
compound_x_times_y().evaluate([2.0, 3.0])               # 6.0
compound_linear_calibration().evaluate([2.0, 3.0, 1.0]) # 7.0  (a=2, x=3, b=1)
```

Available base names: `exp(x)`, `ln(x)`, `identity`, `zero`, `exp(x)-ln(x)`, `exp(x)-x`, `e-x`, `exp(exp(x))`, `e-exp(x)`, `1-ln(x)`, `e/x`, `exp(x)-1`, `exp(x)-e`, `e^e/x`, `ln(ln(x))`, `exp(exp(exp(x)))`.

### Wire Format (Transmit the Math)

Three wire encodings ship:

```python
from osmp.eml import encode_tree, decode_tree, encode_chain_restricted, decode_chain_restricted
from osmp.eml import get_base_chain, tree_ln_x

# Paper tree form: pre-order tagged traversal, 4-byte float32 or 8-byte float64 leaves
tree = tree_ln_x()
wire = encode_tree(tree)            # 7 bytes
decode_tree(wire).evaluate(math.e)  # 1.0

# Restricted chain form (bit-packed, single variable)
chain = get_base_chain("ln(x)")
wire = encode_chain_restricted(chain)        # 2 bytes (self-describing)
decode_chain_restricted(wire).evaluate(math.e)  # 1.0
```

A wide multi-variable form (`encode_chain_wide` / `decode_chain_wide`) handles compounds with up to 15 variables and 15 levels in a single-byte header.

### Cross-Device Determinism

Two receivers on heterogeneous hardware evaluating the same wire-encoded chain must produce byte-exact identical output. The fast-mode backend (fdlibm-derived) guarantees this across IEEE-754-conformant platforms using only basic arithmetic and `frexp` / `ldexp`. Verify by fingerprinting the corpus:

```python
from osmp.eml import corpus_fingerprint
print(corpus_fingerprint())
# e9a4a71383f14624472fe0602ca5e0ff1959e00b09725a62d584e1361f842c1b
```

Identical fingerprint across Python, Go, and TypeScript.

### Precision Modes

Two modes toggled via `set_precision_mode`:

- **`"fast"`** (default) — fdlibm-derived, 1-ULP accurate, ships publicly in this package. Correct for LoRa/BLE/edge-ML, constrained-channel telemetry, drone swarm coordination, and general scientific computation.
- **`"precision"`** — crlibm-derived, correctly-rounded, audit-grade. For regulated industries (medical IEC 62304, aerospace DO-178C, nuclear IEC 61513), audit-grade finance, and cryptographic protocol-frame hash inputs. **Available under commercial license** — contact `licensing@octid.io` or see [PATENTS.md](../../PATENT-NOTICE.md).

```python
from osmp.eml import set_precision_mode, precision_mode_available, PrecisionModeNotAvailable

print(precision_mode_available())  # False in public release

try:
    set_precision_mode("precision")
except PrecisionModeNotAvailable as e:
    print(e)
    # Precision mode requires the commercial precision pack.
    # Contact licensing@octid.io or see PATENTS.md.
```

## SALComposer: NL to SAL

Deterministic composition pipeline. No inference.

```python
from osmp.protocol import SALComposer

composer = SALComposer()

sal, is_sal = composer.compose_or_passthrough("Alert if heart rate exceeds 130")
# sal = "H:HR>130.→H:ALERT", is_sal = True

sal, is_sal = composer.compose_or_passthrough("Order me some tacos")
# sal = "Order me some tacos", is_sal = False (NL passthrough)
```

95.7% opcode coverage on the full 352-opcode dictionary. Generation index with 358 phrase triggers. Confidence gate prevents false positives on common English words.

## MCP Server

The MCP server is a separate package that wraps this SDK:

```
pip install osmp-mcp
osmp-mcp
```

17 tools for AI client integration including `osmp_compose` (NL to SAL), `osmp_macro_list`, and `osmp_macro_invoke`. Connect from Claude Code (`claude mcp add osmp -- osmp-mcp`), Claude Desktop, Cursor, or any MCP-compatible client.

## License

Apache 2.0. Patent pending. Filed March 17, 2026.

## SALBridge: Mixed Environment Integration

When your agents communicate with non-OSMP peers, the bridge handles boundary translation.

```python
from osmp import bridge

b = bridge("MY_NODE")
b.register_peer("GPT_AGENT", attempt_fnp=False)

# Outbound: SAL decoded to NL, annotated with SAL equivalent
out = b.send("H:HR@NODE1>120", "GPT_AGENT")

# Inbound: scanned for SAL acquisition
result = b.receive("A:ACK", "GPT_AGENT")

# Metrics and comparison
metrics = b.get_metrics("GPT_AGENT")
comparison = b.get_comparison("GPT_AGENT")
```

The bridge annotates outbound messages with SAL, seeding the remote agent's context. When the remote agent starts producing valid SAL through exposure, FNP transitions from FALLBACK to ACQUIRED. OSMP spreads by contact, not installation.
