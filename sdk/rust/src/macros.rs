//! Macro registry — pre-validated multi-step SAL chain templates.
//!
//! A macro template carries an opcode sequence with operator glyphs and
//! `{slot_name}` placeholders. The registry stores templates, validates
//! that referenced opcodes exist in the ASD, and produces either a
//! compact wire form (`A:MACRO[id]`) or an expanded chain (the full
//! template with values substituted).
//!
//! Cross-SDK byte-identical with Python `MacroRegistry`, Go
//! `MacroRegistry`, TypeScript `MacroRegistry`.
//!
//! License: Apache-2.0

use crate::asd::AdaptiveSharedDictionary;
use crate::sal_patterns::{frame_ns_op_re, frame_split_re};
use regex::Regex;
use serde::Deserialize;
use std::collections::{BTreeMap, BTreeSet};
use std::sync::OnceLock;

// ── Regex helpers ─────────────────────────────────────────────────────────────

fn placeholder_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\{(\w+)\}").unwrap())
}

fn slot_strip_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\{[^}]+\}").unwrap())
}

fn is_operator_token(s: &str) -> bool {
    matches!(
        s,
        "\u{2192}" | "\u{2227}" | "\u{2228}" | "\u{2194}" | "\u{2225}" | ";" | "->"
    )
}

// ── Public types ──────────────────────────────────────────────────────────────

/// A single template registered with the macro registry.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MacroTemplate {
    /// Stable identifier referenced from `A:MACRO[id]` wire form.
    pub name: String,
    /// SAL chain template with `{slot_name}` placeholders.
    pub body: String,
    /// Ordered slot names — order is the registration argument order, used
    /// for compact wire encoding.
    pub slots: Vec<String>,
    /// Inherited consequence class glyph (⚠/↺/⊘) if any R-namespace frame
    /// in the chain carries one. `None` when the chain is purely sensing.
    pub consequence_class: Option<String>,
    /// Optional human-readable description from the corpus loader.
    pub description: String,
    /// NL trigger phrases harvested at corpus load time. The composer scans
    /// these in `compose()` to give macros priority over single-opcode
    /// composition.
    pub triggers: Vec<String>,
}

/// On-disk JSON shape for a single macro entry. Mirrors the Go struct.
#[derive(Debug, Deserialize)]
struct CorpusEntry {
    macro_id: String,
    chain_template: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    triggers: Vec<String>,
    #[serde(default)]
    slots: Vec<CorpusSlot>,
}

#[derive(Debug, Deserialize)]
struct CorpusSlot {
    name: String,
    #[serde(default)]
    #[allow(dead_code)] // kept for parity with cross-SDK corpus shape
    slot_type: String,
    #[serde(default)]
    #[allow(dead_code)]
    namespace: String,
}

/// Top-level corpus shape.
#[derive(Debug, Deserialize)]
struct Corpus {
    #[serde(default)]
    #[allow(dead_code)]
    corpus_id: String,
    #[serde(default)]
    #[allow(dead_code)]
    version: String,
    #[serde(default)]
    macros: Vec<CorpusEntry>,
}

/// In-memory store of pre-validated SAL chain templates.
#[derive(Debug, Clone)]
pub struct MacroRegistry {
    asd: AdaptiveSharedDictionary,
    templates: BTreeMap<String, MacroTemplate>,
    order: Vec<String>,
}

impl MacroRegistry {
    /// Construct a registry bound to an ASD. If `None`, a fresh default
    /// dictionary is allocated.
    pub fn new(asd: Option<AdaptiveSharedDictionary>) -> Self {
        Self {
            asd: asd.unwrap_or_default(),
            templates: BTreeMap::new(),
            order: Vec::new(),
        }
    }

    /// The dictionary the registry validates against.
    pub fn asd(&self) -> &AdaptiveSharedDictionary {
        &self.asd
    }

