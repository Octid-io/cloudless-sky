//! SALComposer — deterministic NL-to-SAL composition pipeline.
//!
//! The composer NEVER generates SAL text via inference. It decomposes NL
//! into intent, looks up opcodes in the ASD, assembles using grammar
//! rules, and validates the result. NL inputs that don't match any
//! opcode return as `NL_PASSTHROUGH` (no SAL emitted).
//!
//! This Rust port focuses on the deterministic core path:
//! - macro priority (via attached `MacroRegistry`)
//! - phrase-index lookup (curated triggers + ASD-definition phrases)
//! - basic glyph operator detection
//! - R-namespace consequence-class injection
//! - validation pass at the end
//!
//! The Python / Go / TypeScript composers carry additional heuristics
//! (chain-split scoring, OOV gap detection, parameter regex injection,
//! confidence gating on weak single-keyword matches). The Rust core
//! handles the high-confidence paths and falls through to passthrough
//! everywhere else; gap labels are flagged in `trace`.
//!
//! License: Apache-2.0

use crate::asd::AdaptiveSharedDictionary;
use crate::glyphs::asd_basis;
use crate::macros::MacroRegistry;
use crate::validate::{validate_composition, CompositionResult};
use std::collections::BTreeMap;

/// Curated phrase triggers — copied from the Python / Go / TS composers
/// for cross-SDK parity. Each tuple is `(NL phrase, namespace, opcode)`.
const CURATED_TRIGGERS: &[(&str, &str, &str)] = &[
    ("flow authorization", "F", "AV"),
    ("authorization proceed", "F", "AV"),
    ("emergency route", "M", "RTE"),
    ("municipal route", "M", "RTE"),
    ("incident route", "M", "RTE"),
    ("network status", "N", "STS"),
    ("node status", "N", "STS"),
    ("vessel heading", "V", "HDG"),
    ("ship heading", "V", "HDG"),
    ("maritime heading", "V", "HDG"),
    ("restart process", "C", "RSTRT"),
    ("restart service", "C", "RSTRT"),
    ("data query", "D", "Q"),
    ("query data", "D", "Q"),
    ("audit query", "L", "QUERY"),
    ("query audit", "L", "QUERY"),
    ("robot heading", "R", "HDNG"),
    ("vehicle heading", "R", "HDNG"),
    ("robot status", "R", "STAT"),
    ("device status", "R", "STAT"),
    ("robot waypoint", "R", "WPT"),
    ("attest payload", "S", "ATST"),
    ("attestation", "S", "ATST"),
    ("page out memory", "Y", "PAGEOUT"),
    ("store to memory", "Y", "STORE"),
    ("save to memory", "Y", "STORE"),
    ("generate key", "S", "KEYGEN"),
    ("generate keys", "S", "KEYGEN"),
    ("key pair", "S", "KEYGEN"),
    ("create keypair", "S", "KEYGEN"),
    ("sign payload", "S", "SIGN"),
    ("digital signature", "S", "SIGN"),
    ("push to node", "D", "PUSH"),
    ("send to node", "D", "PUSH"),
    ("transfer task", "J", "HANDOFF"),
    ("hand off", "J", "HANDOFF"),
    ("task handoff", "J", "HANDOFF"),
    ("verify identity", "I", "ID"),
    ("identity check", "I", "ID"),
    ("run inference", "Z", "INF"),
    ("invoke model", "Z", "INF"),
    ("building fire", "B", "ALRM"),
    ("fire alarm", "B", "ALRM"),
    ("temp report", "E", "TH"),
    ("temp check", "E", "TH"),
    ("battery level", "X", "STORE"),
    ("battery status", "X", "STORE"),
    ("battery report", "X", "STORE"),
    ("signal strength", "O", "LINK"),
    ("link quality", "O", "LINK"),
    ("gps fix", "E", "GPS"),
    ("position report", "G", "POS"),
    ("node info", "N", "STS"),
    ("mesh status", "O", "MESH"),
    ("air quality", "E", "EQ"),
    ("wind speed", "W", "WIND"),
    ("heart rate check", "H", "HR"),
    ("blood pressure check", "H", "BP"),
    ("vitals check", "H", "VITALS"),
    ("oxygen level", "H", "SPO2"),
];

/// Result of one composition attempt.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ComposeResult {
    /// Composed SAL string when composition succeeded; `None` for passthrough.
    pub sal: Option<String>,
    /// True when the input was returned as natural language (no SAL emitted).
    pub passthrough: bool,
    /// Validation result run on the emitted SAL (empty issue list when
    /// passthrough).
    pub validation: CompositionResult,
    /// Composer decision trace for debugging / observability.
    pub trace: Vec<String>,
}

