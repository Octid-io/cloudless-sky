/*
 * eml.ts — Universal Binary Operator Evaluator (UBOT public reference).
 *
 * Reference implementation of the Universal Binary Operator for mathematical
 * instruction encoding. Patent pending.
 *
 * Based on Odrzywołek (2026, arXiv:2603.21852):
 *
 *     eml(x, y) = exp(x) − ln(y)
 *
 * This module is the PUBLIC library-free evaluator. It uses built-in types
 * and an fdlibm-derived exp/log port; no npm runtime dependencies. Runs
 * under Node.js 18+ and browsers with modern JavaScript engines.
 *
 * Dual-mode precision:
 *
 *     Fast mode      — fdlibm-derived (1-ULP accurate, ships publicly)
 *     Precision mode — crlibm-derived (correctly-rounded, audit-grade)
 *                      AVAILABLE UNDER COMMERCIAL LICENSE.
 *
 * Precision mode (correctly-rounded, cross-device deterministic, audit-grade
 * for regulated industries — medical IEC 62304, aerospace DO-178C, nuclear
 * IEC 61513, audit-grade finance) is available under commercial license.
 * Contact licensing@octid.io for evaluation.
 *
 * Calling setPrecisionMode("precision") without the commercial precision
 * pack installed throws PrecisionModeNotAvailableError.
 *
 * Attribution: built on the universal binary operator eml(x, y) =
 * exp(x) − ln(y) introduced by Andrzej Odrzywołek (Jagiellonian
 * University, arXiv:2603.21852, March 2026). The operator itself is
 * not claimed by any patent; the present work claims the transmission,
 * encoding, and apparatus layer distinct from the operator.
 *
 * License: Apache 2.0 (public module). Precision pack: separate
 * commercial license — see PATENTS.md at repository root.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { createHash } from "crypto";
import { exp as fdlibmExp, log as fdlibmLog } from "./fdlibm.js";
import {
  exp as crlibmExp,
  log as crlibmLog,
  AVAILABLE as CRLIBM_AVAILABLE,
  PrecisionModeNotAvailableError,
} from "./crlibm.js";

export { PrecisionModeNotAvailableError };

export type PrecisionMode = "fast" | "precision";
let currentMode: PrecisionMode = "fast";

/**
 * Set the evaluator precision mode.
 *
 * Precision mode requires the commercial precision pack. If the pack is
 * not installed, setPrecisionMode("precision") throws
 * PrecisionModeNotAvailableError. Fast mode always succeeds.
 * Contact licensing@octid.io for evaluation.
 */
export function setPrecisionMode(m: PrecisionMode): void {
  if (m === "precision" && !CRLIBM_AVAILABLE) {
    throw new PrecisionModeNotAvailableError();
  }
  currentMode = m;
}

export function getPrecisionMode(): PrecisionMode { return currentMode; }

/** Whether the commercial precision-mode backend is installed. */
export function precisionModeAvailable(): boolean { return CRLIBM_AVAILABLE; }

function activeExp(x: number): number {
  if (currentMode === "precision") {
    // Defense-in-depth: setPrecisionMode refuses to switch to "precision"
    // without the pack, so this path fires only if currentMode was set
    // by some other means.
    if (!CRLIBM_AVAILABLE) {
      throw new PrecisionModeNotAvailableError();
    }
    return crlibmExp(x);
  }
  return fdlibmExp(x);
}

function activeLog(y: number): number {
  if (currentMode === "precision") {
    if (!CRLIBM_AVAILABLE) {
      throw new PrecisionModeNotAvailableError();
    }
    return crlibmLog(y);
  }
  return fdlibmLog(y);
}

// =============================================================================
// CORE OPERATOR
// =============================================================================

/** safe_exp argument clamp magnitude. Load-bearing (part of the patent claims). */
export const EXP_CLAMP = 50.0;

/** safe_log input magnitude floor. Load-bearing. */
export const LOG_EPS = 1e-30;

/** exp(x) clamped to [-EXP_CLAMP, +EXP_CLAMP], via current PrecisionMode. */
export function safeExp(x: number): number {
  if (x > EXP_CLAMP) return activeExp(EXP_CLAMP);
  if (x < -EXP_CLAMP) return activeExp(-EXP_CLAMP);
  return activeExp(x);
}

