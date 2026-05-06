// SPDX-License-Identifier: Apache-2.0
//! ADP — ASD Distribution Protocol — SAL-layer dictionary synchronization.
//!
//! Complements the binary FNP handshake with SAL-level instructions for
//! version identity exchange, delta delivery, micro-delta, hash verification,
//! and MDR corpus version tracking.
//!
//! Cross-SDK byte-identical with Python `osmp.protocol` ADP and Go
//! `osmp.adp`. SAL instruction strings, priority classification, version
//! u16↔string mapping, and pending-queue semantics all match.

use std::collections::BTreeMap;
use std::time::SystemTime;

use crate::asd::AdaptiveSharedDictionary;
use crate::types::FLAG_CRITICAL;

// ── Version mapping: u16 wire as u8.u8 (MAJOR.MINOR) ──────────────────

/// Encode `(major, minor)` into the u16 wire form used in the FNP packet.
/// Both inputs must fit in `u8`.
pub fn asd_version_pack(major: u8, minor: u8) -> u16 {
    ((major as u16) << 8) | (minor as u16)
}

/// Decode a u16 ASD version field into `(major, minor)`.
pub fn asd_version_unpack(v: u16) -> (u8, u8) {
    ((v >> 8) as u8, (v & 0xFF) as u8)
}

/// Format a u16 version as the SAL-display string `"MAJOR.MINOR"`.
pub fn asd_version_str(v: u16) -> String {
    let (major, minor) = asd_version_unpack(v);
    format!("{major}.{minor}")
}

/// Parse `"MAJOR.MINOR"` into u16. Returns an error on malformed input or
/// out-of-`u8` components.
pub fn asd_version_parse(s: &str) -> Result<u16, String> {
    let parts: Vec<&str> = s.split('.').collect();
    if parts.len() != 2 {
        return Err(format!("invalid version string: {s}"));
    }
    let major: u8 = parts[0]
        .parse()
        .map_err(|e| format!("invalid major in {s:?}: {e}"))?;
    let minor: u8 = parts[1]
        .parse()
        .map_err(|e| format!("invalid minor in {s:?}: {e}"))?;
    Ok(asd_version_pack(major, minor))
}

/// Returns true when the version transition includes a MAJOR-byte increment.
pub fn asd_version_is_breaking(old_v: u16, new_v: u16) -> bool {
    (new_v >> 8) > (old_v >> 8)
}

// ── Priority constants ────────────────────────────────────────────────

/// Mission traffic — non-ADP instructions transmit at the highest priority.
pub const ADP_PRIORITY_MISSION: u8 = 0;
/// Task-relevant micro-delta (`A:ASD:DEF`).
pub const ADP_PRIORITY_MICRO: u8 = 1;
/// Background delta payload (`A:ASD:DELTA`).
pub const ADP_PRIORITY_DELTA: u8 = 2;
/// Trickle-charge identity / request traffic (`A:ASD:REQ`, `A:ASD?`).
pub const ADP_PRIORITY_TRICKLE: u8 = 3;

/// Returns the ADP priority class for a SAL instruction string. Mission
/// traffic (anything not on the `A:ASD` / `A:MDR` axis) is `MISSION`.
pub fn classify_priority(sal: &str) -> u8 {
    if !sal.starts_with("A:ASD") && !sal.starts_with("A:MDR") {
        return ADP_PRIORITY_MISSION;
    }
    if sal.contains("DEF") {
        return ADP_PRIORITY_MICRO;
    }
    if sal.contains("DELTA") {
        return ADP_PRIORITY_DELTA;
    }
    ADP_PRIORITY_TRICKLE
}

// ── Delta operation ───────────────────────────────────────────────────

/// A single dictionary update operation within an `A:ASD:DELTA` payload.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ADPDeltaOp {
    /// Single-letter namespace (e.g., `"H"` for clinical).
    pub namespace: String,
    /// Update mode glyph: `"+"` (additive), `"\u{2190}"` (REPLACE),
    /// `"\u{2020}"` (DEPRECATE).
    pub mode: String,
    /// Opcode being added / replaced / deprecated.
    pub opcode: String,
    /// New definition string (empty for DEPRECATE).
    pub definition: String,
}

