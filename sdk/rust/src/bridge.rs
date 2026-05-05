//! SAL Bridge — boundary translator between OSMP-native agents and non-OSMP peers.
//!
//! The bridge sits at the boundary between an OSMP-native swarm and non-OSMP
//! agents. It does four things:
//!
//!   1. Detects whether the remote peer speaks OSMP (via FNP negotiation).
//!   2. If not, enters FALLBACK mode: decodes outbound SAL to natural language,
//!      tags inbound natural language as NL_PASSTHROUGH.
//!   3. Annotates outbound messages with SAL equivalents, seeding the remote
//!      agent's context window with SAL patterns.
//!   4. Monitors inbound messages for valid SAL fragments. When the remote
//!      agent starts producing valid SAL (few-shot acquisition), transitions
//!      to ACQUIRED state and begins sending pure SAL.
//!
//! This is Bridge α (sliding-window acquisition) plus a macro-bypass
//! attachment hook. β (TENTATIVE_SAL state machine), γ (probe scheduler),
//! and δ-B (preamble handler) are not in this baseline.
//!
//! Cross-SDK byte-identical with Python `SALBridge`, Go `SALBridge`,
//! TypeScript `SALBridge`. Acquisition thresholds (5/3), event names,
//! and inbound shape all match.
//!
//! License: Apache-2.0

use std::collections::{BTreeMap, BTreeSet};
use std::time::SystemTime;

use crate::asd::AdaptiveSharedDictionary;
use crate::fnp::{FNPSession, FNPState, FNP_CAP_UNCONSTRAINED};
use crate::macros::MacroRegistry;

/// Default consecutive valid-SAL messages before transitioning Fallback -> Acquired.
pub const DEFAULT_ACQUISITION_THRESHOLD: usize = 5;
/// Default consecutive non-SAL messages before transitioning Acquired -> Fallback.
pub const DEFAULT_REGRESSION_THRESHOLD: usize = 3;

// ── metrics ─────────────────────────────────────────────────────────

/// Tracks SAL acquisition progress for a single remote peer.
///
/// Fields mirror Python `AcquisitionMetrics`, Go `AcquisitionMetrics`,
/// and TypeScript `AcquisitionMetrics` 1:1.
#[derive(Debug, Clone, Default)]
pub struct AcquisitionMetrics {
    /// Total inbound messages observed.
    pub total_messages: usize,
    /// Inbound messages containing at least one valid SAL frame.
    pub messages_with_sal: usize,
    /// Current consecutive valid-SAL streak.
    pub consecutive_sal_hits: usize,
    /// Current consecutive non-SAL streak.
    pub consecutive_sal_misses: usize,
    /// Highest streak observed during the session.
    pub peak_consecutive_hits: usize,
    /// Total valid SAL frames observed (sum across all messages).
    pub valid_frames_seen: usize,
    /// Set of unique `"NS:OP"` opcode pairs observed.
    pub unique_opcodes_seen: BTreeSet<String>,
    /// SystemTime when the first SAL frame was observed.
    pub first_sal_seen_at: Option<SystemTime>,
    /// SystemTime when the most recent SAL frame was observed.
    pub last_sal_seen_at: Option<SystemTime>,
}

impl AcquisitionMetrics {
    /// Returns 0.0 to 1.0 based on consecutive valid SAL production.
    pub fn acquisition_score(&self, threshold: usize) -> f64 {
        if self.total_messages == 0 || threshold == 0 {
            return 0.0;
        }
        let raw = self.consecutive_sal_hits as f64 / threshold as f64;
        if raw > 1.0 {
            1.0
        } else {
            raw
        }
    }

    fn record_hit(&mut self, frames: &[(String, String)]) {
        let now = SystemTime::now();
        self.total_messages += 1;
        self.messages_with_sal += 1;
        self.consecutive_sal_hits += 1;
        self.consecutive_sal_misses = 0;
        self.valid_frames_seen += frames.len();
        for (ns, op) in frames {
            self.unique_opcodes_seen.insert(format!("{ns}:{op}"));
        }
        if self.consecutive_sal_hits > self.peak_consecutive_hits {
            self.peak_consecutive_hits = self.consecutive_sal_hits;
        }
        if self.first_sal_seen_at.is_none() {
            self.first_sal_seen_at = Some(now);
        }
        self.last_sal_seen_at = Some(now);
    }