    /// Register a template. Validates that every referenced opcode exists in
    /// the ASD and that placeholder names match declared slot names.
    pub fn register(&mut self, mut template: MacroTemplate) -> Result<(), String> {
        let clean = slot_strip_re().replace_all(&template.body, "X").to_string();

        // Validate referenced opcodes exist in the ASD.
        for raw in frame_split_re().split(&clean) {
            let frame = raw.trim();
            if frame.is_empty() || is_operator_token(frame) {
                continue;
            }
            if let Some(cap) = frame_ns_op_re().captures(frame) {
                let ns = cap.get(1).map(|m| m.as_str()).unwrap_or("");
                let op = cap.get(2).map(|m| m.as_str()).unwrap_or("");
                // I:§ is a structural primitive, not an opcode.
                if ns == "I" && op == "\u{00a7}" {
                    continue;
                }
                if self.asd.lookup(ns, op).is_none() {
                    return Err(format!(
                        "Macro {}: opcode {}:{} not found in ASD",
                        template.name, ns, op
                    ));
                }
            }
        }

        // Validate slot placeholders match declared slots.
        let placeholders: BTreeSet<String> = placeholder_re()
            .captures_iter(&template.body)
            .filter_map(|c| c.get(1).map(|m| m.as_str().to_string()))
            .collect();

        let declared: BTreeSet<String> = template.slots.iter().cloned().collect();

        let missing: Vec<String> = placeholders.difference(&declared).cloned().collect();
        if !missing.is_empty() {
            return Err(format!(
                "Macro {}: slot placeholders {:?} have no matching slot declaration",
                template.name, missing
            ));
        }

        let extra: Vec<String> = declared.difference(&placeholders).cloned().collect();
        if !extra.is_empty() {
            return Err(format!(
                "Macro {}: slot declarations {:?} have no matching placeholder",
                template.name, extra
            ));
        }

        // Inherit consequence class from highest-severity R frame in chain.
        if template.consequence_class.is_none() {
            if let Some(cc) = compute_inherited_cc(&clean) {
                template.consequence_class = Some(cc);
            }
        }

        if !self.templates.contains_key(&template.name) {
            self.order.push(template.name.clone());
        }
        self.templates.insert(template.name.clone(), template);
        Ok(())
    }

    /// Look up a registered template by name.
    pub fn lookup(&self, macro_id: &str) -> Option<&MacroTemplate> {
        self.templates.get(macro_id)
    }

    /// Expand a macro template substituting positional `slots` values into
    /// the placeholders. The slice order must match the template's `slots`
    /// declaration order. Returns the fully expanded SAL chain.
    pub fn expand(&self, macro_id: &str, slots: &[&str]) -> Result<String, String> {
        let template = self
            .templates
            .get(macro_id)
            .ok_or_else(|| format!("Macro not found: {macro_id}"))?;

        if slots.len() != template.slots.len() {
            return Err(format!(
                "Macro {}: expected {} slot values, got {}",
                macro_id,
                template.slots.len(),
                slots.len()
            ));
        }

        let mut out = template.body.clone();
        for (name, value) in template.slots.iter().zip(slots.iter()) {
            out = out.replace(&format!("{{{name}}}"), value);
        }
        Ok(out)
    }

    /// Load a JSON corpus and register every entry. Returns the count loaded.
    pub fn load_corpus(&mut self, json_bytes: &[u8]) -> Result<usize, String> {
        let corpus: Corpus = serde_json::from_slice(json_bytes)
            .map_err(|e| format!("macro corpus parse: {e}"))?;
        let mut count = 0usize;
        for entry in corpus.macros {
            let slot_names: Vec<String> = entry.slots.iter().map(|s| s.name.clone()).collect();
            let template = MacroTemplate {
                name: entry.macro_id,
                body: entry.chain_template,
                slots: slot_names,
                consequence_class: None,
                description: entry.description,
                triggers: entry.triggers,
            };
            self.register(template)?;
            count += 1;
        }
        Ok(count)
    }

    /// Return every registered template in registration order.
    pub fn list(&self) -> Vec<&MacroTemplate> {
        self.order
            .iter()
            .filter_map(|id| self.templates.get(id))
            .collect()
    }
}

impl Default for MacroRegistry {
    fn default() -> Self {
        Self::new(None)
    }
}

