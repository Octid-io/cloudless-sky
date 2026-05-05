// SPDX-License-Identifier: Apache-2.0
//! eml MDR (Master Data Reference) — small reference corpus of `(ns, op, sal,
//! eml-encoding)` tuples for cross-SDK validation.
//!
//! Each entry pairs an OSMP namespace + opcode with a canonical SAL fragment
//! and the `(eml_x, eml_y)` operands a conforming SDK must use when encoding
//! that opcode through the universal binary operator `eml(x, y) = exp(x) − ln(y)`.
//!
//! Public reference corpus. The full registry (including parametric chains,
//! envelope-bounded macros, and pre/post-processing rules) is delivered with
//! the commercial precision pack — see `eml::crlibm`.

/// One entry in the public eml reference corpus.
#[derive(Debug, Clone, PartialEq)]
pub struct EmlMdrEntry {
    /// OSMP namespace prefix (e.g., `"H"`, `"E"`, `"A"`).
    pub ns: &'static str,
    /// Opcode mnemonic within the namespace (e.g., `"HR"`, `"TH"`, `"ACK"`).
    pub op: &'static str,
    /// Canonical SAL fragment for this opcode.
    pub sal: &'static str,
    /// `eml` first operand (the `x` in `exp(x)`).
    pub eml_x: f64,
    /// `eml` second operand (the `y` in `ln(y)`).
    pub eml_y: f64,
}

/// Public reference corpus. Order is lexicographic by `(ns, op)` and is
/// load-bearing for any fingerprint that hashes the corpus as a sequence.
/// Cross-SDK byte-identical with the Python, Go, and TypeScript SDK
/// reference corpora.
pub const CORPUS: &[EmlMdrEntry] = &[
    EmlMdrEntry {
        ns: "A",
        op: "ACK",
        sal: "A:ACK",
        eml_x: 0.0,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "A",
        op: "AR",
        sal: "AR@EP:1",
        eml_x: 1.0,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "B",
        op: "ALRM",
        sal: "ALRM@AREA!",
        eml_x: 1.0,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "E",
        op: "EQ",
        sal: "EQ@4A?TH:0",
        eml_x: 0.0,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "E",
        op: "TH",
        sal: "E:TH",
        eml_x: 0.5,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "H",
        op: "HR",
        sal: "H:HR",
        eml_x: 1.0,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "H",
        op: "TEMP",
        sal: "H:TEMP",
        eml_x: 0.5,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "W",
        op: "TEMP",
        sal: "W:TEMP",
        eml_x: 0.5,
        eml_y: 1.0,
    },
    EmlMdrEntry {
        ns: "Z",
        op: "TEMP",
        sal: "Z:TEMP",
        eml_x: 1.0,
        eml_y: 1.0,
    },
];

/// Returns the corpus entry for the given `(ns, op)` pair, or `None` if not present.
///
/// Lookup is case-sensitive and namespaces / opcodes use uppercase letters
/// per the SAL grammar.
pub fn eml_corpus_lookup(ns: &str, op: &str) -> Option<&'static EmlMdrEntry> {
    CORPUS.iter().find(|e| e.ns == ns && e.op == op)
}

/// Number of entries in the public reference corpus.
pub fn corpus_len() -> usize {
    CORPUS.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn corpus_nonempty() {
        assert!(corpus_len() > 0);
    }

    #[test]
    fn lookup_h_hr() {
        let entry = eml_corpus_lookup("H", "HR").expect("H:HR must be present");
        assert_eq!(entry.ns, "H");
        assert_eq!(entry.op, "HR");
        assert_eq!(entry.sal, "H:HR");
        assert_eq!(entry.eml_x, 1.0);
        assert_eq!(entry.eml_y, 1.0);
    }

    #[test]
    fn lookup_unknown_returns_none() {
        assert!(eml_corpus_lookup("ZZZ", "DOES_NOT_EXIST").is_none());
        assert!(eml_corpus_lookup("H", "DOES_NOT_EXIST").is_none());
    }

    #[test]
    fn lookup_distinguishes_namespace() {
        // H:TEMP and W:TEMP both exist but have distinct namespaces.
        let h_temp = eml_corpus_lookup("H", "TEMP").expect("H:TEMP must be present");
        let w_temp = eml_corpus_lookup("W", "TEMP").expect("W:TEMP must be present");
        assert_eq!(h_temp.ns, "H");
        assert_eq!(w_temp.ns, "W");
        // Different namespaces -> different SAL fragments.
        assert_ne!(h_temp.sal, w_temp.sal);
    }
}
