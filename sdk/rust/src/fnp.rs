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
//! TypeScript `FNPSession`. State machine, packet layout, bitmap encoding,
//! and ADR-004 basis-manifest extended-form support all match.
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

/// FNP message type: extended-form capability advertisement (ADR-004).
/// High bit signals extended form; node_id narrowed to 15 bytes,
/// basis_fingerprint carried at offset 32. Total ADV size unchanged at 40 bytes.
pub const FNP_MSG_ADV_EXTENDED: u8 = 0x81;
/// Bit mask used to detect extended-form ADV in the msg_type byte.
pub const FNP_ADV_EXT_FLAG: u8 = 0x80;

/// FNP match status: ASD and basis match exactly.
pub const FNP_MATCH_EXACT: i32 = 0x00;
/// FNP match status: ASD version mismatch.
pub const FNP_MATCH_VERSION: i32 = 0x01;
/// FNP match status: ASD fingerprint mismatch.
pub const FNP_MATCH_FINGERPRINT: i32 = 0x02;
/// FNP match status (ADR-004): ASD matches, bases differ (both extended).
pub const FNP_MATCH_BASIS_MISMATCH: i32 = 0x03;
/// FNP match status (ADR-004): ASD matches, base form vs extended (length mismatch).
pub const FNP_MATCH_BASIS_EXT_VS_BASE: i32 = 0x04;

/// Channel capacity class: LoRa SF12 BW125kHz floor (51 bytes).
pub const FNP_CAP_FLOOR: u8 = 0x00;
/// Channel capacity class: LoRa SF11 BW250kHz standard (255 bytes).
pub const FNP_CAP_STANDARD: u8 = 0x01;
/// Channel capacity class: BLE (512 bytes).
pub const FNP_CAP_BLE: u8 = 0x02;
/// Channel capacity class: unconstrained (no byte budget).
pub const FNP_CAP_UNCONSTRAINED: u8 = 0x03;

/// Map a capacity class byte to its byte budget. Returns 0 for unconstrained,
/// `None` for unknown class.
pub fn fnp_cap_bytes(cap: u8) -> Option<usize> {
    match cap {
        FNP_CAP_FLOOR => Some(51),
        FNP_CAP_STANDARD => Some(255),
        FNP_CAP_BLE => Some(512),
        FNP_CAP_UNCONSTRAINED => Some(0),
        _ => None,
    }
}

const FNP_ADV_SIZE: usize = 40;
const FNP_ACK_SIZE: usize = 38;
const FNP_PROTOCOL_VERSION: u8 = 0x01;

const NS_LETTERS: &str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

// ── errors ──────────────────────────────────────────────────────────

/// Errors returned by FNP packet construction, parsing, and state transitions.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FnpError {
    /// Packet is malformed — wrong length, wrong msg_type, or otherwise invalid.
    InvalidPacket(String),
    /// State machine refused a transition because the current state does not allow it.
    InvalidState(String),
    /// FNP_ACK echo fingerprint does not match local own fingerprint.
    EchoMismatch,
    /// FNPSessionOptions::basis_fingerprint must be exactly 8 bytes.
    InvalidBasisFingerprint,
}

impl std::fmt::Display for FnpError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FnpError::InvalidPacket(s) => write!(f, "invalid FNP packet: {s}"),
            FnpError::InvalidState(s) => write!(f, "invalid FNP state transition: {s}"),
            FnpError::EchoMismatch => write!(f, "FNP_ACK echo fingerprint mismatch"),
            FnpError::InvalidBasisFingerprint => {
                write!(f, "basis_fingerprint must be exactly 8 bytes")
            }
        }
    }
}

impl std::error::Error for FnpError {}

// ── state ───────────────────────────────────────────────────────────

/// FNP session state.
///
/// Wire-layer state transitions:
/// - `Idle` -> `AdvSent` on `initiate()`.
/// - `AdvSent` -> `Established` / `EstablishedSAIL` / `EstablishedSALOnly` /
///   `SyncNeeded` on receiving a valid ACK / NACK.
/// - `AdvSent` -> `Idle` on `timeout()`.
///
/// Bridge-layer state transitions:
/// - `Idle` or `AdvSent` -> `Fallback` on `fallback()` (peer does not speak OSMP,
///   or transport is known non-OSMP).
/// - `Fallback` -> `Acquired` on `acquire()` (SAL acquisition threshold met).
/// - `Acquired` -> `Fallback` on `regress()` (regression threshold met).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum FNPState {
    /// No handshake started. Initial state. Equivalent to Go `FNPStateIdle`.
    Idle,
    /// Initiator has sent ADV, awaiting ACK / NACK from peer.
    /// Equivalent to Go `FNPStateADVSent`.
    AdvSent,
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

