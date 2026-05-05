//! OSMP Tier 3 — DAG decomposition.
//!
//! Decomposes a compound SAL instruction with chain operators (`;`, `→`,
//! `∧`, `A∥[…]`) into a directed acyclic graph of executable units, then
//! emits one Fragment per node with dependency edges packed into either the
//! `dep` byte (single parent / root) or a u32 bitmap prefix on the payload
//! (multi-parent fan-in, FLAG_EXTENDED_DEP). Reassembly resolves the DAG
//! via Kahn's algorithm with the configured loss policy.
//!
//! Cross-SDK byte-identical with Go (sdk/go/osmp/dag.go), TypeScript
//! (sdk/typescript/src/dag.ts), Python
//! (sdk/python/osmp/protocol.py DAGFragmenter / DAGReassembler).
//!
//! License: Apache-2.0

use std::collections::{BTreeMap, BTreeSet};

use crate::overflow::LossPolicy;
use crate::types::{
    Fragment, FLAG_CRITICAL, FLAG_EXTENDED_DEP, FLAG_TERMINAL, LORA_STANDARD_BYTES,
};

/// One executable unit in a Tier 3 DAG.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DAGNode {
    /// 0-based index of this node in the DAG.
    pub idx: usize,
    /// UTF-8 payload bytes of the leaf SAL atom.
    pub payload: Vec<u8>,
    /// Indices of parent nodes (empty = root).
    pub parents: Vec<usize>,
}

/// Decomposes a compound SAL string into a DAG of fragments.
#[derive(Debug, Clone)]
pub struct DAGFragmenter {
    /// Effective MTU (kept for symmetry with other SDKs; not currently
    /// enforced because DAG nodes are atomic SAL leaves whose individual
    /// size is bounded by grammar rather than MTU).
    pub mtu: usize,
}

impl DAGFragmenter {
    /// Construct with the given MTU. `0` falls through to `LORA_STANDARD_BYTES`.
    pub fn new(mtu: usize) -> Self {
        let effective = if mtu == 0 { LORA_STANDARD_BYTES } else { mtu };
        DAGFragmenter { mtu: effective }
    }

    /// Parse a compound SAL string into ordered DAGNodes.
    pub fn parse(&self, sal: &str) -> Vec<DAGNode> {
        let mut nodes: Vec<DAGNode> = Vec::new();
        self.parse_expr(sal.trim(), &mut nodes, &[]);
        nodes
    }

    fn parse_expr(
        &self,
        expr: &str,
        nodes: &mut Vec<DAGNode>,
        parent_indices: &[usize],
    ) -> Vec<usize> {
        // ; (SEQUENCE) — lowest precedence.
        let parts = split_top_level(expr, ";");
        if parts.len() > 1 {
            let mut tails: Vec<usize> = parent_indices.to_vec();
            for part in parts {
                tails = self.parse_expr(part.trim(), nodes, &tails);
            }
            return tails;
        }

        // → (THEN) — conditional chain.
        let parts = split_top_level(expr, "\u{2192}");
        if parts.len() > 1 {
            let mut tails: Vec<usize> = parent_indices.to_vec();
            for part in parts {
                tails = self.parse_expr(part.trim(), nodes, &tails);
            }
            return tails;
        }

        // ∧ (AND) — parallel fork.
        let parts = split_top_level(expr, "\u{2227}");
        if parts.len() > 1 {
            let mut all_tails: Vec<usize> = Vec::new();
            for part in parts {
                let branch_tails = self.parse_expr(part.trim(), nodes, parent_indices);
                all_tails.extend(branch_tails);
            }
            return all_tails;
        }

        // A∥[...] — parallel execution block.
        let prefix = "A\u{2225}[";
        if expr.starts_with(prefix) && expr.ends_with(']') {
            let inner = &expr[prefix.len()..expr.len() - 1];
            let split = split_top_level(inner, "\u{2227}");
            let parts: Vec<&str> = if split.len() <= 1 {
                vec![inner]
            } else {
                split.iter().map(|s| s.as_str()).collect()
            };
            let mut all_tails: Vec<usize> = Vec::new();
            for part in parts {
                let mut clean = part.trim().to_string();
                if clean.starts_with('?') {
                    clean = clean[1..].to_string();
                }
                let branch_tails = self.parse_expr(&clean, nodes, parent_indices);
                all_tails.extend(branch_tails);
            }
            return all_tails;
        }

        // Atomic leaf node.
        let idx = nodes.len();
        nodes.push(DAGNode {
            idx,
            payload: expr.as_bytes().to_vec(),
            parents: parent_indices.to_vec(),
        });
        vec![idx]
    }