    fn record_miss(&mut self) {
        self.total_messages += 1;
        self.consecutive_sal_hits = 0;
        self.consecutive_sal_misses += 1;
    }
}

// ── log entries ─────────────────────────────────────────────────────

/// A single bridge activity log entry.
///
/// `event_type` values match Python / Go / TypeScript exactly:
/// `"fallback"`, `"annotate"`, `"detect_sal"`, `"acquire"`, `"regress"`,
/// `"send_sal"`, `"passthrough"`.
#[derive(Debug, Clone)]
pub struct BridgeEvent {
    /// SystemTime when the event was emitted.
    pub timestamp: SystemTime,
    /// Event type label.
    pub event_type: String,
    /// Identity of the peer the event concerns.
    pub remote_id: String,
    /// SAL representation of the message, or empty string.
    pub sal: String,
    /// Natural-language representation of the message, or empty string.
    pub nl: String,
    /// Number of valid SAL frames detected (for `detect_sal` events).
    pub frames_detected: usize,
    /// Free-form detail string for human-readable context.
    pub detail: String,
}

/// Result of `SALBridge::receive()`.
///
/// Cross-SDK byte-identical shape with Python `BridgeInbound`, Go
/// `BridgeInbound`, TypeScript `BridgeInbound`.
#[derive(Debug, Clone)]
pub struct BridgeInbound {
    /// SAL representation if the message was valid SAL.
    pub sal: Option<String>,
    /// Natural-language content if the message was NL or mixed.
    pub nl: Option<String>,
    /// True if this is an NL_PASSTHROUGH (unencoded external input).
    pub passthrough: bool,
    /// Identity of the sending peer.
    pub peer_id: String,
    /// FNP session state at time of receipt.
    pub state: FNPState,
    /// Any valid SAL frames detected in a mixed-content message.
    pub detected_frames: Vec<String>,
}

// ── SAL frame detection ─────────────────────────────────────────────

/// Single-character namespace pattern (Tier 1 ASD basis).
///
/// Tier 2 namespaces (two-letter, e.g. `AGT:`) are not detected by the
/// bridge inbound scanner: cross-SDK behavior is to detect Tier 1 only,
/// matching Go `salBridgeFrameRe` and TypeScript `SAL_FRAME_RE_BRIDGE`.
fn is_namespace_char(c: char) -> bool {
    c.is_ascii_uppercase()
}

/// Opcode body character: A-Z, 0-9, or § (human-authorization marker).
fn is_opcode_char(c: char) -> bool {
    c.is_ascii_uppercase() || c.is_ascii_digit() || c == '\u{00A7}'
}

/// First-character of opcode: A-Z or §.
fn is_opcode_start_char(c: char) -> bool {
    c.is_ascii_uppercase() || c == '\u{00A7}'
}

/// Word-boundary check matching Go RE2 `\b` for the cross-SDK regex.
fn is_word_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

