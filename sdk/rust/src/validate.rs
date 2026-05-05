//! Composition validator — deterministic rule checks on a composed SAL string.
//!
//! Cross-SDK byte-identical with Python `validate_composition`, Go
//! `ValidateComposition`, TypeScript `validateComposition`. The rule set
//! mirrors the eight checks documented in the Go validator; the regex
//! building blocks live alongside in `sal_patterns.rs`.
//!
//! License: Apache-2.0

use crate::asd::AdaptiveSharedDictionary;
use crate::macros::MacroRegistry;
use crate::sal_patterns::{frame_ns_op_re, frame_split_re, ns_target_re};

/// Severity classification for a composition issue.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Severity {
    /// Blocks emission — composition is invalid.
    Error,
    /// Advisory — composition still emits but the issue is logged.
    Warning,
}

/// A single issue surfaced by `validate_composition`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompositionIssue {
    /// Rule identifier — stable across SDKs (e.g. "HALLUCINATED_OPCODE").
    pub rule: String,
    /// Severity of this issue.
    pub severity: Severity,
    /// Human-readable description.
    pub message: String,
    /// Offending fragment, when available.
    pub fragment: Option<String>,
}

/// Aggregate result of running the composition validator over a SAL string.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompositionResult {
    /// True when no `Error`-severity issue was found.
    pub valid: bool,
    /// Every issue surfaced (errors and warnings, in encounter order).
    pub issues: Vec<CompositionIssue>,
}

impl CompositionResult {
    /// Returns only the `Error`-severity issues.
    pub fn errors(&self) -> Vec<&CompositionIssue> {
        self.issues
            .iter()
            .filter(|i| i.severity == Severity::Error)
            .collect()
    }

    /// Returns only the `Warning`-severity issues.
    pub fn warnings(&self) -> Vec<&CompositionIssue> {
        self.issues
            .iter()
            .filter(|i| i.severity == Severity::Warning)
            .collect()
    }
}

/// Operator tokens that should be skipped when iterating frames.
fn is_operator_token(token: &str) -> bool {
    matches!(
        token,
        "\u{2192}" | "\u{2227}" | "\u{2228}" | "\u{2194}" | "\u{2225}" | ";"
    )
}