impl ADPDeltaOp {
    /// True when this is a REPLACE operation (mode is `"←"`). REPLACE
    /// operations require mandatory retransmission per spec.
    pub fn is_breaking(&self) -> bool {
        self.mode == "\u{2190}"
    }

    /// SAL representation of this operation, e.g., `"H+[LACTATE]"`.
    pub fn to_sal(&self) -> String {
        format!("{}{}[{}]", self.namespace, self.mode, self.opcode)
    }
}

// ── Delta payload ─────────────────────────────────────────────────────

/// A complete `A:ASD:DELTA` payload comprising version range and operations.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ADPDelta {
    /// SAL-display version string of the sender prior to applying this delta.
    pub from_version: String,
    /// SAL-display version string of the sender after applying this delta.
    pub to_version: String,
    /// Ordered list of operations.
    pub operations: Vec<ADPDeltaOp>,
}

impl ADPDelta {
    /// True when the delta contains at least one REPLACE operation.
    pub fn has_breaking(&self) -> bool {
        self.operations.iter().any(|op| op.is_breaking())
    }

    /// SAL representation of the full delta:
    /// `"A:ASD:DELTA[FROM→TO:op1:op2:…]"`.
    pub fn to_sal(&self) -> String {
        let ops: Vec<String> = self.operations.iter().map(|op| op.to_sal()).collect();
        format!(
            "A:ASD:DELTA[{}\u{2192}{}:{}]",
            self.from_version,
            self.to_version,
            ops.join(":")
        )
    }

    /// Returns the OVERFLOW fragment flags this delta MUST be transmitted
    /// with, per spec §6 / §7 of `OSMP-SPEC-v1.0.2.md`. REPLACE deltas
    /// require `FLAG_CRITICAL` (criticality override) — graceful degradation
    /// on packet loss is not permitted because a lost REPLACE leaves the
    /// receiving node with a stale dictionary entry, a semantic correctness
    /// violation. Non-REPLACE deltas (additive, deprecate) return `0` and
    /// may be transmitted under the node's standing loss-tolerance policy.
    ///
    /// Callers that fragment delta SAL through `OverflowProtocol` MUST OR
    /// this byte into the fragment header `flags` field. The most direct
    /// integration:
    ///
    /// ```ignore
    /// let sal = delta.to_sal();
    /// let critical = (delta.required_overflow_flags() & FLAG_CRITICAL) != 0;
    /// let fragments = overflow.fragment_message(&sal, /* critical = */ critical);
    /// ```
    pub fn required_overflow_flags(&self) -> u8 {
        if self.has_breaking() {
            FLAG_CRITICAL
        } else {
            0
        }
    }
}

// ── Pending instruction ───────────────────────────────────────────────

/// A SAL instruction held in the semantic pending queue while its referenced
/// opcode is unresolved by the local ASD.
#[derive(Debug, Clone)]
pub struct PendingInstruction {
    /// The original SAL instruction text.
    pub sal: String,
    /// Namespace of the unresolved opcode.
    pub unresolved_namespace: String,
    /// The unresolved opcode itself.
    pub unresolved_opcode: String,
    /// Wall-clock instant the instruction was queued.
    pub timestamp: SystemTime,
}

// ── ADP Session ───────────────────────────────────────────────────────

/// SAL-layer dictionary synchronization session manager.
///
/// Tracks the local ASD version, per-namespace minor versions, the pending
/// queue for unresolved opcodes, and remote-peer version state. Generates
/// SAL instruction strings for the entire `A:ASD*` instruction surface
/// (identity, query, alert, REQ, DELTA, DEF, HASH) plus the `A:MDR*` corpus
/// version family.
pub struct ADPSession {
    /// Owned reference to the local ASD (used for `lookup` in
    /// `resolve_or_pend` and the fingerprint in `hash_identity`).
    pub asd: AdaptiveSharedDictionary,
    /// Local ASD version in u8.u8 wire form.
    pub asd_version: u16,
    /// Per-namespace minor-version map. Key is single-letter namespace,
    /// value is the minor-version display string (e.g., `"1"`). Sorted by
    /// `BTreeMap` key order so SAL output is deterministic across SDKs.
    pub namespace_versions: BTreeMap<String, String>,
    /// Instructions awaiting opcode resolution.
    pub pending_queue: Vec<PendingInstruction>,
    /// Diagnostic log of applied deltas (free-form strings). Empty in this
    /// implementation; reserved for downstream tooling.
    pub delta_log: Vec<String>,
    /// Most recent remote version observed via `A:ASD[...]` ingest.
    pub remote_version: Option<u16>,
    /// Most recent remote per-namespace versions observed.
    pub remote_namespace_versions: BTreeMap<String, String>,
}