// ── degradation event (ADR-004) ─────────────────────────────────────

/// ADR-004 degradation event — emitted when a peer presents an unexpected basis
/// fingerprint or when `require_sail` policy refuses a basis-mismatched session.
///
/// Cross-SDK byte-identical fields with Go `DegradationEvent` map.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct DegradationEvent {
    /// Human-readable reason for the degradation.
    pub reason: String,
    /// FNP match status code that triggered the event.
    pub match_status: i32,
    /// Remote node identifier as advertised by the peer.
    pub remote_node_id: String,
    /// Hex-encoded remote basis fingerprint (when known).
    pub remote_basis_fingerprint: Option<String>,
    /// Hex-encoded expected basis fingerprint (when configured locally).
    pub expected_basis_fingerprint: Option<String>,
}

// ── parsed packets (private to module) ──────────────────────────────

struct FnpAdvParsed {
    fingerprint: Vec<u8>,
    asd_version: u16,
    namespace_bitmap: u32,
    channel_capacity: u8,
    node_id: String,
    basis_fingerprint: Option<Vec<u8>>,
}

struct FnpAckParsed {
    match_status: u8,
    echo_fingerprint: Vec<u8>,
    own_fingerprint: Vec<u8>,
    common_bitmap: u32,
    negotiated_capacity: u8,
    node_id: String,
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

fn bitmap_to_namespaces(bitmap: u32) -> Vec<String> {
    let mut result = Vec::new();
    for i in 0..NS_LETTERS.len() {
        if bitmap & (1u32 << i) != 0 {
            let c = NS_LETTERS.as_bytes()[i] as char;
            result.push(c.to_string());
        }
    }
    if bitmap & (1u32 << 26) != 0 {
        result.push("\u{03A9}".to_string());
    }
    result
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

fn hex_encode(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

fn trim_trailing_zeros(slice: &[u8]) -> &[u8] {
    let end = slice
        .iter()
        .rposition(|&b| b != 0)
        .map(|p| p + 1)
        .unwrap_or(0);
    &slice[..end]
}

fn parse_adv(data: &[u8]) -> Result<FnpAdvParsed, FnpError> {
    if data.len() < FNP_ADV_SIZE {
        return Err(FnpError::InvalidPacket("too short for ADV".to_string()));
    }
    let base_type = data[0] & !FNP_ADV_EXT_FLAG;
    if base_type != FNP_MSG_ADV {
        return Err(FnpError::InvalidPacket(format!(
            "bad ADV msg_type 0x{:02x}",
            data[0]
        )));
    }
    let is_extended = (data[0] & FNP_ADV_EXT_FLAG) != 0;

    let asd_version = u16::from_be_bytes([data[10], data[11]]);
    let namespace_bitmap = u32::from_be_bytes([data[12], data[13], data[14], data[15]]);

    let (node_id, basis_fingerprint) = if is_extended {
        let nid = trim_trailing_zeros(&data[17..32]);
        let id = String::from_utf8_lossy(nid).into_owned();
        let bf = data[32..40].to_vec();
        (id, Some(bf))
    } else {
        let nid = trim_trailing_zeros(&data[17..40]);
        let id = String::from_utf8_lossy(nid).into_owned();
        (id, None)
    };

    Ok(FnpAdvParsed {
        fingerprint: data[2..10].to_vec(),
        asd_version,
        namespace_bitmap,
        channel_capacity: data[16],
        node_id,
        basis_fingerprint,
    })
}

fn parse_ack(data: &[u8]) -> Result<FnpAckParsed, FnpError> {
    if data.len() < FNP_ACK_SIZE {
        return Err(FnpError::InvalidPacket("too short for ACK".to_string()));
    }
    if data[0] != FNP_MSG_ACK && data[0] != FNP_MSG_NACK {
        return Err(FnpError::InvalidPacket(format!(
            "bad ACK msg_type 0x{:02x}",
            data[0]
        )));
    }
    let nid = trim_trailing_zeros(&data[23..38]);
    Ok(FnpAckParsed {
        match_status: data[1],
        echo_fingerprint: data[2..10].to_vec(),
        own_fingerprint: data[10..18].to_vec(),
        common_bitmap: u32::from_be_bytes([data[18], data[19], data[20], data[21]]),
        negotiated_capacity: data[22],
        node_id: String::from_utf8_lossy(nid).into_owned(),
    })
}

// ── session options (ADR-004) ───────────────────────────────────────

/// ADR-004 session configuration. Pass to `FNPSession::new_with_options` to
/// activate extended-form ADV (basis manifest support) and `require_sail`
/// policy enforcement.
#[derive(Debug, Clone, Default)]
pub struct FNPSessionOptions {
    /// 8-byte basis fingerprint. Setting this switches the session to
    /// extended-form ADV (msg_type 0x81). Must be exactly 8 bytes.
    pub basis_fingerprint: Option<Vec<u8>>,
    /// Expected peer basis fingerprint. When set, the session records a
    /// `DegradationEvent` if the peer presents a different value.
    pub expected_basis_fingerprint: Option<Vec<u8>>,
    /// Operator policy flag — if true, basis-mismatched sessions are refused
    /// locally rather than degraded to SAL-only.
    pub require_sail: bool,
}

// ── session ─────────────────────────────────────────────────────────

/// FNP session manager — two-message handshake between sovereign nodes.
///
/// Cross-SDK byte-identical with Python `FNPSession`, Go `FNPSession`,
/// TypeScript `FNPSession`. State machine, ADR-004 basis-manifest support,
/// and field semantics match.
///
/// Initiator usage:
/// ```ignore
/// let mut session = FNPSession::new_with_version(&asd, "NODE_A", 1, FNP_CAP_FLOOR);
/// let adv = session.initiate()?;
/// // ... transmit adv, receive ack_packet ...
/// session.receive(&ack_packet)?;
/// // session.state is now Established* / SyncNeeded
/// ```
///
/// Responder usage:
/// ```ignore
/// let mut session = FNPSession::new_with_version(&asd, "NODE_B", 1, FNP_CAP_FLOOR);
/// let ack = session.receive(&adv_packet)?.expect("ACK must be returned");
/// // ... transmit ack ...
/// // session.state is now Established* / SyncNeeded
/// ```
#[derive(Debug, Clone)]
pub struct FNPSession {
    /// Current state of the FNP session.
    pub state: FNPState,
    /// Identity of this local node.
    pub local_node_id: String,
    /// Identity of the remote peer (set after `receive()` or `fallback()`).
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

    // ADR-004 basis manifest support
    /// 8-byte basis fingerprint when in extended-form, `None` for base-form sessions.
    pub basis_fingerprint: Option<Vec<u8>>,
    /// Expected peer basis fingerprint, when configured.
    pub expected_basis_fingerprint: Option<Vec<u8>>,
    /// `require_sail` policy flag.
    pub require_sail: bool,
    /// Remote peer's basis fingerprint (set after extended-form ADV is received).
    pub remote_basis_fingerprint: Option<Vec<u8>>,
    /// Degradation event recorded during state transition, if any.
    pub degradation_event: Option<DegradationEvent>,

    asd_version: u16,
    channel_capacity: u8,
    own_fingerprint: Vec<u8>,
    own_bitmap: u32,
}

impl FNPSession {
    /// Create a new FNP session in `Idle` state.
    ///
    /// Mirrors Go `NewFNPSession(asd, nodeID, asdVersion, channelCapacity)`,
    /// taking `profile` as a single-byte ASD version for legacy compatibility.
    pub fn new(asd: &AdaptiveSharedDictionary, local_id: &str, profile: u8, caps: u8) -> Self {
        Self::new_with_version(asd, local_id, profile as u16, caps)
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
            state: FNPState::Idle,
            local_node_id: local_id.to_string(),
            remote_node_id: String::new(),
            remote_fingerprint: None,
            common_namespaces: Vec::new(),
            match_status: -1,
            negotiated_capacity: -1,
            capabilities: own_bitmap,
            basis_fingerprint: None,
            expected_basis_fingerprint: None,
            require_sail: false,
            remote_basis_fingerprint: None,
            degradation_event: None,
            asd_version,
            channel_capacity,
            own_fingerprint: own_fp,
            own_bitmap,
        }
    }

    /// Constructor with ADR-004 basis-manifest options.
    pub fn new_with_options(
        asd: &AdaptiveSharedDictionary,
        local_id: &str,
        asd_version: u16,
        channel_capacity: u8,
        opts: FNPSessionOptions,
    ) -> Result<Self, FnpError> {
        let mut s = Self::new_with_version(asd, local_id, asd_version, channel_capacity);
        if let Some(fp) = &opts.basis_fingerprint {
            if fp.len() != 8 {
                return Err(FnpError::InvalidBasisFingerprint);
            }
            s.basis_fingerprint = Some(fp.clone());
        }
        s.expected_basis_fingerprint = opts.expected_basis_fingerprint;
        s.require_sail = opts.require_sail;
        Ok(s)
    }

    /// Returns true if this session uses extended-form ADV (basis fingerprint set).
    pub fn is_extended_form(&self) -> bool {
        self.basis_fingerprint.is_some()
    }

    /// Returns true if the negotiated session supports SAIL wire mode (ADR-004).
    pub fn is_sail_capable(&self) -> bool {
        self.state == FNPState::EstablishedSAIL
    }

    /// Build the 40-byte ADV packet for this session.
    fn build_adv(&self) -> Vec<u8> {
        let mut buf = vec![0u8; FNP_ADV_SIZE];
        buf[1] = FNP_PROTOCOL_VERSION;
        buf[2..10].copy_from_slice(&self.own_fingerprint);
        buf[10..12].copy_from_slice(&self.asd_version.to_be_bytes());
        buf[12..16].copy_from_slice(&self.own_bitmap.to_be_bytes());
        buf[16] = self.channel_capacity;

        if self.is_extended_form() {
            buf[0] = FNP_MSG_ADV_EXTENDED;
            let nid = self.local_node_id.as_bytes();
            let nid_len = nid.len().min(15);
            buf[17..17 + nid_len].copy_from_slice(&nid[..nid_len]);
            if let Some(bf) = &self.basis_fingerprint {
                buf[32..40].copy_from_slice(&bf[..8]);
            }
        } else {
            buf[0] = FNP_MSG_ADV;
            let nid = self.local_node_id.as_bytes();
            let nid_len = nid.len().min(23);
            buf[17..17 + nid_len].copy_from_slice(&nid[..nid_len]);
        }
        buf
    }

    /// Build the 38-byte ACK packet for this session.
    fn build_ack(
        &self,
        remote_fp: &[u8],
        match_status: i32,
        common_bitmap: u32,
        neg_cap: u8,
    ) -> Vec<u8> {
        let mut buf = vec![0u8; FNP_ACK_SIZE];
        // ADR-004: basis-graded matches (0x03 / 0x04) are NOT failures —
        // graded capability uses ACK rather than NACK.
        if match_status == FNP_MATCH_EXACT
            || match_status == FNP_MATCH_BASIS_MISMATCH
            || match_status == FNP_MATCH_BASIS_EXT_VS_BASE
        {
            buf[0] = FNP_MSG_ACK;
        } else {
            buf[0] = FNP_MSG_NACK;
        }
        buf[1] = match_status as u8;
        buf[2..10].copy_from_slice(remote_fp);
        buf[10..18].copy_from_slice(&self.own_fingerprint);
        buf[18..22].copy_from_slice(&common_bitmap.to_be_bytes());
        buf[22] = neg_cap;
        let nid = self.local_node_id.as_bytes();
        let nid_len = nid.len().min(15);
        buf[23..23 + nid_len].copy_from_slice(&nid[..nid_len]);
        buf
    }

    /// Start a handshake by building and returning the 40-byte ADV packet.
    /// Transitions: `Idle` -> `AdvSent`.
    pub fn initiate(&mut self) -> Result<Vec<u8>, FnpError> {
        if self.state != FNPState::Idle {
            return Err(FnpError::InvalidState(format!(
                "cannot initiate from {:?}",
                self.state
            )));
        }
        self.state = FNPState::AdvSent;
        Ok(self.build_adv())
    }

    /// Process a received FNP packet.
    ///
    /// If `Idle` and an ADV is received, returns `Some(ack_bytes)` for transmission.
    /// If `AdvSent` and an ACK is received, reads the match result and returns `Ok(None)`.
    pub fn receive(&mut self, data: &[u8]) -> Result<Option<Vec<u8>>, FnpError> {
        if data.is_empty() {
            return Err(FnpError::InvalidPacket("empty packet".to_string()));
        }
        let msg_type = data[0];
        let msg_type_base = msg_type & !FNP_ADV_EXT_FLAG;

        if msg_type_base == FNP_MSG_ADV && self.state == FNPState::Idle {
            let adv = parse_adv(data)?;
            self.remote_node_id = adv.node_id.clone();
            self.remote_fingerprint = Some(adv.fingerprint.clone());
            self.remote_basis_fingerprint = adv.basis_fingerprint.clone();

            let match_status: i32 = if adv.fingerprint != self.own_fingerprint {
                FNP_MATCH_FINGERPRINT
            } else if adv.asd_version != self.asd_version {
                FNP_MATCH_VERSION
            } else {
                let remote_ext = adv.basis_fingerprint.is_some();
                let local_ext = self.is_extended_form();
                if remote_ext && local_ext {
                    if adv.basis_fingerprint.as_deref() == self.basis_fingerprint.as_deref() {
                        FNP_MATCH_EXACT
                    } else {
                        FNP_MATCH_BASIS_MISMATCH
                    }
                } else if remote_ext != local_ext {
                    FNP_MATCH_BASIS_EXT_VS_BASE
                } else {
                    FNP_MATCH_EXACT
                }
            };

            let common = self.own_bitmap & adv.namespace_bitmap;
            self.common_namespaces = bitmap_to_namespaces(common);
            self.match_status = match_status;

            let neg_cap = adv.channel_capacity.min(self.channel_capacity);
            self.negotiated_capacity = neg_cap as i32;

            self.apply_match_to_state(match_status, adv.basis_fingerprint.as_deref());
            return Ok(Some(self.build_ack(&adv.fingerprint, match_status, common, neg_cap)));
        }

        if (msg_type_base == FNP_MSG_ACK || msg_type_base == FNP_MSG_NACK)
            && self.state == FNPState::AdvSent
        {
            let ack = parse_ack(data)?;
            if ack.echo_fingerprint != self.own_fingerprint {
                return Err(FnpError::EchoMismatch);
            }
            self.remote_node_id = ack.node_id;
            self.remote_fingerprint = Some(ack.own_fingerprint);
            self.common_namespaces = bitmap_to_namespaces(ack.common_bitmap);
            self.match_status = ack.match_status as i32;
            self.negotiated_capacity = ack.negotiated_capacity as i32;
            // ACK does not carry remote basis fingerprint per ADR-004; the
            // initiator learns basis agreement via match_status.
            self.apply_match_to_state(ack.match_status as i32, None);
            return Ok(None);
        }

        Err(FnpError::InvalidPacket(format!(
            "unexpected msg_type 0x{:02x} in state {:?}",
            msg_type, self.state
        )))
    }

    /// ADR-004 capability grading helper. Sets `state` and (when applicable)
    /// records a `DegradationEvent`. Refuses the session under `require_sail`
    /// policy by reverting to `Idle`.
    fn apply_match_to_state(&mut self, match_status: i32, peer_basis_fp: Option<&[u8]>) {
        if match_status == FNP_MATCH_EXACT {
            self.state = FNPState::EstablishedSAIL;
            return;
        }
        if match_status == FNP_MATCH_BASIS_MISMATCH || match_status == FNP_MATCH_BASIS_EXT_VS_BASE {
            if self.require_sail {
                self.state = FNPState::Idle;
                self.degradation_event = Some(DegradationEvent {
                    reason: "require_sail policy refused basis-mismatched session".to_string(),
                    match_status,
                    remote_node_id: self.remote_node_id.clone(),
                    remote_basis_fingerprint: peer_basis_fp.map(hex_encode),
                    expected_basis_fingerprint: None,
                });
                return;
            }
            self.state = FNPState::EstablishedSALOnly;
            if let (Some(expected), Some(peer)) =
                (&self.expected_basis_fingerprint, peer_basis_fp)
            {
                if expected.as_slice() != peer {
                    self.degradation_event = Some(DegradationEvent {
                        reason: "remote basis fingerprint differs from expected".to_string(),
                        match_status,
                        remote_node_id: self.remote_node_id.clone(),
                        remote_basis_fingerprint: Some(hex_encode(peer)),
                        expected_basis_fingerprint: Some(hex_encode(expected)),
                    });
                }
            }
            return;
        }
        // FNP_MATCH_VERSION or FNP_MATCH_FINGERPRINT
        self.state = FNPState::SyncNeeded;
    }

    /// Handshake timeout. Transitions: `AdvSent` -> `Idle`.
    pub fn timeout(&mut self) {
        if self.state == FNPState::AdvSent {
            self.state = FNPState::Idle;
            self.remote_node_id.clear();
            self.remote_fingerprint = None;
            self.common_namespaces.clear();
            self.match_status = -1;
            self.negotiated_capacity = -1;
        }
    }

    /// Transition to `Fallback` when the remote peer does not speak OSMP.
    ///
    /// Called when:
    /// - ADV was sent but the response is not a valid FNP packet
    /// - The transport is known to be non-OSMP (e.g., plain JSON-RPC, NL)
    /// - Timeout occurred during a negotiation attempt with a new peer
    ///
    /// Transitions: `AdvSent` -> `Fallback`, or `Idle` -> `Fallback`.
    pub fn fallback(&mut self, remote_id: &str) {
        if self.state == FNPState::AdvSent || self.state == FNPState::Idle {
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
