//! v16 NAMESPACE STRUCTURE — 33 active namespaces.
//!
//! - 20 cleanly-converged 3-character primaries
//! - 9 refactored splits across 4 v15 letters: C/D/K/Q
//! - 3 v15 namespaces locked at 2-character form: I→ID, V→VT, X→EP
//! - 1 sovereign extension: Ω
//!
//! v15 single-letter forms are preserved as deprecated siblings. The
//! AdaptiveSharedDictionary loads BOTH v15 letters AND v16 primaries into
//! its data map so wire-format lookups resolve under either form.
//!
//! Cross-SDK byte-identical with Python ASD_BASIS_V16 / Go ASDBasisV16 /
//! TypeScript ASD_BASIS_V16.

use std::collections::BTreeMap;
use std::sync::OnceLock;

use crate::glyphs::asd_basis;

/// Maps each v15 single-letter namespace to its v16 primary (single-element
/// slice for direct mapping) or split set (multi-element slice for the four
/// split letters C/D/K/Q).
pub fn asd_v15_to_v16() -> &'static BTreeMap<&'static str, &'static [&'static str]> {
    static CACHE: OnceLock<BTreeMap<&'static str, &'static [&'static str]>> = OnceLock::new();
    CACHE.get_or_init(|| {
        let mut m: BTreeMap<&'static str, &'static [&'static str]> = BTreeMap::new();
        m.insert("A", &["AGT"]);
        m.insert("B", &["BLD"]);
        m.insert("C", &["CMP", "RES"]);
        m.insert("D", &["DAT", "QRY", "XFR"]);
        m.insert("E", &["ENV"]);
        m.insert("F", &["FED"]);
        m.insert("G", &["GEO"]);
        m.insert("H", &["HLT"]);
        m.insert("I", &["ID"]);
        m.insert("J", &["CES"]);
        m.insert("K", &["FIN", "TXN"]);
        m.insert("L", &["LOG"]);
        m.insert("M", &["MUN"]);
        m.insert("N", &["NET"]);
        m.insert("O", &["OPE"]);
        m.insert("P", &["PRO"]);
        m.insert("Q", &["QLT", "EVL", "GND"]);
        m.insert("R", &["ROB"]);
        m.insert("S", &["SEC"]);
        m.insert("T", &["TIM"]);
        m.insert("U", &["USR"]);
        m.insert("V", &["VT"]);
        m.insert("W", &["WEA"]);
        m.insert("X", &["EP"]);
        m.insert("Y", &["MEM"]);
        m.insert("Z", &["INF"]);
        m.insert("Ω", &["Ω"]);
        m
    })
}

/// Backward-compatible alias re-exported at the crate root as
/// `ASD_V15_TO_V16` (function form).
pub use asd_v15_to_v16 as ASD_V15_TO_V16;

/// Bridge composer disambiguation for split letters.
///
/// Maps `v15_letter -> opcode -> v16_primary` for the four split letters
/// C/D/K/Q. Opcodes outside these sets fall to NL passthrough at the
/// composer.
///
/// The Q namespace additionally defaults unmatched opcodes to QLT — that
/// fallback is applied in `build_asd_basis_v16()`.
pub fn bridge_split_disambiguation(
) -> &'static BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> {
    static CACHE: OnceLock<BTreeMap<&'static str, BTreeMap<&'static str, &'static str>>> =
        OnceLock::new();
    CACHE.get_or_init(|| {
        let mut m: BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> = BTreeMap::new();

        // C -> CMP: process / compute lifecycle; C -> RES: resource constraints / status
        let mut c: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        c.insert("ALLOC", "CMP");
        c.insert("FREE", "CMP");
        c.insert("KILL", "CMP");
        c.insert("CHKPT", "CMP");
        c.insert("MIGRT", "CMP");
        c.insert("PAUSE", "CMP");
        c.insert("PRTY", "CMP");
        c.insert("RESUME", "CMP");
        c.insert("RSTRT", "CMP");
        c.insert("SCALE", "CMP");
        c.insert("SPAWN", "CMP");
        c.insert("QUOTA", "RES");
        c.insert("LIMIT", "RES");
        c.insert("STAT", "RES");
        m.insert("C", c);

        // D -> DAT / QRY / XFR
        let mut d: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        d.insert("DEL", "DAT");
        d.insert("LOG", "DAT");
        d.insert("PACK", "DAT");
        d.insert("UNPACK", "DAT");
        d.insert("Q", "QRY");
        d.insert("CHUNK", "XFR");
        d.insert("PUSH", "XFR");
        d.insert("PULL", "XFR");
        d.insert("FEED", "XFR");
        d.insert("ABORT", "XFR");
        d.insert("CSUM", "XFR");
        // D:RESUME -> XFR (vs C:RESUME -> CMP); resolved by namespace context.
        d.insert("RESUME", "XFR");
        d.insert("RTN", "XFR");
        d.insert("STAT", "XFR");
        d.insert("XFER", "XFR");
        m.insert("D", d);

        // K -> FIN / TXN
        let mut k: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        k.insert("DIG", "FIN");
        k.insert("TRD", "TXN");
        k.insert("PAY", "TXN");
        k.insert("XFR", "TXN");
        k.insert("ORD", "TXN");
        m.insert("K", k);

        // Q -> EVL / GND (all others default to QLT)
        let mut q: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        q.insert("SCORE", "EVL");
        q.insert("BENCH", "EVL");
        q.insert("CITE", "GND");
        q.insert("GROUND", "GND");
        m.insert("Q", q);

        m
    })
}

/// Backward-compatible alias re-exported at the crate root.
pub use bridge_split_disambiguation as BRIDGE_SPLIT_DISAMBIGUATION;

/// Returns the v16-keyed ASD basis built from the v15 floor basis via the
/// v15->v16 sibling map and the split disambiguation rules.
///
/// For non-split letters, the entire opcode dict is migrated to the v16
/// primary key (a copy, not a shared reference).
///
/// For split letters (C/D/K/Q), opcodes are partitioned into v16 split
/// namespaces per `bridge_split_disambiguation()`. Opcodes not in any
/// split's rule set remain v15-only and are not mirrored to any v16 primary.
///
/// The Q namespace applies a default-to-QLT rule for unmapped opcodes.
///
/// Built once on first call and cached for the lifetime of the process.
pub fn asd_basis_v16() -> &'static BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> {
    static CACHE: OnceLock<BTreeMap<&'static str, BTreeMap<&'static str, &'static str>>> =
        OnceLock::new();
    CACHE.get_or_init(build_asd_basis_v16)
}

