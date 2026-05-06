//! OSMP Wire Modes — SAIL (Semantic Assembly Isomorphic Language) and
//! SEC (Security Envelope).
//!
//! Four wire modes selectable at encode time:
//!   - `Mnemonic` (0x00)  : UTF-8 SAL text (human-readable)
//!   - `SAIL`     (0x01)  : Binary SAIL (table-decoded)
//!   - `SEC`      (0x02)  : SAL + security envelope
//!   - `SAILSEC`  (0x03)  : SAIL + security envelope
//!
//! Cross-SDK byte-identical with Python `wire.py`, Go `wire.go`, TypeScript
//! `osmp_wire.ts`. Wire layout, token table, glyph map, intern table
//! construction, AEAD primitives, signature primitives, and nonce derivation
//! salt all match.
//!
//! License: Apache-2.0

use std::collections::{BTreeSet, HashMap};

use chacha20poly1305::{
    aead::{Aead, KeyInit, Payload},
    ChaCha20Poly1305, Key, Nonce,
};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey, SECRET_KEY_LENGTH};
use rand::{rngs::OsRng, RngCore};

use crate::glyphs::asd_basis;

// ── WireMode ────────────────────────────────────────────────────────

/// Wire mode flag — selects encoding for transmission.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum WireMode {
    /// UTF-8 SAL text, human-readable.
    Mnemonic = 0x00,
    /// Binary SAIL, table-decoded.
    SAIL = 0x01,
    /// Mnemonic SAL + security envelope.
    SEC = 0x02,
    /// Binary SAIL + security envelope.
    SAILSEC = 0x03,
}

impl WireMode {
    /// Display label for this wire mode.
    pub fn label(&self) -> &'static str {
        match self {
            WireMode::Mnemonic => "OSMP",
            WireMode::SAIL => "OSMP-SAIL",
            WireMode::SEC => "OSMP-SEC",
            WireMode::SAILSEC => "OSMP-SAIL-SEC",
        }
    }

    /// Parse a wire mode byte.
    pub fn from_byte(b: u8) -> Option<WireMode> {
        match b {
            0x00 => Some(WireMode::Mnemonic),
            0x01 => Some(WireMode::SAIL),
            0x02 => Some(WireMode::SEC),
            0x03 => Some(WireMode::SAILSEC),
            _ => None,
        }
    }
}

// ── SAIL Token Table ────────────────────────────────────────────────
//
// Cross-SDK byte-identical with Python TOK_*, Go tok*, TypeScript TOK_*.

/// SAIL token: logical AND (`∧`).
pub const TOK_AND: u8 = 0x80;
/// SAIL token: logical OR (`∨`).
pub const TOK_OR: u8 = 0x81;
/// SAIL token: logical NOT (`¬`).
pub const TOK_NOT: u8 = 0x82;
/// SAIL token: implication / sequence (`→`).
pub const TOK_THEN: u8 = 0x83;
/// SAIL token: biconditional (`↔`).
pub const TOK_IFF: u8 = 0x84;
/// SAIL token: universal quantifier (`∀`).
pub const TOK_FOR_ALL: u8 = 0x85;
/// SAIL token: existential quantifier (`∃`).
pub const TOK_EXISTS: u8 = 0x86;
/// SAIL token: parallel composition (`∥`).
pub const TOK_PARALLEL: u8 = 0x87;
/// SAIL token: priority / threshold operator (`>`).
pub const TOK_PRIORITY: u8 = 0x88;
/// SAIL token: approximate equality (`~`).
pub const TOK_APPROX: u8 = 0x89;
/// SAIL token: wildcard target (`*`).
pub const TOK_WILDCARD: u8 = 0x8A;
/// SAIL token: slot assignment colon (`:` in `:k:v`).
pub const TOK_ASSIGN: u8 = 0x8B;
/// SAIL token: sequence separator (`;`).
pub const TOK_SEQUENCE: u8 = 0x8C;
/// SAIL token: query slot prefix (`?`).
pub const TOK_QUERY: u8 = 0x8D;
/// SAIL token: target prefix (`@`).
pub const TOK_TARGET: u8 = 0x8E;
/// SAIL token: repeat-every (`⟳`).
pub const TOK_REPEAT_EVERY: u8 = 0x8F;
/// SAIL token: not-equal (`≠`).
pub const TOK_NOT_EQUAL: u8 = 0x90;
/// SAIL token: priority-order (`⊕`).
pub const TOK_PRIORITY_ORDER: u8 = 0x91;
/// SAIL token: compound `¬→` (UNLESS).
pub const TOK_UNLESS: u8 = 0x92;

/// SAIL token: consequence class HAZARDOUS (`⚠`).
pub const TOK_HAZARDOUS: u8 = 0xA0;
/// SAIL token: consequence class REVERSIBLE (`↺`).
pub const TOK_REVERSIBLE: u8 = 0xA1;
/// SAIL token: consequence class IRREVERSIBLE (`⊘`).
pub const TOK_IRREVERSIBLE: u8 = 0xA2;

