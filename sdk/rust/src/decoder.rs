// License: Apache-2.0
//! OSMP SAL Decoder — inference-free deterministic decode.
//!
//! Analog: HPACK static table decode (RFC 7541 §A). All parsing is
//! deterministic — structured output, no inference, no statistical models,
//! no ambiguity resolution.
//!
//! Cross-SDK byte-identical with Python `SALDecoder`, Go `Decoder`,
//! TypeScript `OSMPDecoder`.

use std::collections::BTreeMap;
use std::fmt;

use crate::asd::AdaptiveSharedDictionary;
use crate::glyphs::{asd_basis, consequence_classes};
use crate::types::DecodedInstruction;

/// Errors returned by the decoder. Reserved for forward-compatibility:
/// the canonical SAL grammar is permissive, so `decode_frame` currently
/// never returns an error for non-empty inputs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DecodeError {
    /// Input was empty after trimming.
    Empty,
}

impl fmt::Display for DecodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DecodeError::Empty => write!(f, "empty SAL frame"),
        }
    }
}

impl std::error::Error for DecodeError {}

/// SAL frame decoder.
#[derive(Debug, Clone)]
pub struct Decoder {
    asd: AdaptiveSharedDictionary,
}

impl Decoder {
    /// Construct a new decoder. Pass `None` to seed from the v15 floor basis.
    pub fn new(asd: Option<AdaptiveSharedDictionary>) -> Self {
        Self {
            asd: asd.unwrap_or_default(),
        }
    }

    /// Borrow the dictionary in use.
    pub fn asd(&self) -> &AdaptiveSharedDictionary {
        &self.asd
    }

    /// Resolve the namespace for an opcode lacking an explicit `NS:` prefix.
    ///
    /// Returns the first namespace in dictionary order (matching Python
    /// ASD_BASIS iteration) that contains `opcode`, or `"A"` as default.
    fn resolve_short_form(&self, opcode: &str) -> String {
        for (ns, ops) in asd_basis().iter() {
            if ops.contains_key(opcode) {
                return (*ns).to_string();
            }
        }
        "A".to_string()
    }

    /// Find the earliest occurrence of any character in `stops` within `s`,
    /// returning byte index. Stop characters are matched at byte boundaries
    /// (callers pass single-byte ASCII or full multi-byte glyphs).
    fn first_stop(s: &str, stops: &[&str]) -> usize {
        let mut earliest = s.len();
        for sc in stops {
            if let Some(idx) = s.find(sc) {
                if idx < earliest {
                    earliest = idx;
                }
            }
        }
        earliest
    }

