//! OSMP Overflow Protocol — fragmentation and loss tolerance.
//!
//! When a SAL payload exceeds the link MTU (LoRa floor ~51 bytes), the payload
//! is split into Fragments with a 6-byte wire header. Reassembly tolerates
//! loss according to a `LossPolicy` selector: FailSafe drops anything
//! incomplete, GracefulDegradation accepts a prefix when a terminal arrives,
//! Atomic requires every fragment.
//!
//! Wire format (6-byte header, big-endian):
//!     bytes 0..2  msg_id  (u16)
//!     byte  2     frag_idx (u8)
//!     byte  3     frag_ct  (u8)
//!     byte  4     flags    (u8)
//!     byte  5     dep      (u8)
//!     bytes 6..   payload
//!
//! Cross-SDK byte-identical with Go (sdk/go/osmp/overflow.go),
//! TypeScript (sdk/typescript/src/overflow.ts), Python
//! (sdk/python/osmp/protocol.py OverflowProtocol).
//!
//! License: Apache-2.0

use std::collections::BTreeMap;

use crate::types::{
    Fragment, FLAG_CRITICAL, FLAG_TERMINAL, FRAGMENT_HEADER_BYTES, LORA_STANDARD_BYTES,
};

/// Loss tolerance policy applied during reassembly.
///
/// Wire-grammar literal mapping: `Φ` = FailSafe, `Γ` = GracefulDegradation,
/// `Λ` = Atomic. The default is GracefulDegradation, which mirrors the Go
/// and TypeScript SDKs.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum LossPolicy {
    /// Φ — drop the whole message if any fragment is missing.
    FailSafe,
    /// Γ — accept whatever prefix is present once a terminal arrives.
    #[default]
    GracefulDegradation,
    /// Λ — require every fragment; partial reassembly never returned.
    Atomic,
}

impl Fragment {
    /// True if the FLAG_TERMINAL bit is set.
    pub fn is_terminal(&self) -> bool {
        self.flags & FLAG_TERMINAL != 0
    }

    /// True if the FLAG_CRITICAL bit is set.
    pub fn is_critical(&self) -> bool {
        self.flags & FLAG_CRITICAL != 0
    }

    /// Pack the fragment to its wire bytes. The internal field widths are
    /// wider than the wire fields (for ergonomics across SDKs); the lower
    /// bits are taken when packing — callers are expected to keep msg_id
    /// in u16 range and frag_idx/frag_ct/dep in u8 range.
    pub fn pack(&self) -> Vec<u8> {
        let mut buf = Vec::with_capacity(FRAGMENT_HEADER_BYTES + self.payload.len());
        let msg_id_u16 = (self.msg_id & 0xFFFF) as u16;
        buf.push((msg_id_u16 >> 8) as u8);
        buf.push((msg_id_u16 & 0xFF) as u8);
        buf.push((self.frag_idx & 0xFF) as u8);
        buf.push((self.frag_ct & 0xFF) as u8);
        buf.push(self.flags);
        buf.push((self.dep & 0xFF) as u8);
        buf.extend_from_slice(&self.payload);
        buf
    }
}

/// Decode a fragment from its wire bytes.
///
/// Returns an error if the input is shorter than the 6-byte header.
pub fn unpack_fragment(data: &[u8]) -> Result<Fragment, String> {
    if data.len() < FRAGMENT_HEADER_BYTES {
        return Err(format!("fragment too short: {} bytes", data.len()));
    }
    let msg_id = ((data[0] as u32) << 8) | (data[1] as u32);
    let frag_idx = data[2] as u16;
    let frag_ct = data[3] as u16;
    let flags = data[4];
    let dep = data[5] as u16;
    let payload = data[FRAGMENT_HEADER_BYTES..].to_vec();
    Ok(Fragment {
        msg_id,
        frag_idx,
        frag_ct,
        flags,
        dep,
        payload,
    })
}

/// Tier 1/2 overflow encoder + reassembler.
///
/// Fragments outgoing payloads when they exceed the MTU. Buffers incoming
/// fragments and yields the reassembled payload according to `policy`.
#[derive(Debug)]
pub struct OverflowProtocol {
    /// Effective MTU including the 6-byte fragment header.
    pub mtu: usize,
    /// Loss tolerance policy applied at reassembly time.
    pub policy: LossPolicy,
    counter: u16,
    buf: BTreeMap<u32, BTreeMap<u16, Fragment>>,
}