/// SAIL token: outcome PASS / TRUE (`⊤`).
pub const TOK_PASS_TRUE: u8 = 0xA8;
/// SAIL token: outcome FAIL / FALSE (`⊥`).
pub const TOK_FAIL_FALSE: u8 = 0xA9;

/// SAIL token: parameter delta (`Δ`).
pub const TOK_DELTA: u8 = 0xB0;
/// SAIL token: home location designator (`⌂`).
pub const TOK_HOME: u8 = 0xB1;
/// SAIL token: abort / cancel (`⊗`).
pub const TOK_ABORT_CANCEL: u8 = 0xB2;
/// SAIL token: timeout (`τ`).
pub const TOK_TIMEOUT: u8 = 0xB3;
/// SAIL token: scope-within (`∈`).
pub const TOK_SCOPE_WITHIN: u8 = 0xB4;
/// SAIL token: missing slot (`∖`).
pub const TOK_MISSING: u8 = 0xB5;

/// SAIL token: loss tolerance fail-safe (`Φ`).
pub const TOK_FAIL_SAFE: u8 = 0xC0;
/// SAIL token: loss tolerance graceful degradation (`Γ`).
pub const TOK_GRACEFUL_DEG: u8 = 0xC1;
/// SAIL token: loss tolerance atomic (`Λ`).
pub const TOK_ATOMIC: u8 = 0xC2;

/// SAIL token: dictionary update ADDITIVE (`+`).
pub const TOK_ADDITIVE: u8 = 0xD0;
/// SAIL token: dictionary update REPLACE (`←`).
pub const TOK_REPLACE: u8 = 0xD1;
/// SAIL token: dictionary update DEPRECATE (`†`).
pub const TOK_DEPRECATE: u8 = 0xD2;

/// SAIL token: namespace:opcode frame marker. Followed by 1-byte ns_index + 1-byte op_index.
pub const TOK_FRAME: u8 = 0xE0;
/// SAIL token: bracket open (`[`).
pub const TOK_BRACKET_OPEN: u8 = 0xE4;
/// SAIL token: bracket close (`]`).
pub const TOK_BRACKET_CLOSE: u8 = 0xE5;

/// SAIL token: positive varint value tag.
pub const TOK_VARINT: u8 = 0xF0;
/// SAIL token: negative varint value tag.
pub const TOK_NEGINT: u8 = 0xF1;
/// SAIL token: float16 value tag (decoder-only — encoder always uses VARINT/NEGINT).
pub const TOK_FLOAT16: u8 = 0xF2;
/// SAIL token: float32 value tag (decoder-only — encoder always uses VARINT/NEGINT).
pub const TOK_FLOAT32: u8 = 0xF3;
/// SAIL token: string value tag.
pub const TOK_STRING: u8 = 0xF4;
/// SAIL token: intern table reference. Followed by varint index.
pub const TOK_REF: u8 = 0xF5;
/// SAIL token: end-of-stream marker.
pub const TOK_END: u8 = 0xFF;

// SEC envelope mode-byte bits
const NODE_ID_LONG_FLAG: u8 = 0x04;

// ── glyph maps ──────────────────────────────────────────────────────

fn build_glyph_to_token() -> HashMap<char, u8> {
    let mut m = HashMap::new();
    m.insert('\u{2227}', TOK_AND);
    m.insert('\u{2228}', TOK_OR);
    m.insert('\u{00AC}', TOK_NOT);
    m.insert('\u{2192}', TOK_THEN);
    m.insert('\u{2194}', TOK_IFF);
    m.insert('\u{2200}', TOK_FOR_ALL);
    m.insert('\u{2203}', TOK_EXISTS);
    m.insert('\u{2225}', TOK_PARALLEL);
    m.insert('>', TOK_PRIORITY);
    m.insert('~', TOK_APPROX);
    m.insert('*', TOK_WILDCARD);
    m.insert(':', TOK_ASSIGN);
    m.insert(';', TOK_SEQUENCE);
    m.insert('?', TOK_QUERY);
    m.insert('@', TOK_TARGET);
    m.insert('\u{27F3}', TOK_REPEAT_EVERY);
    m.insert('\u{2260}', TOK_NOT_EQUAL);
    m.insert('\u{2295}', TOK_PRIORITY_ORDER);
    m.insert('\u{26A0}', TOK_HAZARDOUS);
    m.insert('\u{21BA}', TOK_REVERSIBLE);
    m.insert('\u{2298}', TOK_IRREVERSIBLE);
    m.insert('\u{22A4}', TOK_PASS_TRUE);
    m.insert('\u{22A5}', TOK_FAIL_FALSE);
    m.insert('\u{0394}', TOK_DELTA);
    m.insert('\u{2302}', TOK_HOME);
    m.insert('\u{2297}', TOK_ABORT_CANCEL);
    m.insert('\u{03C4}', TOK_TIMEOUT);
    m.insert('\u{2208}', TOK_SCOPE_WITHIN);
    m.insert('\u{2216}', TOK_MISSING);
    m.insert('\u{03A6}', TOK_FAIL_SAFE);
    m.insert('\u{0393}', TOK_GRACEFUL_DEG);
    m.insert('\u{039B}', TOK_ATOMIC);
    m.insert('+', TOK_ADDITIVE);
    m.insert('\u{2190}', TOK_REPLACE);
    m.insert('\u{2020}', TOK_DEPRECATE);
    m.insert('[', TOK_BRACKET_OPEN);
    m.insert(']', TOK_BRACKET_CLOSE);
    m
}

