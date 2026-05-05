//! Core OSMP types: decoded instructions, fragments, flags.
//!
//! Cross-SDK byte-identical layout with Python, Go, TypeScript.

use std::collections::BTreeMap;

/// A SAL instruction decoded from wire to its semantic components.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct DecodedInstruction {
    /// Single- or multi-character namespace prefix (e.g. "H", "AGT").
    pub namespace: String,
    /// Opcode identifier (e.g. "HR", "ICD").
    pub opcode: String,
    /// Definition pulled from the ASD for this (namespace, opcode), if any.
    pub opcode_meaning: Option<String>,
    /// Optional `@target` segment (node id, broadcast `*`, or query string).
    pub target: Option<String>,
    /// Optional `?` query slot (e.g. `H:HR?TREND`).
    pub query_slot: Option<String>,
    /// Bracketed slot values, e.g. `H:ICD[J93.0]` -> {"_default" -> "J93.0"}.
    pub slots: BTreeMap<String, String>,
    /// Consequence class glyph if present (`⚠`, `↺`, `⊘`).
    pub consequence_class: Option<String>,
    /// Human-readable consequence class name.
    pub consequence_class_name: Option<String>,
    /// The original wire-format string this was decoded from.
    pub raw: String,
}

/// A wire fragment in the OSMP overflow protocol.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fragment {
    /// Truncated message identifier.
    pub msg_id: u32,
    /// 0-based fragment index within the message.
    pub frag_idx: u16,
    /// Total fragment count for the message.
    pub frag_ct: u16,
    /// Bitfield of flags (see FLAG_* constants).
    pub flags: u8,
    /// Index of the parent fragment this depends on (for DAG ordering).
    pub dep: u16,
    /// Raw payload bytes.
    pub payload: Vec<u8>,
}

/// Fragment is terminal in its dependency chain.
pub const FLAG_TERMINAL: u8 = 0b0000_0001;
/// Fragment carries critical (don't drop) data.
pub const FLAG_CRITICAL: u8 = 0b0000_0010;
/// Fragment uses extended dependency bitmap (multi-parent DAG node).
pub const FLAG_EXTENDED_DEP: u8 = 0b0000_1000;
/// Fragment is NL passthrough (BAEL Mode NL_PASSTHROUGH).
pub const FLAG_NL_PASSTHROUGH: u8 = 0x04;

/// Fixed wire header bytes per fragment.
pub const FRAGMENT_HEADER_BYTES: usize = 6;
/// LoRa floor MTU (51 payload bytes minimum across the LoRa platform set).
pub const LORA_FLOOR_BYTES: usize = 51;
/// LoRa large-MTU profile (255 bytes).
pub const LORA_STANDARD_BYTES: usize = 255;