/** log(|y|) floored at LOG_EPS, via current PrecisionMode. */
export function safeLog(y: number): number {
  let mag = Math.abs(y);
  if (mag < LOG_EPS) mag = LOG_EPS;
  return activeLog(mag);
}

/** The universal binary operator: eml(x, y) = safe_exp(x) − safe_log(y). */
export function eml(x: number, y: number): number {
  return safeExp(x) - safeLog(y);
}

// =============================================================================
// PAPER TREE REPRESENTATION
// =============================================================================

export interface EMLNode {
  left: EMLNode | null;
  right: EMLNode | null;
  value: number;  // only meaningful when leaf
  isX: boolean;   // true for var_x leaves
}

export function leaf(v = 1.0): EMLNode {
  return { left: null, right: null, value: v, isX: false };
}

export function varX(): EMLNode {
  return { left: null, right: null, value: 0, isX: true };
}

export function branch(left: EMLNode, right: EMLNode): EMLNode {
  return { left, right, value: 0, isX: false };
}

export const ONE: EMLNode = leaf(1.0);

export function isLeaf(n: EMLNode): boolean {
  return n.left === null;
}

export function treeDepth(n: EMLNode): number {
  if (isLeaf(n)) return 0;
  return 1 + Math.max(treeDepth(n.left!), treeDepth(n.right!));
}

export function evaluateTree(n: EMLNode, x: number): number {
  if (isLeaf(n)) return n.isX ? x : n.value;
  return eml(evaluateTree(n.left!, x), evaluateTree(n.right!, x));
}

// =============================================================================
// PAPER TREE WIRE FORMAT
// =============================================================================

const TAG_LEAF_F32 = 0x00;
const TAG_BRANCH = 0x01;
const TAG_VAR_X = 0x02;
const TAG_LEAF_F64 = 0x03;

export function encodeTree(tree: EMLNode, useF64 = false): Uint8Array {
  const chunks: number[] = [];
  encodeNode(tree, chunks, useF64);
  return new Uint8Array(chunks);
}

function encodeNode(n: EMLNode, out: number[], useF64: boolean): void {
  if (isLeaf(n)) {
    if (n.isX) {
      out.push(TAG_VAR_X);
      return;
    }
    if (useF64) {
      out.push(TAG_LEAF_F64);
      const buf = new ArrayBuffer(8);
      new DataView(buf).setFloat64(0, n.value, true);
      const u = new Uint8Array(buf);
      for (let i = 0; i < 8; i++) out.push(u[i]);
    } else {
      out.push(TAG_LEAF_F32);
      const buf = new ArrayBuffer(4);
      new DataView(buf).setFloat32(0, n.value, true);
      const u = new Uint8Array(buf);
      for (let i = 0; i < 4; i++) out.push(u[i]);
    }
    return;
  }
  out.push(TAG_BRANCH);
  encodeNode(n.left!, out, useF64);
  encodeNode(n.right!, out, useF64);
}

export function decodeTree(data: Uint8Array): EMLNode {
  const { node, offset } = decodeNode(data, 0);
  if (offset !== data.length) {
    throw new Error(`Trailing bytes after tree: ${data.length - offset}`);
  }
  return node;
}

function decodeNode(data: Uint8Array, offset: number): { node: EMLNode; offset: number } {
  if (offset >= data.length) throw new Error("Unexpected end of tree data");
  const tag = data[offset++];
  if (tag === TAG_VAR_X) return { node: varX(), offset };
  if (tag === TAG_LEAF_F32) {
    if (offset + 4 > data.length) throw new Error("Truncated float32 leaf");
    const v = new DataView(data.buffer, data.byteOffset + offset, 4).getFloat32(0, true);
    return { node: leaf(v), offset: offset + 4 };
  }
  if (tag === TAG_LEAF_F64) {
    if (offset + 8 > data.length) throw new Error("Truncated float64 leaf");
    const v = new DataView(data.buffer, data.byteOffset + offset, 8).getFloat64(0, true);
    return { node: leaf(v), offset: offset + 8 };
  }
  if (tag === TAG_BRANCH) {
    const { node: l, offset: o1 } = decodeNode(data, offset);
    const { node: r, offset: o2 } = decodeNode(data, o1);
    return { node: branch(l, r), offset: o2 };
  }
  throw new Error(`Invalid tree tag: 0x${tag.toString(16).padStart(2, "0")}`);
}