fn build_token_to_glyph() -> HashMap<u8, char> {
    let g2t = build_glyph_to_token();
    let mut t2g = HashMap::with_capacity(g2t.len());
    for (g, t) in g2t {
        t2g.insert(t, g);
    }
    t2g
}

// ── varint ──────────────────────────────────────────────────────────

fn encode_varint(mut v: u64) -> Vec<u8> {
    let mut out = Vec::new();
    while v > 0x7F {
        out.push(((v & 0x7F) as u8) | 0x80);
        v >>= 7;
    }
    out.push((v & 0x7F) as u8);
    out
}

fn decode_varint(data: &[u8], mut off: usize) -> (u64, usize) {
    let mut val: u64 = 0;
    let mut shift: u32 = 0;
    while off < data.len() {
        let b = data[off];
        off += 1;
        val |= ((b & 0x7F) as u64) << shift;
        if b & 0x80 == 0 {
            return (val, off);
        }
        shift += 7;
    }
    (val, off)
}

// ── opcode + intern tables (built from v15 ASD basis) ───────────────

type OpToIdx = HashMap<String, HashMap<String, u8>>;
type IdxToOp = HashMap<String, HashMap<u8, String>>;

fn build_opcode_tables() -> (OpToIdx, IdxToOp) {
    let basis = asd_basis();
    let mut op_to_idx: OpToIdx = HashMap::new();
    let mut idx_to_op: IdxToOp = HashMap::new();
    for (ns, ops) in basis {
        let mut sorted: Vec<String> = ops.keys().map(|k| (*k).to_string()).collect();
        sorted.sort();
        let mut ns_op_to_idx: HashMap<String, u8> = HashMap::new();
        let mut ns_idx_to_op: HashMap<u8, String> = HashMap::new();
        for (i, op) in sorted.iter().enumerate() {
            // Wire format reserves a single byte per opcode index. v15 has at
            // most 256 opcodes in any single namespace; assert defensively.
            assert!(i < 256, "opcode index overflow for namespace {ns}");
            ns_op_to_idx.insert(op.clone(), i as u8);
            ns_idx_to_op.insert(i as u8, op.clone());
        }
        op_to_idx.insert((*ns).to_string(), ns_op_to_idx);
        idx_to_op.insert((*ns).to_string(), ns_idx_to_op);
    }
    (op_to_idx, idx_to_op)
}

fn build_intern_table() -> Vec<String> {
    let basis = asd_basis();
    let mut str_set: BTreeSet<String> = BTreeSet::new();
    for ops in basis.values() {
        for op in ops.keys() {
            str_set.insert((*op).to_string());
        }
    }
    // Sort by length descending, then lexicographic ascending — matches Go's
    // buildInternTable ordering exactly.
    let mut all: Vec<String> = str_set.into_iter().collect();
    all.sort_by(|a, b| b.len().cmp(&a.len()).then_with(|| a.cmp(b)));

    let mut result = Vec::new();
    for s in all {
        let idx = result.len();
        let ref_cost = if idx >= 16384 {
            4
        } else if idx >= 128 {
            3
        } else {
            2
        };
        if s.len() > ref_cost {
            result.push(s);
        }
    }
    result
}

// ── SAIL Codec ──────────────────────────────────────────────────────

/// SAIL binary codec — encodes UTF-8 SAL text to a compact byte stream and
/// decodes the byte stream back to SAL text.
///
/// Construction uses the v15 ASD floor basis. Cross-SDK byte-identical with
/// Python `SailCodec`, Go `SAILCodec`, TypeScript `SailCodec` when constructed
/// against the same basis.
pub struct SAILCodec {
    op_to_idx: OpToIdx,
    idx_to_op: IdxToOp,
    str_to_ref: HashMap<String, usize>,
    ref_to_str: HashMap<usize, String>,
    glyph_to_token: HashMap<char, u8>,
    token_to_glyph: HashMap<u8, char>,
}

