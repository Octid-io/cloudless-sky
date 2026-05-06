// SPDX-License-Identifier: Apache-2.0
//! EML expression-tree representation and paper wire format.
//!
//! Pure-Rust port of Python `osmp.eml.EMLNode` / `encode_tree` / `decode_tree`
//! and Go `osmp.eml.Node` / `EncodeTree` / `DecodeTree`.
//!
//! Grammar:  `S → constant | var_x | eml(S, S)`
//!
//! Leaves carry either a numeric constant or a variable-`x` sentinel.
//! Branches apply the universal binary operator `eml(left, right)`.
//!
//! Wire format tags:
//!
//! | Tag             | Byte | Payload                 |
//! |-----------------|------|-------------------------|
//! | `TAG_LEAF_F32`  | 0x00 | 4-byte little-endian f32|
//! | `TAG_BRANCH`    | 0x01 | left subtree, right subtree |
//! | `TAG_VAR_X`     | 0x02 | (no payload)            |
//! | `TAG_LEAF_F64`  | 0x03 | 8-byte little-endian f64|
//!
//! Cross-SDK byte-identical with the Python and Go encoders at the same
//! `use_f64` setting.

use super::eml;

/// Wire tag: leaf carrying a 4-byte little-endian f32 constant.
pub const TAG_LEAF_F32: u8 = 0x00;
/// Wire tag: branch — followed by left subtree, then right subtree.
pub const TAG_BRANCH: u8 = 0x01;
/// Wire tag: variable-x leaf (no payload).
pub const TAG_VAR_X: u8 = 0x02;
/// Wire tag: leaf carrying an 8-byte little-endian f64 constant.
pub const TAG_LEAF_F64: u8 = 0x03;

/// A node in an EML expression tree. Either a leaf (constant or variable-x)
/// or a branch carrying two children.
///
/// Invariant: a leaf has `left` and `right` both `None`; a branch has both
/// `Some`. Use the [`leaf`], [`var_x`], and [`branch`] constructors to
/// preserve the invariant.
#[derive(Debug, Clone, PartialEq)]
pub struct EMLNode {
    /// Left child of a branch; `None` on leaves.
    pub left: Option<Box<EMLNode>>,
    /// Right child of a branch; `None` on leaves.
    pub right: Option<Box<EMLNode>>,
    /// Numeric value carried by a constant leaf. Ignored when `is_x` is set
    /// or when this is a branch.
    pub value: f64,
    /// `true` when this node is the variable-x leaf.
    pub is_x: bool,
}

impl EMLNode {
    /// True if this node is a leaf (no children).
    pub fn is_leaf(&self) -> bool {
        self.left.is_none() && self.right.is_none()
    }

    /// Tree depth (leaf = 0, branch = 1 + max(child depths)). Recursive.
    pub fn depth(&self) -> usize {
        match (&self.left, &self.right) {
            (Some(l), Some(r)) => 1 + l.depth().max(r.depth()),
            _ => 0,
        }
    }

    /// Total node count including this node. Recursive.
    pub fn node_count(&self) -> usize {
        match (&self.left, &self.right) {
            (Some(l), Some(r)) => 1 + l.node_count() + r.node_count(),
            _ => 1,
        }
    }

    /// Evaluate the tree at variable value `x`. For a constant leaf returns
    /// the leaf's value; for a variable-x leaf returns `x`; for a branch
    /// returns `eml(left.evaluate(x), right.evaluate(x))`.
    pub fn evaluate(&self, x: f64) -> f64 {
        match (&self.left, &self.right) {
            (Some(l), Some(r)) => eml(l.evaluate(x), r.evaluate(x)),
            _ => {
                if self.is_x {
                    x
                } else {
                    self.value
                }
            }
        }
    }
}

/// Construct a constant-leaf node with the given numeric value.
pub fn leaf(value: f64) -> EMLNode {
    EMLNode {
        left: None,
        right: None,
        value,
        is_x: false,
    }
}

/// Construct the variable-x leaf node.
pub fn var_x() -> EMLNode {
    EMLNode {
        left: None,
        right: None,
        value: 0.0,
        is_x: true,
    }
}

/// Construct a branch node `eml(left, right)`.
pub fn branch(left: EMLNode, right: EMLNode) -> EMLNode {
    EMLNode {
        left: Some(Box::new(left)),
        right: Some(Box::new(right)),
        value: 0.0,
        is_x: false,
    }
}