/// Scan a message and yield every `(namespace, opcode, span_end)` SAL frame.
///
/// Equivalent to the Go `salBridgeFrameRe.FindAllStringSubmatch` /
/// TypeScript `new RegExp(SAL_FRAME_RE.source, "g")` scan. The scanner
/// recognizes one-letter namespaces only (matching the Tier 1 SAL pattern
/// `\b[A-Z]:[A-Z§][A-Z0-9§]*`).
fn scan_sal_frames(message: &str) -> Vec<(String, String, usize, usize)> {
    let bytes = message.as_bytes();
    let mut out: Vec<(String, String, usize, usize)> = Vec::new();
    let chars: Vec<(usize, char)> = message.char_indices().collect();
    let mut i = 0;
    while i < chars.len() {
        let (byte_start, ch) = chars[i];
        if !is_namespace_char(ch) {
            i += 1;
            continue;
        }
        // Word boundary: previous char must be a non-word character (or BOL).
        let prev_is_word = if i == 0 {
            false
        } else {
            let prev_byte = chars[i - 1].0;
            // Walk back one char.
            let prev_ch = bytes[prev_byte] as char;
            // Use the structured prior char index.
            let prior = chars[i - 1].1;
            let _ = prev_ch;
            is_word_char(prior)
        };
        if prev_is_word {
            i += 1;
            continue;
        }
        // Need a colon next.
        let colon_idx = i + 1;
        if colon_idx >= chars.len() || chars[colon_idx].1 != ':' {
            i += 1;
            continue;
        }
        // Opcode start.
        let op_start_idx = colon_idx + 1;
        if op_start_idx >= chars.len() || !is_opcode_start_char(chars[op_start_idx].1) {
            i += 1;
            continue;
        }
        // Greedy opcode body.
        let mut op_end_idx = op_start_idx + 1;
        while op_end_idx < chars.len() && is_opcode_char(chars[op_end_idx].1) {
            op_end_idx += 1;
        }
        let ns = ch.to_string();
        let opcode_byte_start = chars[op_start_idx].0;
        let opcode_byte_end = if op_end_idx < chars.len() {
            chars[op_end_idx].0
        } else {
            message.len()
        };
        let op = message[opcode_byte_start..opcode_byte_end].to_string();
        out.push((ns, op, byte_start, opcode_byte_end));
        i = op_end_idx;
    }
    out
}

/// Strip a comprehensive frame-with-tail match from `s` and return the residue.
///
/// Mirrors the Go `salFrameWithTailRe` / Python `frame_with_tail_re`
/// regex used by `is_pure_sal`. Tail elements: `@target`, `?query`,
/// `[bracket]`, `:slot`, and consequence-class glyph (⚠ ↺ ⊘).
fn strip_frame_tails(message: &str) -> String {
    // Iteratively find the next SAL frame head and consume its tail.
    let mut out = String::with_capacity(message.len());
    let chars: Vec<(usize, char)> = message.char_indices().collect();
    let mut cursor: usize = 0;
    let bytes = message.len();
    while cursor < bytes {
        // Find the next frame start at or after cursor.
        let frames = scan_sal_frames(&message[cursor..]);
        if frames.is_empty() {
            out.push_str(&message[cursor..]);
            break;
        }
        // Frame positions are relative to the slice; offset back to absolute.
        let (_ns, _op, rel_start, rel_end) = frames[0].clone();
        let abs_start = cursor + rel_start;
        let abs_end = cursor + rel_end;
        // Append the prefix.
        out.push_str(&message[cursor..abs_start]);
        // Consume the tail. Walk forward from abs_end through optional
        // `@target`, `?query`, `[bracket]`, `:slot[:slot...]`, and a
        // single consequence-class glyph.
        let mut tail_end = abs_end;
        // @target (alphanumeric / _ / * / -)
        let _ = chars; // keep for debug
        if tail_end < bytes && message.as_bytes()[tail_end] == b'@' {
            tail_end += 1;
            while tail_end < bytes {
                let b = message.as_bytes()[tail_end] as char;
                if b.is_ascii_alphanumeric() || b == '_' || b == '*' || b == '-' {
                    tail_end += 1;
                } else {
                    break;
                }
            }
        }
        // ?query (alphanumeric / _)
        if tail_end < bytes && message.as_bytes()[tail_end] == b'?' {
            tail_end += 1;
            while tail_end < bytes {
                let b = message.as_bytes()[tail_end] as char;
                if b.is_ascii_alphanumeric() || b == '_' {
                    tail_end += 1;
                } else {
                    break;
                }
            }
        }
        // [bracket]
        if tail_end < bytes && message.as_bytes()[tail_end] == b'[' {
            tail_end += 1;
            while tail_end < bytes && message.as_bytes()[tail_end] != b']' {
                tail_end += 1;
            }
            if tail_end < bytes && message.as_bytes()[tail_end] == b']' {
                tail_end += 1;
            }
        }
        // :slot[:slot...]
        while tail_end < bytes && message.as_bytes()[tail_end] == b':' {
            // Look ahead: only consume if the char after `:` is alphanumeric.
            let ahead = tail_end + 1;
            if ahead >= bytes {
                break;
            }
            let b = message.as_bytes()[ahead] as char;
            if !(b.is_ascii_alphanumeric() || b == '_') {
                break;
            }
            tail_end += 1; // consume ':'
            while tail_end < bytes {
                let b = message.as_bytes()[tail_end] as char;
                if b.is_ascii_alphanumeric() || b == '_' || b == '.' || b == '-' {
                    tail_end += 1;
                } else {
                    break;
                }
            }
        }
        // Consequence-class glyph: ⚠ U+26A0 (3 bytes), ↺ U+21BA (3 bytes),
        // ⊘ U+2298 (3 bytes).
        if tail_end + 3 <= bytes {
            let next3 = &message.as_bytes()[tail_end..tail_end + 3];
            // ⚠: E2 9A A0 ; ↺: E2 86 BA ; ⊘: E2 8A 98
            if (next3[0] == 0xE2 && next3[1] == 0x9A && next3[2] == 0xA0)
                || (next3[0] == 0xE2 && next3[1] == 0x86 && next3[2] == 0xBA)
                || (next3[0] == 0xE2 && next3[1] == 0x8A && next3[2] == 0x98)
            {
                tail_end += 3;
            }
        }
        cursor = tail_end;
    }
    out
}

