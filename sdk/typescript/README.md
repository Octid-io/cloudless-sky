# OSMP TypeScript SDK

TypeScript implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Semantic Assembly Language). 352 opcodes across 26 namespaces. Deterministic decode to structured instructions. No inference. Pure JS D:PACK/BLK via `fzstd` (82KB, zero native deps).

## Install

```
npm install osmp-protocol
```

## Tier 1: Top-Level Functions, Zero Setup

```typescript
import { encode, decode } from "osmp-protocol";

const sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"]);
// "H:HR@NODE1>120;H:CASREP;M:EVA@*"

const text = decode("H:HR@NODE1>120;H:CASREP;M:EVA@*");
// "H:heart_rate →NODE1 >120; H:casualty_report; M:evacuation →*"
```

No constructors. Lazy singleton initialized on first import.

### Additional Tier 1 Functions

```typescript
import { validate, lookup, byteSize } from "osmp-protocol";

const result = validate("R:MOV@BOT1⚠");
console.log(result.valid);   // false -- ⚠ requires I:§ precondition

const definition = lookup("R:WPT");
// "waypoint"

console.log(byteSize("H:HR@NODE1>120"));
// 15
```

## Tier 2: Class-Based Interface

For explicit ASD control, custom dependency rules, or concurrent instances:

```typescript
import { AdaptiveSharedDictionary, OSMPEncoder, OSMPDecoder } from "osmp-protocol";

const asd = new AdaptiveSharedDictionary();
const enc = new OSMPEncoder(asd);
const dec = new OSMPDecoder(asd);

const sal = enc.encodeSequence(["H:HR@NODE1>120", "H:CASREP"]);
const result = dec.decodeFrame("H:HR@NODE1>120");
// result.namespace = "H"
// result.opcode = "HR"
// result.opcodeMeaning = "heart_rate"
// result.target = "NODE1"
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

```typescript
import { resolveBlk } from "osmp-protocol";

const result = resolveBlk("mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack", "J93.0");
// "Spontaneous tension pneumothorax"
```

Three corpora bundled: ICD-10-CM (74,719 codes), ISO 20022 (47,835 codes), MITRE ATT&CK (1,661 codes).

## EML — Universal Binary Operator Evaluator

A companion math-evaluation module. Based on Odrzywołek (2026, [arXiv:2603.21852](https://arxiv.org/abs/2603.21852)): a single binary operator `eml(x, y) = exp(x) − ln(y)`, together with the constant 1, generates the standard calculator function basis — exp, ln, sin, cos, sqrt, arithmetic, and more — as compact expression trees.

Byte-exact evaluation across Python, Go, and TypeScript on every IEEE-754-conformant platform. Full sin(x) or sqrt(x) approximation fits in fewer than 100 bytes on the wire.

```typescript
import { eml, leaf, varX, branch, evaluateTree } from "osmp-protocol/eml";

// The operator itself
eml(2.0, 1.0);  // exp(2) - ln(1) = 7.389056...

// Build an expression tree: exp(x) = eml(x, 1)
const tree = branch(varX(), leaf(1.0));
evaluateTree(tree, 2.0);  // 7.389056...
```

### Pre-Built Corpus

Sixteen single-variable base functions and four multi-variable arithmetic compounds ship pre-verified:

```typescript
import {
  getBaseChain, evaluateChain,
  compoundXPlusY, compoundXTimesY, compoundLinearCalibration,
} from "osmp-protocol/eml";

// Base corpus (single variable x)
const chain = getBaseChain("ln(x)");
evaluateChain(chain, [Math.E]);        // 1.0
evaluateChain(chain, [Math.E ** 2]);   // 2.0

// Arithmetic compounds (multi-variable)
evaluateChain(compoundXPlusY(), [2.0, 3.0]);                // 5.0
evaluateChain(compoundXTimesY(), [2.0, 3.0]);               // 6.0
evaluateChain(compoundLinearCalibration(), [2.0, 3.0, 1.0]);// 7.0
```

Available base names: `exp(x)`, `ln(x)`, `identity`, `zero`, `exp(x)-ln(x)`, `exp(x)-x`, `e-x`, `exp(exp(x))`, `e-exp(x)`, `1-ln(x)`, `e/x`, `exp(x)-1`, `exp(x)-e`, `e^e/x`, `ln(ln(x))`, `exp(exp(exp(x)))`.

### Wire Format

Three wire encodings ship:

```typescript
import { encodeTree, decodeTree, encodeChainRestricted, decodeChainRestricted } from "osmp-protocol/eml";

// Paper tree form: pre-order tagged traversal, 4-byte float32 or 8-byte float64 leaves
const tree = getBaseChain("ln(x)");  // Or build manually via branch()/leaf()/varX()
const wireBytes = encodeTree(tree);   // Uint8Array
const decoded = decodeTree(wireBytes);
evaluateTree(decoded, Math.E);        // 1.0

// Restricted chain form (bit-packed, single variable)
const chain = getBaseChain("ln(x)");
const chainBytes = encodeChainRestricted(chain, true);  // self-describing
const decodedChain = decodeChainRestricted(chainBytes, { selfDescribing: true, variableName: "x" });
evaluateChain(decodedChain, [Math.E]);  // 1.0
```

A wide multi-variable form (`encodeChainWide` / `decodeChainWide`) handles compounds with up to 15 variables and 15 levels in a single-byte header.

### Cross-Device Determinism

```typescript
import { corpusFingerprint } from "osmp-protocol/eml";

corpusFingerprint();
// "e9a4a71383f14624472fe0602ca5e0ff1959e00b09725a62d584e1361f842c1b"
```

Identical fingerprint across Python, Go, and TypeScript on every IEEE-754-conformant platform.

### Precision Modes

Two modes toggled via `setPrecisionMode`:

- **`"fast"`** (default) — fdlibm-derived, 1-ULP accurate, ships publicly.
- **`"precision"`** — crlibm-derived, correctly-rounded, audit-grade. For regulated industries (medical IEC 62304, aerospace DO-178C, nuclear IEC 61513), audit-grade finance, and cryptographic protocol-frame hash inputs. **Available under commercial license** — contact `licensing@octid.io` or see [PATENTS.md](../../PATENT-NOTICE.md).

```typescript
import { setPrecisionMode, precisionModeAvailable, PrecisionModeNotAvailableError } from "osmp-protocol/eml";

precisionModeAvailable();  // false in public release

try {
  setPrecisionMode("precision");
} catch (e) {
  if (e instanceof PrecisionModeNotAvailableError) {
    console.log(e.message);
    // "Precision mode requires the commercial precision pack.
    //  Contact licensing@octid.io or see PATENTS.md."
  }
}
```

## Build

```
cd sdk/typescript
npm install
npm run build
```

## License

Apache 2.0. Patent pending.

## SALBridge: Mixed Environment Integration

```typescript
import { SALBridge } from "osmp-protocol";

const b = new SALBridge("MY_NODE");
b.registerPeer("GPT_AGENT", false);

// Outbound: SAL decoded to annotated NL
const out = b.send("H:HR@NODE1>120", "GPT_AGENT");

// Inbound: scanned for SAL acquisition
const result = b.receive("A:ACK", "GPT_AGENT");

// Metrics
const metrics = b.getMetrics("GPT_AGENT");
```
