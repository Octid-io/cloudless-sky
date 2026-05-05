//! AdaptiveSharedDictionary — version-pinned, compiled-in floor basis.
//!
//! Cross-SDK byte-identical with Python AdaptiveSharedDictionary, Go
//! AdaptiveSharedDictionary, TypeScript AdaptiveSharedDictionary.
//!
//! Fingerprint serialization matches Python `json.dumps(data, sort_keys=True,
//! ensure_ascii=True)` exactly: `", "` and `": "` separators, non-ASCII
//! escaped as `\uXXXX`.

use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write as _;

use sha2::{Digest, Sha256};

use crate::glyphs::{asd_basis, ASD_FLOOR_VERSION as GLYPHS_FLOOR_VERSION};

/// Floor-basis version identifier exposed at the crate root.
pub const ASD_FLOOR_VERSION: &str = GLYPHS_FLOOR_VERSION;

/// CRDT delta application mode for ASD updates.
///
/// Source: Shapiro et al. "A comprehensive study of CRDTs" (2011)
/// INRIA-00555588. ADDITIVE = G-Set (grow-only), REPLACE = LWW-Register,
/// DEPRECATE = tombstone.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DictUpdateMode {
    /// Grow-only: insert if not present, never overwrite.
    Additive,
    /// Last-write-wins: insert or overwrite, clears tombstone.
    Replace,
    /// Tombstone: remove the entry from lookups.
    Deprecate,
}

/// Recorded delta entry kept in the ASD's audit log.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeltaLogEntry {
    /// Namespace key.
    pub ns: String,
    /// Opcode key.
    pub op: String,
    /// Definition string (only meaningful for Additive / Replace).
    pub def: String,
    /// Update mode applied.
    pub mode: DictUpdateMode,
    /// Version pointer for the delta (e.g. dictionary version string).
    pub ver: String,
}

/// Adaptive shared dictionary holding the v15 floor basis plus runtime deltas.
///
/// Analog: QUIC static table (RFC 9204 §A).
#[derive(Debug, Clone)]
pub struct AdaptiveSharedDictionary {
    /// Floor-basis version identifier.
    pub floor_version: String,
    data: BTreeMap<String, BTreeMap<String, String>>,
    tombstones: BTreeSet<String>,
    log: Vec<DeltaLogEntry>,
}

impl AdaptiveSharedDictionary {
    /// Construct a new dictionary seeded from the v15 floor basis.
    pub fn new() -> Self {
        let mut data: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
        for (ns, ops) in asd_basis().iter() {
            let mut owned_ops: BTreeMap<String, String> = BTreeMap::new();
            for (op, def) in ops.iter() {
                owned_ops.insert((*op).to_string(), (*def).to_string());
            }
            data.insert((*ns).to_string(), owned_ops);
        }
        Self {
            floor_version: ASD_FLOOR_VERSION.to_string(),
            data,
            tombstones: BTreeSet::new(),
            log: Vec::new(),
        }
    }

    /// Look up a definition for `(namespace, opcode)`.
    ///
    /// Returns `None` when the entry is tombstoned or not present.
    pub fn lookup(&self, namespace: &str, opcode: &str) -> Option<&str> {
        let key = format!("{namespace}::{opcode}");
        if self.tombstones.contains(&key) {
            return None;
        }
        self.data
            .get(namespace)
            .and_then(|ops| ops.get(opcode).map(String::as_str))
    }

    /// Apply a CRDT delta to the dictionary.
    pub fn apply_delta(
        &mut self,
        namespace: &str,
        opcode: &str,
        definition: &str,
        mode: DictUpdateMode,
        version_pointer: &str,
    ) {
        self.log.push(DeltaLogEntry {
            ns: namespace.to_string(),
            op: opcode.to_string(),
            def: definition.to_string(),
            mode,
            ver: version_pointer.to_string(),
        });
        let key = format!("{namespace}::{opcode}");
        match mode {
            DictUpdateMode::Additive => {
                let entry = self
                    .data
                    .entry(namespace.to_string())
                    .or_default();
                entry
                    .entry(opcode.to_string())
                    .or_insert_with(|| definition.to_string());
            }
            DictUpdateMode::Replace => {
                let entry = self
                    .data
                    .entry(namespace.to_string())
                    .or_default();
                entry.insert(opcode.to_string(), definition.to_string());
                self.tombstones.remove(&key);
            }
            DictUpdateMode::Deprecate => {
                self.tombstones.insert(key);
            }
        }
    }