/// Strip chain operators and whitespace from `s`.
///
/// Operators stripped: ∧ ∨ ¬ → ↔ ∥ ⟳ ≠ ⊕ ; whitespace ()
fn strip_operators_and_whitespace(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        let cp = ch as u32;
        let is_op = matches!(
            cp,
            0x2227 // ∧
            | 0x2228 // ∨
            | 0x00AC // ¬
            | 0x2192 // →
            | 0x2194 // ↔
            | 0x2225 // ∥
            | 0x27F3 // ⟳
            | 0x2260 // ≠
            | 0x2295 // ⊕
        );
        let is_ws_or_punct = ch == ';' || ch.is_whitespace() || ch == '(' || ch == ')';
        if is_op || is_ws_or_punct {
            continue;
        }
        out.push(ch);
    }
    out
}

// ── SALBridge ───────────────────────────────────────────────────────

/// Boundary translator between OSMP-native agents and non-OSMP peers.
///
/// Internal agents always speak SAL. The bridge handles negotiation,
/// fallback, annotation, and acquisition automatically.
///
/// Cross-SDK byte-identical with Python `SALBridge`, Go `SALBridge`,
/// TypeScript `SALBridge`.
#[derive(Debug)]
pub struct SALBridge {
    /// Identity of this OSMP node.
    pub node_id: String,
    /// Adaptive shared dictionary used for opcode lookup and decode-to-NL.
    pub asd: AdaptiveSharedDictionary,
    /// If true, outbound NL messages to FALLBACK peers are annotated with
    /// `[SAL: ...]` tags to seed the remote context window.
    pub annotate: bool,
    /// Number of consecutive messages with valid SAL before transitioning
    /// from FALLBACK to ACQUIRED.
    pub acquisition_threshold: usize,
    /// Number of consecutive messages without SAL before transitioning from
    /// ACQUIRED back to FALLBACK.
    pub regression_threshold: usize,

    sessions: BTreeMap<String, FNPSession>,
    metrics: BTreeMap<String, AcquisitionMetrics>,
    log: Vec<BridgeEvent>,
    macro_registry: Option<MacroRegistry>,
}

impl SALBridge {
    /// Construct a new bridge instance.
    ///
    /// If `asd` is `None`, a fresh `AdaptiveSharedDictionary` seeded from
    /// the v15 floor basis is used.
    pub fn new(node_id: &str, asd: Option<AdaptiveSharedDictionary>, annotate: bool) -> Self {
        let asd = asd.unwrap_or_default();
        Self {
            node_id: node_id.to_string(),
            asd,
            annotate,
            acquisition_threshold: DEFAULT_ACQUISITION_THRESHOLD,
            regression_threshold: DEFAULT_REGRESSION_THRESHOLD,
            sessions: BTreeMap::new(),
            metrics: BTreeMap::new(),
            log: Vec::new(),
            macro_registry: None,
        }
    }

