/*
 * fdlibm.ts — Sun fdlibm-derived exp and log (TypeScript port).
 *
 * Reference implementations of exp(x) and log(x) using Sun fdlibm's argument-
 * reduction + polynomial-approximation algorithm. All constants match Sun's
 * e_exp.c and e_log.c (public domain).
 *
 * Provides byte-exact cross-language determinism with the Python and Go
 * ports. Uses only IEEE-754-exact basic arithmetic plus frexp/ldexp
 * primitives implemented via DataView bit manipulation — which is
 * platform-independent at the IEEE-754 level.
 *
 * SPDX-License-Identifier: Patent-pending
 */

const LN2_HI = 6.93147180369123816490e-01;
const LN2_LO = 1.90821492927058770002e-10;
const INV_LN2 = 1.44269504088896338700e+00;
const P1 = 1.66666666666666019037e-01;
const P2 = -2.77777777770155933842e-03;
const P3 = 6.61375632143793436117e-05;
const P4 = -1.65339022054652515390e-06;
const P5 = 4.13813679705723846039e-08;
const EXP_OVERFLOW_THRESHOLD = 709.782712893383973096;
const EXP_UNDERFLOW_THRESHOLD = -745.133219101941108420;
const SQRT_HALF = 0.70710678118654752440;

const LG1 = 6.666666666666735130e-01;
const LG2 = 3.999999999940941908e-01;
const LG3 = 2.857142874366239149e-01;
const LG4 = 2.222219843214978396e-01;
const LG5 = 1.818357216161805012e-01;
const LG6 = 1.531383769920937332e-01;
const LG7 = 1.479819860511658591e-01;

/**
 * frexp(x) -> [m, e] such that x = m · 2^e and m ∈ [0.5, 1.0) for finite x.
 * Implemented via IEEE-754 bit extraction to guarantee identical behavior
 * across JavaScript engines.
 */
export function frexp(x: number): [number, number] {
  if (x === 0 || !isFinite(x) || isNaN(x)) return [x, 0];
  const buf = new ArrayBuffer(8);
  const dv = new DataView(buf);
  dv.setFloat64(0, x, true);
  const hi = dv.getUint32(4, true);
  const rawExp = (hi >>> 20) & 0x7FF;
  if (rawExp === 0) {
    // Subnormal: scale up by 2^54 and recurse
    const scaled = x * 18014398509481984; // 2^54
    dv.setFloat64(0, scaled, true);
    const hi2 = dv.getUint32(4, true);
    const rawExp2 = (hi2 >>> 20) & 0x7FF;
    const e = rawExp2 - 1022 - 54;
    const newHi = (hi2 & 0x800FFFFF) | (1022 << 20);
    dv.setUint32(4, newHi, true);
    return [dv.getFloat64(0, true), e];
  }
  const e = rawExp - 1022;
  const newHi = (hi & 0x800FFFFF) | (1022 << 20);
  dv.setUint32(4, newHi, true);
  return [dv.getFloat64(0, true), e];
}

/**
 * ldexp(y, k) -> y · 2^k, via IEEE-754 bit manipulation.
 */
export function ldexp(y: number, k: number): number {
  if (y === 0 || !isFinite(y) || isNaN(y)) return y;
  if (k > 1023) return y > 0 ? Infinity : -Infinity;
  if (k < -1074) return 0;
  const buf = new ArrayBuffer(8);
  const dv = new DataView(buf);
  dv.setFloat64(0, y, true);
  const hi = dv.getUint32(4, true);
  const rawExp = (hi >>> 20) & 0x7FF;
  if (rawExp === 0) {
    // Subnormal y — rescale via multiplication
    const scaled = y * 18014398509481984; // 2^54
    dv.setFloat64(0, scaled, true);
    const hi2 = dv.getUint32(4, true);
    const rawExp2 = (hi2 >>> 20) & 0x7FF;
    const newExp = rawExp2 + k - 54;
    if (newExp <= 0) return 0;
    if (newExp >= 2047) return y > 0 ? Infinity : -Infinity;
    dv.setUint32(4, (hi2 & 0x800FFFFF) | (newExp << 20), true);
    return dv.getFloat64(0, true);
  }
  const newExp = rawExp + k;
  if (newExp <= 0) return 0; // underflow to 0 (skip subnormal support)
  if (newExp >= 2047) return y > 0 ? Infinity : -Infinity;
  dv.setUint32(4, (hi & 0x800FFFFF) | (newExp << 20), true);
  return dv.getFloat64(0, true);
}

const TWO_TO_NEG_28 = ldexp(1.0, -28);
const TWO_TO_NEG_20 = ldexp(1.0, -20);

/** exp(x) — Sun fdlibm algorithm, byte-exact with Python and Go ports. */
export function exp(x: number): number {
  if (isNaN(x)) return x;
  if (x === Infinity) return x;
  if (x === -Infinity) return 0.0;
  if (x > EXP_OVERFLOW_THRESHOLD) return Infinity;
  if (x < EXP_UNDERFLOW_THRESHOLD) return 0.0;
  if (x === 0.0) return 1.0;
  if (x > -TWO_TO_NEG_28 && x < TWO_TO_NEG_28) return 1.0 + x;

  // Argument reduction
  let k: number;
  if (x >= 0) k = Math.trunc(x * INV_LN2 + 0.5);
  else k = Math.trunc(x * INV_LN2 - 0.5);
  const fk = k;
  const hi = x - fk * LN2_HI;
  const lo = fk * LN2_LO;
  const r = hi - lo;

  const t = r * r;
  const c = r - t * (P1 + t * (P2 + t * (P3 + t * (P4 + t * P5))));
  let y: number;
  if (k === 0) y = 1.0 - ((r * c) / (c - 2.0) - r);
  else y = 1.0 - ((lo - (r * c) / (2.0 - c)) - hi);

  return ldexp(y, k);
}

/** log(x) for x > 0 — Sun fdlibm algorithm, byte-exact with Python and Go ports. */
export function log(x: number): number {
  if (isNaN(x)) return x;
  if (x === 0.0) return -Infinity;
  if (x < 0.0) return NaN;
  if (x === Infinity) return x;

  let [m, k] = frexp(x);
  if (m < SQRT_HALF) {
    m *= 2.0;
    k--;
  }
  const f = m - 1.0;

  if (f > -TWO_TO_NEG_20 && f < TWO_TO_NEG_20) {
    if (f === 0.0) {
      if (k === 0) return 0.0;
      const dk = k;
      return dk * LN2_HI + dk * LN2_LO;
    }
    const R = f * f * (0.5 - f * (1.0 / 3.0));
    if (k === 0) return f - R;
    const dk = k;
    return dk * LN2_HI - ((R - dk * LN2_LO) - f);
  }

  const s = f / (2.0 + f);
  const z = s * s;
  const w = z * z;
  const t1 = w * (LG2 + w * (LG4 + w * LG6));
  const t2 = z * (LG1 + w * (LG3 + w * (LG5 + w * LG7)));
  const R = t2 + t1;
  const hfsq = 0.5 * f * f;
  if (k === 0) return f - (hfsq - s * (hfsq + R));
  const dk = k;
  return dk * LN2_HI - ((hfsq - (s * (hfsq + R) + dk * LN2_LO)) - f);
}