    /// SHA-256 fingerprint truncated to 16 hex characters (8 bytes).
    ///
    /// Cross-SDK byte-identical with Python / Go / TypeScript fingerprint().
    pub fn fingerprint(&self) -> String {
        let canonical = self.canonical_json();
        let mut hasher = Sha256::new();
        hasher.update(canonical.as_bytes());
        let result = hasher.finalize();
        let mut hex = String::with_capacity(16);
        for byte in &result[..8] {
            write!(&mut hex, "{byte:02x}").expect("write to String never fails");
        }
        hex
    }

    /// Canonical JSON serialization of the dictionary, matching Python
    /// `json.dumps(data, sort_keys=True, ensure_ascii=True)`.
    ///
    /// Uses `", "` and `": "` separators; escapes non-ASCII to `\uXXXX`.
    /// Required for cross-SDK fingerprint wire compatibility.
    pub fn canonical_json(&self) -> String {
        let mut out = String::new();
        out.push('{');
        let ns_list = self.namespaces();
        for (i, ns) in ns_list.iter().enumerate() {
            if i > 0 {
                out.push_str(", ");
            }
            py_quote_into(ns, &mut out);
            out.push_str(": {");
            // BTreeMap iteration is already sorted by key, but for parity with
            // the other SDKs we sort explicitly here.
            let ops = self
                .data
                .get(ns.as_str())
                .expect("namespace in list must exist in data");
            let mut op_keys: Vec<&str> = ops.keys().map(String::as_str).collect();
            op_keys.sort_unstable();
            for (j, op) in op_keys.iter().enumerate() {
                if j > 0 {
                    out.push_str(", ");
                }
                py_quote_into(op, &mut out);
                out.push_str(": ");
                py_quote_into(
                    ops.get(*op).expect("op key from this map's keys"),
                    &mut out,
                );
            }
            out.push('}');
        }
        out.push('}');
        out
    }

    /// Sorted list of namespace keys currently in the dictionary.
    pub fn namespaces(&self) -> Vec<String> {
        // BTreeMap is ordered, but we collect into Vec for the public API.
        self.data.keys().cloned().collect()
    }

    /// Snapshot copy of the delta log.
    pub fn version_log(&self) -> Vec<DeltaLogEntry> {
        self.log.clone()
    }
}

impl Default for AdaptiveSharedDictionary {
    fn default() -> Self {
        Self::new()
    }
}

/// Append a Python-compatible JSON string literal to `out`.
///
/// Matches `json.dumps(s, ensure_ascii=True)`:
/// - `"` -> `\"`
/// - `\` -> `\\`
/// - control chars (< 0x20) -> `\uXXXX`
/// - non-ASCII (> 0x7e) -> `\uXXXX` (surrogate pair for codepoints above BMP)
/// - everything else: passthrough
#[allow(clippy::manual_range_contains)] // explicit `||` reads more clearly here
fn py_quote_into(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        let cp = ch as u32;
        if ch == '"' {
            out.push_str("\\\"");
        } else if ch == '\\' {
            out.push_str("\\\\");
        } else if cp < 0x20 || cp > 0x7e {
            if cp <= 0xFFFF {
                write!(out, "\\u{cp:04x}").expect("write to String never fails");
            } else {
                // Encode as UTF-16 surrogate pair to match Python behavior.
                let v = cp - 0x10000;
                let hi = 0xD800 + (v >> 10);
                let lo = 0xDC00 + (v & 0x3FF);
                write!(out, "\\u{hi:04x}\\u{lo:04x}")
                    .expect("write to String never fails");
            }
        } else {
            out.push(ch);
        }
    }
    out.push('"');
}