/// Validate a composed SAL chain.
///
/// Rules implemented:
/// 1. SLASH_OPERATOR — `/` is not a SAL operator
/// 2. NAMESPACE_AS_TARGET — `@NS:OP` is invalid (target must be a node id or `*`)
/// 3. HALLUCINATED_OPCODE — every `NS:OP` must exist in the ASD
/// 4. CONSEQUENCE_CLASS_OMISSION — R-namespace frames need ⚠/↺/⊘ (except R:ESTOP)
/// 5. AUTHORIZATION_OMISSION — chains containing ⚠/⊘ require I:§
/// 6. BYTE_INFLATION — SAL bytes must be < NL bytes (unless safety-exempt)
/// 7. MIXED_MODE — embedded natural language inside a frame
///
/// `enforce_strict` reserved for stricter dependency rule application; the
/// macro registry argument is currently unused but kept on the signature for
/// API parity with the other SDKs.
pub fn validate_composition(
    sal: &str,
    nl: &str,
    _macro_registry: Option<&MacroRegistry>,
    enforce_strict: bool,
    asd: Option<&AdaptiveSharedDictionary>,
) -> CompositionResult {
    let owned;
    let asd_ref: &AdaptiveSharedDictionary = match asd {
        Some(a) => a,
        None => {
            owned = AdaptiveSharedDictionary::new();
            &owned
        }
    };

    let mut issues: Vec<CompositionIssue> = Vec::new();

    // Rule: SLASH_OPERATOR
    if sal.contains('/') {
        issues.push(CompositionIssue {
            rule: "SLASH_OPERATOR".to_string(),
            severity: Severity::Error,
            message: "/ is not a SAL operator. Use \u{2192} for THEN, \u{2227} for AND, \u{2228} for OR.".to_string(),
            fragment: Some(sal.to_string()),
        });
    }

    // Rule: NAMESPACE_AS_TARGET
    for caps in ns_target_re().captures_iter(sal) {
        let ns = caps.get(1).map(|m| m.as_str()).unwrap_or("");
        let op = caps.get(2).map(|m| m.as_str()).unwrap_or("");
        issues.push(CompositionIssue {
            rule: "NAMESPACE_AS_TARGET".to_string(),
            severity: Severity::Error,
            message: format!(
                "@ target must be a node_id or *, not a namespace:opcode. Found @{ns}:{op}"
            ),
            fragment: Some(format!("@{ns}:{op}")),
        });
    }

    // Split into frames on operator glyphs.
    let parts: Vec<&str> = frame_split_re().split(sal).collect();
    let mut frames: Vec<&str> = Vec::new();
    for raw in parts {
        let trimmed = raw.trim();
        if !trimmed.is_empty() && !is_operator_token(trimmed) {
            frames.push(trimmed);
        }
    }

    let mut has_r_namespace = false;
    let mut has_r_haz_or_irr = false;
    let mut has_i_section = false;

    for frame in &frames {
        let cap = match frame_ns_op_re().captures(frame) {
            Some(c) => c,
            None => {
                // Frame doesn't start with NS:OP — flag if it looks like
                // embedded natural language.
                if frame.len() > 20 && frame.contains(' ') {
                    let trunc: String = if frame.chars().count() > 40 {
                        frame.chars().take(40).collect::<String>() + "..."
                    } else {
                        (*frame).to_string()
                    };
                    issues.push(CompositionIssue {
                        rule: "MIXED_MODE".to_string(),
                        severity: Severity::Warning,
                        message: format!(
                            "Frame appears to contain embedded natural language: '{trunc}'"
                        ),
                        fragment: Some((*frame).to_string()),
                    });
                }
                continue;
            }
        };
        let ns = cap.get(1).map(|m| m.as_str()).unwrap_or("");
        let op = cap.get(2).map(|m| m.as_str()).unwrap_or("");

        // Rule: HALLUCINATED_OPCODE (I:§ is the human-authorization marker
        // and bypasses ASD lookup — it's a structural primitive, not an opcode).
        if !(ns == "I" && op == "\u{00a7}") && asd_ref.lookup(ns, op).is_none() {
            issues.push(CompositionIssue {
                rule: "HALLUCINATED_OPCODE".to_string(),
                severity: Severity::Error,
                message: format!(
                    "{ns}:{op} does not exist in the Adaptive Shared Dictionary."
                ),
                fragment: Some((*frame).to_string()),
            });
        }

        if ns == "R" {
            has_r_namespace = true;
            if op != "ESTOP" {
                let has_cc = frame.contains('\u{26a0}')
                    || frame.contains('\u{21ba}')
                    || frame.contains('\u{2298}');
                if !has_cc {
                    issues.push(CompositionIssue {
                        rule: "CONSEQUENCE_CLASS_OMISSION".to_string(),
                        severity: Severity::Error,
                        message: format!(
                            "R:{op} requires a consequence class designator (\u{26a0}/\u{21ba}/\u{2298}). R:ESTOP is the sole exception."
                        ),
                        fragment: Some((*frame).to_string()),
                    });
                }
                if frame.contains('\u{26a0}') || frame.contains('\u{2298}') {
                    has_r_haz_or_irr = true;
                }
            }
        }

        if ns == "I" && op == "\u{00a7}" {
            has_i_section = true;
        }
    }

    // Rule: AUTHORIZATION_OMISSION
    if has_r_haz_or_irr && !has_i_section {
        issues.push(CompositionIssue {
            rule: "AUTHORIZATION_OMISSION".to_string(),
            severity: Severity::Error,
            message: "R namespace instructions with \u{26a0} (HAZARDOUS) or \u{2298} (IRREVERSIBLE) require I:\u{00a7} as a structural precondition in the instruction chain.".to_string(),
            fragment: None,
        });
    }

    // Rule: BYTE_INFLATION
    if !nl.is_empty() {
        let sal_bytes = sal.len();
        let nl_bytes = nl.len();
        if sal_bytes >= nl_bytes {
            // r_safety_exempt mirrored from the Go signature: when strict
            // enforcement is off and the chain is an R-namespace safety
            // sequence, downgrade to advisory.
            if !enforce_strict && has_r_namespace {
                issues.push(CompositionIssue {
                    rule: "BYTE_CHECK_EXEMPT".to_string(),
                    severity: Severity::Warning,
                    message: format!(
                        "SAL ({sal_bytes}B) >= NL ({nl_bytes}B). Exempt: safety-complete R namespace chain."
                    ),
                    fragment: None,
                });
            } else {
                issues.push(CompositionIssue {
                    rule: "BYTE_INFLATION".to_string(),
                    severity: Severity::Error,
                    message: format!(
                        "SAL ({sal_bytes}B) >= NL ({nl_bytes}B). Use NL_PASSTHROUGH. BAEL compression floor guarantee violated."
                    ),
                    fragment: None,
                });
            }
        }
    }

    let valid = issues.iter().all(|i| i.severity != Severity::Error);
    CompositionResult { valid, issues }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hallucinated_opcode_caught() {
        let result = validate_composition("H:NOTREAL", "alert", None, true, None);
        assert!(!result.valid, "H:NOTREAL must be rejected");
        assert!(
            result
                .issues
                .iter()
                .any(|i| i.rule == "HALLUCINATED_OPCODE"),
            "issues: {:?}",
            result.issues,
        );
    }

    #[test]
    fn namespace_as_target_caught() {
        let result =
            validate_composition("H:CASREP@H:ICD[J93.0]", "report", None, true, None);
        assert!(!result.valid, "namespace-as-target must be rejected");
        assert!(
            result
                .issues
                .iter()
                .any(|i| i.rule == "NAMESPACE_AS_TARGET")
        );
    }

    #[test]
    fn r_namespace_missing_consequence_class_caught() {
        let result = validate_composition("R:MOV@BOT1", "move robot one", None, true, None);
        assert!(!result.valid);
        assert!(
            result
                .issues
                .iter()
                .any(|i| i.rule == "CONSEQUENCE_CLASS_OMISSION")
        );
    }

    #[test]
    fn r_estop_no_consequence_class_required() {
        let result = validate_composition("R:ESTOP", "emergency stop", None, true, None);
        // R:ESTOP doesn't require a CC; the only failure path here would be
        // BYTE_INFLATION (8B SAL vs 14B NL — 8 < 14, so it's fine).
        assert!(
            result.errors().is_empty(),
            "R:ESTOP must validate clean; got {:?}",
            result.issues
        );
    }

    #[test]
    fn slash_operator_caught() {
        let result =
            validate_composition("H:HR/H:BP", "heart rate slash blood pressure", None, true, None);
        assert!(!result.valid);
        assert!(result.issues.iter().any(|i| i.rule == "SLASH_OPERATOR"));
    }

    #[test]
    fn r_hazardous_without_authorization_caught() {
        let result = validate_composition(
            "R:MOV@BOT1\u{26a0}",
            "move robot one hazardously without authorization",
            None,
            true,
            None,
        );
        assert!(!result.valid);
        assert!(
            result
                .issues
                .iter()
                .any(|i| i.rule == "AUTHORIZATION_OMISSION")
        );
    }

    #[test]
    fn valid_chain_passes() {
        let result = validate_composition(
            "H:HR\u{2227}H:BP",
            "report heart rate and blood pressure together",
            None,
            true,
            None,
        );
        assert!(
            result.valid,
            "valid composition should pass: {:?}",
            result.issues
        );
    }

    #[test]
    fn byte_inflation_caught_when_sal_longer_than_nl() {
        // SAL is much longer than the trivial NL.
        let result = validate_composition("H:HR\u{2227}H:BP\u{2227}H:SPO2", "x", None, true, None);
        assert!(!result.valid);
        assert!(result.issues.iter().any(|i| i.rule == "BYTE_INFLATION"));
    }
}