/// The canonical constant-1 leaf.
pub fn one() -> EMLNode {
    leaf(1.0)
}

// ── Paper tree wire format ────────────────────────────────────────────

/// Serialize an EML tree to the paper wire format.
///
/// `use_f64 = false` emits 4-byte f32 leaves (5 bytes per leaf).
/// `use_f64 = true` emits 8-byte f64 leaves (9 bytes per leaf).
pub fn encode_tree(tree: &EMLNode, use_f64: bool) -> Vec<u8> {
    let mut buf = Vec::new();
    encode_node(&mut buf, tree, use_f64);
    buf
}

fn encode_node(buf: &mut Vec<u8>, n: &EMLNode, use_f64: bool) {
    match (&n.left, &n.right) {
        (Some(l), Some(r)) => {
            buf.push(TAG_BRANCH);
            encode_node(buf, l, use_f64);
            encode_node(buf, r, use_f64);
        }
        _ => {
            if n.is_x {
                buf.push(TAG_VAR_X);
                return;
            }
            if use_f64 {
                buf.push(TAG_LEAF_F64);
                buf.extend_from_slice(&n.value.to_le_bytes());
            } else {
                buf.push(TAG_LEAF_F32);
                buf.extend_from_slice(&(n.value as f32).to_le_bytes());
            }
        }
    }
}

/// Deserialize an EML tree from the paper wire format. Returns an error on
/// trailing bytes, truncated leaves, or unknown tags.
pub fn decode_tree(data: &[u8]) -> Result<EMLNode, String> {
    let (node, off) = decode_node(data, 0)?;
    if off != data.len() {
        return Err(format!("trailing bytes after tree: {}", data.len() - off));
    }
    Ok(node)
}