// =============================================================================
// CHAIN REPRESENTATION
// =============================================================================

export interface ChainLevel {
  left: string;
  right: string;
}

export type ChainVariant = "restricted" | "wide" | "wide_multivar";

export interface Chain {
  levels: ChainLevel[];
  variables: string[];
  variant: ChainVariant;
}

export function evaluateChain(c: Chain, values: number[]): number {
  if (values.length !== c.variables.length) {
    throw new Error(`Got ${values.length} values, expected ${c.variables.length}`);
  }
  const varMap: Record<string, number> = { "1": 1.0 };
  c.variables.forEach((v, i) => { varMap[v] = values[i]; });
  const f: number[] = [];
  c.levels.forEach((lvl, k) => {
    const a = resolveOperand(lvl.left, varMap, f, k + 1);
    const b = resolveOperand(lvl.right, varMap, f, k + 1);
    f.push(eml(a, b));
  });
  return f.length === 0 ? 0 : f[f.length - 1];
}

function resolveOperand(op: string, varMap: Record<string, number>, f: number[], k: number): number {
  if (op === "1") return 1.0;
  if (op === "f") {
    if (k < 2) throw new Error("'f' referenced at L1");
    return f[k - 2];
  }
  if (op.length > 1 && op[0] === "f") {
    const rest = op.slice(1);
    if (/^\d+$/.test(rest)) {
      const idx = parseInt(rest, 10);
      if (idx < 1 || idx >= k) throw new Error(`f${idx} out of range at L${k}`);
      return f[idx - 1];
    }
  }
  if (op in varMap) return varMap[op];
  throw new Error(`Unknown operand ${JSON.stringify(op)}`);
}

// =============================================================================
// RESTRICTED CHAIN WIRE FORMAT
// =============================================================================

const R_L1_CODE: Record<string, number> = { "1": 0, "x": 1 };
const R_LK_CODE: Record<string, number> = { "1": 0b00, "x": 0b01, "f": 0b10 };

export function encodeChainRestricted(c: Chain, selfDescribing = true): Uint8Array {
  if (c.variant !== "restricted") throw new Error(`Not restricted: ${c.variant}`);
  if (c.variables.length !== 1) throw new Error("Restricted chain must be single-variable");
  const varName = c.variables[0];
  const bits: number[] = [];
  if (selfDescribing) {
    if (c.levels.length > 15) throw new Error("Self-describing supports N≤15");
    for (let i = 3; i >= 0; i--) bits.push((c.levels.length >> i) & 1);
  }
  c.levels.forEach((lvl, k) => {
    const bpi = k + 1 === 1 ? 1 : 2;
    const codebook = k + 1 === 1 ? R_L1_CODE : R_LK_CODE;
    for (const operand of [lvl.left, lvl.right]) {
      const op = operand === varName ? "x" : operand;
      if (!(op in codebook)) throw new Error(`Operand ${operand} not encodable at L${k + 1}`);
      const code = codebook[op];
      for (let i = bpi - 1; i >= 0; i--) bits.push((code >> i) & 1);
    }
  });
  return packBits(bits);
}

const R_L1_DECODE: Record<number, string> = { 0: "1", 1: "x" };
const R_LK_DECODE: Record<number, string> = { 0b00: "1", 0b01: "x", 0b10: "f" };