    /// Register a remote peer.
    ///
    /// If `attempt_fnp` is false, immediately enters `Fallback` (use for
    /// peers known to be non-OSMP, e.g. plain JSON-RPC endpoints).
    pub fn register_peer(&mut self, peer_id: &str, attempt_fnp: bool) -> FNPState {
        let mut session = FNPSession::new_with_version(
            &self.asd,
            &self.node_id,
            1,
            FNP_CAP_UNCONSTRAINED,
        );
        if !attempt_fnp {
            session.fallback(peer_id);
        }
        let state = session.state;
        self.sessions.insert(peer_id.to_string(), session);
        self.metrics
            .insert(peer_id.to_string(), AcquisitionMetrics::default());
        if !attempt_fnp {
            self.emit(
                "fallback",
                peer_id,
                "",
                "",
                0,
                "direct registration, no FNP attempt",
            );
        }
        state
    }

    /// Return the FNP session state for a peer, or `None` if unregistered.
    pub fn peer_state(&self, peer_id: &str) -> Option<FNPState> {
        self.sessions.get(peer_id).map(|s| s.state)
    }

    /// Translate outbound SAL for the target peer.
    ///
    /// - `Established` / `EstablishedSAIL` / `EstablishedSALOnly` /
    ///   `SyncNeeded`: returns SAL unchanged.
    /// - `Acquired`: returns SAL unchanged.
    /// - `Fallback`: decodes to NL, optionally annotated with `[SAL: ...]`.
    /// - Unknown peer: auto-registers as Fallback, then translates.
    pub fn send(&mut self, sal: &str, peer_id: &str) -> String {
        if !self.sessions.contains_key(peer_id) {
            self.register_peer(peer_id, false);
        }
        let state = self
            .sessions
            .get(peer_id)
            .map(|s| s.state)
            .unwrap_or(FNPState::Fallback);

        // Native OSMP peer — send SAL directly.
        if matches!(
            state,
            FNPState::Established
                | FNPState::EstablishedSAIL
                | FNPState::EstablishedSALOnly
                | FNPState::SyncNeeded
        ) {
            self.emit("send_sal", peer_id, sal, "", 0, "native OSMP peer");
            return sal.to_string();
        }

        // Acquired peer — send SAL directly (they learned it).
        if state == FNPState::Acquired {
            self.emit(
                "send_sal",
                peer_id,
                sal,
                "",
                0,
                "acquired peer, sending SAL",
            );
            return sal.to_string();
        }

        // Fallback peer — decode to NL.
        let nl = self.decode_to_nl(sal);

        if self.annotate {
            let annotated = format!("{nl}\n[SAL: {sal}]");
            self.emit(
                "annotate",
                peer_id,
                sal,
                &nl,
                0,
                "annotated outbound for context seeding",
            );
            return annotated;
        }

        self.emit(
            "passthrough",
            peer_id,
            sal,
            &nl,
            0,
            "outbound decoded to NL, no annotation",
        );
        nl
    }