impl SAILCodec {
    /// Construct a new SAIL codec from the v15 ASD floor basis.
    pub fn new() -> Self {
        let (op_to_idx, idx_to_op) = build_opcode_tables();
        let intern = build_intern_table();
        let mut str_to_ref = HashMap::new();
        let mut ref_to_str = HashMap::new();
        for (i, s) in intern.into_iter().enumerate() {
            str_to_ref.insert(s.clone(), i);
            ref_to_str.insert(i, s);
        }
        Self {
            op_to_idx,
            idx_to_op,
            str_to_ref,
            ref_to_str,
            glyph_to_token: build_glyph_to_token(),
            token_to_glyph: build_token_to_glyph(),
        }
    }

    fn encode_token(&self, token: &str) -> Vec<u8> {
        if let Some(&idx) = self.str_to_ref.get(token) {
            let mut out = vec![TOK_REF];
            out.extend_from_slice(&encode_varint(idx as u64));
            if out.len() < token.len() {
                return out;
            }
        }
        token.as_bytes().to_vec()
    }

    /// Encode a UTF-8 SAL string to binary SAIL bytes.
    pub fn encode(&self, sal: &str) -> Vec<u8> {
        let runes: Vec<char> = sal.chars().collect();
        let n = runes.len();
        let mut out: Vec<u8> = Vec::with_capacity(sal.len());
        let mut pos = 0;

        while pos < n {
            let ch = runes[pos];

            // Compound: ¬→ → UNLESS
            if pos + 1 < n && ch == '\u{00AC}' && runes[pos + 1] == '\u{2192}' {
                out.push(TOK_UNLESS);
                pos += 2;
                continue;
            }

            // Multi-byte glyph
            if (ch as u32) >= 0x80 {
                if let Some(&tok) = self.glyph_to_token.get(&ch) {
                    out.push(tok);
                    pos += 1;
                    continue;
                }
            }

            // Namespace:Opcode (single-letter NS prefix uses the wire-frame index
            // = ns[0] - 'A'; matches Go's wire layout).
            if ch.is_ascii_uppercase() {
                if let Some((encoded, new_pos)) = self.try_ns_op(&runes, pos, n) {
                    out.extend_from_slice(&encoded);
                    pos = new_pos;
                    continue;
                }
            }

            // ASCII structural single-char tokens
            match ch {
                '@' | '?' | ';' | '*' | '~' => {
                    out.push(*self.glyph_to_token.get(&ch).unwrap());
                    pos += 1;
                    continue;
                }
                ':' => {
                    out.push(TOK_ASSIGN);
                    pos += 1;
                    continue;
                }
                '>' => {
                    out.push(TOK_PRIORITY);
                    pos += 1;
                    continue;
                }
                '+' => {
                    out.push(TOK_ADDITIVE);
                    pos += 1;
                    continue;
                }
                '[' => {
                    out.push(TOK_BRACKET_OPEN);
                    pos += 1;
                    continue;
                }
                ']' => {
                    out.push(TOK_BRACKET_CLOSE);
                    pos += 1;
                    continue;
                }
                _ => {}
            }

            // Alphanumeric run (with optional negative-number leading dash)
            let is_alnum_ext =
                |c: char| -> bool { c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.' };
            let neg_num_start =
                ch == '-' && pos + 1 < n && runes[pos + 1].is_ascii_digit();

            if (ch.is_ascii() && is_alnum_ext(ch)) || neg_num_start {
                let start = pos;
                while pos < n && runes[pos].is_ascii() && is_alnum_ext(runes[pos]) {
                    pos += 1;
                }
                if runes[start] == '-' {
                    pos = start + 1;
                    while pos < n && runes[pos].is_ascii() && is_alnum_ext(runes[pos]) {
                        pos += 1;
                    }
                }
                let token: String = runes[start..pos].iter().collect();
                if let Some(num_bytes) = self.try_numeric(&token) {
                    out.extend_from_slice(&num_bytes);
                } else {
                    out.extend_from_slice(&self.encode_token(&token));
                }
                continue;
            }

            // Remaining ASCII single chars
            if ch.is_ascii() {
                out.extend_from_slice(&self.encode_token(&ch.to_string()));
                pos += 1;
                continue;
            }

            // Unknown Unicode — emit raw UTF-8 bytes
            let mut buf = [0u8; 4];
            out.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
            pos += 1;
        }

        out.push(TOK_END);
        out
    }

    fn try_ns_op(&self, runes: &[char], pos: usize, n: usize) -> Option<(Vec<u8>, usize)> {
        let end = (pos + 3).min(n);
        let colon = runes[pos..end]
            .iter()
            .position(|&c| c == ':')
            .map(|p| pos + p)?;
        if colon <= pos || colon - pos > 2 {
            return None;
        }
        let ns: String = runes[pos..colon].iter().collect();
        if !ns.chars().next()?.is_ascii_uppercase() {
            return None;
        }
        // Wire frame uses single-byte ns_index = first ASCII letter - 'A'.
        let ns_index = ns.as_bytes()[0] - b'A';
        let op_start = colon + 1;
        let mut op_end = op_start;
        // U+00A7 (§) admitted into opcode class; matches Python/TS/Go for the
        // I:§ sentinel (instructional namespace frame marker).
        while op_end < n {
            let c = runes[op_end];
            if c.is_ascii_uppercase() || c.is_ascii_digit() || c as u32 == 0x00A7 {
                op_end += 1;
            } else {
                break;
            }
        }
        let opcode: String = runes[op_start..op_end].iter().collect();
        if opcode.is_empty() {
            return None;
        }
        let ns_ops = self.op_to_idx.get(&ns)?;
        let &op_idx = ns_ops.get(&opcode)?;
        Some((vec![TOK_FRAME, ns_index, op_idx], op_end))
    }

    fn try_numeric(&self, token: &str) -> Option<Vec<u8>> {
        let is_neg = token.starts_with('-');
        let num_part = if is_neg { &token[1..] } else { token };
        if num_part.is_empty() {
            return None;
        }
        let mut has_dot = false;
        let mut pure = true;
        for c in num_part.chars() {
            if c == '.' {
                if has_dot {
                    pure = false;
                    break;
                }
                has_dot = true;
            } else if !c.is_ascii_digit() {
                pure = false;
                break;
            }
        }
        if !pure {
            return None;
        }
        let has_leading_zero =
            !is_neg && num_part.len() > 1 && num_part.as_bytes()[0] == b'0';
        if has_dot || has_leading_zero {
            return None;
        }
        let mut val: u64 = 0;
        for c in num_part.chars() {
            val = val * 10 + (c as u64 - '0' as u64);
        }
        let mut out: Vec<u8> = Vec::new();
        out.push(if is_neg { TOK_NEGINT } else { TOK_VARINT });
        out.extend_from_slice(&encode_varint(val));
        Some(out)
    }

    /// Decode binary SAIL bytes back to UTF-8 SAL text.
    pub fn decode(&self, data: &[u8]) -> String {
        let mut parts: Vec<String> = Vec::new();
        let mut pos = 0;
        let n = data.len();

        while pos < n {
            let b = data[pos];
            if b == TOK_END {
                break;
            }
            if b == TOK_FRAME {
                pos += 1;
                if pos + 1 >= n {
                    break;
                }
                let ns_idx = data[pos];
                pos += 1;
                let op_idx = data[pos];
                pos += 1;
                let ns = if ns_idx < 26 {
                    ((b'A' + ns_idx) as char).to_string()
                } else {
                    format!("?{}", ns_idx)
                };
                let opcode = self
                    .idx_to_op
                    .get(&ns)
                    .and_then(|m| m.get(&op_idx))
                    .cloned()
                    .unwrap_or_else(|| format!("?{}", op_idx));
                parts.push(format!("{}:{}", ns, opcode));
                continue;
            }
            if b == TOK_REF {
                pos += 1;
                let (idx, new_pos) = decode_varint(data, pos);
                pos = new_pos;
                if let Some(s) = self.ref_to_str.get(&(idx as usize)) {
                    parts.push(s.clone());
                } else {
                    parts.push(format!("?REF{}", idx));
                }
                continue;
            }
            if b == TOK_STRING {
                pos += 1;
                let (str_len, new_pos) = decode_varint(data, pos);
                pos = new_pos;
                let str_len = str_len as usize;
                if pos + str_len <= n {
                    parts.push(String::from_utf8_lossy(&data[pos..pos + str_len]).into_owned());
                    pos += str_len;
                }
                continue;
            }
            if let Some(&g) = self.token_to_glyph.get(&b) {
                parts.push(g.to_string());
                pos += 1;
                continue;
            }
            if b == TOK_VARINT {
                pos += 1;
                let (v, new_pos) = decode_varint(data, pos);
                pos = new_pos;
                parts.push(format!("{}", v));
                continue;
            }
            if b == TOK_NEGINT {
                pos += 1;
                let (v, new_pos) = decode_varint(data, pos);
                pos = new_pos;
                parts.push(format!("-{}", v));
                continue;
            }
            // FLOAT16/FLOAT32 decode paths intentionally omitted — encoder
            // never emits these tokens (numeric runs always go via VARINT/NEGINT).
            if b < 0x80 {
                parts.push((b as char).to_string());
                pos += 1;
                continue;
            }
            pos += 1;
        }
        parts.join("")
    }
}

impl Default for SAILCodec {
    fn default() -> Self {
        Self::new()
    }
}

// ── SEC Codec ───────────────────────────────────────────────────────

/// Canonical SEC nonce salt — pads short envelope headers up to the 12-byte
/// ChaCha20-Poly1305 nonce length. Identical across Python, TypeScript, Go
/// SDKs.
pub const SEC_NONCE_SALT: &[u8] = b"OSMP-SEC-v1\x00";

/// Errors returned by SEC envelope construction and parsing.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SecError {
    /// `node_id` must be 2 or 4 bytes.
    InvalidNodeId,
    /// Key length or content invalid.
    InvalidKey(String),
    /// AEAD authentication tag did not verify.
    AuthFailure,
    /// Ed25519 signature did not verify.
    SignatureFailure,
    /// Envelope shorter than minimum (87 bytes for 2-byte node_id).
    ShortEnvelope,
    /// Unknown wire mode in the envelope mode byte.
    BadMode(u8),
}