    /// Full Tier 3 pipeline: parse → assign DEP → emit Fragments.
    pub fn fragmentize(&self, sal: &str, msg_id: u32, force_multi: bool) -> Vec<Fragment> {
        let nodes = self.parse(sal);
        if nodes.is_empty() {
            return Vec::new();
        }
        let frag_ct = nodes.len() as u16;
        let mut frags: Vec<Fragment> = Vec::with_capacity(nodes.len());
        let critical_bit = if force_multi { FLAG_CRITICAL } else { 0 };

        for node in &nodes {
            let is_last = node.idx + 1 == frag_ct as usize;
            let mut flags = critical_bit;
            if is_last {
                flags |= FLAG_TERMINAL;
            }

            let (dep, payload) = match node.parents.len() {
                0 => (node.idx as u16, node.payload.clone()),
                1 => (node.parents[0] as u16, node.payload.clone()),
                _ => {
                    flags |= FLAG_EXTENDED_DEP;
                    let primary = node.parents[0] as u16;
                    let mut bitmap: u32 = 0;
                    for p in &node.parents {
                        bitmap |= 1u32 << (*p as u32);
                    }
                    let mut payload = Vec::with_capacity(4 + node.payload.len());
                    payload.extend_from_slice(&bitmap.to_be_bytes());
                    payload.extend_from_slice(&node.payload);
                    (primary, payload)
                }
            };

            frags.push(Fragment {
                msg_id,
                frag_idx: node.idx as u16,
                frag_ct,
                flags,
                dep,
                payload,
            });
        }
        frags
    }
}

/// Buffers DAG fragments and resolves dependency order under loss tolerance.
#[derive(Debug)]
pub struct DAGReassembler {
    /// Loss tolerance policy applied at reassembly time.
    pub policy: LossPolicy,
    buf: BTreeMap<u32, BTreeMap<u16, Fragment>>,
}

impl DAGReassembler {
    /// Construct a reassembler with the given policy.
    pub fn new(policy: LossPolicy) -> Self {
        DAGReassembler {
            policy,
            buf: BTreeMap::new(),
        }
    }

    /// Buffer a fragment and attempt DAG resolution. Returns ordered
    /// payloads in execution order, or an empty vector if not yet
    /// resolvable. `R:ESTOP` payloads bypass buffering and return
    /// immediately as the sole emitted node.
    pub fn receive(&mut self, frag: Fragment) -> Vec<Vec<u8>> {
        if contains_estop(&frag.payload) {
            return vec![frag.payload];
        }

        let mid = frag.msg_id;
        let exp = frag.frag_ct as usize;
        let policy = self.policy;
        let entry = self.buf.entry(mid).or_default();
        let frag_terminal = frag.is_terminal();
        entry.insert(frag.frag_idx, frag);
        let rcv_len = entry.len();

        let resolution = match policy {
            LossPolicy::FailSafe | LossPolicy::Atomic => {
                if rcv_len == exp {
                    Some(resolve_dag(entry))
                } else {
                    None
                }
            }
            LossPolicy::GracefulDegradation => {
                if frag_terminal && rcv_len == exp {
                    Some(resolve_dag(entry))
                } else if frag_terminal {
                    Some(resolve_dag_partial(entry))
                } else {
                    None
                }
            }
        };
        resolution.unwrap_or_default()
    }

    /// Generate a NACK string identifying any missing fragment indices.
    pub fn nack(&self, msg_id: u32, expected_ct: usize) -> String {
        let rcv = self.buf.get(&msg_id);
        let missing: Vec<String> = (0..expected_ct as u16)
            .filter(|i| rcv.map(|m| !m.contains_key(i)).unwrap_or(true))
            .map(|i| i.to_string())
            .collect();
        format!("A:NACK[MSG:{}\u{2216}[{}]]", msg_id, missing.join(","))
    }
}

fn contains_estop(payload: &[u8]) -> bool {
    payload.windows(7).any(|w| w == b"R:ESTOP")
}