impl ADPSession {
    /// Construct a new session from an owned ASD plus initial version state.
    /// Pass `None` for `namespace_versions` to start with an empty map.
    pub fn new(
        asd: AdaptiveSharedDictionary,
        asd_version: u16,
        namespace_versions: Option<BTreeMap<String, String>>,
    ) -> Self {
        Self {
            asd,
            asd_version,
            namespace_versions: namespace_versions.unwrap_or_default(),
            pending_queue: Vec::new(),
            delta_log: Vec::new(),
            remote_version: None,
            remote_namespace_versions: BTreeMap::new(),
        }
    }

    /// Generate the `A:ASD[...]` version-identity SAL instruction. With
    /// `include_namespaces = true` and a non-empty `namespace_versions`,
    /// per-namespace minor versions are appended after the ASD version,
    /// sorted by namespace key.
    pub fn version_identity(&self, include_namespaces: bool) -> String {
        let ver = asd_version_str(self.asd_version);
        if include_namespaces && !self.namespace_versions.is_empty() {
            let mut ns_str = String::new();
            for (k, v) in &self.namespace_versions {
                ns_str.push_str(&format!(":{k}{v}"));
            }
            format!("A:ASD[{ver}{ns_str}]")
        } else {
            format!("A:ASD[{ver}]")
        }
    }

    /// Generate the `A:ASD?` version-query broadcast.
    pub fn version_query(&self) -> &'static str {
        "A:ASD?"
    }

    /// Generate the `A:ASD[...]⚠` HAZARDOUS-tagged version-update alert.
    pub fn version_alert(&self) -> String {
        format!("A:ASD[{}]\u{26A0}", asd_version_str(self.asd_version))
    }

    /// Generate an `A:ASD:REQ[FROM→TARGET]` delta-request instruction. The
    /// FROM half is the local version; TARGET is the version the requester
    /// wants to reach.
    pub fn request_delta(&self, target: &str) -> String {
        let my_ver = asd_version_str(self.asd_version);
        format!("A:ASD:REQ[{my_ver}\u{2192}{target}]")
    }

    /// Generate an `A:ASD:DEF?[NAMESPACE:OPCODE]` micro-delta request.
    pub fn request_definition(&self, namespace: &str, opcode: &str) -> String {
        format!("A:ASD:DEF?[{namespace}:{opcode}]")
    }

    /// Generate an `A:ASD:DEF[NAMESPACE:OPCODE:DEFINITION:LAYER]`
    /// micro-delta response.
    pub fn send_definition(
        &self,
        namespace: &str,
        opcode: &str,
        definition: &str,
        layer: u32,
    ) -> String {
        format!("A:ASD:DEF[{namespace}:{opcode}:{definition}:{layer}]")
    }

    /// Generate an `A:ASD:HASH[VERSION:FINGERPRINT]` hash-verification
    /// instruction. `hex_length` truncates the local fingerprint to the first
    /// N hex characters (use 16 for the canonical short form).
    pub fn hash_identity(&self, hex_length: usize) -> String {
        let ver = asd_version_str(self.asd_version);
        let fp = self.asd.fingerprint();
        let truncated = if fp.len() > hex_length {
            &fp[..hex_length]
        } else {
            &fp[..]
        };
        format!("A:ASD:HASH[{ver}:{truncated}]")
    }

    /// Decide whether a SAL instruction's leading opcode is resolvable
    /// against the local ASD.
    ///
    /// Returns `(resolved, pending, micro_request)`:
    ///
    /// - `(true, false, "")` — opcode is resolvable, no further action.
    /// - `(false, true, micro_req)` — opcode is unresolved; the instruction
    ///   was queued and `micro_req` is the SAL string to send to the peer
    ///   asking for that opcode's definition.
    pub fn resolve_or_pend(&mut self, sal: &str) -> (bool, bool, String) {
        let (ns, opcode) = extract_ns_opcode(sal);
        if ns.is_empty() {
            return (true, false, String::new());
        }
        if self.asd.lookup(&ns, &opcode).is_some() {
            return (true, false, String::new());
        }
        self.pending_queue.push(PendingInstruction {
            sal: sal.to_string(),
            unresolved_namespace: ns.clone(),
            unresolved_opcode: opcode.clone(),
            timestamp: SystemTime::now(),
        });
        let micro_req = self.request_definition(&ns, &opcode);
        (false, true, micro_req)
    }
}

