# OSMP TypeScript SDK

TypeScript implementation of the Octid Semantic Mesh Protocol. Encodes, decodes, and validates agentic AI instructions using SAL (Structured Agent Language). 342 opcodes across 26 namespaces. Inference-free decode by table lookup.

## Install

```
npm install osmp-protocol
```

## Build from source

```
cd sdk/typescript
npm install
npm run build
```

## Encode

```typescript
import { OSMPEncoder } from "osmp-protocol";

const enc = new OSMPEncoder();
const sal = enc.encode({ namespace: "H", opcode: "HR", target: "NODE1", slots: { threshold: "130" } });
// "H:HR@NODE1[130]"
```

## Decode

```typescript
import { OSMPDecoder } from "osmp-protocol";

const dec = new OSMPDecoder();
const result = dec.decodeFrame("H:HR@NODE1[130]");
// result.namespace = "H"
// result.opcode = "HR"
// result.opcodeMeaning = "heart_rate"
// result.target = "NODE1"
```

## Validate Composition

Always validate before emitting composed SAL:

```typescript
import { validateComposition } from "osmp-protocol";

const result = validateComposition("R:MOV@BOT1", "Move the robot to BOT1");
console.log(result.valid);   // false
console.log(result.errors);  // [CONSEQUENCE_CLASS_OMISSION: R:MOV requires ⚠/↺/⊘]

const ok = validateComposition("I:§→R:MOV@BOT1⚠", "Move the robot to BOT1");
console.log(ok.valid);       // true
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

```typescript
import { AdaptiveSharedDictionary } from "osmp-protocol";

const asd = new AdaptiveSharedDictionary();
const definition = asd.lookup("R", "WPT");
// "waypoint"
```

## Domain Code Resolution

```typescript
import { resolveBlk } from "osmp-protocol";

const result = await resolveBlk("mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack", "J93.0");
// "Spontaneous tension pneumothorax"
```

Three corpora bundled: ICD-10-CM (74,719 codes), ISO 20022 (47,835 codes), MITRE ATT&CK (1,661 codes).

## Benchmark

```typescript
import { runBenchmark } from "osmp-protocol";

const report = await runBenchmark("protocol/test-vectors/canonical-test-vectors.json");
console.log(`Mean reduction: ${report.meanReductionPct.toFixed(1)}%`);
console.log(`Conformant: ${report.conformant}`);
```

## License

Apache 2.0. Patent pending (Application #64/007,684).
