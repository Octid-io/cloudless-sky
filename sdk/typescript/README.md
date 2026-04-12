# OSMP TypeScript SDK

TypeScript implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Semantic Assembly Language). 356 opcodes across 26 namespaces. Inference-free decode by table lookup. Pure JS D:PACK/BLK via `fzstd` (82KB, zero native deps).

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

## Build

```
cd sdk/typescript
npm install
npm run build
```

## License

Apache 2.0. Patent pending. Filed March 17, 2026.

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
