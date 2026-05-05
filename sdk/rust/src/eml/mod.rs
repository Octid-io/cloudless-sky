// SPDX-License-Identifier: Apache-2.0
//! eml — Universal Binary Operator Evaluator (public reference).
//!
//! `eml(x, y) = exp(x) − ln(y)`. The universal binary operator at the heart
//! of OSMP's compute-by-wire layer. The public [`eml`] function evaluates
//! this with the fast (FDLIBM-derived, 1-ULP) backend; [`eml_precise`] is
//! the gated precision-mode entry point that returns
//! [`EmlError::PrecisionUnavailable`] in the public release.
//!
//! Cross-SDK byte-identical with the Python, Go, and TypeScript SDKs at
//! common inputs.

pub mod crlibm;
pub mod fdlibm;
pub mod mdr;

pub use crlibm::{exp as precise_exp, log as precise_log, AVAILABLE as PRECISE_AVAILABLE};
pub use fdlibm::{exp as fast_exp, log as fast_log, AVAILABLE as FAST_AVAILABLE};
pub use mdr::{eml_corpus_lookup, EmlMdrEntry};

/// Errors returned by precision-gated eml entry points.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EmlError {
    /// The commercial precision-mode backend is not installed in this build.
    PrecisionUnavailable,
}

impl std::fmt::Display for EmlError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EmlError::PrecisionUnavailable => f.write_str(
                "eml precision mode requires the commercial precision pack; \
                 contact ack@octid.io",
            ),
        }
    }
}

impl std::error::Error for EmlError {}

/// Evaluates the universal binary operator using the fast backend.
///
/// `eml(x, y) = exp(x) − ln(y)`. Public default; cross-SDK byte-identical
/// with the Go, Python, and TypeScript fast-mode evaluators.
pub fn eml(x: f64, y: f64) -> f64 {
    fast_exp(x) - fast_log(y)
}

/// Evaluates the universal binary operator using the precision-mode backend.
///
/// Returns [`EmlError::PrecisionUnavailable`] in the public release. The
/// commercial precision pack replaces the [`crlibm`] module to enable this
/// path; behaviour and signatures are otherwise identical.
pub fn eml_precise(x: f64, y: f64) -> Result<f64, EmlError> {
    if !PRECISE_AVAILABLE {
        return Err(EmlError::PrecisionUnavailable);
    }
    Ok(precise_exp(x) - precise_log(y))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eml_zero_one_is_one() {
        // eml(0, 1) = exp(0) − ln(1) = 1 − 0 = 1.
        assert_eq!(eml(0.0, 1.0), 1.0);
    }

    #[test]
    fn eml_one_one() {
        // eml(1, 1) = e − 0 = e.
        let v = eml(1.0, 1.0);
        assert!((v - std::f64::consts::E).abs() < 1e-15);
    }

    #[test]
    fn eml_precise_unavailable_in_public_release() {
        match eml_precise(0.0, 1.0) {
            Err(EmlError::PrecisionUnavailable) => {}
            other => panic!("expected PrecisionUnavailable, got {other:?}"),
        }
    }

    #[test]
    fn fast_backend_available() {
        assert!(FAST_AVAILABLE);
    }

    #[test]
    fn precise_backend_unavailable_in_public_release() {
        assert!(!PRECISE_AVAILABLE);
    }

    #[test]
    fn corpus_lookup_h_hr_via_reexport() {
        let entry = eml_corpus_lookup("H", "HR").expect("H:HR must be present");
        assert_eq!(entry.eml_x, 1.0);
        assert_eq!(entry.eml_y, 1.0);
    }
}