impl std::fmt::Display for SecError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SecError::InvalidNodeId => write!(f, "node_id must be 2 or 4 bytes"),
            SecError::InvalidKey(s) => write!(f, "invalid key: {s}"),
            SecError::AuthFailure => write!(f, "AEAD authentication failure"),
            SecError::SignatureFailure => write!(f, "Ed25519 signature verification failure"),
            SecError::ShortEnvelope => write!(f, "envelope too short"),
            SecError::BadMode(b) => write!(f, "unknown wire mode 0x{b:02x}"),
        }
    }
}

impl std::error::Error for SecError {}

/// SEC envelope: parsed structure containing the unsealed payload and
/// authenticated metadata.
#[derive(Debug, Clone)]
pub struct SecEnvelope {
    /// Wire mode encoded in the envelope.
    pub mode: WireMode,
    /// Sender node identifier (2 or 4 bytes).
    pub node_id: Vec<u8>,
    /// Monotonic per-sender sequence counter.
    pub seq_counter: u32,
    /// Decrypted plaintext payload.
    pub payload: Vec<u8>,
    /// 16-byte ChaCha20-Poly1305 authentication tag.
    pub auth_tag: Vec<u8>,
    /// 64-byte Ed25519 signature.
    pub signature: Vec<u8>,
}