fn build_asd_basis_v16() -> BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> {
    let mut v16: BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> = BTreeMap::new();
    let basis = asd_basis();
    let v15_map = asd_v15_to_v16();
    let split_disamb = bridge_split_disambiguation();

    for (v15_letter, targets) in v15_map.iter() {
        let opcodes = match basis.get(v15_letter) {
            Some(m) => m,
            None => continue,
        };
        if targets.len() == 1 {
            // Single mapping (or sovereign Ω): copy entire opcode dict.
            let target = targets[0];
            let mut cp: BTreeMap<&'static str, &'static str> = BTreeMap::new();
            for (op, def) in opcodes.iter() {
                cp.insert(*op, *def);
            }
            v16.insert(target, cp);
        } else {
            // Split letter: partition opcodes per disambiguation table.
            let disamb = split_disamb
                .get(v15_letter)
                .expect("split letter must have disambiguation table");
            for split in targets.iter() {
                v16.entry(*split).or_default();
            }
            for (op, def) in opcodes.iter() {
                if let Some(v16_target) = disamb.get(op) {
                    v16.entry(*v16_target).or_default().insert(*op, *def);
                }
                // Orphan opcode under split letter: stays v15-only.
                // Q applies default-to-QLT below; other splits do not.
            }
        }
    }

    // Apply Q's default-to-QLT fallback.
    if let Some(q_opcodes) = basis.get("Q") {
        let q_disamb_default: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        let q_disamb = split_disamb.get("Q").unwrap_or(&q_disamb_default);
        let qlt_map = v16.entry("QLT").or_default();
        for (op, def) in q_opcodes.iter() {
            if !q_disamb.contains_key(op) {
                qlt_map.insert(*op, *def);
            }
        }
    }

    v16
}

/// Backward-compatible alias re-exported at the crate root as
/// `ASD_BASIS_V16` (function form).
pub use asd_basis_v16 as ASD_BASIS_V16;

/// Resolve a `(namespace, opcode)` pair to its v16 primary namespace.
///
/// Returns:
/// - `Some(v16_primary)` for known mappings (e.g. `("A", "ACK") -> "AGT"`,
///   `("C", "ALLOC") -> "CMP"`, `("D", "STAT") -> "XFR"`).
/// - `Some(namespace)` if the input is already a v16 primary (passthrough).
/// - `None` if the namespace is unknown or the opcode is an orphan under a
///   split letter that has no rule for it.
///
/// The Q namespace's default-to-QLT rule for unmapped opcodes is applied here.
///
/// Cross-SDK byte-identical with Python `disambiguate_to_v16` / Go
/// `DisambiguateToV16` / TypeScript `disambiguateToV16`.
pub fn disambiguate_to_v16(namespace: &str, opcode: &str) -> Option<&'static str> {
    let v16 = asd_basis_v16();
    // Already a v16 primary? Passthrough — return the static-lifetime key.
    if let Some((k, _)) = v16.get_key_value(namespace) {
        return Some(*k);
    }
    let v15_map = asd_v15_to_v16();
    let targets = v15_map.get(namespace)?;
    if targets.len() == 1 {
        return Some(targets[0]);
    }
    let split_disamb = bridge_split_disambiguation();
    if let Some(disamb) = split_disamb.get(namespace) {
        if let Some(v16_target) = disamb.get(opcode) {
            return Some(*v16_target);
        }
    }
    // Q applies default-to-QLT for unmapped opcodes.
    if namespace == "Q" {
        return Some("QLT");
    }
    // Other split letters (C, D, K) without a rule: orphan — no v16 home.
    None
}