    /// Process an inbound message from a peer.
    ///
    /// Scans for valid SAL fragments, updates acquisition metrics,
    /// and handles state transitions Fallback <-> Acquired.
    pub fn receive(&mut self, message: &str, peer_id: &str) -> BridgeInbound {
        if !self.sessions.contains_key(peer_id) {
            self.register_peer(peer_id, false);
        }
        let state = self
            .sessions
            .get(peer_id)
            .map(|s| s.state)
            .unwrap_or(FNPState::Fallback);

        // Native OSMP peer — pass through as SAL.
        if matches!(
            state,
            FNPState::Established
                | FNPState::EstablishedSAIL
                | FNPState::EstablishedSALOnly
                | FNPState::SyncNeeded
        ) {
            return BridgeInbound {
                sal: Some(message.to_string()),
                nl: None,
                passthrough: false,
                peer_id: peer_id.to_string(),
                state,
                detected_frames: Vec::new(),
            };
        }

        // Strip [SAL: ...] annotation wrapper if the model echoed our format.
        let processed = strip_sal_wrapper(message);

        // Scan for SAL fragments.
        let detected = self.detect_sal_frames(&processed);

        if !detected.is_empty() {
            // Record hit on metrics.
            let frames_owned: Vec<(String, String)> = detected
                .iter()
                .map(|(ns, op)| (ns.clone(), op.clone()))
                .collect();
            if let Some(m) = self.metrics.get_mut(peer_id) {
                m.record_hit(&frames_owned);
            }

            let frame_strs: Vec<String> = detected
                .iter()
                .map(|(ns, op)| format!("{ns}:{op}"))
                .collect();
            let detail = format!("valid SAL frames: {}", frame_strs.join(", "));
            self.emit(
                "detect_sal",
                peer_id,
                &processed,
                "",
                detected.len(),
                &detail,
            );

            // Check acquisition transition.
            let unique_count = self
                .metrics
                .get(peer_id)
                .map(|m| m.unique_opcodes_seen.len())
                .unwrap_or(0);
            let consec = self
                .metrics
                .get(peer_id)
                .map(|m| m.consecutive_sal_hits)
                .unwrap_or(0);
            if state == FNPState::Fallback && consec >= self.acquisition_threshold {
                if let Some(s) = self.sessions.get_mut(peer_id) {
                    s.acquire();
                }
                let detail = format!(
                    "acquisition threshold met ({} consecutive hits, {} unique opcodes)",
                    self.acquisition_threshold, unique_count
                );
                self.emit("acquire", peer_id, "", "", 0, &detail);
            }

            let new_state = self
                .sessions
                .get(peer_id)
                .map(|s| s.state)
                .unwrap_or(state);

            // If the entire message is pure SAL, return it as SAL.
            if self.is_pure_sal(&processed) {
                return BridgeInbound {
                    sal: Some(processed),
                    nl: None,
                    passthrough: false,
                    peer_id: peer_id.to_string(),
                    state: new_state,
                    detected_frames: Vec::new(),
                };
            }

            // Mixed content — return both.
            return BridgeInbound {
                sal: None,
                nl: Some(processed),
                passthrough: true,
                peer_id: peer_id.to_string(),
                state: new_state,
                detected_frames: frame_strs,
            };
        }

        // No SAL detected.
        if let Some(m) = self.metrics.get_mut(peer_id) {
            m.record_miss();
        }
        let consec_misses = self
            .metrics
            .get(peer_id)
            .map(|m| m.consecutive_sal_misses)
            .unwrap_or(0);

        // Check regression.
        if state == FNPState::Acquired && consec_misses >= self.regression_threshold {
            if let Some(s) = self.sessions.get_mut(peer_id) {
                s.regress();
            }
            let detail = format!(
                "regression threshold met ({} consecutive misses)",
                self.regression_threshold
            );
            self.emit("regress", peer_id, "", "", 0, &detail);
        }

        let new_state = self
            .sessions
            .get(peer_id)
            .map(|s| s.state)
            .unwrap_or(state);

        BridgeInbound {
            sal: None,
            nl: Some(processed),
            passthrough: true,
            peer_id: peer_id.to_string(),
            state: new_state,
            detected_frames: Vec::new(),
        }
    }

    /// Attach a macro registry to enable macro-bypass on outbound paths.
    ///
    /// At this baseline the bridge stores the registry as a hook for the
    /// composer / macro-expansion layer; full macro-bypass behavior is
    /// provided by the composer when the registry is wired through. The
    /// bridge does not invoke the registry directly — see Go `composer.go`
    /// `SetMacroRegistry` for the equivalent attachment surface.
    pub fn attach_macro_registry(&mut self, registry: MacroRegistry) {
        self.macro_registry = Some(registry);
    }

    /// Returns the attached macro registry, or `None`.
    pub fn macro_registry(&self) -> Option<&MacroRegistry> {
        self.macro_registry.as_ref()
    }

    /// Acquisition metrics for a peer, or `None` if the peer is not registered.
    pub fn metrics(&self, peer_id: &str) -> Option<&AcquisitionMetrics> {
        self.metrics.get(peer_id)
    }

    /// Read-only view of the bridge event log.
    pub fn log(&self) -> &[BridgeEvent] {
        &self.log
    }

