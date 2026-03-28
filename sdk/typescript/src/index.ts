/**
 * OSMP TypeScript SDK — npm: osmp-protocol
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
export { AdaptiveSharedDictionary } from "./asd.js";
export { validateComposition } from "./validate.js";
export type { CompositionIssue, CompositionResult } from "./validate.js";
export { OSMPEncoder } from "./encoder.js";
export { OSMPDecoder } from "./decoder.js";
export { OverflowProtocol, packFragment, unpackFragment, isTerminal, isCritical } from "./overflow.js";
export { DAGFragmenter, DAGReassembler } from "./dag.js";
export type { DAGNode } from "./dag.js";
export { BAELEncoder, utf8Bytes } from "./bael.js";
export { runBenchmark } from "./benchmark.js";
export { ASD_BASIS, ASD_FLOOR_VERSION, GLYPH_OPERATORS, COMPOUND_OPERATORS,
         CONSEQUENCE_CLASSES, OUTCOME_STATES, PARAMETER_DESIGNATORS,
         LOSS_POLICIES, DICT_UPDATE_MODES } from "./glyphs.js";
export { resolveBlk, statsBlk } from "./dpack.js";
export type { BlkStats } from "./dpack.js";
export type { DecodedInstruction, Fragment, BenchmarkReport, VectorResult,
              DeltaLogEntry, BAELResult } from "./types.js";
export { LossPolicy, BAELMode, DictUpdateMode, FLAG_TERMINAL, FLAG_CRITICAL,
         FLAG_EXTENDED_DEP, FLAG_NL_PASSTHROUGH, FRAGMENT_HEADER_BYTES, LORA_FLOOR_BYTES,
         LORA_STANDARD_BYTES } from "./types.js";
export { FNPSession, FNP_MSG_ADV, FNP_MSG_ACK, FNP_MSG_NACK,
         FNP_MATCH_EXACT, FNP_MATCH_VERSION, FNP_MATCH_FINGERPRINT,
         FNP_CAP_FLOOR, FNP_CAP_STANDARD, FNP_CAP_BLE, FNP_CAP_UNCONSTRAINED,
         FNP_CAP_BYTES, FNP_ADV_SIZE, FNP_ACK_SIZE } from "./fnp.js";
export type { FNPState, FNPSessionInfo } from "./fnp.js";
export { ADPSession, asdVersionPack, asdVersionUnpack, asdVersionStr,
         asdVersionParse, asdVersionIsBreaking, deltaToSal, deltaHasBreaking,
         deltaOpToSal, deltaOpIsBreaking,
         ADP_PRIORITY_MISSION, ADP_PRIORITY_MICRO,
         ADP_PRIORITY_DELTA, ADP_PRIORITY_TRICKLE } from "./adp.js";
export type { ADPDeltaOp, ADPDelta, PendingInstruction } from "./adp.js";