fn get_parents(frag: &Fragment) -> Vec<usize> {
    if frag.flags & FLAG_EXTENDED_DEP != 0 {
        if frag.payload.len() < 4 {
            return Vec::new();
        }
        let bitmap = u32::from_be_bytes([
            frag.payload[0],
            frag.payload[1],
            frag.payload[2],
            frag.payload[3],
        ]);
        let mut parents = Vec::new();
        for i in 0u32..32 {
            if bitmap & (1 << i) != 0 {
                parents.push(i as usize);
            }
        }
        return parents;
    }
    // Self-reference = root.
    if frag.dep == frag.frag_idx {
        return Vec::new();
    }
    vec![frag.dep as usize]
}

fn get_payload(frag: &Fragment) -> Vec<u8> {
    if frag.flags & FLAG_EXTENDED_DEP != 0 && frag.payload.len() >= 4 {
        return frag.payload[4..].to_vec();
    }
    frag.payload.clone()
}

fn resolve_dag(rcv: &BTreeMap<u16, Fragment>) -> Vec<Vec<u8>> {
    let node_set: BTreeSet<usize> = rcv.keys().map(|k| *k as usize).collect();
    let order = topo_sort(rcv, &node_set);
    order
        .into_iter()
        .map(|idx| {
            let f = rcv.get(&(idx as u16)).expect("frag in node_set");
            get_payload(f)
        })
        .collect()
}

fn resolve_dag_partial(rcv: &BTreeMap<u16, Fragment>) -> Vec<Vec<u8>> {
    let present: BTreeSet<usize> = rcv.keys().map(|k| *k as usize).collect();
    let mut executable: BTreeSet<usize> = BTreeSet::new();
    for idx in &present {
        if ancestors_satisfied(rcv, *idx, &present) {
            executable.insert(*idx);
        }
    }
    if executable.is_empty() {
        return Vec::new();
    }
    let order = topo_sort(rcv, &executable);
    order
        .into_iter()
        .map(|idx| {
            let f = rcv.get(&(idx as u16)).expect("frag in executable set");
            get_payload(f)
        })
        .collect()
}

fn ancestors_satisfied(
    rcv: &BTreeMap<u16, Fragment>,
    idx: usize,
    present: &BTreeSet<usize>,
) -> bool {
    let mut visited: BTreeSet<usize> = BTreeSet::new();
    let mut stack: Vec<usize> = vec![idx];
    while let Some(cur) = stack.pop() {
        if visited.contains(&cur) {
            continue;
        }
        visited.insert(cur);
        if !present.contains(&cur) {
            return false;
        }
        if let Some(frag) = rcv.get(&(cur as u16)) {
            for p in get_parents(frag) {
                if !visited.contains(&p) {
                    stack.push(p);
                }
            }
        }
    }
    true
}

fn topo_sort(rcv: &BTreeMap<u16, Fragment>, node_set: &BTreeSet<usize>) -> Vec<usize> {
    let mut in_deg: BTreeMap<usize, usize> = BTreeMap::new();
    let mut children: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    for i in node_set {
        in_deg.insert(*i, 0);
        children.insert(*i, Vec::new());
    }

    for idx in node_set {
        let frag = rcv.get(&(*idx as u16)).expect("frag for node");
        let parents = get_parents(frag);
        for p in parents {
            if node_set.contains(&p) {
                *in_deg.entry(*idx).or_insert(0) += 1;
                children.entry(p).or_default().push(*idx);
            }
        }
    }

    // Initial queue: roots, sorted ascending.
    let mut queue: Vec<usize> = node_set
        .iter()
        .copied()
        .filter(|i| *in_deg.get(i).unwrap_or(&0) == 0)
        .collect();
    queue.sort();

    let mut order: Vec<usize> = Vec::new();
    while !queue.is_empty() {
        let node = queue.remove(0);
        order.push(node);
        let mut ch = children.get(&node).cloned().unwrap_or_default();
        ch.sort();
        for c in ch {
            if let Some(d) = in_deg.get_mut(&c) {
                if *d > 0 {
                    *d -= 1;
                    if *d == 0 {
                        queue.push(c);
                    }
                }
            }
        }
    }
    order
}

