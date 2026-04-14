/**
 * OSMP Type Definitions
 * Patent pending — inventor Clay Holberg | License: Apache 2.0
 */
export interface DecodedInstruction {
  namespace: string; opcode: string; opcodeMeaning: string | null;
  target: string | null; querySlot: string | null;
  slots: Record<string, string>;
  consequenceClass: string | null; consequenceClassName: string | null;
  raw: string;
}
export interface Fragment {
  msgId: number; fragIdx: number; fragCt: number;
  flags: number; dep: number; payload: Uint8Array;
}
export const FLAG_TERMINAL      = 0b00000001;
export const FLAG_CRITICAL      = 0b00000010;
export const FLAG_EXTENDED_DEP  = 0b00001000;
export const FLAG_NL_PASSTHROUGH = 0x04;
export const FRAGMENT_HEADER_BYTES = 6;
export const LORA_FLOOR_BYTES   = 51;
export const LORA_STANDARD_BYTES = 255;
export enum LossPolicy {
  FAIL_SAFE            = "Φ",
  GRACEFUL_DEGRADATION = "Γ",
  ATOMIC               = "Λ",
}
export enum BAELMode {
  FULL_OSMP      = 0x00,
  TCL_ONLY       = 0x02,
  NL_PASSTHROUGH = 0x04,
}
export interface BAELResult { mode: BAELMode; payload: string; flagsByte: number; }
export enum DictUpdateMode { ADDITIVE = "ADDITIVE", REPLACE = "REPLACE", DEPRECATE = "DEPRECATE" }
export interface VectorResult {
  id: string; nlBytes: number; osmpBytes: number;
  reductionPct: number; expectedReductionPct: number;
  conformant: boolean; decodeOk: boolean; mustPass: boolean;
}
export interface BenchmarkReport {
  conformant: boolean; passed: number; totalMustPass: number;
  meanReductionPct: number; minReductionPct: number; maxReductionPct: number;
  vectors: VectorResult[];
}
export interface DeltaLogEntry { ns: string; op: string; def: string; mode: string; ver: string; }
