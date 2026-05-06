// License: Apache-2.0
//! OSMP — Octid Semantic Mesh Protocol.
//!
//! Bandwidth-agnostic semantic instruction encoding. Every instruction
//! decodes to a (namespace, opcode, target, slots, consequence_class)
//! tuple via a shared adaptive dictionary; no inference required.
//!
//! Cross-SDK byte-identical with the Python, Go, and TypeScript SDKs.

#![warn(rust_2018_idioms)]
#![warn(missing_docs)]

pub mod adp;
pub mod asd;
pub mod asd_v16;
pub mod bael;
pub mod benchmark;
pub mod bridge;
pub mod dag;
pub mod decoder;
pub mod dpack;
pub mod eml;
pub mod encoder;
pub mod fnp;
pub mod glyphs;
pub mod macros;
pub mod overflow;
pub mod sal_composer;
pub mod sal_patterns;
pub mod types;
pub mod validate;
pub mod wire;

pub use adp::{
    acknowledge_def, acknowledge_hash, acknowledge_version, asd_version_is_breaking,
    asd_version_pack, asd_version_parse, asd_version_str, asd_version_unpack,
    classify_priority, mdr_identity, mdr_request, ADPDelta, ADPDeltaOp, ADPSession,
    PendingInstruction, ADP_PRIORITY_DELTA, ADP_PRIORITY_MICRO, ADP_PRIORITY_MISSION,
    ADP_PRIORITY_TRICKLE,
};
pub use asd::{
    AdaptiveSharedDictionary, DeltaLogEntry, DictUpdateMode, ASD_FLOOR_VERSION,
};
pub use asd_v16::{
    asd_basis_v16, asd_v15_to_v16, bridge_split_disambiguation, disambiguate_to_v16,
    ASD_BASIS_V16, ASD_V15_TO_V16, BRIDGE_SPLIT_DISAMBIGUATION,
};
pub use bael::{BAELEncoder, BAELMode, BAELResult};
pub use benchmark::{run_benchmark, BenchmarkReport, VectorResult};
pub use bridge::{
    AcquisitionMetrics, BridgeEvent, BridgeInbound, SALBridge,
    DEFAULT_ACQUISITION_THRESHOLD, DEFAULT_REGRESSION_THRESHOLD,
};
pub use dag::{DAGFragmenter, DAGNode, DAGReassembler};
pub use dpack::{DPackDecoder, DPackEncoder};
pub use macros::{MacroRegistry, MacroTemplate};
pub use decoder::{split_compound, DecodeError, Decoder};
pub use eml::{
    corpus_fingerprint_envelope_bounded as eml_corpus_fingerprint_envelope_bounded,
    corpus_fingerprint_mdr as eml_corpus_fingerprint_mdr, decode_chain_restricted,
    decode_chain_wide, encode_chain_restricted, encode_chain_wide, eml, eml_precise,
    in_bit_exact_corpus as eml_in_bit_exact_corpus, macro_count as eml_macro_count,
    mdr_lookup as eml_mdr_lookup, Chain, ChainLevel, ChainVariant, EmlError, EnvelopeBound,
    FingerprintMembership, FunctionClass, MacroDefinition, ParametricChain, PrecisionClass,
    VariantTag, CANONICAL_INPUTS_MDR as EML_CANONICAL_INPUTS_MDR, REGISTRY as EML_REGISTRY,
};
pub use encoder::{EncodeError, Encoder};
pub use fnp::{
    fnp_cap_bytes, DegradationEvent, FNPSession, FNPSessionOptions, FNPState, FnpError,
    FNP_ADV_EXT_FLAG, FNP_CAP_BLE, FNP_CAP_FLOOR, FNP_CAP_STANDARD, FNP_CAP_UNCONSTRAINED,
    FNP_MATCH_BASIS_EXT_VS_BASE, FNP_MATCH_BASIS_MISMATCH, FNP_MATCH_EXACT,
    FNP_MATCH_FINGERPRINT, FNP_MATCH_VERSION, FNP_MSG_ACK, FNP_MSG_ADV, FNP_MSG_ADV_EXTENDED,
    FNP_MSG_NACK,
};
pub use wire::{
    OSMPWireCodec, SAILCodec, SecCodec, SecEnvelope, SecError, WireError, WireMode,
    SEC_NONCE_SALT, TOK_AND, TOK_END, TOK_FRAME, TOK_NEGINT, TOK_REF, TOK_THEN, TOK_VARINT,
};
pub use overflow::{unpack_fragment, LossPolicy, OverflowProtocol};
pub use glyphs::{
    asd_basis, compound_operators, consequence_classes, glyph_operators,
    GLYPH_AND, GLYPH_BELIEVE, GLYPH_BICOND, GLYPH_EXISTS, GLYPH_FORALL,
    GLYPH_HAZARDOUS, GLYPH_IN, GLYPH_INTERSECT, GLYPH_IRREVERSIBLE,
    GLYPH_JOIN, GLYPH_KNOW, GLYPH_MERGE, GLYPH_NECESS, GLYPH_NOT,
    GLYPH_NOT_IN, GLYPH_OR, GLYPH_PARALLEL, GLYPH_POSS, GLYPH_REVERSIBLE,
    GLYPH_SECTION, GLYPH_SEQ, GLYPH_SUBSET, GLYPH_THEN, GLYPH_UNION,
    GLYPH_XOR,
};
pub use sal_composer::{ComposeResult, SALComposer};
pub use sal_patterns::{
    chain_frame_re, frame_ns_op_re, frame_split_re, ns_target_re,
    prereq_re, sal_frame_re_bridge, NS_PATTERN, OPCODE_PATTERN,
};
pub use types::{
    DecodedInstruction, Fragment, FLAG_CRITICAL, FLAG_EXTENDED_DEP, FLAG_NL_PASSTHROUGH,
    FLAG_TERMINAL, FRAGMENT_HEADER_BYTES, LORA_FLOOR_BYTES, LORA_STANDARD_BYTES,
};
pub use validate::{
    validate_composition, CompositionIssue, CompositionResult, Severity,
};

