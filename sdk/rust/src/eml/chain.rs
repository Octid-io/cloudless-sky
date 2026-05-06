// SPDX-License-Identifier: Apache-2.0
//! EML chain wire codec — restricted and wide-multivariate grammars.
//!
//! Pure-Rust port of Python `osmp.eml.encode_chain_restricted` /
//! `decode_chain_restricted` / `encode_chain_wide` / `decode_chain_wide`
//! and Go `osmp.eml.EncodeChainRestricted` / `DecodeChainRestricted` /
//! `EncodeChainWide` / `DecodeChainWide`.
//!
//! Operand codes inside a chain level:
//!
//!   - `"1"`        — constant `1.0`
//!   - `<var name>` — named input variable (e.g., `"x"`, `"y"`)
//!   - `"f"`        — `f_{k-1}` (restricted-chain shorthand)
//!   - `"fN"`       — `f_N` (wide-chain explicit, `N` in `1..k`)
//!
//! Cross-SDK byte-identical wire format.

use super::eml;

/// A single chain level with two operand codes (`left`, `right`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChainLevel {
    /// Left operand code.
    pub left: String,
    /// Right operand code.
    pub right: String,
}

/// Wire-format grammar variant.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChainVariant {
    /// Single-variable restricted grammar (1 bit at L1, 2 bits at Lk≥2).
    Restricted,
    /// Wide multi-variable grammar (variable bits-per-input by `V + k`).
    WideMultivar,
}

/// An EML chain: ordered levels, named variables, and grammar variant.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Chain {
    /// Ordered chain levels.
    pub levels: Vec<ChainLevel>,
    /// Named input variables (`["x"]` for the restricted single-variable grammar).
    pub variables: Vec<String>,
    /// Grammar variant.
    pub variant: ChainVariant,
}

impl Chain {
    /// Number of chain levels.
    pub fn n_levels(&self) -> usize {
        self.levels.len()
    }

    /// Number of named variables.
    pub fn n_variables(&self) -> usize {
        self.variables.len()
    }

    /// Evaluate the chain at `values` (positional, one entry per variable).
    /// Returns the f64 result of the last level, or `0.0` for an empty chain.
    pub fn evaluate(&self, values: &[f64]) -> Result<f64, String> {
        if values.len() != self.variables.len() {
            return Err(format!(
                "got {} values, expected {}",
                values.len(),
                self.variables.len()
            ));
        }
        let mut var_map: std::collections::HashMap<&str, f64> =
            std::collections::HashMap::new();
        var_map.insert("1", 1.0);
        for (i, name) in self.variables.iter().enumerate() {
            var_map.insert(name.as_str(), values[i]);
        }
        let mut f: Vec<f64> = Vec::with_capacity(self.levels.len());
        for (k0, level) in self.levels.iter().enumerate() {
            let k = k0 + 1;
            let a = resolve_operand(&level.left, &var_map, &f, k)?;
            let b = resolve_operand(&level.right, &var_map, &f, k)?;
            f.push(eml(a, b));
        }
        Ok(f.last().copied().unwrap_or(0.0))
    }
}

fn resolve_operand(
    op: &str,
    var_map: &std::collections::HashMap<&str, f64>,
    f: &[f64],
    k: usize,
) -> Result<f64, String> {
    if op == "1" {
        return Ok(1.0);
    }
    if op == "f" {
        if k < 2 {
            return Err("'f' referenced at L1".to_string());
        }
        return Ok(f[k - 2]);
    }
    if op.len() > 1 && op.starts_with('f') {
        if let Ok(idx) = op[1..].parse::<usize>() {
            if idx >= 1 && idx < k {
                return Ok(f[idx - 1]);
            }
            return Err(format!("f{idx} out of range at L{k}"));
        }
    }
    if let Some(&v) = var_map.get(op) {
        return Ok(v);
    }
    Err(format!("unknown operand {op:?}"))
}

// ── Restricted-chain wire format ──────────────────────────────────────