    /// Decode a single SAL frame to its semantic components.
    ///
    /// Cross-SDK byte-identical with Python `SALDecoder.decode_frame`, Go
    /// `(*Decoder).DecodeFrame`, TypeScript `OSMPDecoder.decodeFrame`.
    pub fn decode_frame(&self, encoded: &str) -> Result<DecodedInstruction, DecodeError> {
        let raw = encoded.trim().to_string();
        if raw.is_empty() {
            return Err(DecodeError::Empty);
        }
        let mut remaining: String = raw.clone();

        // Extract consequence class suffix (any glyph from CONSEQUENCE_CLASSES).
        let mut cc: Option<String> = None;
        let mut cc_name: Option<String> = None;
        for (glyph, name) in consequence_classes().iter() {
            if remaining.ends_with(glyph) {
                cc = Some((*glyph).to_string());
                cc_name = Some((*name).to_string());
                let new_len = remaining.len() - glyph.len();
                remaining.truncate(new_len);
                break;
            }
        }

        // Detect explicit namespace (colon before first @ or ?).
        let before_target_at = remaining.split('@').next().unwrap_or("");
        let before_target = before_target_at.split('?').next().unwrap_or("");
        let has_explicit_ns = before_target.contains(':');

        let namespace: String;
        if has_explicit_ns {
            let first_colon = remaining
                .find(':')
                .expect("colon must exist when has_explicit_ns is true");
            namespace = remaining[..first_colon].to_string();
            remaining = remaining[first_colon + 1..].to_string();
        } else {
            let pre_at = remaining.split('@').next().unwrap_or("");
            let pre = pre_at.split('?').next().unwrap_or("");
            namespace = self.resolve_short_form(pre);
        }

        // Extract opcode.
        let opcode_end = Self::first_stop(&remaining, &["@", "?", ":"]);
        let opcode = remaining[..opcode_end].to_string();
        remaining = remaining[opcode_end..].to_string();

        let opcode_meaning = self
            .asd
            .lookup(&namespace, &opcode)
            .map(|s| s.to_string());

        // Extract target.
        let mut target: Option<String> = None;
        if remaining.starts_with('@') {
            remaining = remaining[1..].to_string();
            let end = Self::first_stop(
                &remaining,
                &[
                    "?", ":", "\u{2227}", "\u{2228}", "\u{2192}", "\u{2194}", ";",
                    "\u{2225}",
                ],
            );
            target = Some(remaining[..end].to_string());
            remaining = remaining[end..].to_string();
        }

        // Extract query slot.
        let mut query_slot: Option<String> = None;
        if remaining.starts_with('?') {
            remaining = remaining[1..].to_string();
            let end = Self::first_stop(
                &remaining,
                &[":", "\u{2227}", "\u{2228}", "\u{2192}", ";"],
            );
            query_slot = Some(remaining[..end].to_string());
            remaining = remaining[end..].to_string();
        }

        // Extract slot assignments.
        let mut slots: BTreeMap<String, String> = BTreeMap::new();
        while remaining.starts_with(':') {
            remaining = remaining[1..].to_string();
            match remaining.find(':') {
                None => {
                    slots.insert(remaining.clone(), String::new());
                    remaining.clear();
                    break;
                }
                Some(colon_idx) => {
                    let slot_name = remaining[..colon_idx].to_string();
                    remaining = remaining[colon_idx + 1..].to_string();
                    let val_end = Self::first_stop(
                        &remaining,
                        &[
                            ":", "\u{2227}", "\u{2228}", "\u{2192}", ";", "\u{26A0}",
                            "\u{21BA}", "\u{2298}",
                        ],
                    );
                    slots.insert(slot_name, remaining[..val_end].to_string());
                    remaining = remaining[val_end..].to_string();
                }
            }
        }

        Ok(DecodedInstruction {
            namespace,
            opcode,
            opcode_meaning,
            target,
            query_slot,
            slots,
            consequence_class: cc,
            consequence_class_name: cc_name,
            raw,
        })
    }

    /// Split a compound SAL chain on chain operators and decode each frame.
    ///
    /// Splits on the chain operators `→`, `∧`, `∨`, `↔`, `∥`, `;` (and the
    /// ASCII shorthand `->`). Operators themselves are dropped from the
    /// output; only the decoded frames are returned.
    ///
    /// Cross-SDK byte-identical with Python `SALDecoder.decode_compound`, Go
    /// equivalent, TypeScript equivalent.
    pub fn decode_compound(&self, encoded: &str) -> Vec<DecodedInstruction> {
        let mut out: Vec<DecodedInstruction> = Vec::new();
        for frame in split_compound(encoded) {
            let trimmed = frame.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(decoded) = self.decode_frame(trimmed) {
                out.push(decoded);
            }
        }
        out
    }
}

/// Split a SAL chain into frames on the canonical chain operators.
///
/// Order matters: `->` (ASCII shorthand for `→`) must match before any
/// single-char operator that would otherwise consume the leading `-`.
pub fn split_compound(input: &str) -> Vec<String> {
    let mut frames: Vec<String> = Vec::new();
    let mut current = String::new();
    let chars: Vec<char> = input.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        // Check the two-char ASCII shorthand "->"
        if chars[i] == '-' && i + 1 < chars.len() && chars[i + 1] == '>' {
            frames.push(std::mem::take(&mut current));
            i += 2;
            continue;
        }
        let c = chars[i];
        if c == '\u{2192}'   // →
            || c == '\u{2227}' // ∧
            || c == '\u{2228}' // ∨
            || c == '\u{2194}' // ↔
            || c == '\u{2225}' // ∥
            || c == ';'
        {
            frames.push(std::mem::take(&mut current));
            i += 1;
            continue;
        }
        current.push(c);
        i += 1;
    }
    frames.push(current);
    frames
}