#[cfg(test)]
mod smoke {
    use super::*;

    #[test]
    fn asd_basis_total_opcode_count() {
        let basis = asd_basis();
        assert_eq!(basis.len(), 26, "v15 floor basis has 26 namespaces");
        let total: usize = basis.values().map(|ops| ops.len()).sum();
        assert_eq!(total, 356, "v15 floor basis has 356 opcodes total");
    }

    #[test]
    fn lookup_health_heart_rate() {
        let asd = AdaptiveSharedDictionary::new();
        assert_eq!(asd.lookup("H", "HR"), Some("heart_rate"));
    }

    #[test]
    fn lookup_unknown_returns_none() {
        let asd = AdaptiveSharedDictionary::new();
        assert_eq!(asd.lookup("H", "DOES_NOT_EXIST"), None);
        assert_eq!(asd.lookup("ZZZ", "HR"), None);
    }

    #[test]
    fn disambiguate_a_ack_to_agt() {
        assert_eq!(disambiguate_to_v16("A", "ACK"), Some("AGT"));
    }

    #[test]
    fn disambiguate_c_alloc_to_cmp() {
        assert_eq!(disambiguate_to_v16("C", "ALLOC"), Some("CMP"));
    }

    #[test]
    fn disambiguate_d_stat_to_xfr() {
        assert_eq!(disambiguate_to_v16("D", "STAT"), Some("XFR"));
    }

    #[test]
    fn disambiguate_q_unmapped_falls_to_qlt() {
        // FLAG is in Q but not in the EVL/GND disambiguation rules.
        assert_eq!(disambiguate_to_v16("Q", "FLAG"), Some("QLT"));
    }

    #[test]
    fn disambiguate_v16_primary_passthrough() {
        assert_eq!(disambiguate_to_v16("AGT", "ACK"), Some("AGT"));
    }

    #[test]
    fn disambiguate_unknown_namespace_returns_none() {
        assert_eq!(disambiguate_to_v16("ZZZ", "XX"), None);
    }

    #[test]
    fn asd_basis_v16_namespace_count() {
        // 32 active namespaces: 20 converged primaries + 9 splits across C/D/K/Q
        // (the Ω sovereign extension is not present because v15 ASD_BASIS does
        // not contain a Ω namespace yet; identical behavior to Python and Go).
        // Cross-SDK byte-identical with Python ASD_BASIS_V16 (len = 32).
        let len = asd_basis_v16().len();
        assert_eq!(len, 32, "asd_basis_v16 namespace count must match Python");
    }

