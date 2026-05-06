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

pub mod chain;
pub mod crlibm;
pub mod fdlibm;
pub mod mdr;

pub use chain::{
    decode_chain_restricted, decode_chain_wide, encode_chain_restricted, encode_chain_wide,
    Chain, ChainLevel, ChainVariant,
};

pub use crlibm::{exp as precise_exp, log as precise_log, AVAILABLE as PRECISE_AVAILABLE};
pub use fdlibm::{exp as fast_exp, log as fast_log, AVAILABLE as FAST_AVAILABLE};
pub use mdr::{
    corpus_fingerprint_envelope_bounded, corpus_fingerprint_mdr, in_bit_exact_corpus,
    lookup as mdr_lookup, macro_count, EnvelopeBound, FingerprintMembership, FunctionClass,
    MacroDefinition, ParametricChain, PrecisionClass, VariantTag, CANONICAL_INPUTS_MDR,
    REGISTRY,
};

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
    #[allow(clippy::assertions_on_constants)]
    fn fast_backend_available() {
        assert!(FAST_AVAILABLE);
    }

    #[test]
    #[allow(clippy::assertions_on_constants)]
    fn precise_backend_unavailable_in_public_release() {
        assert!(!PRECISE_AVAILABLE);
    }

    #[test]
    fn mdr_lookup_exp_via_reexport() {
        let m = mdr_lookup("EXP").expect("EXP must be present");
        assert_eq!(m.shorthand_id, "EXP");
        assert_eq!(m.function_class, FunctionClass::CompoundArithmetic);
    }

    #[test]
    fn mdr_macro_count_is_89() {
        assert_eq!(macro_count(), 89);
    }
}
