// SPDX-License-Identifier: Apache-2.0
// The constants below are reproduced verbatim from Sun fdlibm `e_exp.c` /
// `e_log.c` (public domain) so that Rust's f64 parser produces the same
// IEEE-754 bit pattern that Python's fdlibm.py / Go's eml/fdlibm.go /
// TypeScript's fdlibm.ts emit. Clippy's `excessive_precision` lint flags
// literals with more decimal digits than f64 can represent, but the parser
// rounds to the same nearest-representable value either way; truncating the
// literal source would obscure the cross-SDK correspondence without
// changing the runtime value. INV_LN2 and SQRT_HALF coincide with the
// `std::f64::consts` named constants, so `approx_constant` fires there too.
#![allow(clippy::excessive_precision, clippy::approx_constant)]

//! FDLIBM-derived fast exp/log primitives — pure-Rust port of the Sun fdlibm
//! algorithm.
//!
//! Constants from Sun fdlibm `e_exp.c` and `e_log.c` (public domain). The
//! algorithm is a direct port of the Python reference at
//! `sdk/python/osmp/fdlibm.py`, which is itself a faithful port of the same
//! Sun fdlibm code paths used by Go's `osmp/eml/fdlibm` and TypeScript's
//! `osmp/fdlibm` modules.
//!
//! Argument reduction, polynomial evaluation, and reconstruction use only
//! IEEE-754 basic arithmetic (`+`, `-`, `*`, `/`) plus bit-level
//! `frexp` / `ldexp` implemented via direct manipulation of the f64 binary
//! representation. No platform `f64::exp` / `f64::ln` calls — those are
//! correctly-rounded on glibc, 1-ULP on Go's `math`, and platform-dependent on
//! Windows MSVC, which would break cross-device byte-identicalness.
//!
//! Cross-SDK byte-identical with Python `osmp.fdlibm`, Go
//! `osmp/eml/fdlibm`, and TypeScript `osmp/fdlibm` for all common-input
//! exp / log evaluations.

/// Whether this fast backend is available. Always `true` in the public release.
pub const AVAILABLE: bool = true;

// ── exp() constants (Sun fdlibm e_exp.c) ────────────────────────────

const LN2_HI: f64 = 6.93147180369123816490e-01;
const LN2_LO: f64 = 1.90821492927058770002e-10;
const INV_LN2: f64 = 1.44269504088896338700e+00;
const P1: f64 = 1.66666666666666019037e-01;
const P2: f64 = -2.77777777770155933842e-03;
const P3: f64 = 6.61375632143793436117e-05;
const P4: f64 = -1.65339022054652515390e-06;
const P5: f64 = 4.13813679705723846039e-08;
const EXP_OVERFLOW_THRESHOLD: f64 = 709.782712893383973096;
const EXP_UNDERFLOW_THRESHOLD: f64 = -745.133219101941108420;

// ── log() constants (Sun fdlibm e_log.c) ────────────────────────────

const LG1: f64 = 6.666666666666735130e-01;
const LG2: f64 = 3.999999999940941908e-01;
const LG3: f64 = 2.857142874366239149e-01;
const LG4: f64 = 2.222219843214978396e-01;
const LG5: f64 = 1.818357216161805012e-01;
const LG6: f64 = 1.531383769920937332e-01;
const LG7: f64 = 1.479819860511658591e-01;
const SQRT_HALF: f64 = 0.70710678118654752440;

// ── frexp / ldexp (bit-level, deterministic) ────────────────────────

/// Return `(mantissa, exponent)` such that `x = mantissa * 2^exponent` with
/// `0.5 <= |mantissa| < 1.0` for finite nonzero `x`. Matches Python `math.frexp`.
fn frexp(x: f64) -> (f64, i32) {
    if x == 0.0 || !x.is_finite() {
        return (x, 0);
    }
    let bits = x.to_bits();
    let raw_exp = ((bits >> 52) & 0x7FF) as i32;
    if raw_exp == 0 {
        // Subnormal: scale up by 2^54, recurse, adjust exponent back.
        let scaled = x * f64::from_bits(0x4350_0000_0000_0000); // 2^54
        let (m, e) = frexp(scaled);
        return (m, e - 54);
    }
    // Replace biased exponent with 0x3FE (which decodes to 2^-1), so the
    // resulting f64 lies in [0.5, 1.0). Mantissa bits and sign bit are kept.
    let mantissa_bits = (bits & 0x800F_FFFF_FFFF_FFFF) | (0x3FE_u64 << 52);
    (f64::from_bits(mantissa_bits), raw_exp - 1022)
}

/// Return `x * 2^k`. Saturates to ±infinity or signed zero on extreme `k`.
/// Matches Python `math.ldexp`.
fn ldexp(x: f64, k: i32) -> f64 {
    if x == 0.0 || !x.is_finite() {
        return x;
    }
    if k >= 1024 {
        return f64::INFINITY.copysign(x);
    }
    if k <= -1075 {
        return 0.0_f64.copysign(x);
    }
    if k >= -1022 {
        x * f64::from_bits(((k + 1023) as u64) << 52)
    } else {
        // Subnormal range: chain two multiplications so each scale fits the
        // normal exponent range.
        let half_k = k / 2;
        let other_k = k - half_k;
        x * f64::from_bits(((half_k + 1023) as u64) << 52)
            * f64::from_bits(((other_k + 1023) as u64) << 52)
    }
}

// ── exp(x) ──────────────────────────────────────────────────────────