export function decodeChainRestricted(
  data: Uint8Array,
  opts: { selfDescribing?: boolean; nLevels?: number; variableName?: string } = {}
): Chain {
  const selfDescribing = opts.selfDescribing ?? true;
  let nLevels = opts.nLevels ?? 0;
  const variableName = opts.variableName ?? "x";
  const bits = unpackBits(data);
  let off = 0;
  if (selfDescribing) {
    if (nLevels !== 0) throw new Error("Cannot pass nLevels with selfDescribing");
    if (bits.length < 4) throw new Error("Truncated header");
    for (let i = 0; i < 4; i++) { nLevels = (nLevels << 1) | bits[off++]; }
  }
  if (nLevels === 0) throw new Error("nLevels required when not self-describing");
  const levels: ChainLevel[] = [];
  for (let k = 1; k <= nLevels; k++) {
    const bpi = k === 1 ? 1 : 2;
    const decoder = k === 1 ? R_L1_DECODE : R_LK_DECODE;
    const ops: string[] = [];
    for (let i = 0; i < 2; i++) {
      if (off + bpi > bits.length) throw new Error(`Truncated at L${k}`);
      let code = 0;
      for (let j = 0; j < bpi; j++) code = (code << 1) | bits[off++];
      if (!(code in decoder)) throw new Error(`Reserved code ${code} at L${k}`);
      let op = decoder[code];
      if (op === "x") op = variableName;
      ops.push(op);
    }
    levels.push({ left: ops[0], right: ops[1] });
  }
  return { levels, variables: [variableName], variant: "restricted" };
}

// =============================================================================
// WIDE MULTI-VARIABLE CHAIN WIRE FORMAT
// =============================================================================

function bitsPerInputAtLevel(V: number, k: number): number {
  const options = V + k;
  let b = 0;
  while ((1 << b) < options) b++;
  return Math.max(b, 1);
}

export function encodeChainWide(c: Chain): Uint8Array {
  if (c.variant !== "wide" && c.variant !== "wide_multivar") {
    throw new Error(`Not wide: ${c.variant}`);
  }
  const V = c.variables.length;
  const N = c.levels.length;
  if (V < 1 || V > 255 || N < 1 || N > 255) {
    throw new Error(`V=${V}, N=${N} out of range (1..255)`);
  }
  const varIndex: Record<string, number> = {};
  c.variables.forEach((v, i) => { varIndex[v] = i + 1; });

  const bits: number[] = [];
  if (V <= 15 && N <= 15) {
    pushByte(bits, (V << 4) | N);
  } else {
    pushByte(bits, 0xFF);
    pushByte(bits, N);
    pushByte(bits, V);
  }
  c.levels.forEach((lvl, k) => {
    const bpi = bitsPerInputAtLevel(V, k + 1);
    for (const operand of [lvl.left, lvl.right]) {
      const idx = wideOperandIndex(operand, varIndex, V, k + 1);
      for (let i = bpi - 1; i >= 0; i--) bits.push((idx >> i) & 1);
    }
  });
  return packBits(bits);
}

function wideOperandIndex(op: string, varIndex: Record<string, number>, V: number, k: number): number {
  if (op === "1") return 0;
  if (op in varIndex) return varIndex[op];
  if (op === "f") {
    if (k < 2) throw new Error("'f' at L1");
    return V + (k - 1);
  }
  if (op.length > 1 && op[0] === "f" && /^\d+$/.test(op.slice(1))) {
    const fi = parseInt(op.slice(1), 10);
    if (fi < 1 || fi >= k) throw new Error(`f${fi} out of range at L${k}`);
    return V + fi;
  }
  throw new Error(`Unknown operand ${JSON.stringify(op)}`);
}

export function decodeChainWide(data: Uint8Array, variables?: string[]): Chain {
  const bits = unpackBits(data);
  let off = 0;
  let header = 0;
  for (let i = 0; i < 8; i++) header = (header << 1) | bits[off++];
  let V: number, N: number;
  if (header === 0xFF) {
    N = 0; V = 0;
    for (let i = 0; i < 8; i++) N = (N << 1) | bits[off++];
    for (let i = 0; i < 8; i++) V = (V << 1) | bits[off++];
  } else {
    V = (header >> 4) & 0x0F;
    N = header & 0x0F;
  }
  if (!variables) {
    variables = Array.from({ length: V }, (_, i) => `x${i + 1}`);
  } else if (variables.length !== V) {
    throw new Error(`Got ${variables.length} variable names, header says V=${V}`);
  }
  const idxToVar: Record<number, string> = {};
  variables.forEach((v, i) => { idxToVar[i + 1] = v; });

  const levels: ChainLevel[] = [];
  for (let k = 1; k <= N; k++) {
    const bpi = bitsPerInputAtLevel(V, k);
    const ops: string[] = [];
    for (let i = 0; i < 2; i++) {
      if (off + bpi > bits.length) throw new Error(`Truncated at L${k}`);
      let idx = 0;
      for (let j = 0; j < bpi; j++) idx = (idx << 1) | bits[off++];
      let op: string;
      if (idx === 0) op = "1";
      else if (idx <= V) op = idxToVar[idx];
      else if (idx < V + k) op = `f${idx - V}`;
      else throw new Error(`Operand idx ${idx} out of range at L${k}`);
      ops.push(op);
    }
    levels.push({ left: ops[0], right: ops[1] });
  }
  return { levels, variables, variant: "wide_multivar" };
}

