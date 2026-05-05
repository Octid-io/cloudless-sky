// License: Apache-2.0
//! OSMP SAL Encoder.
//!
//! Builds wire-format SAL strings from structured input. Cross-SDK
//! byte-identical with Python `SALEncoder`, Go `Encoder`, TypeScript
//! `OSMPEncoder`.

use std::collections::BTreeMap;
use std::fmt;

use crate::asd::AdaptiveSharedDictionary;
use crate::glyphs::{compound_operators, consequence_classes, glyph_operators};

/// Errors returned by the encoder.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EncodeError {
    /// `R` namespace was used without a valid consequence class. The R
    /// namespace requires `⚠` (HAZARDOUS), `↺` (REVERSIBLE), or `⊘`
    /// (IRREVERSIBLE) on every instruction except `R:ESTOP`.
    MissingConsequenceClass(String),
    /// Unknown chain operator passed to `encode_compound`.
    UnknownOperator(String),
}

impl fmt::Display for EncodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EncodeError::MissingConsequenceClass(got) => write!(
                f,
                "R namespace requires consequence class (⚠/↺/⊘). Got: {got:?}",
            ),
            EncodeError::UnknownOperator(op) => write!(f, "unknown operator: {op:?}"),
        }
    }
}

impl std::error::Error for EncodeError {}

/// Borrowed inputs for `encode_compound_chain`.
#[derive(Debug, Clone)]
pub struct EncodedFrame<'a> {
    /// Namespace prefix.
    pub namespace: &'a str,
    /// Opcode identifier.
    pub opcode: &'a str,
    /// Optional `@target` segment.
    pub target: Option<&'a str>,
    /// Optional `?query` slot.
    pub query_slot: Option<&'a str>,
    /// Bracketed slot assignments: `:k:v` repeated.
    pub slots: Option<&'a BTreeMap<String, String>>,
    /// Consequence class glyph if applicable.
    pub consequence_class: Option<&'a str>,
}

/// SAL frame encoder.
#[derive(Debug, Clone)]
pub struct Encoder {
    asd: AdaptiveSharedDictionary,
}

impl Encoder {
    /// Construct a new encoder. Pass `None` to seed from the v15 floor basis.
    pub fn new(asd: Option<AdaptiveSharedDictionary>) -> Self {
        Self {
            asd: asd.unwrap_or_default(),
        }
    }

    /// Borrow the dictionary in use.
    pub fn asd(&self) -> &AdaptiveSharedDictionary {
        &self.asd
    }

    /// Build a wire-format SAL frame from structured input.
    ///
    /// Cross-SDK byte-identical with Python `SALEncoder.encode_frame`, Go
    /// `(*Encoder).EncodeFrame`, TypeScript `OSMPEncoder.encodeFrame`.
    pub fn encode(
        &self,
        namespace: &str,
        opcode: &str,
        target: Option<&str>,
        query_slot: Option<&str>,
        slots: Option<&BTreeMap<String, String>>,
        consequence_class: Option<&str>,
    ) -> Result<String, EncodeError> {
        if namespace == "R" {
            let valid = match consequence_class {
                Some(cc) => consequence_classes().contains_key(cc),
                None => false,
            };
            if !valid {
                let got = consequence_class
                    .map(|s| s.to_string())
                    .unwrap_or_else(|| "None".to_string());
                return Err(EncodeError::MissingConsequenceClass(got));
            }
        }
        let mut out = String::new();
        out.push_str(namespace);
        out.push(':');
        out.push_str(opcode);
        if let Some(t) = target {
            out.push('@');
            out.push_str(t);
        }
        if let Some(q) = query_slot {
            out.push('?');
            out.push_str(q);
        }
        if let Some(slot_map) = slots {
            for (k, v) in slot_map.iter() {
                out.push(':');
                out.push_str(k);
                out.push(':');
                out.push_str(v);
            }
        }
        if let Some(cc) = consequence_class {
            out.push_str(cc);
        }
        Ok(out)
    }

    /// Concatenate two frames with a chain operator.
    ///
    /// Cross-SDK byte-identical with Python `SALEncoder.encode_compound`, Go
    /// `(*Encoder).EncodeCompound`, TypeScript `OSMPEncoder.encodeCompound`.
    pub fn encode_compound(
        &self,
        left: &str,
        operator: &str,
        right: &str,
    ) -> Result<String, EncodeError> {
        if !glyph_operators().contains_key(operator)
            && !compound_operators().contains_key(operator)
        {
            return Err(EncodeError::UnknownOperator(operator.to_string()));
        }
        let mut out = String::with_capacity(left.len() + operator.len() + right.len());
        out.push_str(left);
        out.push_str(operator);
        out.push_str(right);
        Ok(out)
    }

    /// Wrap a list of instructions in the parallel envelope `A∥[?…∧?…]`.
    ///
    /// Cross-SDK byte-identical with Python `SALEncoder.encode_parallel`, Go
    /// `(*Encoder).EncodeParallel`, TypeScript `OSMPEncoder.encodeParallel`.
    pub fn encode_parallel(&self, instructions: &[&str]) -> String {
        let prefixed: Vec<String> = instructions
            .iter()
            .map(|i| {
                if i.starts_with('?') {
                    (*i).to_string()
                } else {
                    format!("?{i}")
                }
            })
            .collect();
        format!("A\u{2225}[{}]", prefixed.join("\u{2227}"))
    }

    /// Join instructions with the sequence operator `;`.
    ///
    /// Cross-SDK byte-identical with Python `SALEncoder.encode_sequence`, Go
    /// `(*Encoder).EncodeSequence`, TypeScript `OSMPEncoder.encodeSequence`.
    pub fn encode_sequence(&self, instructions: &[&str]) -> String {
        instructions.join(";")
    }

    /// Build a broadcast frame: `NS:OP@*`.
    ///
    /// Cross-SDK byte-identical with Python `SALEncoder.encode_broadcast`, Go
    /// `(*Encoder).EncodeBroadcast`, TypeScript `OSMPEncoder.encodeBroadcast`.
    pub fn encode_broadcast(&self, namespace: &str, opcode: &str) -> String {
        format!("{namespace}:{opcode}@*")
    }
}