fn split_top_level(expr: &str, sep: &str) -> Vec<String> {
    let mut parts: Vec<String> = Vec::new();
    let mut depth: i32 = 0;
    let mut current = String::new();
    let runes: Vec<char> = expr.chars().collect();
    let sep_chars: Vec<char> = sep.chars().collect();
    let sep_len = sep_chars.len();
    let mut i = 0;
    while i < runes.len() {
        let ch = runes[i];
        if ch == '[' || ch == '(' {
            depth += 1;
            current.push(ch);
            i += 1;
        } else if ch == ']' || ch == ')' {
            depth -= 1;
            current.push(ch);
            i += 1;
        } else if depth == 0
            && i + sep_len <= runes.len()
            && runes[i..i + sep_len] == sep_chars[..]
        {
            parts.push(current.clone());
            current.clear();
            i += sep_len;
        } else {
            current.push(ch);
            i += 1;
        }
    }
    if !current.is_empty() {
        parts.push(current);
    }
    parts
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_diamond_pattern_yields_4_nodes() {
        // A;B∧C;D — A, then B and C in parallel, then D depending on B and C.
        let df = DAGFragmenter::new(255);
        let nodes = df.parse("A;B\u{2227}C;D");
        assert_eq!(nodes.len(), 4);
        assert_eq!(nodes[0].payload, b"A");
        assert_eq!(nodes[1].payload, b"B");
        assert_eq!(nodes[2].payload, b"C");
        assert_eq!(nodes[3].payload, b"D");

        // A is root.
        assert_eq!(nodes[0].parents, Vec::<usize>::new());
        // B and C both depend on A.
        assert_eq!(nodes[1].parents, vec![0]);
        assert_eq!(nodes[2].parents, vec![0]);
        // D fans in from B and C.
        assert_eq!(nodes[3].parents, vec![1, 2]);
    }

    #[test]
    fn parse_simple_sequence() {
        let df = DAGFragmenter::new(255);
        let nodes = df.parse("A;B;C");
        assert_eq!(nodes.len(), 3);
        assert_eq!(nodes[0].parents, Vec::<usize>::new());
        assert_eq!(nodes[1].parents, vec![0]);
        assert_eq!(nodes[2].parents, vec![1]);
    }

    #[test]
    fn fragmentize_diamond_emits_fragments() {
        let df = DAGFragmenter::new(255);
        let frags = df.fragmentize("A;B\u{2227}C;D", 7, false);
        assert_eq!(frags.len(), 4);
        // Last fragment is terminal.
        assert!(frags[3].is_terminal());
        // Diamond tail (D) has multi-parent → FLAG_EXTENDED_DEP set.
        assert_ne!(frags[3].flags & FLAG_EXTENDED_DEP, 0);
        // Bitmap (1<<1)|(1<<2) = 0x06.
        let bm = u32::from_be_bytes([
            frags[3].payload[0],
            frags[3].payload[1],
            frags[3].payload[2],
            frags[3].payload[3],
        ]);
        assert_eq!(bm, 0b110);
        // Tail SAL byte after bitmap = 'D'.
        assert_eq!(&frags[3].payload[4..], b"D");
    }

    #[test]
    fn pack_unpack_roundtrip_on_dag_fragment() {
        let df = DAGFragmenter::new(255);
        let frags = df.fragmentize("A;B\u{2227}C;D", 9, true);
        for f in frags {
            let bytes = f.pack();
            let g = crate::overflow::unpack_fragment(&bytes).expect("unpack");
            assert_eq!(g, f);
        }
    }

    #[test]
    fn reassemble_diamond_topo_orders_correctly() {
        let df = DAGFragmenter::new(255);
        let frags = df.fragmentize("A;B\u{2227}C;D", 11, false);
        let mut dr = DAGReassembler::new(LossPolicy::Atomic);
        let mut out: Vec<Vec<u8>> = Vec::new();
        for f in frags {
            let r = dr.receive(f);
            if !r.is_empty() {
                out = r;
            }
        }
        assert_eq!(out.len(), 4);
        // Topo order: A, B, C, D (B and C alphabetic by index)
        assert_eq!(out[0], b"A");
        assert_eq!(out[1], b"B");
        assert_eq!(out[2], b"C");
        assert_eq!(out[3], b"D");
    }

    #[test]
    fn estop_bypass_in_dag_reassembler() {
        let mut dr = DAGReassembler::new(LossPolicy::Atomic);
        let frag = Fragment {
            msg_id: 5,
            frag_idx: 0,
            frag_ct: 4,
            flags: 0,
            dep: 0,
            payload: b"R:ESTOP@*".to_vec(),
        };
        let r = dr.receive(frag);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0], b"R:ESTOP@*");
    }
}
