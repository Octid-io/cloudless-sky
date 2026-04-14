/**
 * OSMP Type Definitions
 * Patent pending — inventor Clay Holberg | License: Apache 2.0
 */
export interface DecodedInstruction {
    namespace: string;
    opcode: string;
    opcodeMeaning: string | null;
    target: string | null;
    querySlot: string | null;
    slots: Record<string, string>;
    consequenceClass: string | null;
    consequenceClassName: string | null;
    raw: string;
}
export interface Fragment {
    msgId: number;
    fragIdx: number;
    fragCt: number;
    flags: number;
    dep: number;
    payload: Uint8Array;
}
export declare const FLAG_TERMINAL = 1;
export declare const FLAG_CRITICAL = 2;
export declare const FLAG_EXTENDED_DEP = 8;
export declare const FLAG_NL_PASSTHROUGH = 4;
export declare const FRAGMENT_HEADER_BYTES = 6;
export declare const LORA_FLOOR_BYTES = 51;
export declare const LORA_STANDARD_BYTES = 255;
export declare enum LossPolicy {
    FAIL_SAFE = "\u03A6",
    GRACEFUL_DEGRADATION = "\u0393",
    ATOMIC = "\u039B"
}
export declare enum BAELMode {
    FULL_OSMP = 0,
    TCL_ONLY = 2,
    NL_PASSTHROUGH = 4
}
export interface BAELResult {
    mode: BAELMode;
    payload: string;
    flagsByte: number;
}
export declare enum DictUpdateMode {
    ADDITIVE = "ADDITIVE",
    REPLACE = "REPLACE",
    DEPRECATE = "DEPRECATE"
}
export interface VectorResult {
    id: string;
    nlBytes: number;
    osmpBytes: number;
    reductionPct: number;
    expectedReductionPct: number;
    conformant: boolean;
    decodeOk: boolean;
    mustPass: boolean;
}
export interface BenchmarkReport {
    conformant: boolean;
    passed: number;
    totalMustPass: number;
    meanReductionPct: number;
    minReductionPct: number;
    maxReductionPct: number;
    vectors: VectorResult[];
}
export interface DeltaLogEntry {
    ns: string;
    op: string;
    def: string;
    mode: string;
    ver: string;
}