    /// Bridge event log filtered to a single peer.
    pub fn log_for_peer(&self, peer_id: &str) -> Vec<BridgeEvent> {
        self.log
            .iter()
            .filter(|e| e.remote_id == peer_id)
            .cloned()
            .collect()
    }

    // ── internal ────────────────────────────────────────────────────

    fn decode_to_nl(&self, sal: &str) -> String {
        let mut parts: Vec<String> = Vec::new();
        for raw in sal.split(';') {
            let trimmed = raw.trim();
            if trimmed.is_empty() {
                continue;
            }
            // Match leading "NS:OP" head (Tier 1 only for cross-SDK parity
            // with the Python `^([A-Z]):([A-Z]+)` head match in
            // `_decode_to_nl`).
            let bytes = trimmed.as_bytes();
            let mut head_end = 0usize;
            if bytes.len() >= 3
                && (bytes[0] as char).is_ascii_uppercase()
                && bytes[1] == b':'
                && (bytes[2] as char).is_ascii_uppercase()
            {
                head_end = 3;
                while head_end < bytes.len()
                    && (bytes[head_end] as char).is_ascii_uppercase()
                {
                    head_end += 1;
                }
                let ns = &trimmed[0..1];
                let op = &trimmed[2..head_end];
                if let Some(def) = self.asd.lookup(ns, op) {
                    let rest = trimmed[head_end..].trim();
                    if rest.is_empty() {
                        parts.push(def.to_string());
                    } else {
                        parts.push(format!("{def} {rest}"));
                    }
                    continue;
                }
            }
            // Fallback: passthrough the original frame.
            parts.push(trimmed.to_string());
            let _ = head_end;
        }
        parts.join("; ")
    }

    fn detect_sal_frames(&self, message: &str) -> Vec<(String, String)> {
        let mut valid: Vec<(String, String)> = Vec::new();
        for (ns, op, _start, _end) in scan_sal_frames(message) {
            if self.asd.lookup(&ns, &op).is_some() {
                valid.push((ns, op));
            }
        }
        valid
    }

    fn is_pure_sal(&self, message: &str) -> bool {
        let stripped = message.trim();
        if stripped.is_empty() {
            return false;
        }
        // Strip every valid SAL frame with its tail.
        let residue = strip_frame_tails(stripped);
        // Strip chain operators, parens, and whitespace.
        let residue = strip_operators_and_whitespace(&residue);
        if !residue.is_empty() {
            return false;
        }
        // Second pass: every recognized frame must contain a real SAL frame match.
        let frames: Vec<&str> = stripped
            .split(';')
            .map(str::trim)
            .filter(|f| !f.is_empty())
            .collect();
        for f in frames {
            if scan_sal_frames(f).is_empty() {
                return false;
            }
        }
        true
    }

    fn emit(
        &mut self,
        event_type: &str,
        remote_id: &str,
        sal: &str,
        nl: &str,
        frames_detected: usize,
        detail: &str,
    ) {
        self.log.push(BridgeEvent {
            timestamp: SystemTime::now(),
            event_type: event_type.to_string(),
            remote_id: remote_id.to_string(),
            sal: sal.to_string(),
            nl: nl.to_string(),
            frames_detected,
            detail: detail.to_string(),
        });
    }
}

/// Strip a `[SAL: ...]` wrapper if the message echoes the bridge's annotation.
///
/// Matches the Python `^\s*\[SAL:\s*(.+?)\]\s*$` regex behavior used in
/// `bridge.py` — the model may echo our annotation format back to us, and
/// the bridge unwraps it so detection sees the raw SAL.
fn strip_sal_wrapper(message: &str) -> String {
    let trimmed = message.trim();
    let bytes = trimmed.as_bytes();
    if bytes.len() < 7 {
        return message.to_string();
    }
    if !trimmed.starts_with("[SAL:") {
        return message.to_string();
    }
    if !trimmed.ends_with(']') {
        return message.to_string();
    }
    // Find first content char after "[SAL:" and any whitespace.
    let inner_start = 5;
    let inner_end = trimmed.len() - 1;
    let inner = trimmed[inner_start..inner_end].trim();
    inner.to_string()
}
