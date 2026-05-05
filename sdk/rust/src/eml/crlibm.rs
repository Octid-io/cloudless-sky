// SPDX-License-Identifier: Apache-2.0
//! CRLIBM precision-mode placeholder.
//!
//! Precision mode (correctly-rounded transcendentals, cross-device
//! deterministic) is provided by a commercial precision pack. This file is
//! a stub in the public release: `AVAILABLE = false`. Calling `exp` or
//! `log` panics; `eml_precise` returns `EmlError::PrecisionUnavailable`
//! before reaching them.
//!
//! Contact ack@octid.io for evaluation access.

/// Whether the commercial precision-mode backend is installed. Public release: `false`.
pub const AVAILABLE: bool = false;

/// Stub: panics in the public release. Reachable only via defense-in-depth paths.
pub fn exp(_x: f64) -> f64 {
    panic!(
        "crlibm precision mode not available in public release; contact ack@octid.io"
    )
}

/// Stub: panics in the public release. Reachable only via defense-in-depth paths.
pub fn log(_x: f64) -> f64 {
    panic!(
        "crlibm precision mode not available in public release; contact ack@octid.io"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[allow(clippy::assertions_on_constants)]
    fn crlibm_unavailable_in_public_release() {
        assert!(!AVAILABLE);
    }

    #[test]
    #[should_panic(expected = "crlibm precision mode not available")]
    fn crlibm_exp_panics() {
        let _ = exp(1.0);
    }

    #[test]
    #[should_panic(expected = "crlibm precision mode not available")]
    fn crlibm_log_panics() {
        let _ = log(1.0);
    }
}