// =============================================================================
// BIT PACKING
// =============================================================================

function packBits(bits: number[]): Uint8Array {
  const n = Math.ceil(bits.length / 8);
  const out = new Uint8Array(n);
  for (let i = 0; i < bits.length; i++) {
    if (bits[i]) out[i >> 3] |= 1 << (7 - (i & 7));
  }
  return out;
}

function unpackBits(data: Uint8Array): number[] {
  const bits: number[] = [];
  for (const b of data) {
    for (let i = 7; i >= 0; i--) bits.push((b >> i) & 1);
  }
  return bits;
}

function pushByte(bits: number[], b: number): void {
  for (let i = 7; i >= 0; i--) bits.push((b >> i) & 1);
}

// =============================================================================
// CORPUS — base restricted-chain structures (must match eml.py)
// =============================================================================

export const BASE_CORPUS_ORDER = [
  "exp(x)", "ln(x)", "identity", "zero",
  "exp(x)-ln(x)", "exp(x)-x", "e-x", "exp(exp(x))",
  "e-exp(x)", "1-ln(x)", "e/x", "exp(x)-1",
  "exp(x)-e", "e^e/x", "ln(ln(x))", "exp(exp(exp(x)))",
];

const BASE_CHAIN_PAIRS: Record<string, [string, string][]> = {
  "exp(x)":           [["x", "1"]],
  "ln(x)":            [["1", "x"], ["f", "1"], ["1", "f"]],
  "identity":         [["1", "x"], ["f", "1"], ["1", "f"], ["f", "1"]],
  "zero":             [["1", "1"], ["f", "1"], ["1", "f"]],
  "exp(x)-ln(x)":     [["x", "x"]],
  "exp(x)-x":         [["x", "1"], ["x", "f"]],
  "e-x":              [["x", "1"], ["1", "f"]],
  "exp(exp(x))":      [["x", "1"], ["f", "1"]],
  "e-exp(x)":         [["x", "1"], ["f", "1"], ["1", "f"]],
  "1-ln(x)":          [["1", "1"], ["f", "1"], ["1", "f"], ["f", "x"]],
  "e/x":              [["1", "1"], ["f", "1"], ["1", "f"], ["f", "x"], ["f", "1"]],
  "exp(x)-1":         [["1", "1"], ["x", "f"]],
  "exp(x)-e":         [["1", "1"], ["f", "1"], ["x", "f"]],
  "e^e/x":            [["1", "x"], ["f", "1"]],
  "ln(ln(x))":        [["1", "x"], ["f", "1"], ["1", "f"], ["1", "f"], ["f", "1"], ["1", "f"]],
  "exp(exp(exp(x)))": [["x", "1"], ["f", "1"], ["f", "1"]],
};

export function getBaseChain(name: string): Chain {
  const pairs = BASE_CHAIN_PAIRS[name];
  if (!pairs) throw new Error(`Unknown base corpus entry: ${name}`);
  return {
    levels: pairs.map(([l, r]) => ({ left: l, right: r })),
    variables: ["x"],
    variant: "restricted",
  };
}

// =============================================================================
// COMPOUND PRIMITIVES (must match eml.py exactly)
// =============================================================================

const COMPOUND_NEG_Y: [string, string][] = [
  ["1", "1"], ["f1", "1"], ["1", "f2"],
  ["1", "f3"], ["f4", "1"], ["1", "f5"],
  ["y", "1"], ["f6", "f7"],
];