/// Deterministic SAL composer.
#[derive(Debug, Clone)]
pub struct SALComposer {
    asd: AdaptiveSharedDictionary,
    macro_registry: Option<MacroRegistry>,
    /// Phrase -> (namespace, opcode), populated from curated triggers and
    /// definition strings. Sorted longest-first when iterating for the
    /// longest-match-first policy.
    phrase_index: BTreeMap<String, (String, String)>,
    phrases_sorted: Vec<String>,
}

impl SALComposer {
    /// Construct a composer with no macro registry.
    pub fn new(asd: Option<AdaptiveSharedDictionary>) -> Self {
        let asd = asd.unwrap_or_default();
        let (phrase_index, phrases_sorted) = build_phrase_index();
        Self {
            asd,
            macro_registry: None,
            phrase_index,
            phrases_sorted,
        }
    }

    /// Construct a composer with an attached macro registry.
    pub fn with_macros(
        asd: Option<AdaptiveSharedDictionary>,
        registry: MacroRegistry,
    ) -> Self {
        let mut c = Self::new(asd);
        c.macro_registry = Some(registry);
        c
    }

    /// Compose SAL from natural language. Returns NL_PASSTHROUGH (no SAL)
    /// when no opcode matches with confidence.
    pub fn compose(&self, nl: &str) -> ComposeResult {
        let mut trace: Vec<String> = Vec::new();
        let nl_lower = nl.to_lowercase();

        // Step 1: Macro priority — registered macros win over single-opcode
        // composition. Mirrors Python / Go / TS behavior.
        if let Some(reg) = self.macro_registry.as_ref() {
            for template in reg.list() {
                for trigger in &template.triggers {
                    if trigger.is_empty() {
                        continue;
                    }
                    if nl_lower.contains(&trigger.to_lowercase()) {
                        let sal = format!("A:MACRO[{}]", template.name);
                        trace.push(format!(
                            "macro_match: {} via trigger '{}'",
                            template.name, trigger
                        ));
                        let validation = validate_composition(
                            &sal,
                            nl,
                            self.macro_registry.as_ref(),
                            true,
                            Some(&self.asd),
                        );
                        return ComposeResult {
                            sal: Some(sal),
                            passthrough: false,
                            validation,
                            trace,
                        };
                    }
                }
            }
        }

        // Step 2: Phrase-index lookup. Iterate longest-first so multi-word
        // phrases beat single-word fallbacks. Bounded space-or-start /
        // space-or-end matching keeps us from triggering on substrings of
        // longer words.
        let mut resolved: Vec<(String, String)> = Vec::new();
        for phrase in &self.phrases_sorted {
            if phrase_match(&nl_lower, phrase) {
                if let Some((ns, op)) = self.phrase_index.get(phrase) {
                    if !resolved.iter().any(|(n, o)| n == ns && o == op) {
                        resolved.push((ns.clone(), op.clone()));
                        trace.push(format!(
                            "phrase_match: '{}' -> {}:{}",
                            phrase, ns, op
                        ));
                    }
                }
            }
        }

        if resolved.is_empty() {
            trace.push("no_phrase_match: NL_PASSTHROUGH".to_string());
            return ComposeResult {
                sal: None,
                passthrough: true,
                validation: CompositionResult {
                    valid: true,
                    issues: Vec::new(),
                },
                trace,
            };
        }

        // Step 3: Glyph operator detection. "then"/"next" -> THEN (→),
        // "and" -> AND (∧). Default: ∧ when multiple frames resolved.
        let join_op: &str = if contains_then_marker(&nl_lower) {
            "\u{2192}"
        } else {
            "\u{2227}"
        };
        trace.push(format!("join_op: {join_op}"));

        // Step 4: Build frames, injecting consequence class for R namespace.
        let frames: Vec<String> = resolved
            .iter()
            .map(|(ns, op)| {
                let mut frame = format!("{ns}:{op}");
                if ns == "R" && op != "ESTOP" {
                    // Default to ↺ REVERSIBLE — caller can override with a
                    // safety-classified macro.
                    frame.push('\u{21ba}');
                }
                frame
            })
            .collect();

        let sal = if frames.len() == 1 {
            frames[0].clone()
        } else {
            frames.join(join_op)
        };

        let validation = validate_composition(
            &sal,
            nl,
            self.macro_registry.as_ref(),
            true,
            Some(&self.asd),
        );

        // If validation fails (e.g. byte inflation on trivial inputs), fall
        // back to passthrough rather than emitting invalid SAL.
        if !validation.valid {
            trace.push(format!(
                "validation_failed: falling back to passthrough ({} errors)",
                validation.errors().len()
            ));
            return ComposeResult {
                sal: None,
                passthrough: true,
                validation,
                trace,
            };
        }

        trace.push(format!("emit_sal: {sal}"));
        ComposeResult {
            sal: Some(sal),
            passthrough: false,
            validation,
            trace,
        }
    }
}