/// Bit-pack a restricted (single-variable) chain. With
/// `self_describing = true` a 4-bit length nibble prefixes the payload
/// (supports `n_levels ≤ 15`).
pub fn encode_chain_restricted(c: &Chain, self_describing: bool) -> Result<Vec<u8>, String> {
    if c.variant != ChainVariant::Restricted {
        return Err("not a restricted chain".to_string());
    }
    if c.variables.len() != 1 {
        return Err("restricted chain must be single-variable".to_string());
    }
    let var_name = &c.variables[0];

    let mut bits: Vec<u8> = Vec::new();
    if self_describing {
        if c.n_levels() > 15 {
            return Err("self-describing restricted format supports N <= 15".to_string());
        }
        for i in (0..4).rev() {
            bits.push(((c.n_levels() >> i) & 1) as u8);
        }
    }
    for (k0, level) in c.levels.iter().enumerate() {
        let k = k0 + 1;
        let bits_per_input = if k == 1 { 1 } else { 2 };
        for operand in [&level.left, &level.right] {
            let op_norm = if operand == var_name { "x" } else { operand.as_str() };
            let code = match (k, op_norm) {
                (1, "1") => 0u8,
                (1, "x") => 1u8,
                (_, "1") => 0b00,
                (_, "x") => 0b01,
                (_, "f") => 0b10,
                _ => {
                    return Err(format!(
                        "operand {operand:?} not encodable at L{k} (restricted)"
                    ));
                }
            };
            for i in (0..bits_per_input).rev() {
                bits.push((code >> i) & 1);
            }
        }
    }
    Ok(pack_bits(&bits))
}

/// Decode a restricted-chain wire payload. When `self_describing = true`
/// the 4-bit length nibble is read from the head of `data`; otherwise
/// `n_levels` must be supplied.
pub fn decode_chain_restricted(
    data: &[u8],
    self_describing: bool,
    n_levels: Option<usize>,
    variable_name: &str,
) -> Result<Chain, String> {
    let bits = unpack_bits(data);
    let mut off = 0usize;
    let n: usize = if self_describing {
        if n_levels.is_some() {
            return Err("cannot pass n_levels with self_describing=true".to_string());
        }
        if bits.len() < 4 {
            return Err("truncated self-describing header".to_string());
        }
        let mut v: usize = 0;
        for _ in 0..4 {
            v = (v << 1) | bits[off] as usize;
            off += 1;
        }
        v
    } else {
        n_levels.ok_or_else(|| "n_levels required when self_describing=false".to_string())?
    };

    let mut levels: Vec<ChainLevel> = Vec::with_capacity(n);
    for k in 1..=n {
        let bits_per_input = if k == 1 { 1 } else { 2 };
        let mut ops: [String; 2] = [String::new(), String::new()];
        for op_slot in &mut ops {
            if off + bits_per_input > bits.len() {
                return Err(format!("truncated payload at L{k}"));
            }
            let mut code: u8 = 0;
            for _ in 0..bits_per_input {
                code = (code << 1) | bits[off];
                off += 1;
            }
            let decoded = match (k, code) {
                (1, 0) => "1",
                (1, 1) => "x",
                (_, 0b00) => "1",
                (_, 0b01) => "x",
                (_, 0b10) => "f",
                _ => return Err(format!("reserved operand code {code:b} at L{k}")),
            };
            *op_slot = if decoded == "x" {
                variable_name.to_string()
            } else {
                decoded.to_string()
            };
        }
        levels.push(ChainLevel {
            left: ops[0].clone(),
            right: ops[1].clone(),
        });
    }
    Ok(Chain {
        levels,
        variables: vec![variable_name.to_string()],
        variant: ChainVariant::Restricted,
    })
}

// ── Wide multi-variable chain wire format ─────────────────────────────

fn bits_per_input_at_level(v: usize, k: usize) -> usize {
    let options = v + k;
    let mut b = 0;
    while (1usize << b) < options {
        b += 1;
    }
    b.max(1)
}