fn decode_node(data: &[u8], mut offset: usize) -> Result<(EMLNode, usize), String> {
    if offset >= data.len() {
        return Err("unexpected end of tree data".to_string());
    }
    let tag = data[offset];
    offset += 1;
    match tag {
        TAG_VAR_X => Ok((var_x(), offset)),
        TAG_LEAF_F32 => {
            if offset + 4 > data.len() {
                return Err("truncated float32 leaf".to_string());
            }
            let mut buf = [0u8; 4];
            buf.copy_from_slice(&data[offset..offset + 4]);
            let f = f32::from_le_bytes(buf);
            Ok((leaf(f as f64), offset + 4))
        }
        TAG_LEAF_F64 => {
            if offset + 8 > data.len() {
                return Err("truncated float64 leaf".to_string());
            }
            let mut buf = [0u8; 8];
            buf.copy_from_slice(&data[offset..offset + 8]);
            let f = f64::from_le_bytes(buf);
            Ok((leaf(f), offset + 8))
        }
        TAG_BRANCH => {
            let (l, off2) = decode_node(data, offset)?;
            let (r, off3) = decode_node(data, off2)?;
            Ok((branch(l, r), off3))
        }
        other => Err(format!("invalid tree tag: 0x{other:02x}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn leaf_is_leaf() {
        let n = leaf(2.5);
        assert!(n.is_leaf());
        assert_eq!(n.depth(), 0);
        assert_eq!(n.node_count(), 1);
        assert_eq!(n.value, 2.5);
        assert!(!n.is_x);
    }

    #[test]
    fn var_x_is_leaf_and_x() {
        let n = var_x();
        assert!(n.is_leaf());
        assert!(n.is_x);
    }

    #[test]
    fn branch_depth_and_count() {
        // eml(eml(x, 1), 1) — depth 2, 5 nodes.
        let inner = branch(var_x(), one());
        let tree = branch(inner, one());
        assert_eq!(tree.depth(), 2);
        assert_eq!(tree.node_count(), 5);
        assert!(!tree.is_leaf());
    }

    #[test]
    fn evaluate_leaf_constant() {
        let n = leaf(42.0);
        assert_eq!(n.evaluate(0.0), 42.0);
        assert_eq!(n.evaluate(123.0), 42.0); // x ignored for constant leaves
    }

    #[test]
    fn evaluate_var_x_returns_x() {
        let n = var_x();
        assert_eq!(n.evaluate(7.5), 7.5);
        assert_eq!(n.evaluate(-3.0), -3.0);
    }

    #[test]
    fn evaluate_exp_x_at_zero() {
        // exp(x) = eml(x, 1)
        let tree = branch(var_x(), one());
        let v = tree.evaluate(0.0);
        // exp(0) - ln(1) = 1 - 0 = 1
        assert!((v - 1.0).abs() < 1e-15);
    }

    #[test]
    fn evaluate_exp_exp_x() {
        // exp(exp(x)) = eml(eml(x, 1), 1)
        let inner = branch(var_x(), one());
        let tree = branch(inner, one());
        let v = tree.evaluate(0.0);
        // exp(exp(0)) = exp(1) = e
        assert!((v - std::f64::consts::E).abs() < 1e-12);
    }

    #[test]
    fn encode_tree_var_x_single_byte() {
        let bytes = encode_tree(&var_x(), false);
        assert_eq!(bytes, vec![TAG_VAR_X]);
    }

    #[test]
    fn encode_tree_leaf_f32_five_bytes() {
        let bytes = encode_tree(&leaf(1.0), false);
        assert_eq!(bytes.len(), 5);
        assert_eq!(bytes[0], TAG_LEAF_F32);
        // f32 1.0 LE = 0x00, 0x00, 0x80, 0x3F
        assert_eq!(&bytes[1..], &[0x00, 0x00, 0x80, 0x3F]);
    }

    #[test]
    fn encode_tree_leaf_f64_nine_bytes() {
        let bytes = encode_tree(&leaf(1.0), true);
        assert_eq!(bytes.len(), 9);
        assert_eq!(bytes[0], TAG_LEAF_F64);
        // f64 1.0 LE = 0x00 * 6, 0xF0, 0x3F
        assert_eq!(&bytes[1..], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xF0, 0x3F]);
    }

    #[test]
    fn encode_tree_branch_recursive() {
        let tree = branch(var_x(), one());
        let bytes = encode_tree(&tree, false);
        // Branch tag, then var_x tag, then leaf-f32 1.0 (5 bytes).
        assert_eq!(bytes[0], TAG_BRANCH);
        assert_eq!(bytes[1], TAG_VAR_X);
        assert_eq!(bytes[2], TAG_LEAF_F32);
        assert_eq!(bytes.len(), 1 + 1 + 5);
    }

    #[test]
    fn decode_tree_var_x() {
        let n = decode_tree(&[TAG_VAR_X]).expect("decode");
        assert!(n.is_x);
        assert!(n.is_leaf());
    }

    #[test]
    fn decode_tree_leaf_f64() {
        let pi = std::f64::consts::PI;
        let mut bytes = vec![TAG_LEAF_F64];
        bytes.extend_from_slice(&pi.to_le_bytes());
        let n = decode_tree(&bytes).expect("decode");
        assert!(n.is_leaf());
        assert!(!n.is_x);
        assert_eq!(n.value, pi);
    }

    #[test]
    fn decode_tree_truncated_leaf_errors() {
        // Tag byte present but no float bytes.
        assert!(decode_tree(&[TAG_LEAF_F32]).is_err());
        assert!(decode_tree(&[TAG_LEAF_F64]).is_err());
    }

    #[test]
    fn decode_tree_invalid_tag_errors() {
        assert!(decode_tree(&[0xFE]).is_err());
    }

    #[test]
    fn decode_tree_trailing_bytes_error() {
        // Valid var_x followed by garbage.
        assert!(decode_tree(&[TAG_VAR_X, 0xFF]).is_err());
    }

    #[test]
    fn decode_tree_empty_errors() {
        assert!(decode_tree(&[]).is_err());
    }

    #[test]
    fn encode_decode_tree_roundtrip_f32() {
        let tree = branch(branch(var_x(), one()), branch(one(), var_x()));
        let bytes = encode_tree(&tree, false);
        let back = decode_tree(&bytes).expect("decode");
        // f32 round-trip is exact for integer-valued constants like 1.0.
        assert_eq!(back, tree);
    }

    #[test]
    fn encode_decode_tree_roundtrip_f64() {
        // f64 round-trip for fractional constant.
        let tree = branch(leaf(std::f64::consts::E), var_x());
        let bytes = encode_tree(&tree, true);
        let back = decode_tree(&bytes).expect("decode");
        assert_eq!(back, tree);
    }

    #[test]
    fn one_constant_is_leaf_one() {
        let n = one();
        assert!(n.is_leaf());
        assert_eq!(n.value, 1.0);
        assert!(!n.is_x);
    }
}