impl OverflowProtocol {
    /// Construct a new OverflowProtocol. `mtu` of 0 falls through to
    /// `LORA_STANDARD_BYTES` (255) to mirror the Go default.
    pub fn new(mtu: usize, policy: LossPolicy) -> Self {
        let effective_mtu = if mtu == 0 { LORA_STANDARD_BYTES } else { mtu };
        OverflowProtocol {
            mtu: effective_mtu,
            policy,
            counter: 0,
            buf: BTreeMap::new(),
        }
    }

    fn next_id(&mut self) -> u16 {
        self.counter = self.counter.wrapping_add(1);
        self.counter
    }

    /// Fragment a payload. When the payload (plus header) fits inside the MTU
    /// a single terminal fragment is returned. Otherwise the payload is
    /// chunked at `mtu - 6` per fragment, with FLAG_TERMINAL set on the last.
    ///
    /// `force_multi` (called `critical` in the Go SDK) sets FLAG_CRITICAL on
    /// every emitted fragment.
    pub fn fragment(&mut self, payload: &[u8], force_multi: bool) -> Vec<Fragment> {
        let avail = self.mtu.saturating_sub(FRAGMENT_HEADER_BYTES);
        let critical_bit = if force_multi { FLAG_CRITICAL } else { 0 };

        if payload.len() + FRAGMENT_HEADER_BYTES <= self.mtu {
            let id = self.next_id() as u32;
            return vec![Fragment {
                msg_id: id,
                frag_idx: 0,
                frag_ct: 1,
                flags: FLAG_TERMINAL | critical_bit,
                dep: 0,
                payload: payload.to_vec(),
            }];
        }

        let mut chunks: Vec<&[u8]> = Vec::new();
        let mut i = 0;
        while i < payload.len() {
            let end = std::cmp::min(i + avail, payload.len());
            chunks.push(&payload[i..end]);
            i = end;
        }
        let id = self.next_id() as u32;
        let ct = chunks.len() as u16;
        chunks
            .into_iter()
            .enumerate()
            .map(|(idx, chunk)| {
                let is_last = idx + 1 == ct as usize;
                let mut flags = critical_bit;
                if is_last {
                    flags |= FLAG_TERMINAL;
                }
                Fragment {
                    msg_id: id,
                    frag_idx: idx as u16,
                    frag_ct: ct,
                    flags,
                    dep: 0,
                    payload: chunk.to_vec(),
                }
            })
            .collect()
    }

    /// Receive a fragment. Returns the reassembled payload when the policy's
    /// completion condition is satisfied, or `None` while still buffering.
    ///
    /// `R:ESTOP` payloads bypass buffering and return immediately — atomic
    /// floor for the emergency-stop opcode.
    pub fn receive(&mut self, frag: Fragment) -> Option<Vec<u8>> {
        if contains_estop(&frag.payload) {
            return Some(frag.payload);
        }
        let mid = frag.msg_id;
        let exp = frag.frag_ct as usize;
        let policy = self.policy;
        let entry = self.buf.entry(mid).or_default();
        let frag_is_terminal = frag.is_terminal();
        let frag_is_critical = frag.is_critical();
        entry.insert(frag.frag_idx, frag);
        let rcv_len = entry.len();

        match policy {
            LossPolicy::Atomic => {
                if rcv_len == exp {
                    return Some(reassemble(entry, exp));
                }
            }
            LossPolicy::FailSafe => {
                if rcv_len == exp {
                    return Some(reassemble(entry, exp));
                }
            }
            LossPolicy::GracefulDegradation => {
                if frag_is_critical && rcv_len == exp {
                    return Some(reassemble(entry, exp));
                }
                if frag_is_terminal && rcv_len == exp {
                    return Some(reassemble(entry, exp));
                }
                if frag_is_terminal {
                    return Some(reassemble_partial(entry, exp));
                }
            }
        }
        None
    }

    /// Generate a NACK string identifying any missing fragment indices for
    /// `msg_id`. Format: `A:NACK[MSG:<id>∖[<i>,<j>,...]]`.
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
    payload
        .windows(7)
        .any(|w| w == b"R:ESTOP")
}

fn reassemble(rcv: &BTreeMap<u16, Fragment>, exp: usize) -> Vec<u8> {
    let mut out = Vec::new();
    for i in 0..exp as u16 {
        if let Some(frag) = rcv.get(&i) {
            out.extend_from_slice(&frag.payload);
        }
    }
    out
}