/// Walk every R-namespace frame in `clean_chain` and return the
/// highest-severity consequence class glyph found.
///
/// Severity ordering: ↺ < ⚠ < ⊘.
fn compute_inherited_cc(clean_chain: &str) -> Option<String> {
    let mut max_sev = 0u8;
    for raw in frame_split_re().split(clean_chain) {
        let frame = raw.trim();
        if frame.is_empty() || is_operator_token(frame) {
            continue;
        }
        let cap = match frame_ns_op_re().captures(frame) {
            Some(c) => c,
            None => continue,
        };
        if cap.get(1).map(|m| m.as_str()) != Some("R") {
            continue;
        }
        if frame.contains('\u{2298}') && max_sev < 3 {
            max_sev = 3;
        } else if frame.contains('\u{26a0}') && max_sev < 2 {
            max_sev = 2;
        } else if frame.contains('\u{21ba}') && max_sev < 1 {
            max_sev = 1;
        }
    }
    match max_sev {
        3 => Some("\u{2298}".to_string()),
        2 => Some("\u{26a0}".to_string()),
        1 => Some("\u{21ba}".to_string()),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h_hr_template() -> MacroTemplate {
        MacroTemplate {
            name: "VITALS_CHECK".to_string(),
            body: "H:HR\u{2227}H:BP".to_string(),
            slots: vec![],
            consequence_class: None,
            description: "Vitals check macro".to_string(),
            triggers: vec!["vitals check".to_string()],
        }
    }

    #[test]
    fn register_and_lookup_returns_template() {
        let mut reg = MacroRegistry::new(None);
        reg.register(h_hr_template()).expect("register");
        let t = reg.lookup("VITALS_CHECK").expect("lookup");
        assert_eq!(t.name, "VITALS_CHECK");
        assert_eq!(t.body, "H:HR\u{2227}H:BP");
    }

    #[test]
    fn register_rejects_unknown_opcode() {
        let mut reg = MacroRegistry::new(None);
        let bogus = MacroTemplate {
            name: "BOGUS".to_string(),
            body: "H:NOTREAL".to_string(),
            slots: vec![],
            consequence_class: None,
            description: String::new(),
            triggers: vec![],
        };
        assert!(reg.register(bogus).is_err());
    }

    #[test]
    fn expand_with_slot_values_substitutes_placeholders() {
        let mut reg = MacroRegistry::new(None);
        let template = MacroTemplate {
            name: "ICD_REPORT".to_string(),
            body: "H:ICD[{code}]\u{2192}H:CASREP".to_string(),
            slots: vec!["code".to_string()],
            consequence_class: None,
            description: String::new(),
            triggers: vec![],
        };
        reg.register(template).expect("register");
        let expanded = reg.expand("ICD_REPORT", &["J93.0"]).expect("expand");
        assert_eq!(expanded, "H:ICD[J93.0]\u{2192}H:CASREP");
    }

    #[test]
    fn expand_unknown_macro_errors() {
        let reg = MacroRegistry::new(None);
        assert!(reg.expand("DOES_NOT_EXIST", &[]).is_err());
    }

    #[test]
    fn list_returns_registration_order() {
        let mut reg = MacroRegistry::new(None);
        reg.register(h_hr_template()).expect("register A");
        let second = MacroTemplate {
            name: "SECOND".to_string(),
            body: "H:SPO2".to_string(),
            slots: vec![],
            consequence_class: None,
            description: String::new(),
            triggers: vec![],
        };
        reg.register(second).expect("register B");
        let listed = reg.list();
        assert_eq!(listed.len(), 2);
        assert_eq!(listed[0].name, "VITALS_CHECK");
        assert_eq!(listed[1].name, "SECOND");
    }

    #[test]
    fn load_corpus_round_trips_json() {
        let mut reg = MacroRegistry::new(None);
        let json = br#"{
            "corpus_id": "test",
            "version": "1.0",
            "macros": [
                {
                    "macro_id": "TINY",
                    "chain_template": "H:HR",
                    "description": "tiny macro",
                    "triggers": ["pulse"],
                    "slots": []
                }
            ]
        }"#;
        let count = reg.load_corpus(json).expect("load");
        assert_eq!(count, 1);
        let t = reg.lookup("TINY").expect("registered");
        assert_eq!(t.body, "H:HR");
        assert_eq!(t.triggers, vec!["pulse".to_string()]);
    }
}