/// Bit-pack a wide multi-variable chain.
pub fn encode_chain_wide(c: &Chain) -> Result<Vec<u8>, String> {
    if c.variant != ChainVariant::WideMultivar {
        return Err("not a wide-multivar chain".to_string());
    }
    let v = c.n_variables();
    let n = c.n_levels();
    if !(1..=255).contains(&v) || !(1..=255).contains(&n) {
        return Err(format!(
            "V={v}, N={n} out of supported range (1..255)"
        ));
    }
    let mut var_index: std::collections::HashMap<&str, usize> = std::collections::HashMap::new();
    for (i, name) in c.variables.iter().enumerate() {
        var_index.insert(name.as_str(), i + 1);
    }

    let mut bits: Vec<u8> = Vec::new();
    if v <= 15 && n <= 15 {
        let header: u8 = ((v as u8) << 4) | (n as u8);
        push_byte(&mut bits, header);
    } else {
        push_byte(&mut bits, 0xFF);
        push_byte(&mut bits, n as u8);
        push_byte(&mut bits, v as u8);
    }

    for (k0, level) in c.levels.iter().enumerate() {
        let k = k0 + 1;
        let bpi = bits_per_input_at_level(v, k);
        for operand in [&level.left, &level.right] {
            let idx = wide_operand_index(operand, &var_index, v, k)?;
            for i in (0..bpi).rev() {
                bits.push(((idx >> i) & 1) as u8);
            }
        }
    }
    Ok(pack_bits(&bits))
}

fn wide_operand_index(
    op: &str,
    var_index: &std::collections::HashMap<&str, usize>,
    v: usize,
    k: usize,
) -> Result<usize, String> {
    if op == "1" {
        return Ok(0);
    }
    if let Some(&idx) = var_index.get(op) {
        return Ok(idx);
    }
    if op == "f" {
        if k < 2 {
            return Err("'f' operand at L1".to_string());
        }
        return Ok(v + (k - 1));
    }
    if op.len() > 1 && op.starts_with('f') {
        if let Ok(fi) = op[1..].parse::<usize>() {
            if fi < 1 || fi >= k {
                return Err(format!("f{fi} out of range at L{k}"));
            }
            return Ok(v + fi);
        }
    }
    Err(format!("unknown operand {op:?}"))
}

/// Decode a wide multi-variable chain wire payload. Pass `None` for
/// `variables` to default to `["x1", "x2", ..., "xV"]`.
pub fn decode_chain_wide(
    data: &[u8],
    variables: Option<Vec<String>>,
) -> Result<Chain, String> {
    let bits = unpack_bits(data);
    let mut off = 0usize;
    if bits.len() < 8 {
        return Err("truncated header".to_string());
    }
    let mut header: usize = 0;
    for _ in 0..8 {
        header = (header << 1) | bits[off] as usize;
        off += 1;
    }
    let (v_count, n_count) = if header == 0xFF {
        if bits.len() < off + 16 {
            return Err("truncated extended header".to_string());
        }
        let mut n: usize = 0;
        for _ in 0..8 {
            n = (n << 1) | bits[off] as usize;
            off += 1;
        }
        let mut v: usize = 0;
        for _ in 0..8 {
            v = (v << 1) | bits[off] as usize;
            off += 1;
        }
        (v, n)
    } else {
        ((header >> 4) & 0x0F, header & 0x0F)
    };

    let variables_resolved: Vec<String> = match variables {
        None => (1..=v_count).map(|i| format!("x{i}")).collect(),
        Some(names) => {
            if names.len() != v_count {
                return Err(format!(
                    "got {} variable names, header says V={v_count}",
                    names.len()
                ));
            }
            names
        }
    };
    let idx_to_var: std::collections::HashMap<usize, String> = variables_resolved
        .iter()
        .enumerate()
        .map(|(i, name)| (i + 1, name.clone()))
        .collect();

    let mut levels: Vec<ChainLevel> = Vec::with_capacity(n_count);
    for k in 1..=n_count {
        let bpi = bits_per_input_at_level(v_count, k);
        let mut ops: [String; 2] = [String::new(), String::new()];
        for op_slot in &mut ops {
            if off + bpi > bits.len() {
                return Err(format!("truncated at L{k}"));
            }
            let mut idx: usize = 0;
            for _ in 0..bpi {
                idx = (idx << 1) | bits[off] as usize;
                off += 1;
            }
            *op_slot = if idx == 0 {
                "1".to_string()
            } else if idx <= v_count {
                idx_to_var[&idx].clone()
            } else if idx < v_count + k {
                format!("f{}", idx - v_count)
            } else {
                return Err(format!("operand idx {idx} out of range at L{k}"));
            };
        }
        levels.push(ChainLevel {
            left: ops[0].clone(),
            right: ops[1].clone(),
        });
    }
    Ok(Chain {
        levels,
        variables: variables_resolved,
        variant: ChainVariant::WideMultivar,
    })
}