/// Security envelope codec — Ed25519 signatures + ChaCha20-Poly1305 AEAD.
///
/// Cross-SDK byte-identical wire format with Python `SecCodec`, Go `SecCodec`,
/// TypeScript `SecCodec`. Uses canonical `SEC_NONCE_SALT` for deterministic
/// nonce derivation.
pub struct SecCodec {
    node_id: Vec<u8>,
    signing_key: SigningKey,
    verify_key: VerifyingKey,
    aead: ChaCha20Poly1305,
    seq_counter: u32,
}

impl SecCodec {
    /// Construct a SEC codec.
    /// - `node_id` must be 2 or 4 bytes.
    /// - `signing_key_seed`, when `Some`, must be 32 bytes (Ed25519 seed). When
    ///   `None`, a fresh random seed is generated.
    /// - `symmetric_key`, when `Some`, must be 32 bytes (ChaCha20-Poly1305
    ///   key). When `None`, a fresh random key is generated.
    pub fn new(
        node_id: &[u8],
        signing_key_seed: Option<&[u8]>,
        symmetric_key: Option<&[u8]>,
    ) -> Result<Self, SecError> {
        Self::new_with_verify_key(node_id, signing_key_seed, symmetric_key, None)
    }

    /// Full constructor including a peer public key for inter-node
    /// verification. If `verify_key` is `None`, the codec defaults to verifying
    /// with its own public key (loopback / local-only).
    pub fn new_with_verify_key(
        node_id: &[u8],
        signing_key_seed: Option<&[u8]>,
        symmetric_key: Option<&[u8]>,
        verify_key: Option<&[u8]>,
    ) -> Result<Self, SecError> {
        if node_id.len() != 2 && node_id.len() != 4 {
            return Err(SecError::InvalidNodeId);
        }

        let seed: [u8; SECRET_KEY_LENGTH] = match signing_key_seed {
            Some(s) => {
                if s.len() != SECRET_KEY_LENGTH {
                    return Err(SecError::InvalidKey(format!(
                        "signing seed must be {SECRET_KEY_LENGTH} bytes, got {}",
                        s.len()
                    )));
                }
                let mut arr = [0u8; SECRET_KEY_LENGTH];
                arr.copy_from_slice(s);
                arr
            }
            None => {
                let mut arr = [0u8; SECRET_KEY_LENGTH];
                OsRng.fill_bytes(&mut arr);
                arr
            }
        };
        let signing_key = SigningKey::from_bytes(&seed);
        let own_verify = signing_key.verifying_key();

        let verify_key_final = match verify_key {
            Some(vk) => {
                if vk.len() != 32 {
                    return Err(SecError::InvalidKey(format!(
                        "verify key must be 32 bytes, got {}",
                        vk.len()
                    )));
                }
                let mut arr = [0u8; 32];
                arr.copy_from_slice(vk);
                VerifyingKey::from_bytes(&arr)
                    .map_err(|e| SecError::InvalidKey(format!("ed25519: {e}")))?
            }
            None => own_verify,
        };

        let sym_key: [u8; 32] = match symmetric_key {
            Some(k) => {
                if k.len() != 32 {
                    return Err(SecError::InvalidKey(format!(
                        "symmetric key must be 32 bytes, got {}",
                        k.len()
                    )));
                }
                let mut arr = [0u8; 32];
                arr.copy_from_slice(k);
                arr
            }
            None => {
                let mut arr = [0u8; 32];
                OsRng.fill_bytes(&mut arr);
                arr
            }
        };
        let aead = ChaCha20Poly1305::new(Key::from_slice(&sym_key));

        Ok(Self {
            node_id: node_id.to_vec(),
            signing_key,
            verify_key: verify_key_final,
            aead,
            seq_counter: 0,
        })
    }