    #[test]
    fn fingerprint_format() {
        let asd = AdaptiveSharedDictionary::new();
        let fp = asd.fingerprint();
        assert_eq!(fp.len(), 16, "fingerprint must be 16 hex characters");
        assert!(
            fp.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()),
            "fingerprint must be lowercase hex: got {fp}",
        );
    }

    #[test]
    fn fingerprint_cross_sdk_identical() {
        // Reference value computed from the Python SDK on the v15 floor basis:
        //     hashlib.sha256(json.dumps(ASD_BASIS, sort_keys=True).encode()).hexdigest()[:16]
        // Cross-SDK byte-identical with Python AdaptiveSharedDictionary.fingerprint(),
        // Go (*AdaptiveSharedDictionary).Fingerprint(), TypeScript .fingerprint().
        let asd = AdaptiveSharedDictionary::new();
        assert_eq!(asd.fingerprint(), "9ecc507e2c24c4a7");
    }

    #[test]
    fn apply_delta_additive() {
        let mut asd = AdaptiveSharedDictionary::new();
        asd.apply_delta("X", "NEWOP", "new_definition", DictUpdateMode::Additive, "v15.1");
        assert_eq!(asd.lookup("X", "NEWOP"), Some("new_definition"));
        // Additive does not overwrite existing.
        asd.apply_delta("X", "NEWOP", "different", DictUpdateMode::Additive, "v15.2");
        assert_eq!(asd.lookup("X", "NEWOP"), Some("new_definition"));
    }

    #[test]
    fn apply_delta_replace_then_deprecate() {
        let mut asd = AdaptiveSharedDictionary::new();
        asd.apply_delta("H", "HR", "replaced_def", DictUpdateMode::Replace, "v15.1");
        assert_eq!(asd.lookup("H", "HR"), Some("replaced_def"));
        asd.apply_delta("H", "HR", "", DictUpdateMode::Deprecate, "v15.2");
        assert_eq!(asd.lookup("H", "HR"), None);
    }

    // ── Decoder ──────────────────────────────────────────────────────────

    #[test]
    fn decode_h_hr_node1_with_target() {
        let dec = Decoder::new(None);
        let d = dec.decode_frame("H:HR@NODE1").expect("decode must succeed");
        assert_eq!(d.namespace, "H");
        assert_eq!(d.opcode, "HR");
        assert_eq!(d.target, Some("NODE1".to_string()));
        assert_eq!(d.opcode_meaning, Some("heart_rate".to_string()));
        assert_eq!(d.consequence_class, None);
    }

    #[test]
    fn decode_h_icd_with_bracket_slot_default_key() {
        // The Python decoder treats "H:ICD[J93.0]" as opcode="ICD[J93.0]".
        // Bracket slots are not parsed by the deterministic frame decoder;
        // they live in the opcode body. Here we round-trip the canonical
        // raw form and confirm the J93.0 substring is preserved verbatim.
        let dec = Decoder::new(None);
        let d = dec.decode_frame("H:ICD[J93.0]").expect("decode must succeed");
        assert_eq!(d.namespace, "H");
        // The opcode body absorbs the bracketed value because '[' is not in
        // the stop set — this matches Python / Go / TypeScript behavior.
        assert!(d.opcode.starts_with("ICD"));
        assert!(d.raw.contains("J93.0"));
    }

    #[test]
    fn decode_r_mov_bot1_reversible() {
        let dec = Decoder::new(None);
        let d = dec
            .decode_frame("R:MOV@BOT1\u{21BA}")
            .expect("decode must succeed");
        assert_eq!(d.namespace, "R");
        assert_eq!(d.opcode, "MOV");
        assert_eq!(d.target, Some("BOT1".to_string()));
        assert_eq!(d.consequence_class, Some("\u{21BA}".to_string()));
        assert_eq!(d.consequence_class_name, Some("REVERSIBLE".to_string()));
    }

    #[test]
    fn decode_i_section_human_authorization() {
        let dec = Decoder::new(None);
        let d = dec.decode_frame("I:\u{00A7}").expect("decode must succeed");
        assert_eq!(d.namespace, "I");
        assert_eq!(d.opcode, "\u{00A7}");
        assert_eq!(
            d.opcode_meaning,
            Some("human_operator_confirmation".to_string()),
        );
    }

    #[test]
    fn decode_compound_chain_two_frames() {
        let dec = Decoder::new(None);
        let frames = dec.decode_compound("H:HR@NODE1\u{2192}H:CASREP");
        assert_eq!(frames.len(), 2);
        assert_eq!(frames[0].namespace, "H");
        assert_eq!(frames[0].opcode, "HR");
        assert_eq!(frames[1].namespace, "H");
        assert_eq!(frames[1].opcode, "CASREP");
    }

    #[test]
    fn decode_compound_full_canonical_chain() {
        // "H:HR@NODE1>120→H:CASREP∧M:EVA@*" — the canonical multi-namespace
        // example. Note the '>120' inline condition rides on the target body.
        let dec = Decoder::new(None);
        let frames = dec
            .decode_compound("H:HR@NODE1>120\u{2192}H:CASREP\u{2227}M:EVA@*");
        assert_eq!(frames.len(), 3);
        assert_eq!(frames[0].namespace, "H");
        assert_eq!(frames[0].opcode, "HR");
        // The decoder preserves '>120' as part of the target string —
        // condition stripping is a layer above the deterministic decoder.
        assert!(frames[0].target.as_deref().unwrap_or("").contains("NODE1"));
        assert_eq!(frames[2].namespace, "M");
        assert_eq!(frames[2].opcode, "EVA");
        assert_eq!(frames[2].target, Some("*".to_string()));
    }

    // ── Encoder ──────────────────────────────────────────────────────────

    #[test]
    fn encode_h_hr_with_target() {
        let enc = Encoder::new(None);
        let s = enc
            .encode("H", "HR", Some("NODE1"), None, None, None)
            .expect("encode must succeed");
        assert_eq!(s, "H:HR@NODE1");
    }

    #[test]
    fn encode_r_mov_requires_consequence_class() {
        let enc = Encoder::new(None);
        let err = enc
            .encode("R", "MOV", Some("BOT1"), None, None, None)
            .unwrap_err();
        match err {
            EncodeError::MissingConsequenceClass(_) => {}
            other => panic!("wrong error variant: {other:?}"),
        }
        let s = enc
            .encode("R", "MOV", Some("BOT1"), None, None, Some("\u{21BA}"))
            .expect("encode with cc must succeed");
        assert_eq!(s, "R:MOV@BOT1\u{21BA}");
    }

    #[test]
    fn encode_compound_chain_with_then_glyph() {
        let enc = Encoder::new(None);
        let s = enc
            .encode_compound("H:HR@NODE1", "\u{2192}", "H:CASREP")
            .expect("encode_compound must succeed");
        assert_eq!(s, "H:HR@NODE1\u{2192}H:CASREP");
    }

    #[test]
    fn encode_broadcast_format() {
        let enc = Encoder::new(None);
        assert_eq!(enc.encode_broadcast("M", "EVA"), "M:EVA@*");
    }

    // ── Round-trip ───────────────────────────────────────────────────────

    #[test]
    fn round_trip_h_hr_target() {
        let dec = Decoder::new(None);
        let enc = Encoder::new(None);
        let original = "H:HR@NODE1";
        let d = dec.decode_frame(original).expect("decode must succeed");
        let s = enc
            .encode(
                &d.namespace,
                &d.opcode,
                d.target.as_deref(),
                d.query_slot.as_deref(),
                Some(&d.slots),
                d.consequence_class.as_deref(),
            )
            .expect("encode must succeed");
        assert_eq!(s, original);
    }

    #[test]
    fn round_trip_r_mov_reversible() {
        let dec = Decoder::new(None);
        let enc = Encoder::new(None);
        let original = "R:MOV@BOT1\u{21BA}";
        let d = dec.decode_frame(original).expect("decode must succeed");
        let s = enc
            .encode(
                &d.namespace,
                &d.opcode,
                d.target.as_deref(),
                d.query_slot.as_deref(),
                Some(&d.slots),
                d.consequence_class.as_deref(),
            )
            .expect("encode must succeed");
        assert_eq!(s, original);
    }

    #[test]
    fn round_trip_i_section() {
        let dec = Decoder::new(None);
        let enc = Encoder::new(None);
        let original = "I:\u{00A7}";
        let d = dec.decode_frame(original).expect("decode must succeed");
        let s = enc
            .encode(
                &d.namespace,
                &d.opcode,
                d.target.as_deref(),
                d.query_slot.as_deref(),
                Some(&d.slots),
                d.consequence_class.as_deref(),
            )
            .expect("encode must succeed");
        assert_eq!(s, original);
    }

    // ── Glyph tables ─────────────────────────────────────────────────────

    #[test]
    fn glyph_operators_contains_canonical_set() {
        let ops = glyph_operators();
        assert_eq!(ops.get("\u{2227}"), Some(&"AND"));
        assert_eq!(ops.get("\u{2192}"), Some(&"THEN"));
        assert_eq!(ops.get("\u{2225}"), Some(&"PARALLEL"));
        assert_eq!(ops.get("\u{2295}"), Some(&"PRIORITY-ORDER"));
    }

    #[test]
    fn consequence_classes_table_complete() {
        let cc = consequence_classes();
        assert_eq!(cc.len(), 3);
        assert_eq!(cc.get("\u{26A0}"), Some(&"HAZARDOUS"));
        assert_eq!(cc.get("\u{21BA}"), Some(&"REVERSIBLE"));
        assert_eq!(cc.get("\u{2298}"), Some(&"IRREVERSIBLE"));
    }

    #[test]
    fn compound_operators_unless_only() {
        let co = compound_operators();
        assert_eq!(co.len(), 1);
        assert_eq!(co.get("\u{00AC}\u{2192}"), Some(&"UNLESS"));
    }

    // ── Regex patterns ───────────────────────────────────────────────────

    #[test]
    fn sal_frame_re_bridge_matches_basic_frame() {
        let re = sal_frame_re_bridge();
        let m = re.find("see H:HR for status").expect("must match");
        assert_eq!(m.as_str(), "H:HR");
    }

    #[test]
    fn frame_ns_op_re_extracts_namespace_and_opcode() {
        let re = frame_ns_op_re();
        let caps = re.captures("H:HR@NODE1").expect("must capture");
        assert_eq!(&caps[1], "H");
        assert_eq!(&caps[2], "HR");
    }

    #[test]
    fn frame_ns_op_re_handles_section_opcode() {
        let re = frame_ns_op_re();
        let caps = re.captures("I:\u{00A7}").expect("must capture I:§");
        assert_eq!(&caps[1], "I");
        assert_eq!(&caps[2], "\u{00A7}");
    }

    #[test]
    fn split_compound_recognizes_arrow_glyph() {
        let parts = split_compound("H:HR@NODE1\u{2192}H:CASREP");
        assert_eq!(parts, vec!["H:HR@NODE1".to_string(), "H:CASREP".to_string()]);
    }

    #[test]
    fn split_compound_recognizes_ascii_arrow_shorthand() {
        let parts = split_compound("H:HR@NODE1->H:CASREP");
        assert_eq!(parts, vec!["H:HR@NODE1".to_string(), "H:CASREP".to_string()]);
    }

    // ── FNP ──────────────────────────────────────────────────────────────

    #[test]
    fn fnp_new_session_starts_in_initial_state() {
        let asd = AdaptiveSharedDictionary::new();
        let session = FNPSession::new(&asd, "NODE_A", 1, FNP_CAP_UNCONSTRAINED);
        assert_eq!(session.state, FNPState::Idle);
        assert_eq!(session.local_node_id, "NODE_A");
        assert_eq!(session.remote_node_id, "");
        assert_eq!(session.match_status, -1);
        assert_eq!(session.negotiated_capacity, -1);
    }

    #[test]
    fn fnp_fallback_transitions_to_fallback_state() {
        let asd = AdaptiveSharedDictionary::new();
        let mut session = FNPSession::new(&asd, "NODE_A", 1, FNP_CAP_UNCONSTRAINED);
        session.fallback("PEER_X");
        assert_eq!(session.state, FNPState::Fallback);
        assert_eq!(session.remote_node_id, "PEER_X");
    }

    #[test]
    fn fnp_acquire_only_from_fallback() {
        let asd = AdaptiveSharedDictionary::new();
        let mut session = FNPSession::new(&asd, "NODE_A", 1, FNP_CAP_UNCONSTRAINED);
        // Cannot acquire from Initial.
        session.acquire();
        assert_eq!(session.state, FNPState::Idle);
        // Fallback -> Acquired.
        session.fallback("PEER_X");
        session.acquire();
        assert_eq!(session.state, FNPState::Acquired);
        assert!(session.is_acquired());
    }

    #[test]
    fn fnp_regress_only_from_acquired() {
        let asd = AdaptiveSharedDictionary::new();
        let mut session = FNPSession::new(&asd, "NODE_A", 1, FNP_CAP_UNCONSTRAINED);
        session.fallback("PEER_X");
        session.acquire();
        session.regress();
        assert_eq!(session.state, FNPState::Fallback);
    }

    #[test]
    fn fnp_capabilities_field_populated() {
        let asd = AdaptiveSharedDictionary::new();
        let session = FNPSession::new(&asd, "NODE_A", 1, FNP_CAP_UNCONSTRAINED);
        assert_ne!(session.capabilities, 0);
        assert_eq!(
            session.capabilities & ((1u32 << 26) - 1),
            (1u32 << 26) - 1,
            "all 26 single-letter namespace bits should be set",
        );
    }

    // ── Bridge: registration / state ─────────────────────────────────────

    #[test]
    fn bridge_register_peer_no_fnp_enters_fallback() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        let state = bridge.register_peer("GPT_AGENT_1", false);
        assert_eq!(state, FNPState::Fallback);
        assert_eq!(bridge.peer_state("GPT_AGENT_1"), Some(FNPState::Fallback));
    }

    #[test]
    fn bridge_register_peer_with_fnp_starts_initial() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        let state = bridge.register_peer("GPT_AGENT_2", true);
        assert_eq!(state, FNPState::Idle);
        assert_eq!(bridge.peer_state("GPT_AGENT_2"), Some(FNPState::Idle));
    }

    #[test]
    fn bridge_peer_state_unregistered_is_none() {
        let bridge = SALBridge::new("NODE_LOCAL", None, true);
        assert_eq!(bridge.peer_state("UNKNOWN_PEER"), None);
    }

    // ── Bridge: send paths ───────────────────────────────────────────────

    #[test]
    fn bridge_send_to_acquired_peer_returns_sal_unchanged() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        for _ in 0..DEFAULT_ACQUISITION_THRESHOLD {
            bridge.receive("H:HR@NODE1", "GPT_AGENT_1");
        }
        assert_eq!(
            bridge.peer_state("GPT_AGENT_1"),
            Some(FNPState::Acquired),
        );
        let out = bridge.send("H:HR@NODE1;A:ACK", "GPT_AGENT_1");
        assert_eq!(out, "H:HR@NODE1;A:ACK");
    }

    #[test]
    fn bridge_send_to_fallback_with_annotate_returns_annotated_form() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        let out = bridge.send("H:HR@NODE1", "GPT_AGENT_1");
        assert!(
            out.contains("[SAL: H:HR@NODE1]"),
            "annotated outbound must contain [SAL: ...] tag, got: {out}",
        );
        assert!(
            out.contains("heart_rate"),
            "annotated outbound must contain decoded NL, got: {out}",
        );
    }

    #[test]
    fn bridge_send_to_fallback_without_annotate_returns_nl_only() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, false);
        bridge.register_peer("GPT_AGENT_1", false);
        let out = bridge.send("H:HR@NODE1", "GPT_AGENT_1");
        assert!(
            !out.contains("[SAL:"),
            "non-annotated must not contain wrapper",
        );
        assert!(out.contains("heart_rate"));
    }

    #[test]
    fn bridge_send_unknown_peer_auto_registers_as_fallback() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        let _out = bridge.send("H:HR", "BRAND_NEW_PEER");
        assert_eq!(
            bridge.peer_state("BRAND_NEW_PEER"),
            Some(FNPState::Fallback),
        );
    }

    // ── Bridge: receive / acquisition ────────────────────────────────────

    #[test]
    fn bridge_receive_sal_frame_increments_metrics() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        bridge.receive("H:HR@NODE1", "GPT_AGENT_1");
        let m = bridge.metrics("GPT_AGENT_1").expect("peer must have metrics");
        assert_eq!(m.total_messages, 1);
        assert_eq!(m.messages_with_sal, 1);
        assert_eq!(m.consecutive_sal_hits, 1);
        assert_eq!(m.consecutive_sal_misses, 0);
        assert_eq!(m.valid_frames_seen, 1);
        assert!(m.unique_opcodes_seen.contains("H:HR"));
    }

    #[test]
    fn bridge_receive_threshold_transitions_to_acquired() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        for _ in 0..(DEFAULT_ACQUISITION_THRESHOLD - 1) {
            bridge.receive("H:HR@NODE1", "GPT_AGENT_1");
        }
        assert_eq!(bridge.peer_state("GPT_AGENT_1"), Some(FNPState::Fallback));
        bridge.receive("A:ACK", "GPT_AGENT_1");
        assert_eq!(bridge.peer_state("GPT_AGENT_1"), Some(FNPState::Acquired));
    }

    #[test]
    fn bridge_receive_nl_only_records_miss() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        let inbound = bridge.receive(
            "no codes in this message at all just words",
            "GPT_AGENT_1",
        );
        assert!(inbound.passthrough);
        assert_eq!(inbound.sal, None);
        assert!(inbound.nl.is_some());
        let m = bridge.metrics("GPT_AGENT_1").expect("metrics present");
        assert_eq!(m.consecutive_sal_misses, 1);
        assert_eq!(m.consecutive_sal_hits, 0);
    }

    #[test]
    fn bridge_receive_acquired_regresses_after_threshold_misses() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        for _ in 0..DEFAULT_ACQUISITION_THRESHOLD {
            bridge.receive("H:HR@NODE1", "GPT_AGENT_1");
        }
        assert_eq!(bridge.peer_state("GPT_AGENT_1"), Some(FNPState::Acquired));
        for _ in 0..DEFAULT_REGRESSION_THRESHOLD {
            bridge.receive("plain words no sal here", "GPT_AGENT_1");
        }
        assert_eq!(bridge.peer_state("GPT_AGENT_1"), Some(FNPState::Fallback));
    }

    #[test]
    fn bridge_receive_pure_sal_returns_sal_field() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        let inbound = bridge.receive("H:HR@NODE1;A:ACK", "GPT_AGENT_1");
        assert!(inbound.sal.is_some(), "pure SAL must populate .sal");
        assert!(!inbound.passthrough);
    }

    #[test]
    fn bridge_receive_mixed_content_marks_passthrough() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        let inbound = bridge.receive(
            "Authorize via I:\u{00A7} before proceeding",
            "GPT_AGENT_1",
        );
        assert!(inbound.passthrough);
        assert!(inbound.sal.is_none());
        assert!(inbound.nl.is_some());
    }

    #[test]
    fn bridge_log_records_events() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("GPT_AGENT_1", false);
        let log = bridge.log();
        assert!(
            log.iter().any(|e| e.event_type == "fallback"),
            "register_peer with attempt_fnp=false must emit fallback event",
        );
        bridge.send("H:HR", "GPT_AGENT_1");
        let log = bridge.log();
        assert!(
            log.iter().any(|e| e.event_type == "annotate"),
            "send to fallback peer with annotate=true must emit annotate event",
        );
    }

    #[test]
    fn bridge_attach_macro_registry_stores_handle() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        assert!(bridge.macro_registry().is_none());
        let reg = MacroRegistry::new(None);
        bridge.attach_macro_registry(reg);
        assert!(bridge.macro_registry().is_some());
    }

    #[test]
    fn bridge_thresholds_match_cross_sdk_constants() {
        assert_eq!(DEFAULT_ACQUISITION_THRESHOLD, 5);
        assert_eq!(DEFAULT_REGRESSION_THRESHOLD, 3);
    }

    #[test]
    fn bridge_acquisition_score_caps_at_one() {
        let mut bridge = SALBridge::new("NODE_LOCAL", None, true);
        bridge.register_peer("PEER", false);
        for _ in 0..(DEFAULT_ACQUISITION_THRESHOLD * 2) {
            bridge.receive("H:HR", "PEER");
        }
        let m = bridge.metrics("PEER").expect("metrics present");
        let score = m.acquisition_score(DEFAULT_ACQUISITION_THRESHOLD);
        assert!(
            (score - 1.0).abs() < 1e-9,
            "acquisition_score must cap at 1.0, got {score}",
        );
    }

    // ── FNP packet codec ─────────────────────────────────────────────────

    #[test]
    fn fnp_initiate_produces_40_byte_adv() {
        let asd = AdaptiveSharedDictionary::new();
        let mut session = FNPSession::new_with_version(&asd, "NODE_A", 1, FNP_CAP_FLOOR);
        let adv = session.initiate().expect("initiate must succeed");
        assert_eq!(adv.len(), 40, "FNP ADV packet must be 40 bytes");
        assert_eq!(adv[0], FNP_MSG_ADV, "first byte must be FNP_MSG_ADV");
        assert_eq!(session.state, FNPState::AdvSent);
    }

    #[test]
    fn fnp_initiate_only_from_idle() {
        let asd = AdaptiveSharedDictionary::new();
        let mut session = FNPSession::new_with_version(&asd, "NODE_A", 1, FNP_CAP_FLOOR);
        session.fallback("PEER");
        let result = session.initiate();
        assert!(matches!(result, Err(FnpError::InvalidState(_))));
    }

    #[test]
    fn fnp_handshake_round_trip_idle_to_established_sail() {
        // Two sessions with identical ASD basis should reach EstablishedSAIL on
        // exact match. ADV: A -> B, ACK: B -> A.
        let asd = AdaptiveSharedDictionary::new();
        let mut a = FNPSession::new_with_version(&asd, "NODE_A", 1, FNP_CAP_FLOOR);
        let mut b = FNPSession::new_with_version(&asd, "NODE_B", 1, FNP_CAP_FLOOR);
        let adv = a.initiate().expect("A initiates");
        let ack = b
            .receive(&adv)
            .expect("B receives ADV")
            .expect("B returns ACK bytes");
        assert_eq!(ack.len(), 38, "FNP ACK packet must be 38 bytes");
        assert_eq!(ack[0], FNP_MSG_ACK, "ACK msg_type on exact match");
        assert_eq!(b.state, FNPState::EstablishedSAIL);
        let _ = a.receive(&ack).expect("A receives ACK");
        assert_eq!(a.state, FNPState::EstablishedSAIL);
        assert_eq!(a.match_status, FNP_MATCH_EXACT);
        assert_eq!(b.match_status, FNP_MATCH_EXACT);
    }

    #[test]
    fn fnp_extended_form_sets_high_bit_and_carries_basis_fp() {
        let asd = AdaptiveSharedDictionary::new();
        let opts = FNPSessionOptions {
            basis_fingerprint: Some(vec![0xAA; 8]),
            ..Default::default()
        };
        let mut session =
            FNPSession::new_with_options(&asd, "NODE_A", 1, FNP_CAP_FLOOR, opts).unwrap();
        let adv = session.initiate().expect("initiate");
        assert_eq!(adv.len(), 40);
        assert_eq!(adv[0], FNP_MSG_ADV_EXTENDED);
        assert_eq!(adv[0] & FNP_ADV_EXT_FLAG, FNP_ADV_EXT_FLAG);
        assert_eq!(&adv[32..40], &[0xAA; 8]);
        assert!(session.is_extended_form());
    }

    #[test]
    fn fnp_basis_fingerprint_must_be_eight_bytes() {
        let asd = AdaptiveSharedDictionary::new();
        let opts = FNPSessionOptions {
            basis_fingerprint: Some(vec![0xAA; 7]),
            ..Default::default()
        };
        let result = FNPSession::new_with_options(&asd, "NODE_A", 1, FNP_CAP_FLOOR, opts);
        assert_eq!(result.err(), Some(FnpError::InvalidBasisFingerprint));
    }

    #[test]
    fn fnp_echo_mismatch_rejected() {
        // Forge an ACK with a tampered echo fingerprint; receive must reject.
        let asd = AdaptiveSharedDictionary::new();
        let mut a = FNPSession::new_with_version(&asd, "NODE_A", 1, FNP_CAP_FLOOR);
        let _ = a.initiate().expect("initiate");
        let mut bad_ack = vec![0u8; 38];
        bad_ack[0] = FNP_MSG_ACK;
        bad_ack[1] = FNP_MATCH_EXACT as u8;
        // Wrong echo fingerprint at offset [2..10]:
        for byte in &mut bad_ack[2..10] {
            *byte = 0xFF;
        }
        let result = a.receive(&bad_ack);
        assert_eq!(result.err(), Some(FnpError::EchoMismatch));
    }

    #[test]
    fn fnp_timeout_resets_to_idle() {
        let asd = AdaptiveSharedDictionary::new();
        let mut session = FNPSession::new_with_version(&asd, "NODE_A", 1, FNP_CAP_FLOOR);
        let _ = session.initiate().expect("initiate");
        session.timeout();
        assert_eq!(session.state, FNPState::Idle);
        assert_eq!(session.match_status, -1);
    }

    // ── SAIL codec ────────────────────────────────────────────────────────

    #[test]
    fn sail_encode_h_hr_uses_tok_frame() {
        let codec = wire::SAILCodec::new();
        let bytes = codec.encode("H:HR");
        // First byte must be TOK_FRAME, last must be TOK_END.
        assert!(!bytes.is_empty());
        assert_eq!(bytes[0], TOK_FRAME);
        assert_eq!(*bytes.last().unwrap(), TOK_END);
        // ns_index for H = 'H' - 'A' = 7.
        assert_eq!(bytes[1], 7);
    }

    #[test]
    fn sail_encode_decode_roundtrip_h_hr() {
        let codec = wire::SAILCodec::new();
        let original = "H:HR";
        let bytes = codec.encode(original);
        let decoded = codec.decode(&bytes);
        assert_eq!(decoded, original);
    }

    #[test]
    fn sail_encode_compound_chain_with_then_glyph() {
        let codec = wire::SAILCodec::new();
        let original = "H:HR\u{2192}H:CASREP";
        let bytes = codec.encode(original);
        // Find the THEN glyph token in the bytes.
        assert!(bytes.contains(&TOK_THEN));
        let decoded = codec.decode(&bytes);
        assert_eq!(decoded, original);
    }

    #[test]
    fn sail_encode_numeric_uses_varint() {
        let codec = wire::SAILCodec::new();
        let bytes = codec.encode("H:HR@NODE1");
        // Must contain TOK_FRAME for H:HR.
        assert!(bytes.contains(&TOK_FRAME));
    }

    // ── SEC codec ─────────────────────────────────────────────────────────

    #[test]
    fn sec_pack_unpack_roundtrip_self_verify() {
        let seed = [0x11u8; 32];
        let sym = [0x22u8; 32];
        let mut codec =
            wire::SecCodec::new(&[0x00, 0x01], Some(&seed), Some(&sym)).expect("construct");
        let payload = b"H:HR@NODE1\xe2\x86\xbaH:CASREP";
        let envelope = codec.pack(payload, WireMode::SEC).expect("pack");
        // Overhead: 87 bytes for 2-byte node_id (1 mode + 2 nid + 4 seq + payload + 16 tag + 64 sig).
        assert_eq!(envelope.len(), payload.len() + 87);
        let unpacked = codec.unpack(&envelope).expect("unpack");
        assert_eq!(unpacked.payload, payload);
        assert_eq!(unpacked.mode, WireMode::SEC);
        assert_eq!(unpacked.node_id, vec![0x00, 0x01]);
        assert_eq!(unpacked.seq_counter, 1);
    }

    #[test]
    fn sec_pack_unpack_4byte_node_id() {
        let seed = [0x33u8; 32];
        let sym = [0x44u8; 32];
        let mut codec = wire::SecCodec::new(&[0xDE, 0xAD, 0xBE, 0xEF], Some(&seed), Some(&sym))
            .expect("construct");
        let payload = b"hello";
        let envelope = codec.pack(payload, WireMode::SAILSEC).expect("pack");
        // Overhead: 89 bytes for 4-byte node_id.
        assert_eq!(envelope.len(), payload.len() + 89);
        let unpacked = codec.unpack(&envelope).expect("unpack");
        assert_eq!(unpacked.node_id, vec![0xDE, 0xAD, 0xBE, 0xEF]);
        assert_eq!(unpacked.mode, WireMode::SAILSEC);
    }

    #[test]
    fn sec_seq_counter_monotonic() {
        let seed = [0x55u8; 32];
        let sym = [0x66u8; 32];
        let mut codec =
            wire::SecCodec::new(&[0x00, 0x02], Some(&seed), Some(&sym)).expect("construct");
        let e1 = codec.pack(b"first", WireMode::SEC).unwrap();
        let e2 = codec.pack(b"second", WireMode::SEC).unwrap();
        let u1 = codec.unpack(&e1).unwrap();
        let u2 = codec.unpack(&e2).unwrap();
        assert_eq!(u1.seq_counter, 1);
        assert_eq!(u2.seq_counter, 2);
    }

    #[test]
    fn sec_invalid_node_id_rejected() {
        let result = wire::SecCodec::new(&[0x00], None, None);
        assert_eq!(result.err(), Some(SecError::InvalidNodeId));
    }

    #[test]
    fn sec_tampered_signature_rejected() {
        let seed = [0x77u8; 32];
        let sym = [0x88u8; 32];
        let mut codec =
            wire::SecCodec::new(&[0x00, 0x03], Some(&seed), Some(&sym)).expect("construct");
        let mut envelope = codec.pack(b"payload", WireMode::SEC).unwrap();
        // Flip the last byte (within the signature region).
        let last = envelope.len() - 1;
        envelope[last] ^= 0x01;
        let result = codec.unpack(&envelope);
        assert!(matches!(
            result,
            Err(SecError::SignatureFailure) | Err(SecError::AuthFailure)
        ));
    }

    #[test]
    fn sec_nonce_salt_canonical_value() {
        assert_eq!(SEC_NONCE_SALT, b"OSMP-SEC-v1\x00");
    }

    #[test]
    fn sec_replay_attempt_rejected() {
        // Pack one envelope, unpack it once (succeeds), unpack again
        // (rejected as replay).
        let seed = [0xCDu8; 32];
        let sym = [0xCEu8; 32];
        let mut codec =
            wire::SecCodec::new(&[0x00, 0x10], Some(&seed), Some(&sym)).expect("construct");
        let envelope = codec.pack(b"alpha", WireMode::SEC).expect("pack");
        let _ = codec.unpack(&envelope).expect("first unpack succeeds");
        let result = codec.unpack(&envelope);
        match result {
            Err(SecError::ReplayDetected {
                seq_counter,
                last_accepted,
                ..
            }) => {
                assert_eq!(seq_counter, 1);
                assert_eq!(last_accepted, 1);
            }
            other => panic!("expected ReplayDetected, got {other:?}"),
        }
    }

    #[test]
    fn sec_out_of_order_sequence_rejected() {
        // Pack two envelopes (seq=1 then seq=2), unpack the LATER one first.
        // The earlier one is then rejected because its seq is below the
        // newly recorded high-water mark.
        let seed = [0xDEu8; 32];
        let sym = [0xDFu8; 32];
        let mut codec =
            wire::SecCodec::new(&[0x00, 0x11], Some(&seed), Some(&sym)).expect("construct");
        let e1 = codec.pack(b"first", WireMode::SEC).expect("pack 1");
        let e2 = codec.pack(b"second", WireMode::SEC).expect("pack 2");
        let u2 = codec.unpack(&e2).expect("unpack newer first");
        assert_eq!(u2.seq_counter, 2);
        let result = codec.unpack(&e1);
        match result {
            Err(SecError::ReplayDetected {
                seq_counter,
                last_accepted,
                ..
            }) => {
                assert_eq!(seq_counter, 1);
                assert_eq!(last_accepted, 2);
            }
            other => panic!("expected ReplayDetected, got {other:?}"),
        }
    }

    #[test]
    fn sec_replay_per_sender_independent() {
        // The seen-sequence map is keyed by sender node_id. An envelope from
        // a sender with node_id A and seq=1 must NOT poison the replay
        // window for a different sender B with seq=1.
        //
        // This test simulates that by constructing two codecs (different
        // node_ids) with the SAME symmetric and signing keys, packing one
        // envelope from each, and verifying the third codec accepts both.
        let sym = [0xEAu8; 32];
        let seed = [0xEBu8; 32];
        let mut sender_a =
            wire::SecCodec::new(&[0xAA, 0xAA], Some(&seed), Some(&sym)).expect("A");
        let mut sender_b =
            wire::SecCodec::new(&[0xBB, 0xBB], Some(&seed), Some(&sym)).expect("B");
        let mut receiver =
            wire::SecCodec::new(&[0xCC, 0xCC], Some(&seed), Some(&sym)).expect("R");

        let env_a = sender_a.pack(b"from-a", WireMode::SEC).unwrap();
        let env_b = sender_b.pack(b"from-b", WireMode::SEC).unwrap();
        // Both envelopes carry seq=1 but different node_ids.
        let r_a = receiver.unpack(&env_a).expect("receive A");
        assert_eq!(r_a.node_id, vec![0xAA, 0xAA]);
        assert_eq!(r_a.seq_counter, 1);
        let r_b = receiver.unpack(&env_b).expect("receive B");
        assert_eq!(r_b.node_id, vec![0xBB, 0xBB]);
        assert_eq!(r_b.seq_counter, 1);
    }

    #[test]
    fn sec_reset_seen_seq_clears_replay_state() {
        // reset_seen_seq is for tests / fresh-session restarts. After reset
        // a previously-seen envelope is accepted again.
        let seed = [0xFAu8; 32];
        let sym = [0xFBu8; 32];
        let mut codec =
            wire::SecCodec::new(&[0x00, 0x12], Some(&seed), Some(&sym)).expect("construct");
        let envelope = codec.pack(b"hello", WireMode::SEC).expect("pack");
        let _ = codec.unpack(&envelope).expect("first unpack");
        assert!(matches!(
            codec.unpack(&envelope),
            Err(SecError::ReplayDetected { .. })
        ));
        codec.reset_seen_seq();
        let _ = codec.unpack(&envelope).expect("after reset, accepted again");
    }

    // ── Unified wire codec ────────────────────────────────────────────────

    #[test]
    fn wire_mode_byte_values_match_spec() {
        assert_eq!(WireMode::Mnemonic as u8, 0x00);
        assert_eq!(WireMode::SAIL as u8, 0x01);
        assert_eq!(WireMode::SEC as u8, 0x02);
        assert_eq!(WireMode::SAILSEC as u8, 0x03);
    }

    #[test]
    fn wire_mode_labels() {
        assert_eq!(WireMode::Mnemonic.label(), "OSMP");
        assert_eq!(WireMode::SAIL.label(), "OSMP-SAIL");
        assert_eq!(WireMode::SEC.label(), "OSMP-SEC");
        assert_eq!(WireMode::SAILSEC.label(), "OSMP-SAIL-SEC");
    }

    #[test]
    fn osmp_wire_codec_mnemonic_roundtrip() {
        let mut codec = OSMPWireCodec::new(&[0x00, 0x04], None, None).expect("construct");
        let original = "H:HR@NODE1";
        let bytes = codec.encode(original, WireMode::Mnemonic).unwrap();
        assert_eq!(bytes, original.as_bytes());
        let decoded = codec.decode(&bytes, WireMode::Mnemonic).unwrap();
        assert_eq!(decoded, original);
    }

    #[test]
    fn osmp_wire_codec_sail_roundtrip() {
        let mut codec = OSMPWireCodec::new(&[0x00, 0x05], None, None).expect("construct");
        let original = "H:HR@NODE1\u{2192}H:CASREP";
        let bytes = codec.encode(original, WireMode::SAIL).unwrap();
        // SAIL bytes will be shorter than UTF-8 for the THEN glyph (1 byte token vs 3 bytes UTF-8).
        let decoded = codec.decode(&bytes, WireMode::SAIL).unwrap();
        assert_eq!(decoded, original);
    }

    #[test]
    fn osmp_wire_codec_sec_roundtrip() {
        let seed = [0x99u8; 32];
        let sym = [0xAAu8; 32];
        let mut codec =
            OSMPWireCodec::new(&[0x00, 0x06], Some(&seed), Some(&sym)).expect("construct");
        let original = "H:HR@NODE1";
        let bytes = codec.encode(original, WireMode::SEC).unwrap();
        let decoded = codec.decode(&bytes, WireMode::SEC).unwrap();
        assert_eq!(decoded, original);
    }

    #[test]
    fn osmp_wire_codec_sailsec_roundtrip() {
        let seed = [0xBBu8; 32];
        let sym = [0xCCu8; 32];
        let mut codec =
            OSMPWireCodec::new(&[0x00, 0x07], Some(&seed), Some(&sym)).expect("construct");
        let original = "H:HR@NODE1\u{2192}H:CASREP";
        let bytes = codec.encode(original, WireMode::SAILSEC).unwrap();
        let decoded = codec.decode(&bytes, WireMode::SAILSEC).unwrap();
        assert_eq!(decoded, original);
    }
}
