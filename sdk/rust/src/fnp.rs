//! FNP — Frame Negotiation Protocol.
//!
//! Two-message capability advertisement + acknowledgment completing within
//! 78 bytes total (40 ADV + 38 ACK), designed for the LoRa physical layer
//! payload floor.
//!
//! Negotiates three properties in two packets:
//!   1. Dictionary alignment (ASD fingerprint match)
//!   2. Namespace intersection (shared domain capabilities)
//!   3. Channel capacity (byte budget for the session)
//!
//! Cross-SDK byte-identical with Python `FNPSession`, Go `FNPSession`,
//! TypeScript `FNPSession`. State machine, packet layout, and bitmap
//! encoding all match.
//!
//! License: Apache-2.0

use crate::asd::AdaptiveSharedDictionary;

// ── constants ───────────────────────────────────────────────────────

/// FNP message type: capability advertisement (initiator).
pub const FNP_MSG_ADV: u8 = 0x01;
/// FNP message type: capability acknowledgment (responder, on match).
pub const FNP_MSG_ACK: u8 = 0x02;
/// FNP message type: capability negative acknowledgment (responder, on mismatch).
pub const FNP_MSG_NACK: u8 = 0x03;

/// Channel capacity class: LoRa SF12 BW125kHz floor (51 bytes).
pub const FNP_CAP_FLOOR: u8 = 0x00;
/// Channel capacity class: LoRa SF11 BW250kHz standard (255 bytes).
pub const FNP_CAP_STANDARD: u8 = 0x01;
/// Channel capacity class: BLE (512 bytes).
pub const FNP_CAP_BLE: u8 = 0x02;
/// Channel capacity class: unconstrained (no byte budget).
///
/// Wire value 0x03 matches Go `FNPCapUnconstrained`, Python
/// `FNP_CAP_UNCONSTRAINED`, TypeScript `FNP_CAP_UNCONSTRAINED`. The
/// channel_capacity field on `FNPSession::new` is a single byte; the
/// constant is exposed as `u8` for cross-SDK byte-identical wire
/// compatibility.
pub const FNP_CAP_UNCONSTRAINED: u8 = 0x03;

const NS_LETTERS: &str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

// ── state ───────────────────────────────────────────────────────────

/// FNP session state.
///
/// State transitions:
/// - `Initial` -> `Probing` on `initiate()`.
/// - `Probing` -> `Established` / `EstablishedSAIL` / `EstablishedSALOnly`
///   / `SyncNeeded` on receiving a valid ACK / NACK.
/// - `Initial` or `Probing` -> `Fallback` on `fallback()` (peer does not
///   speak OSMP, or transport is known non-OSMP).
/// - `Fallback` -> `Acquired` on `acquire()` (SAL acquisition threshold met).
/// - `Acquired` -> `Fallback` on `regress()` (regression threshold met).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum FNPState {
    /// No handshake started. Initial state.
    Initial,
    /// Initiator has sent ADV, awaiting ACK / NACK from peer.
    Probing,
    /// Peer does not speak OSMP. Bridge translates to NL on outbound.
    Fallback,
    /// Peer has acquired SAL through few-shot exposure. Bridge sends pure SAL.
    Acquired,
    /// FNP handshake complete. Native OSMP peer (legacy alias).
    Established,
    /// FNP handshake complete with matching basis fingerprint (SAIL capable).
    EstablishedSAIL,
    /// FNP handshake complete but basis fingerprints differ (SAL only).
    EstablishedSALOnly,
    /// FNP handshake completed with version or fingerprint mismatch.
    SyncNeeded,
}

// ── helpers ─────────────────────────────────────────────────────────

fn namespace_bitmap(namespaces: &[String]) -> u32 {
    let mut bitmap: u32 = 0;
    for ns in namespaces {
        if ns.len() == 1 {
            if let Some(idx) = NS_LETTERS.find(ns.as_str()) {
                bitmap |= 1u32 << idx;
            }
        }
        // Ω sovereign extension occupies bit 26.
        if ns == "\u{03A9}" {
            bitmap |= 1u32 << 26;
        }
    }
    bitmap
}

fn fingerprint_bytes(asd: &AdaptiveSharedDictionary) -> Vec<u8> {
    let hex = asd.fingerprint();
    let mut bytes = Vec::with_capacity(8);
    for i in 0..8 {
        let pair = &hex[i * 2..i * 2 + 2];
        let b = u8::from_str_radix(pair, 16).expect("fingerprint() returns ascii hex");
        bytes.push(b);
    }
    bytes
}

// ── session ─────────────────────────────────────────────────────────

/// FNP session manager — two-message handshake between sovereign nodes.
///
/// Cross-SDK byte-identical with Python `FNPSession`, Go `FNPSession`,
/// TypeScript `FNPSession`. State machine and field semantics match.
#[derive(Debug, Clone)]
pub struct FNPSession {
    /// Current state of the FNP session.
    pub state: FNPState,
    /// Identity of this local node.
    pub local_node_id: String,
    /// Identity of the remote peer (set after `Receive` or `Fallback`).
    pub remote_node_id: String,
    /// 8-byte ASD fingerprint of the remote peer.
    pub remote_fingerprint: Option<Vec<u8>>,
    /// Common namespaces between this node and the peer.
    pub common_namespaces: Vec<String>,
    /// Match status code from the negotiation, or -1 if not yet negotiated.
    pub match_status: i32,
    /// Negotiated channel capacity class, or -1 if not yet negotiated.
    pub negotiated_capacity: i32,
    /// Capability bitmap (compatibility with public API spec).
    pub capabilities: u32,