    /// Returns the 32-byte raw Ed25519 public key for distribution to peers.
    pub fn public_signing_key(&self) -> [u8; 32] {
        self.signing_key.verifying_key().to_bytes()
    }

    /// Derive 12-byte ChaCha20-Poly1305 nonce from envelope header padded with
    /// canonical `SEC_NONCE_SALT`. Cross-SDK byte-identical with Go/Python/TS.
    fn derive_nonce(&self, header: &[u8]) -> [u8; 12] {
        let mut out = [0u8; 12];
        if header.len() >= 12 {
            out.copy_from_slice(&header[..12]);
        } else {
            out[..header.len()].copy_from_slice(header);
            let need = 12 - header.len();
            out[header.len()..].copy_from_slice(&SEC_NONCE_SALT[..need]);
        }
        out
    }

    fn seal(&self, ad: &[u8], payload: &[u8]) -> Result<(Vec<u8>, Vec<u8>), SecError> {
        let nonce_bytes = self.derive_nonce(ad);
        let nonce = Nonce::from_slice(&nonce_bytes);
        let sealed = self
            .aead
            .encrypt(
                nonce,
                Payload {
                    msg: payload,
                    aad: ad,
                },
            )
            .map_err(|_| SecError::AuthFailure)?;
        let tag_off = sealed.len() - 16;
        let ciphertext = sealed[..tag_off].to_vec();
        let auth_tag = sealed[tag_off..].to_vec();
        Ok((ciphertext, auth_tag))
    }

    fn open(&self, ad: &[u8], ciphertext: &[u8], auth_tag: &[u8]) -> Result<Vec<u8>, SecError> {
        let nonce_bytes = self.derive_nonce(ad);
        let nonce = Nonce::from_slice(&nonce_bytes);
        let mut combined: Vec<u8> = Vec::with_capacity(ciphertext.len() + auth_tag.len());
        combined.extend_from_slice(ciphertext);
        combined.extend_from_slice(auth_tag);
        self.aead
            .decrypt(
                nonce,
                Payload {
                    msg: &combined,
                    aad: ad,
                },
            )
            .map_err(|_| SecError::AuthFailure)
    }

    /// Pack a payload into a SEC-wrapped envelope. Mode is encoded in the
    /// envelope header byte; ChaCha20-Poly1305 seals the payload and Ed25519
    /// signs the entire (header || ciphertext || auth_tag) prefix.
    pub fn pack(&mut self, payload: &[u8], mode: WireMode) -> Result<Vec<u8>, SecError> {
        let mut mode_byte = (mode as u8) & 0x03;
        if self.node_id.len() == 4 {
            mode_byte |= NODE_ID_LONG_FLAG;
        }
        self.seq_counter = self.seq_counter.wrapping_add(1);
        let seq_buf = self.seq_counter.to_be_bytes();
        let mut header: Vec<u8> = Vec::with_capacity(1 + self.node_id.len() + 4);
        header.push(mode_byte);
        header.extend_from_slice(&self.node_id);
        header.extend_from_slice(&seq_buf);
        let (ciphertext, auth_tag) = self.seal(&header, payload)?;
        let mut sign_input: Vec<u8> =
            Vec::with_capacity(header.len() + ciphertext.len() + auth_tag.len());
        sign_input.extend_from_slice(&header);
        sign_input.extend_from_slice(&ciphertext);
        sign_input.extend_from_slice(&auth_tag);
        let sig: Signature = self.signing_key.sign(&sign_input);
        let sig_bytes = sig.to_bytes();
        let mut result: Vec<u8> = Vec::with_capacity(sign_input.len() + sig_bytes.len());
        result.extend_from_slice(&sign_input);
        result.extend_from_slice(&sig_bytes);
        Ok(result)
    }