fn reassemble_partial(rcv: &BTreeMap<u16, Fragment>, exp: usize) -> Vec<u8> {
    let mut out = Vec::new();
    for i in 0..exp as u16 {
        match rcv.get(&i) {
            Some(frag) => out.extend_from_slice(&frag.payload),
            None => break,
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pack_unpack_roundtrip() {
        let f = Fragment {
            msg_id: 0x1234,
            frag_idx: 2,
            frag_ct: 5,
            flags: FLAG_TERMINAL | FLAG_CRITICAL,
            dep: 1,
            payload: b"H:HR[78]".to_vec(),
        };
        let bytes = f.pack();
        assert_eq!(bytes.len(), FRAGMENT_HEADER_BYTES + 8);
        // Wire-format byte verification (matches Go big-endian layout)
        assert_eq!(bytes[0], 0x12);
        assert_eq!(bytes[1], 0x34);
        assert_eq!(bytes[2], 2);
        assert_eq!(bytes[3], 5);
        assert_eq!(bytes[4], FLAG_TERMINAL | FLAG_CRITICAL);
        assert_eq!(bytes[5], 1);
        assert_eq!(&bytes[6..], b"H:HR[78]");

        let g = unpack_fragment(&bytes).expect("unpack");
        assert_eq!(g, f);
    }

    #[test]
    fn pack_byte_identical_with_go() {
        // Reference value computed from sdk/go/osmp/overflow.go Fragment.Pack()
        // with the same inputs:
        //   MsgIDFull = 0x1234, FragIdx = 2, FragCt = 5,
        //   Flags = FlagTerminal | FlagCritical (0x03), Dep = 1,
        //   Payload = []byte("H:HR[78]")
        // Go output: 12 34 02 05 03 01 48 3a 48 52 5b 37 38 5d
        let f = Fragment {
            msg_id: 0x1234,
            frag_idx: 2,
            frag_ct: 5,
            flags: FLAG_TERMINAL | FLAG_CRITICAL,
            dep: 1,
            payload: b"H:HR[78]".to_vec(),
        };
        let expected: [u8; 14] = [
            0x12, 0x34, 0x02, 0x05, 0x03, 0x01, 0x48, 0x3a, 0x48, 0x52, 0x5b, 0x37, 0x38, 0x5d,
        ];
        assert_eq!(f.pack(), expected.to_vec());
    }

    #[test]
    fn unpack_too_short_errors() {
        assert!(unpack_fragment(&[0u8; 3]).is_err());
    }

    #[test]
    fn fragment_under_mtu_single_terminal() {
        let mut op = OverflowProtocol::new(51, LossPolicy::GracefulDegradation);
        let payload = b"H:HR[78]";
        let frags = op.fragment(payload, false);
        assert_eq!(frags.len(), 1);
        assert!(frags[0].is_terminal());
        assert_eq!(frags[0].frag_ct, 1);
        assert_eq!(frags[0].payload, payload);
    }

    #[test]
    fn fragment_200_bytes_with_mtu_51_yields_multi() {
        let mut op = OverflowProtocol::new(51, LossPolicy::GracefulDegradation);
        let payload = vec![b'A'; 200];
        let frags = op.fragment(&payload, false);
        // 51 - 6 = 45 bytes per chunk; 200 / 45 = 5 (rounded up)
        assert!(frags.len() >= 5);
        // Only the last is terminal
        let terminal_count = frags.iter().filter(|f| f.is_terminal()).count();
        assert_eq!(terminal_count, 1);
        assert!(frags.last().unwrap().is_terminal());
        // Reassembled payload matches
        let total: Vec<u8> = frags.iter().flat_map(|f| f.payload.clone()).collect();
        assert_eq!(total, payload);
        // Common msg_id across all fragments
        let id = frags[0].msg_id;
        assert!(frags.iter().all(|f| f.msg_id == id));
    }

    #[test]
    fn receive_atomic_completes_only_when_full() {
        let mut op = OverflowProtocol::new(51, LossPolicy::Atomic);
        let payload = vec![b'X'; 100];
        let frags = op.fragment(&payload, false);
        let last_idx = frags.len() - 1;
        let mut result = None;
        for (i, f) in frags.iter().cloned().enumerate() {
            let r = op.receive(f);
            if i < last_idx {
                assert!(r.is_none());
            } else {
                result = r;
            }
        }
        assert_eq!(result.unwrap(), payload);
    }

    #[test]
    fn receive_estop_bypasses_buffer() {
        let mut op = OverflowProtocol::new(51, LossPolicy::Atomic);
        let frag = Fragment {
            msg_id: 99,
            frag_idx: 0,
            frag_ct: 4,
            flags: 0,
            dep: 0,
            payload: b"R:ESTOP@*".to_vec(),
        };
        let r = op.receive(frag).expect("estop bypass");
        assert_eq!(r, b"R:ESTOP@*");
    }
}
