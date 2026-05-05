//! OSMP BAEL — Bandwidth-Agnostic Efficiency Layer.
//!
//! Selects the wire mode (FULL_OSMP / TCL_ONLY / NL_PASSTHROUGH) for a
//! single message based on UTF-8 byte counts and an ESTOP atomic floor.
//! `R:ESTOP@*` always returns NL_PASSTHROUGH so the receiver does not need
//! the dictionary to act on the emergency-stop directive.
//!
//! Cross-SDK byte-identical mode flag values with Go and TypeScript:
//!   FullOSMP      = 0x00
//!   TCLOnly       = 0x02
//!   NLPassthrough = 0x04
//!
//! License: Apache-2.0

use crate::types::FLAG_NL_PASSTHROUGH;

/// Wire-format mode for an emitted SAL message.
///
/// Values are pinned to the Go/TS BAELMode flag bytes to keep the wire
/// representation byte-identical across SDKs.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BAELMode {
    /// Full SAL with adaptive shared dictionary semantics.
    FullOSMP = 0x00,
    /// Truncated component layer only.
    TCLOnly = 0x02,
    /// Natural-language passthrough for receivers without OSMP support.
    NLPassthrough = 0x04,
}

/// Output of a single BAEL selection.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BAELResult {
    /// The selected mode.
    pub mode: BAELMode,
    /// The chosen wire payload string.
    pub payload: String,
    /// The fragment-flags byte to attach when the message hits the wire.
    pub flags_byte: u8,
}

/// BAEL encoder selector.
#[derive(Debug, Default, Clone)]
pub struct BAELEncoder;

impl BAELEncoder {
    /// Construct a default encoder.
    pub fn new() -> Self {
        BAELEncoder
    }

    /// Choose a wire mode for a single message.
    ///
    /// Inputs:
    /// * `nl`  — natural-language form of the instruction.
    /// * `sal` — OSMP/SAL-encoded form of the same instruction.
    /// * `peer_caps` — peer capability hint. Recognised values:
    ///   - empty / `"FULL"` / `"FULL_OSMP"` / `"OSMP"` — peer supports SAL.
    ///   - `"TCL_ONLY"` — peer supports SAL+TCL but not full OSMP semantics.
    ///   - `"NL_ONLY"` / `"NO_OSMP"` — peer is dictionary-less; force
    ///     NL passthrough.
    ///
    /// ESTOP precedence: any `R:ESTOP@*` payload (in either `nl` or `sal`)
    /// returns `NLPassthrough` regardless of capability or size, with the
    /// NL form preferred when present.
    pub fn select_mode(&self, nl: &str, sal: &str, peer_caps: &str) -> BAELResult {
        // ESTOP atomic floor — no dictionary required at the receiver.
        if sal.contains("R:ESTOP") || nl.contains("R:ESTOP") {
            let payload = if !nl.is_empty() {
                nl.to_string()
            } else {
                sal.to_string()
            };
            return BAELResult {
                mode: BAELMode::NLPassthrough,
                payload,
                flags_byte: FLAG_NL_PASSTHROUGH,
            };
        }

        let caps = peer_caps.to_ascii_uppercase();
        if matches!(caps.as_str(), "NL_ONLY" | "NO_OSMP") {
            return BAELResult {
                mode: BAELMode::NLPassthrough,
                payload: nl.to_string(),
                flags_byte: FLAG_NL_PASSTHROUGH,
            };
        }

        let nl_b = utf8_bytes(nl);
        let sal_b = utf8_bytes(sal);
        // No separate TCL form here; mirror Python's tcl_b = osmp_b + 1
        // sentinel, which keeps TCL_ONLY out of the comparison unless an
        // explicit TCL string is supplied (a future overload may take it).
        let tcl_b = sal_b + 1;

        if nl_b <= sal_b && nl_b <= tcl_b {
            return BAELResult {
                mode: BAELMode::NLPassthrough,
                payload: nl.to_string(),
                flags_byte: FLAG_NL_PASSTHROUGH,
            };
        }
        if matches!(caps.as_str(), "TCL_ONLY") && tcl_b < sal_b {
            return BAELResult {
                mode: BAELMode::TCLOnly,
                payload: sal.to_string(),
                flags_byte: 0x00,
            };
        }
        BAELResult {
            mode: BAELMode::FullOSMP,
            payload: sal.to_string(),
            flags_byte: 0x00,
        }
    }
}

/// UTF-8 byte count of a string. Canonical measurement basis used by every
/// OSMP SDK for BAEL comparisons.
pub fn utf8_bytes(s: &str) -> usize {
    s.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn estop_returns_nl_passthrough() {
        let enc = BAELEncoder::new();
        let r = enc.select_mode("emergency stop now", "R:ESTOP@*", "FULL");
        assert_eq!(r.mode, BAELMode::NLPassthrough);
        assert_eq!(r.flags_byte, FLAG_NL_PASSTHROUGH);
        assert_eq!(r.payload, "emergency stop now");
    }

    #[test]
    fn estop_with_empty_nl_falls_back_to_sal() {
        let enc = BAELEncoder::new();
        let r = enc.select_mode("", "R:ESTOP@*", "");
        assert_eq!(r.mode, BAELMode::NLPassthrough);
        assert_eq!(r.payload, "R:ESTOP@*");
    }

    #[test]
    fn nl_only_peer_forces_passthrough() {
        let enc = BAELEncoder::new();
        let r = enc.select_mode(
            "patient heart rate is 78 beats per minute",
            "H:HR[78]",
            "NL_ONLY",
        );
        assert_eq!(r.mode, BAELMode::NLPassthrough);
        assert_eq!(r.flags_byte, FLAG_NL_PASSTHROUGH);
    }

    #[test]
    fn osmp_chosen_when_smaller() {
        let enc = BAELEncoder::new();
        let r = enc.select_mode(
            "patient heart rate is 78 beats per minute",
            "H:HR[78]",
            "FULL",
        );
        assert_eq!(r.mode, BAELMode::FullOSMP);
        assert_eq!(r.flags_byte, 0x00);
        assert_eq!(r.payload, "H:HR[78]");
    }

    #[test]
    fn nl_chosen_when_shorter() {
        let enc = BAELEncoder::new();
        // NL is shorter than the SAL encoding — passthrough wins.
        let r = enc.select_mode(
            "ok",
            "A:LONGER_OPCODE_THAN_NEEDED",
            "FULL",
        );
        assert_eq!(r.mode, BAELMode::NLPassthrough);
    }

    #[test]
    fn mode_flag_byte_values_match_cross_sdk() {
        assert_eq!(BAELMode::FullOSMP as u8, 0x00);
        assert_eq!(BAELMode::TCLOnly as u8, 0x02);
        assert_eq!(BAELMode::NLPassthrough as u8, 0x04);
    }
}
