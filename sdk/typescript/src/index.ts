/**
 * OSMP TypeScript SDK — npm: osmp-protocol
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
export { AdaptiveSharedDictionary } from "./asd.js";
export { OSMPEncoder } from "./encoder.js";
export { OSMPDecoder } from "./decoder.js";
export { OverflowProtocol, packFragment, unpackFragment, isTerminal, isCritical } from "./overflow.js";
export { BAELEncoder, utf8Bytes } from "./bael.js";
export { runBenchmark } from "./benchmark.js";
export { ASD_BASIS, ASD_FLOOR_VERSION, GLYPH_OPERATORS, COMPOUND_OPERATORS,
         CONSEQUENCE_CLASSES, OUTCOME_STATES, PARAMETER_DESIGNATORS } from "./glyphs.js";
export type { DecodedInstruction, Fragment, BenchmarkReport, VectorResult,
              DeltaLogEntry, BAELResult } from "./types.js";
export { LossPolicy, BAELMode, DictUpdateMode, FLAG_TERMINAL, FLAG_CRITICAL,
         FLAG_NL_PASSTHROUGH, FRAGMENT_HEADER_BYTES, LORA_FLOOR_BYTES,
         LORA_STANDARD_BYTES } from "./types.js";