/// Extract the leading `(namespace, opcode)` pair from a SAL instruction.
/// Returns `("", "")` when the input does not begin with a single-letter
/// namespace followed by `:`.
fn extract_ns_opcode(sal: &str) -> (String, String) {
    let bytes = sal.as_bytes();
    if bytes.is_empty() || !bytes[0].is_ascii_uppercase() || !sal.contains(':') {
        return (String::new(), String::new());
    }
    let parts: Vec<&str> = sal.splitn(3, ':').collect();
    if parts.len() < 2 || parts[0].len() != 1 {
        return (String::new(), String::new());
    }
    let op_raw = parts[1];
    let mut opcode = String::new();
    for ch in op_raw.chars() {
        if "[]?<>@\u{2227}\u{2228}\u{2192}\u{26A0}".contains(ch) {
            break;
        }
        opcode.push(ch);
    }
    (parts[0].to_string(), opcode)
}

// ── MDR helpers ───────────────────────────────────────────────────────

/// Generate the `A:MDR[corpus1:ver1:corpus2:ver2…]` MDR corpus version
/// identity. Keys are emitted in sorted (`BTreeMap`) order so SAL output is
/// deterministic.
pub fn mdr_identity(corpora: &BTreeMap<String, String>) -> String {
    let parts: Vec<String> = corpora.iter().map(|(k, v)| format!("{k}:{v}")).collect();
    format!("A:MDR[{}]", parts.join(":"))
}

/// Generate an `A:MDR:REQ[CORPUS:FROM→TO]` MDR delta-request instruction.
pub fn mdr_request(corpus: &str, from_ver: &str, to_ver: &str) -> String {
    format!("A:MDR:REQ[{corpus}:{from_ver}\u{2192}{to_ver}]")
}

// ── Acknowledge helpers ───────────────────────────────────────────────

/// Generate `A:ACK[ASD:VERSION]` for a version-identity acknowledgment.
pub fn acknowledge_version(version: &str) -> String {
    format!("A:ACK[ASD:{version}]")
}

/// `A:ACK[ASD:HASH]` — fixed hash-verification acknowledgment.
pub fn acknowledge_hash() -> &'static str {
    "A:ACK[ASD:HASH]"
}

/// `A:ACK[ASD:DEF]` — fixed micro-delta acknowledgment.
pub fn acknowledge_def() -> &'static str {
    "A:ACK[ASD:DEF]"
}

// ── Spec-mandated criticality validator ───────────────────────────────

/// Reasons a received delta can be rejected at the ADP layer per the spec.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DeltaValidationError {
    /// The wire form contains the REPLACE glyph (`\u{2190}`) but the
    /// fragment carrying it does not have `FLAG_CRITICAL` set. Per spec
    /// §6 / §7 this is a protocol violation — REPLACE deltas must always
    /// carry the criticality flag because graceful degradation on REPLACE
    /// loss leaves the receiver with a silently stale dictionary entry.
    ReplaceWithoutCriticality,
}

impl std::fmt::Display for DeltaValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DeltaValidationError::ReplaceWithoutCriticality => write!(
                f,
                "REPLACE delta received without FLAG_CRITICAL — spec violation"
            ),
        }
    }
}

impl std::error::Error for DeltaValidationError {}

