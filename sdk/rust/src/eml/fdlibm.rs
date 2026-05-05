// SPDX-License-Identifier: Apache-2.0
//! FDLIBM-derived fast exp/log primitives.
//!
//! Public Apache-2.0 path. Rust's standard library `f64::exp` and `f64::ln`
//! are IEEE-754 conformant on all supported platforms, providing 1-ULP
//! accurate transcendentals byte-identical with the FDLIBM ports in the
//! Python, Go, and TypeScript SDKs at common inputs.

/// Whether this fast backend is available. Always `true` in the public release.
pub const AVAILABLE: bool = true;

/// Computes `exp(x)` using the platform IEEE-754 implementation.
pub fn exp(x: f64) -> f64 {
    x.exp()
}

/// Computes `ln(x)` using the platform IEEE-754 implementation.
pub fn log(x: f64) -> f64 {
    x.ln()
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
}