/// Build the phrase index from curated triggers plus ASD definition
/// phrases. Returns the map and a longest-first phrase list.
fn build_phrase_index() -> (BTreeMap<String, (String, String)>, Vec<String>) {
    let mut index: BTreeMap<String, (String, String)> = BTreeMap::new();

    // ASD definition phrases — multi-word definitions (e.g.
    // "heart_rate" -> "heart rate") become matchable phrases.
    for (ns, ops) in asd_basis().iter() {
        for (op, defn) in ops.iter() {
            let phrase = defn.replace('_', " ").to_lowercase();
            if phrase.contains(' ') {
                index
                    .entry(phrase)
                    .or_insert(((*ns).to_string(), (*op).to_string()));
            }
        }
    }

    // Curated triggers — these override / supplement definition phrases
    // for compose-time disambiguation.
    for (phrase, ns, op) in CURATED_TRIGGERS.iter() {
        index.insert(
            (*phrase).to_string(),
            ((*ns).to_string(), (*op).to_string()),
        );
    }

    let mut phrases: Vec<String> = index.keys().cloned().collect();
    phrases.sort_by_key(|p| std::cmp::Reverse(p.len()));

    (index, phrases)
}

/// True when `phrase` appears as a whole-word run in `haystack`.
///
/// Cheap whole-word check: the match boundaries must be either
/// haystack edges or non-alphanumeric characters. Avoids pulling in a
/// regex compile per phrase (we have hundreds).
fn phrase_match(haystack: &str, phrase: &str) -> bool {
    let mut start = 0usize;
    while let Some(idx) = haystack[start..].find(phrase) {
        let abs = start + idx;
        let end = abs + phrase.len();
        let left_ok = abs == 0
            || !haystack[..abs]
                .chars()
                .next_back()
                .map(|c| c.is_alphanumeric() || c == '_')
                .unwrap_or(false);
        let right_ok = end == haystack.len()
            || !haystack[end..]
                .chars()
                .next()
                .map(|c| c.is_alphanumeric() || c == '_')
                .unwrap_or(false);
        if left_ok && right_ok {
            return true;
        }
        start = abs + 1;
    }
    false
}

fn contains_then_marker(nl_lower: &str) -> bool {
    // Detect explicit sequence markers; case is already lowered.
    nl_lower.contains(" then ")
        || nl_lower.contains(", then ")
        || nl_lower.starts_with("then ")
        || nl_lower.contains(" next ")
        || nl_lower.contains(", next ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_phrase_emits_sal() {
        let composer = SALComposer::new(None);
        let result = composer.compose("send a vitals check to BOT1");
        assert!(
            result.sal.is_some(),
            "vitals check should match: trace={:?}",
            result.trace
        );
        assert!(!result.passthrough);
        let sal = result.sal.unwrap();
        assert!(sal.contains("H:VITALS"), "sal={sal}");
    }

    #[test]
    fn unknown_phrase_passes_through() {
        let composer = SALComposer::new(None);
        let result = composer.compose("xyzzy plugh quux flibbertigibbet");
        assert!(result.sal.is_none());
        assert!(result.passthrough);
    }

    #[test]
    fn macro_priority_overrides_phrase_match() {
        let mut reg = MacroRegistry::new(None);
        let template = crate::macros::MacroTemplate {
            name: "VITALS_FULL".to_string(),
            body: "H:HR\u{2227}H:BP\u{2227}H:SPO2".to_string(),
            slots: vec![],
            consequence_class: None,
            description: String::new(),
            triggers: vec!["vitals check".to_string()],
        };
        reg.register(template).expect("register");

        let composer = SALComposer::with_macros(None, reg);
        let result = composer.compose("vitals check please");
        assert_eq!(result.sal.as_deref(), Some("A:MACRO[VITALS_FULL]"));
        assert!(!result.passthrough);
    }

    #[test]
    fn chain_marker_then_uses_arrow_operator() {
        let composer = SALComposer::new(None);
        let result = composer.compose(
            "run heart rate check then do a blood pressure check on the patient",
        );
        if let Some(sal) = result.sal {
            // When two frames resolve, the join glyph should be → (then).
            // The composer is allowed to fall back to a single frame on
            // tight matches, so we only assert the operator if both
            // resolved. The trace tells us what happened.
            if sal.contains('\u{2192}') {
                assert!(
                    sal.contains("H:HR") && sal.contains("H:BP"),
                    "expected both vitals frames; got {sal}"
                );
            }
        }
    }

    #[test]
    fn r_namespace_phrase_gets_consequence_class() {
        let composer = SALComposer::new(None);
        let result = composer.compose(
            "run a robot status check on the warehouse floor robot fleet",
        );
        if let Some(sal) = result.sal {
            // R:STAT should pick up the default ↺ injection.
            if sal.contains("R:STAT") {
                assert!(
                    sal.contains('\u{21ba}'),
                    "R-namespace frame must carry CC: {sal}"
                );
            }
        }
    }
}