/// Validate a received delta SAL string against the fragment-flag context it
/// arrived in. Rejects REPLACE deltas that did not arrive with
/// `FLAG_CRITICAL` set. Pass the OR-of-fragment-flags (e.g.
/// `fragment.flags`) as `received_flags`.
///
/// `sal` is the reassembled SAL string (post-OVERFLOW reassembly). The
/// validator is conservative: it inspects the literal REPLACE glyph
/// (`\u{2190}`) inside the `A:ASD:DELTA[...]` payload — a syntactic check
/// that does not require parsing the full SAL grammar.
pub fn validate_received_delta(
    sal: &str,
    received_flags: u8,
) -> Result<(), DeltaValidationError> {
    if !sal.starts_with("A:ASD:DELTA[") {
        return Ok(());
    }
    if !sal.contains('\u{2190}') {
        return Ok(());
    }
    if received_flags & FLAG_CRITICAL == 0 {
        return Err(DeltaValidationError::ReplaceWithoutCriticality);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fresh_session() -> ADPSession {
        ADPSession::new(AdaptiveSharedDictionary::new(), asd_version_pack(15, 1), None)
    }

    #[test]
    fn version_pack_roundtrip() {
        let v = asd_version_pack(15, 1);
        assert_eq!(asd_version_unpack(v), (15, 1));
        assert_eq!(asd_version_str(v), "15.1");
    }

    #[test]
    fn version_parse_roundtrip() {
        let v = asd_version_parse("15.1").expect("parse");
        assert_eq!(v, asd_version_pack(15, 1));
    }

    #[test]
    fn version_parse_rejects_malformed() {
        assert!(asd_version_parse("15").is_err());
        assert!(asd_version_parse("15.1.2").is_err());
        assert!(asd_version_parse("a.b").is_err());
    }

    #[test]
    fn version_breaking_detection() {
        let v_15_1 = asd_version_pack(15, 1);
        let v_15_2 = asd_version_pack(15, 2);
        let v_16_0 = asd_version_pack(16, 0);
        assert!(!asd_version_is_breaking(v_15_1, v_15_2));
        assert!(asd_version_is_breaking(v_15_1, v_16_0));
    }

    #[test]
    fn classify_priority_basic() {
        assert_eq!(classify_priority("H:HR@NODE1"), ADP_PRIORITY_MISSION);
        assert_eq!(classify_priority("A:ASD:DEF[H:LACTATE:lactate:1]"), ADP_PRIORITY_MICRO);
        assert_eq!(classify_priority("A:ASD:DELTA[15.0\u{2192}15.1:H+[LACTATE]]"), ADP_PRIORITY_DELTA);
        assert_eq!(classify_priority("A:ASD?"), ADP_PRIORITY_TRICKLE);
        assert_eq!(classify_priority("A:ASD[15.1]"), ADP_PRIORITY_TRICKLE);
        assert_eq!(classify_priority("A:MDR[icd10cm:2026]"), ADP_PRIORITY_TRICKLE);
    }

    #[test]
    fn delta_op_to_sal() {
        let op = ADPDeltaOp {
            namespace: "H".to_string(),
            mode: "+".to_string(),
            opcode: "LACTATE".to_string(),
            definition: "lactate".to_string(),
        };
        assert_eq!(op.to_sal(), "H+[LACTATE]");
        assert!(!op.is_breaking());
    }

    #[test]
    fn delta_op_replace_is_breaking() {
        let op = ADPDeltaOp {
            namespace: "H".to_string(),
            mode: "\u{2190}".to_string(),
            opcode: "HR".to_string(),
            definition: "heart_rate_v2".to_string(),
        };
        assert_eq!(op.to_sal(), "H\u{2190}[HR]");
        assert!(op.is_breaking());
    }

    #[test]
    fn delta_to_sal_full() {
        let d = ADPDelta {
            from_version: "15.0".to_string(),
            to_version: "15.1".to_string(),
            operations: vec![
                ADPDeltaOp {
                    namespace: "H".to_string(),
                    mode: "+".to_string(),
                    opcode: "LACTATE".to_string(),
                    definition: "lactate".to_string(),
                },
                ADPDeltaOp {
                    namespace: "M".to_string(),
                    mode: "\u{2020}".to_string(),
                    opcode: "OLDOP".to_string(),
                    definition: String::new(),
                },
            ],
        };
        assert_eq!(d.to_sal(), "A:ASD:DELTA[15.0\u{2192}15.1:H+[LACTATE]:M\u{2020}[OLDOP]]");
        assert!(!d.has_breaking());
    }

    #[test]
    fn version_identity_no_namespaces() {
        let s = fresh_session();
        assert_eq!(s.version_identity(false), "A:ASD[15.1]");
        assert_eq!(s.version_identity(true), "A:ASD[15.1]"); // empty ns map
    }

    #[test]
    fn version_identity_with_namespaces_sorted() {
        let mut ns = BTreeMap::new();
        ns.insert("H".to_string(), "1".to_string());
        ns.insert("A".to_string(), "0".to_string());
        ns.insert("M".to_string(), "2".to_string());
        let s = ADPSession::new(
            AdaptiveSharedDictionary::new(),
            asd_version_pack(15, 1),
            Some(ns),
        );
        // Sorted: A, H, M
        assert_eq!(s.version_identity(true), "A:ASD[15.1:A0:H1:M2]");
    }

    #[test]
    fn version_query_constant() {
        let s = fresh_session();
        assert_eq!(s.version_query(), "A:ASD?");
    }

    #[test]
    fn version_alert_carries_hazardous_glyph() {
        let s = fresh_session();
        assert_eq!(s.version_alert(), "A:ASD[15.1]\u{26A0}");
    }

    #[test]
    fn request_delta_format() {
        let s = fresh_session();
        assert_eq!(s.request_delta("15.2"), "A:ASD:REQ[15.1\u{2192}15.2]");
    }

    #[test]
    fn request_definition_format() {
        let s = fresh_session();
        assert_eq!(s.request_definition("H", "LACTATE"), "A:ASD:DEF?[H:LACTATE]");
    }

    #[test]
    fn send_definition_format() {
        let s = fresh_session();
        assert_eq!(
            s.send_definition("H", "LACTATE", "lactate", 1),
            "A:ASD:DEF[H:LACTATE:lactate:1]",
        );
    }

    #[test]
    fn hash_identity_truncates_fingerprint() {
        let s = fresh_session();
        let h = s.hash_identity(16);
        assert!(h.starts_with("A:ASD:HASH[15.1:"));
        assert!(h.contains("9ecc507e2c24c4a7"), "expected canonical fingerprint, got {h}");
    }

    #[test]
    fn resolve_or_pend_known_opcode() {
        let mut s = fresh_session();
        let (resolved, pending, micro) = s.resolve_or_pend("H:HR@NODE1");
        assert!(resolved);
        assert!(!pending);
        assert!(micro.is_empty());
        assert!(s.pending_queue.is_empty());
    }

    #[test]
    fn resolve_or_pend_unknown_opcode_queues_and_requests() {
        let mut s = fresh_session();
        let (resolved, pending, micro) = s.resolve_or_pend("H:LACTATE@NODE1");
        assert!(!resolved);
        assert!(pending);
        assert_eq!(micro, "A:ASD:DEF?[H:LACTATE]");
        assert_eq!(s.pending_queue.len(), 1);
        assert_eq!(s.pending_queue[0].unresolved_namespace, "H");
        assert_eq!(s.pending_queue[0].unresolved_opcode, "LACTATE");
    }

    #[test]
    fn resolve_or_pend_non_sal_input() {
        let mut s = fresh_session();
        let (resolved, pending, micro) = s.resolve_or_pend("plain natural language");
        assert!(resolved);
        assert!(!pending);
        assert!(micro.is_empty());
    }

    #[test]
    fn mdr_identity_sorted_keys() {
        let mut corpora = BTreeMap::new();
        corpora.insert("iso20022".to_string(), "2024".to_string());
        corpora.insert("icd10cm".to_string(), "2026".to_string());
        corpora.insert("mitre-attack".to_string(), "v18.1".to_string());
        let sal = mdr_identity(&corpora);
        assert_eq!(sal, "A:MDR[icd10cm:2026:iso20022:2024:mitre-attack:v18.1]");
    }

    #[test]
    fn mdr_request_format() {
        assert_eq!(
            mdr_request("icd10cm", "2025", "2026"),
            "A:MDR:REQ[icd10cm:2025\u{2192}2026]",
        );
    }

    #[test]
    fn acknowledge_helpers() {
        assert_eq!(acknowledge_version("15.1"), "A:ACK[ASD:15.1]");
        assert_eq!(acknowledge_hash(), "A:ACK[ASD:HASH]");
        assert_eq!(acknowledge_def(), "A:ACK[ASD:DEF]");
    }

    // ── Criticality wiring (spec §6 / §7: REPLACE → FLAGS[C] mandatory) ──

    #[test]
    fn additive_delta_required_flags_is_zero() {
        let d = ADPDelta {
            from_version: "15.0".to_string(),
            to_version: "15.1".to_string(),
            operations: vec![ADPDeltaOp {
                namespace: "H".to_string(),
                mode: "+".to_string(),
                opcode: "LACTATE".to_string(),
                definition: "lactate".to_string(),
            }],
        };
        assert_eq!(d.required_overflow_flags(), 0);
    }

    #[test]
    fn deprecate_delta_required_flags_is_zero() {
        let d = ADPDelta {
            from_version: "15.0".to_string(),
            to_version: "15.1".to_string(),
            operations: vec![ADPDeltaOp {
                namespace: "M".to_string(),
                mode: "\u{2020}".to_string(),
                opcode: "OLDOP".to_string(),
                definition: String::new(),
            }],
        };
        assert_eq!(d.required_overflow_flags(), 0);
    }

    #[test]
    fn replace_delta_required_flags_is_critical() {
        let d = ADPDelta {
            from_version: "15.0".to_string(),
            to_version: "15.1".to_string(),
            operations: vec![ADPDeltaOp {
                namespace: "H".to_string(),
                mode: "\u{2190}".to_string(),
                opcode: "HR".to_string(),
                definition: "heart_rate_v2".to_string(),
            }],
        };
        assert_eq!(d.required_overflow_flags(), FLAG_CRITICAL);
    }

    #[test]
    fn mixed_delta_with_any_replace_is_critical() {
        let d = ADPDelta {
            from_version: "15.0".to_string(),
            to_version: "15.1".to_string(),
            operations: vec![
                ADPDeltaOp {
                    namespace: "H".to_string(),
                    mode: "+".to_string(),
                    opcode: "LACTATE".to_string(),
                    definition: "lactate".to_string(),
                },
                ADPDeltaOp {
                    namespace: "H".to_string(),
                    mode: "\u{2190}".to_string(),
                    opcode: "HR".to_string(),
                    definition: "heart_rate_v2".to_string(),
                },
            ],
        };
        assert_eq!(d.required_overflow_flags(), FLAG_CRITICAL);
    }

    #[test]
    fn validate_received_replace_without_critical_rejects() {
        let sal = "A:ASD:DELTA[15.0\u{2192}15.1:H\u{2190}[HR]]";
        let result = validate_received_delta(sal, 0);
        assert_eq!(result, Err(DeltaValidationError::ReplaceWithoutCriticality));
    }

    #[test]
    fn validate_received_replace_with_critical_accepts() {
        let sal = "A:ASD:DELTA[15.0\u{2192}15.1:H\u{2190}[HR]]";
        let result = validate_received_delta(sal, FLAG_CRITICAL);
        assert!(result.is_ok());
    }

    #[test]
    fn validate_received_additive_without_critical_accepts() {
        // Non-REPLACE deltas may be transmitted under the node's standing policy.
        let sal = "A:ASD:DELTA[15.0\u{2192}15.1:H+[LACTATE]]";
        let result = validate_received_delta(sal, 0);
        assert!(result.is_ok());
    }

    #[test]
    fn validate_non_delta_sal_is_passthrough() {
        // Non-A:ASD:DELTA traffic is out of ADP scope; validator is a no-op.
        assert!(validate_received_delta("H:HR@NODE1", 0).is_ok());
        assert!(validate_received_delta("A:ASD[15.1]", 0).is_ok());
    }
}