// ── Bit packing helpers ───────────────────────────────────────────────

fn pack_bits(bits: &[u8]) -> Vec<u8> {
    let n = bits.len().div_ceil(8);
    let mut out = vec![0u8; n];
    for (i, &b) in bits.iter().enumerate() {
        if b != 0 {
            out[i / 8] |= 1 << (7 - (i % 8));
        }
    }
    out
}

fn unpack_bits(data: &[u8]) -> Vec<u8> {
    let mut bits: Vec<u8> = Vec::with_capacity(data.len() * 8);
    for &b in data {
        for i in (0..8).rev() {
            bits.push((b >> i) & 1);
        }
    }
    bits
}

fn push_byte(bits: &mut Vec<u8>, b: u8) {
    for i in (0..8).rev() {
        bits.push((b >> i) & 1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn restricted_chain(levels: &[(&str, &str)]) -> Chain {
        Chain {
            levels: levels
                .iter()
                .map(|(l, r)| ChainLevel {
                    left: l.to_string(),
                    right: r.to_string(),
                })
                .collect(),
            variables: vec!["x".to_string()],
            variant: ChainVariant::Restricted,
        }
    }

    #[test]
    fn evaluate_exp_x_at_zero_is_one() {
        // exp(x) = eml(x, 1)
        let c = restricted_chain(&[("x", "1")]);
        let v = c.evaluate(&[0.0]).expect("evaluate");
        // exp(0) - ln(1) = 1 - 0 = 1
        assert!((v - 1.0).abs() < 1e-15);
    }

    #[test]
    fn evaluate_e_minus_lnx_at_one() {
        // e - ln(x) = eml(1, x)
        let c = restricted_chain(&[("1", "x")]);
        let v = c.evaluate(&[1.0]).expect("evaluate");
        // exp(1) - ln(1) = e - 0 = e
        assert!((v - std::f64::consts::E).abs() < 1e-15);
    }

    #[test]
    fn evaluate_chain_with_f_reference() {
        // L1: eml(x, 1) = exp(x); L2: eml(f1, 1) = exp(f1) = exp(exp(x))
        let c = restricted_chain(&[("x", "1"), ("f", "1")]);
        let v = c.evaluate(&[0.0]).expect("evaluate");
        // exp(exp(0)) = exp(1) = e
        assert!((v - std::f64::consts::E).abs() < 1e-12);
    }

    #[test]
    fn evaluate_rejects_value_count_mismatch() {
        let c = restricted_chain(&[("x", "1")]);
        assert!(c.evaluate(&[1.0, 2.0]).is_err());
        assert!(c.evaluate(&[]).is_err());
    }

    #[test]
    fn restricted_roundtrip_self_describing() {
        let c = restricted_chain(&[("x", "1"), ("f", "x"), ("1", "f")]);
        let bytes = encode_chain_restricted(&c, true).expect("encode");
        let back = decode_chain_restricted(&bytes, true, None, "x").expect("decode");
        assert_eq!(back, c);
    }

    #[test]
    fn restricted_roundtrip_external_n_levels() {
        let c = restricted_chain(&[("x", "1"), ("f", "f"), ("1", "x")]);
        let bytes = encode_chain_restricted(&c, false).expect("encode");
        let back = decode_chain_restricted(&bytes, false, Some(3), "x").expect("decode");
        assert_eq!(back, c);
    }

    #[test]
    fn restricted_rejects_more_than_15_levels_self_describing() {
        let levels: Vec<(&str, &str)> = (0..16).map(|_| ("x", "1")).collect();
        let c = restricted_chain(&levels);
        assert!(encode_chain_restricted(&c, true).is_err());
    }

    fn wide_chain(levels: &[(&str, &str)], variables: &[&str]) -> Chain {
        Chain {
            levels: levels
                .iter()
                .map(|(l, r)| ChainLevel {
                    left: l.to_string(),
                    right: r.to_string(),
                })
                .collect(),
            variables: variables.iter().map(|s| s.to_string()).collect(),
            variant: ChainVariant::WideMultivar,
        }
    }

    #[test]
    fn wide_roundtrip_two_variables() {
        let c = wide_chain(
            &[("x", "y"), ("1", "f1"), ("f2", "x")],
            &["x", "y"],
        );
        let bytes = encode_chain_wide(&c).expect("encode");
        let back = decode_chain_wide(&bytes, Some(vec!["x".to_string(), "y".to_string()]))
            .expect("decode");
        assert_eq!(back, c);
    }

    #[test]
    fn wide_default_variable_names() {
        // Use "f1" (normalized) instead of "f" — the wide wire format
        // canonicalizes bare "f" to "f{N}" on decode, matching Go and Python.
        let c = wide_chain(&[("x1", "1"), ("f1", "x1")], &["x1"]);
        let bytes = encode_chain_wide(&c).expect("encode");
        let back = decode_chain_wide(&bytes, None).expect("decode");
        assert_eq!(back.variables, vec!["x1".to_string()]);
        assert_eq!(back.levels, c.levels);
    }

    #[test]
    fn wide_extended_header_for_large_v_or_n() {
        // Force the extended-header path with V=16. Use "f1" (normalized).
        let vars: Vec<String> = (1..=16).map(|i| format!("x{i}")).collect();
        let var_refs: Vec<&str> = vars.iter().map(|s| s.as_str()).collect();
        let c = wide_chain(&[("x1", "x16"), ("1", "f1")], &var_refs);
        let bytes = encode_chain_wide(&c).expect("encode");
        // First byte should be the 0xFF sentinel.
        assert_eq!(bytes[0], 0xFF);
        let back = decode_chain_wide(&bytes, Some(vars)).expect("decode");
        assert_eq!(back.levels, c.levels);
    }

    #[test]
    fn wide_bare_f_canonicalizes_to_indexed_on_roundtrip() {
        // Bare "f" is accepted on encode (means f_{k-1}) but the decoder
        // always emits the explicit "f{N}" form. Document that round-trip.
        let c = wide_chain(&[("x", "1"), ("f", "x")], &["x"]);
        let bytes = encode_chain_wide(&c).expect("encode");
        let back = decode_chain_wide(&bytes, Some(vec!["x".to_string()])).expect("decode");
        assert_eq!(back.levels[0], ChainLevel { left: "x".to_string(), right: "1".to_string() });
        assert_eq!(back.levels[1], ChainLevel { left: "f1".to_string(), right: "x".to_string() });
    }

    #[test]
    fn wide_rejects_invalid_variant() {
        let c = restricted_chain(&[("x", "1")]);
        assert!(encode_chain_wide(&c).is_err());
    }

    #[test]
    fn restricted_rejects_invalid_variant() {
        let c = wide_chain(&[("x", "y")], &["x", "y"]);
        assert!(encode_chain_restricted(&c, true).is_err());
    }

    #[test]
    fn pack_unpack_bits_roundtrip() {
        let bits = vec![1u8, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1];
        let packed = pack_bits(&bits);
        let unpacked = unpack_bits(&packed);
        // unpack pads to whole bytes; first 11 bits should match
        assert_eq!(&unpacked[..bits.len()], &bits[..]);
    }
}