    asd_version: u16,
    channel_capacity: u8,
    own_fingerprint: Vec<u8>,
    own_bitmap: u32,
}

impl FNPSession {
    /// Create a new FNP session in `Initial` state.
    ///
    /// Mirrors Go `NewFNPSession(asd, nodeID, asdVersion, channelCapacity)`.
    pub fn new(
        asd: &AdaptiveSharedDictionary,
        local_id: &str,
        profile: u8,
        caps: u8,
    ) -> Self {
        let own_fp = fingerprint_bytes(asd);
        let own_bitmap = namespace_bitmap(&asd.namespaces());
        Self {
            state: FNPState::Initial,
            local_node_id: local_id.to_string(),
            remote_node_id: String::new(),
            remote_fingerprint: None,
            common_namespaces: Vec::new(),
            match_status: -1,
            negotiated_capacity: -1,
            capabilities: own_bitmap,
            asd_version: profile as u16,
            channel_capacity: caps,
            own_fingerprint: own_fp,
            own_bitmap,
        }
    }

    /// Convenience constructor matching the Go signature exactly:
    /// `(asd, local_id, asd_version: u16, channel_capacity: u8)`.
    pub fn new_with_version(
        asd: &AdaptiveSharedDictionary,
        local_id: &str,
        asd_version: u16,
        channel_capacity: u8,
    ) -> Self {
        let own_fp = fingerprint_bytes(asd);
        let own_bitmap = namespace_bitmap(&asd.namespaces());
        Self {
            state: FNPState::Initial,
            local_node_id: local_id.to_string(),
            remote_node_id: String::new(),
            remote_fingerprint: None,
            common_namespaces: Vec::new(),
            match_status: -1,
            negotiated_capacity: -1,
            capabilities: own_bitmap,
            asd_version,
            channel_capacity,
            own_fingerprint: own_fp,
            own_bitmap,
        }
    }

    /// Transition to `Fallback` when the remote peer does not speak OSMP.
    ///
    /// Called when:
    /// - ADV was sent but the response is not a valid FNP packet
    /// - The transport is known to be non-OSMP (e.g., plain JSON-RPC, NL)
    /// - Timeout occurred during a negotiation attempt with a new peer
    ///
    /// Transitions: `Probing` -> `Fallback`, or `Initial` -> `Fallback`.
    pub fn fallback(&mut self, remote_id: &str) {
        if self.state == FNPState::Probing || self.state == FNPState::Initial {
            self.state = FNPState::Fallback;
            self.remote_node_id = remote_id.to_string();
            self.remote_fingerprint = None;
            self.common_namespaces.clear();
            self.match_status = -1;
            self.negotiated_capacity = -1;
        }
    }

    /// Transition to `Acquired` when the remote peer starts producing valid SAL.
    ///
    /// Called by `SALBridge` when the acquisition score exceeds threshold.
    /// Transitions: `Fallback` -> `Acquired`.
    pub fn acquire(&mut self) {
        if self.state == FNPState::Fallback {
            self.state = FNPState::Acquired;
        }
    }

    /// Transition back to `Fallback` when an `Acquired` peer stops producing valid SAL.
    ///
    /// Transitions: `Acquired` -> `Fallback`.
    pub fn regress(&mut self) {
        if self.state == FNPState::Acquired {
            self.state = FNPState::Fallback;
        }
    }

    /// Force the session to `Established` state. Reserved for tests and
    /// integration paths where the negotiation handshake is provided
    /// out-of-band.
    pub fn establish(&mut self) {
        self.state = FNPState::Established;
    }

    /// Returns true if the session is in `Fallback` or `Acquired` state.
    pub fn is_legacy_peer(&self) -> bool {
        self.state == FNPState::Fallback || self.state == FNPState::Acquired
    }

    /// Returns true if the session is in `Acquired` state.
    pub fn is_acquired(&self) -> bool {
        self.state == FNPState::Acquired
    }

    /// Returns true if the session has reached any `Established*` variant.
    pub fn is_established(&self) -> bool {
        matches!(
            self.state,
            FNPState::Established
                | FNPState::EstablishedSAIL
                | FNPState::EstablishedSALOnly
                | FNPState::SyncNeeded
        )
    }

    /// Local node identifier.
    pub fn node_id(&self) -> &str {
        &self.local_node_id
    }

    /// Negotiated ASD profile/version field.
    pub fn asd_version(&self) -> u16 {
        self.asd_version
    }

    /// Negotiated channel capacity class byte (wire field).
    pub fn channel_capacity(&self) -> u8 {
        self.channel_capacity
    }

    /// 8-byte ASD fingerprint advertised by this node.
    pub fn own_fingerprint(&self) -> &[u8] {
        &self.own_fingerprint
    }

    /// Namespace bitmap advertised by this node.
    pub fn own_bitmap(&self) -> u32 {
        self.own_bitmap
    }
}