/// Computes `exp(x)` using Sun fdlibm's argument reduction + degree-5
/// polynomial. Cross-SDK byte-identical with Python / Go / TypeScript.
pub fn exp(x: f64) -> f64 {
    if x.is_nan() {
        return x;
    }
    if x == f64::INFINITY {
        return x;
    }
    if x == f64::NEG_INFINITY {
        return 0.0;
    }
    if x > EXP_OVERFLOW_THRESHOLD {
        return f64::INFINITY;
    }
    if x < EXP_UNDERFLOW_THRESHOLD {
        return 0.0;
    }
    if x == 0.0 {
        return 1.0;
    }

    // 2^-28 — small-input shortcut. Pre-computed bit pattern avoids
    // depending on the platform's `f64::powi`.
    let small = f64::from_bits(0x3E30_0000_0000_0000); // 2^-28
    if x > -small && x < small {
        return 1.0 + x;
    }

    let k = if x >= 0.0 {
        (x * INV_LN2 + 0.5) as i32
    } else {
        (x * INV_LN2 - 0.5) as i32
    };

    let hi = x - (k as f64) * LN2_HI;
    let lo = (k as f64) * LN2_LO;
    let r = hi - lo;

    let t = r * r;
    let c = r - t * (P1 + t * (P2 + t * (P3 + t * (P4 + t * P5))));

    let y = if k == 0 {
        1.0 - ((r * c) / (c - 2.0) - r)
    } else {
        1.0 - ((lo - (r * c) / (2.0 - c)) - hi)
    };

    ldexp(y, k)
}

// ── log(x) ──────────────────────────────────────────────────────────

/// Computes `ln(x)` using Sun fdlibm's argument reduction + degree-7
/// polynomial. Cross-SDK byte-identical with Python / Go / TypeScript.
/// Returns `NaN` for `x < 0`, `-INFINITY` for `x == 0`.
pub fn log(x: f64) -> f64 {
    if x.is_nan() {
        return x;
    }
    if x == 0.0 {
        return f64::NEG_INFINITY;
    }
    if x < 0.0 {
        return f64::NAN;
    }
    if x == f64::INFINITY {
        return x;
    }

    let (mut m, mut k) = frexp(x);
    if m < SQRT_HALF {
        m *= 2.0;
        k -= 1;
    }

    let f = m - 1.0;
    let small = f64::from_bits(0x3EB0_0000_0000_0000); // 2^-20

    if f.abs() < small {
        if f == 0.0 {
            if k == 0 {
                return 0.0;
            }
            let dk = k as f64;
            return dk * LN2_HI + dk * LN2_LO;
        }
        let r = f * f * (0.5 - f * (1.0 / 3.0));
        if k == 0 {
            return f - r;
        }
        let dk = k as f64;
        return dk * LN2_HI - ((r - dk * LN2_LO) - f);
    }

    let s = f / (2.0 + f);
    let z = s * s;
    let w = z * z;
    let t1 = w * (LG2 + w * (LG4 + w * LG6));
    let t2 = z * (LG1 + w * (LG3 + w * (LG5 + w * LG7)));
    let r = t2 + t1;
    let hfsq = 0.5 * f * f;
    if k == 0 {
        return f - (hfsq - s * (hfsq + r));
    }
    let dk = k as f64;
    dk * LN2_HI - ((hfsq - (s * (hfsq + r) + dk * LN2_LO)) - f)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[allow(clippy::assertions_on_constants)]
    fn fdlibm_available() {
        assert!(AVAILABLE);
    }

    #[test]
    fn exp_zero_is_one() {
        assert_eq!(exp(0.0), 1.0);
    }

    #[test]
    fn log_one_is_zero() {
        assert_eq!(log(1.0), 0.0);
    }

    #[test]
    fn exp_one_is_e() {
        // Python fdlibm.exp(1.0) → 2.718281828459045 (one-ulp off true e)
        let v = exp(1.0);
        assert!((v - std::f64::consts::E).abs() < 1e-15);
    }

    #[test]
    fn log_e_is_one() {
        let v = log(std::f64::consts::E);
        assert!((v - 1.0).abs() < 1e-15);
    }

    #[test]
    fn exp_log_roundtrip() {
        for x in [0.5_f64, 1.0, 1.5, 2.0, 3.14159, 10.0] {
            let v = log(exp(x));
            assert!((v - x).abs() < 1e-12, "exp(log({x})) = {v}, expected {x}");
        }
    }

    #[test]
    fn exp_overflow_returns_infinity() {
        assert!(exp(800.0).is_infinite());
    }

    #[test]
    fn exp_underflow_returns_zero() {
        assert_eq!(exp(-800.0), 0.0);
    }

    #[test]
    fn log_zero_is_negative_infinity() {
        assert_eq!(log(0.0), f64::NEG_INFINITY);
    }

    #[test]
    fn log_negative_is_nan() {
        assert!(log(-1.0).is_nan());
    }

    #[test]
    fn frexp_one_is_half_one() {
        let (m, e) = frexp(1.0);
        assert_eq!(m, 0.5);
        assert_eq!(e, 1);
    }

    #[test]
    fn frexp_two_is_half_two() {
        let (m, e) = frexp(2.0);
        assert_eq!(m, 0.5);
        assert_eq!(e, 2);
    }

    #[test]
    fn ldexp_inverse_of_frexp() {
        for x in [0.5_f64, 1.0, 1.5, 2.0, 17.5, 1234.567, 1e-10, 1e10] {
            let (m, e) = frexp(x);
            assert_eq!(ldexp(m, e), x, "ldexp(frexp({x})) round-trip");
        }
    }
}