const COMPOUND_X_PLUS_Y: [string, string][] = [
  ["1", "1"], ["f1", "1"], ["1", "f2"],
  ["1", "f3"], ["f4", "1"], ["1", "f5"],
  ["y", "1"], ["f6", "f7"],
  ["1", "x"], ["f9", "1"], ["1", "f10"],
  ["f8", "1"],
  ["f11", "f12"],
];

const COMPOUND_X_TIMES_Y: [string, string][] = [
  ["1", "1"], ["f1", "1"], ["1", "f2"],
  ["1", "x"], ["f4", "1"], ["1", "f5"],
  ["1", "y"], ["f7", "1"], ["1", "f8"],
  ["1", "f3"], ["f10", "1"], ["1", "f11"],
  ["f12", "y"],
  ["1", "f6"], ["f14", "1"], ["1", "f15"],
  ["f13", "1"],
  ["f16", "f17"],
  ["f18", "1"],
];

const COMPOUND_LINEAR_CAL: [string, string][] = [
  ["1", "1"], ["f1", "1"], ["1", "f2"],
  ["1", "a"], ["f4", "1"], ["1", "f5"],
  ["1", "x"], ["f7", "1"], ["1", "f8"],
  ["1", "f3"], ["f10", "1"], ["1", "f11"],
  ["f12", "x"],
  ["1", "f6"], ["f14", "1"], ["1", "f15"],
  ["f13", "1"],
  ["f16", "f17"],
  ["f18", "1"],
  ["b", "1"],
  ["f12", "f20"],
  ["1", "f19"], ["f22", "1"], ["1", "f23"],
  ["f21", "1"],
  ["f24", "f25"],
];

function buildCompound(pairs: [string, string][], vars: string[]): Chain {
  return {
    levels: pairs.map(([l, r]) => ({ left: l, right: r })),
    variables: vars,
    variant: "wide_multivar",
  };
}

export const compoundNegY = (): Chain => buildCompound(COMPOUND_NEG_Y, ["y"]);
export const compoundXPlusY = (): Chain => buildCompound(COMPOUND_X_PLUS_Y, ["x", "y"]);
export const compoundXTimesY = (): Chain => buildCompound(COMPOUND_X_TIMES_Y, ["x", "y"]);
export const compoundLinearCalibration = (): Chain => buildCompound(COMPOUND_LINEAR_CAL, ["a", "x", "b"]);

// =============================================================================
// TEST VECTORS & FINGERPRINT
// =============================================================================

export const CANONICAL_INPUTS: number[] = [
  0.5, 1.0, 1.5, 2.0, Math.E, Math.PI, 3.0, 5.0, 7.0, 10.0,
];

export function evaluateBaseCorpus(): Record<string, number[]> {
  const out: Record<string, number[]> = {};
  for (const name of BASE_CORPUS_ORDER) {
    const chain = getBaseChain(name);
    out[name] = CANONICAL_INPUTS.map(x => evaluateChain(chain, [x]));
  }
  return out;
}

export function evaluateCompounds(): Record<string, number[][]> {
  const out: Record<string, number[][]> = {};
  const negY = compoundNegY();
  out["neg_y"] = CANONICAL_INPUTS.map(y => [evaluateChain(negY, [y])]);
  const plus = compoundXPlusY();
  const mul = compoundXTimesY();
  out["x_plus_y"] = [];
  out["x_times_y"] = [];
  for (const x of CANONICAL_INPUTS) {
    for (const y of CANONICAL_INPUTS) {
      out["x_plus_y"].push([evaluateChain(plus, [x, y])]);
      out["x_times_y"].push([evaluateChain(mul, [x, y])]);
    }
  }
  const lc = compoundLinearCalibration();
  out["linear_calibration"] = [];
  for (const a of [0.5, 1.0, Math.PI]) {
    for (const x of [1.0, Math.E]) {
      for (const b of [0.5, 1.0, Math.E]) {
        out["linear_calibration"].push([evaluateChain(lc, [a, x, b])]);
      }
    }
  }
  return out;
}