    /// Unpack a SEC-wrapped envelope. Verifies AEAD tag and Ed25519 signature.
    pub fn unpack(&self, data: &[u8]) -> Result<SecEnvelope, SecError> {
        if data.len() < 87 {
            return Err(SecError::ShortEnvelope);
        }
        let mode_byte = data[0];
        let mode =
            WireMode::from_byte(mode_byte & 0x03).ok_or(SecError::BadMode(mode_byte))?;
        let node_id_len = if mode_byte & NODE_ID_LONG_FLAG != 0 { 4 } else { 2 };
        let mut pos = 1usize;
        if data.len() < pos + node_id_len + 4 + 80 {
            return Err(SecError::ShortEnvelope);
        }
        let node_id = data[pos..pos + node_id_len].to_vec();
        pos += node_id_len;
        let seq_counter = u32::from_be_bytes([
            data[pos], data[pos + 1], data[pos + 2], data[pos + 3],
        ]);
        pos += 4;
        let header = data[..pos].to_vec();
        let payload_end = data.len() - 80;
        if payload_end < pos {
            return Err(SecError::ShortEnvelope);
        }
        let ciphertext = &data[pos..payload_end];
        let auth_tag = &data[payload_end..payload_end + 16];
        let signature_bytes = &data[payload_end + 16..payload_end + 80];

        // Verify AEAD
        let plaintext = self.open(&header, ciphertext, auth_tag)?;

        // Verify signature
        let mut sign_input: Vec<u8> =
            Vec::with_capacity(header.len() + ciphertext.len() + auth_tag.len());
        sign_input.extend_from_slice(&header);
        sign_input.extend_from_slice(ciphertext);
        sign_input.extend_from_slice(auth_tag);
        let mut sig_arr = [0u8; 64];
        sig_arr.copy_from_slice(signature_bytes);
        let signature = Signature::from_bytes(&sig_arr);
        self.verify_key
            .verify(&sign_input, &signature)
            .map_err(|_| SecError::SignatureFailure)?;

        Ok(SecEnvelope {
            mode,
            node_id,
            seq_counter,
            payload: plaintext,
            auth_tag: auth_tag.to_vec(),
            signature: signature_bytes.to_vec(),
        })
    }
}

// ── Unified Wire Codec ──────────────────────────────────────────────

/// Errors returned by `OSMPWireCodec`.
#[derive(Debug)]
pub enum WireError {
    /// Underlying SEC envelope error.
    Sec(SecError),
}

impl std::fmt::Display for WireError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WireError::Sec(e) => write!(f, "SEC error: {e}"),
        }
    }
}

impl std::error::Error for WireError {}

impl From<SecError> for WireError {
    fn from(e: SecError) -> Self {
        WireError::Sec(e)
    }
}

/// Unified wire codec routing among the four wire modes (Mnemonic / SAIL /
/// SEC / SAILSEC). Cross-SDK byte-identical with Go `OSMPWireCodec`, Python
/// `OsmpWireCodec`, TypeScript `OSMPWireCodec`.
pub struct OSMPWireCodec {
    /// Underlying SAIL binary codec.
    pub sail: SAILCodec,
    /// Underlying SEC envelope codec.
    pub sec: SecCodec,
}

impl OSMPWireCodec {
    /// Construct a new unified wire codec.
    pub fn new(
        node_id: &[u8],
        signing_key_seed: Option<&[u8]>,
        symmetric_key: Option<&[u8]>,
    ) -> Result<Self, SecError> {
        let nid: &[u8] = if node_id.is_empty() {
            &[0x00, 0x01]
        } else {
            node_id
        };
        Ok(Self {
            sail: SAILCodec::new(),
            sec: SecCodec::new(nid, signing_key_seed, symmetric_key)?,
        })
    }

    /// Encode a SAL string to wire bytes for the given mode.
    pub fn encode(&mut self, sal: &str, mode: WireMode) -> Result<Vec<u8>, WireError> {
        match mode {
            WireMode::Mnemonic => Ok(sal.as_bytes().to_vec()),
            WireMode::SAIL => Ok(self.sail.encode(sal)),
            WireMode::SEC => Ok(self.sec.pack(sal.as_bytes(), WireMode::SEC)?),
            WireMode::SAILSEC => {
                let bin = self.sail.encode(sal);
                Ok(self.sec.pack(&bin, WireMode::SAILSEC)?)
            }
        }
    }

    /// Decode wire bytes to a SAL string for the given mode.
    pub fn decode(&self, data: &[u8], mode: WireMode) -> Result<String, WireError> {
        match mode {
            WireMode::Mnemonic => Ok(String::from_utf8_lossy(data).into_owned()),
            WireMode::SAIL => Ok(self.sail.decode(data)),
            WireMode::SEC => {
                let env = self.sec.unpack(data)?;
                Ok(String::from_utf8_lossy(&env.payload).into_owned())
            }
            WireMode::SAILSEC => {
                let env = self.sec.unpack(data)?;
                Ok(self.sail.decode(&env.payload))
            }
        }
    }
}