export function corpusFingerprint(): string {
  const h = createHash("sha256");
  const base = evaluateBaseCorpus();
  for (const name of BASE_CORPUS_ORDER) {
    h.update(Buffer.from(name, "utf-8"));
    h.update(":");
    for (const y of base[name]) {
      const buf = Buffer.alloc(8);
      buf.writeDoubleLE(y, 0);
      h.update(buf);
    }
  }
  const compound = evaluateCompounds();
  for (const name of ["neg_y", "x_plus_y", "x_times_y", "linear_calibration"]) {
    h.update(Buffer.from(name, "utf-8"));
    h.update(":");
    for (const row of compound[name]) {
      for (const y of row) {
        const buf = Buffer.alloc(8);
        buf.writeDoubleLE(y, 0);
        h.update(buf);
      }
    }
  }
  return h.digest("hex");
}

// =============================================================================
// CLI / SELF-TEST
// =============================================================================

export function selfTest(): void {
  console.log("eml.ts production evaluator — self-test");
  console.log("============================================================");
  console.log(`EXP_CLAMP = ${EXP_CLAMP}`);
  console.log(`LOG_EPS   = ${LOG_EPS}`);
  console.log();

  console.log("Base corpus (restricted chain):");
  const base = evaluateBaseCorpus();
  for (const name of BASE_CORPUS_ORDER) {
    const ch = getBaseChain(name);
    console.log(`  ${name.padEnd(25)}  L=${String(ch.levels.length).padStart(2)}  @x=0.5 -> ${base[name][0]}`);
  }
  console.log();

  console.log("Arithmetic compounds (wide multi-variable chain):");
  console.log(`  neg_y(2.0)                        -> ${evaluateChain(compoundNegY(), [2.0])}  (target -2.0)`);
  console.log(`  x_plus_y(2.0, 3.0)                -> ${evaluateChain(compoundXPlusY(), [2.0, 3.0])}  (target 5.0)`);
  console.log(`  x_times_y(2.0, 3.0)               -> ${evaluateChain(compoundXTimesY(), [2.0, 3.0])}  (target 6.0)`);
  console.log(`  linear_calibration(2.0, 3.0, 1.0) -> ${evaluateChain(compoundLinearCalibration(), [2.0, 3.0, 1.0])}  (target 7.0)`);
  console.log();

  // Tree round-trip
  const tree = branch(ONE, branch(branch(ONE, varX()), ONE));
  const encT = encodeTree(tree);
  const decT = decodeTree(encT);
  console.log("Tree wire format round-trip:");
  console.log(`  ln(x) tree: ${encT.length} bytes`);
  console.log(`  decoded at x=e -> ${evaluateTree(decT, Math.E)}  (target 1.0)`);
  console.log();

  // Restricted chain round-trip
  const ch = getBaseChain("ln(x)");
  const encR = encodeChainRestricted(ch, true);
  const decR = decodeChainRestricted(encR, { selfDescribing: true, variableName: "x" });
  console.log("Restricted chain wire format round-trip:");
  console.log(`  ln(x) chain: ${encR.length} bytes (self-describing)`);
  console.log(`  decoded at x=e -> ${evaluateChain(decR, [Math.E])}  (target 1.0)`);
  console.log();

  // Wide chain round-trip
  const chW = compoundNegY();
  const encW = encodeChainWide(chW);
  const decW = decodeChainWide(encW, ["y"]);
  console.log("Wide multi-variable chain wire format round-trip:");
  console.log(`  neg_y chain: ${encW.length} bytes (header + payload)`);
  console.log(`  decoded at y=2.0 -> ${evaluateChain(decW, [2.0])}  (target -2.0)`);
  console.log();

  console.log("Corpus determinism fingerprints (SHA-256):");
  setPrecisionMode("fast");
  console.log(`  fast      mode (fdlibm, 1-ULP):    ${corpusFingerprint()}`);
  if (precisionModeAvailable()) {
    setPrecisionMode("precision");
    console.log(`  precision mode (crlibm, 0-ULP):    ${corpusFingerprint()}`);
    setPrecisionMode("fast");
  } else {
    console.log(`  precision mode: available under commercial license`);
    console.log(`    (contact licensing@octid.io or see PATENTS.md)`);
  }
}

// (Self-test auto-run removed for ESM compatibility — call selfTest() explicitly if desired.)
