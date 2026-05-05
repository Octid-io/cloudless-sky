// License: Apache-2.0
//! OSMP Glyph Tables and ASD Basis Set.
//!
//! Cross-SDK byte-identical with Python ASD_BASIS, Go ASDFloorBasis,
//! TypeScript ASD_BASIS. Source: dictionary v15.
//!
//! 26 namespaces, 356 opcodes.

use std::collections::BTreeMap;
use std::sync::OnceLock;

/// ASD basis set version.
pub const ASD_FLOOR_VERSION: &str = "1.0";

// ─────────────────────────────────────────────────────────────────────────────
// CATEGORY 1 — GLYPH OPERATORS (logical / compositional)
// Source: OSMP-semantic-dictionary-v15.csv Section 1, Category 1
// Cross-SDK byte-identical with Python GLYPH_OPERATORS, Go GlyphOperators,
// TypeScript GLYPH_OPERATORS.
// ─────────────────────────────────────────────────────────────────────────────

/// AND — logical conjunction (U+2227).
pub const GLYPH_AND: &str = "\u{2227}";
/// OR — logical disjunction (U+2228).
pub const GLYPH_OR: &str = "\u{2228}";
/// NOT — logical negation (U+00AC).
pub const GLYPH_NOT: &str = "\u{00AC}";
/// THEN — material implication (U+2192).
pub const GLYPH_THEN: &str = "\u{2192}";
/// IFF — biconditional (U+2194).
pub const GLYPH_BICOND: &str = "\u{2194}";
/// XOR / PRIORITY-ORDER (U+2295).
pub const GLYPH_XOR: &str = "\u{2295}";
/// SEQUENCE — strict sequence (`;`).
pub const GLYPH_SEQ: &str = ";";
/// PARALLEL — concurrent execution (U+2225).
pub const GLYPH_PARALLEL: &str = "\u{2225}";
/// MERGE — bowtie / join (U+22C8).
pub const GLYPH_MERGE: &str = "\u{22C8}";
/// JOIN — meet / greatest-lower-bound (U+2293).
pub const GLYPH_JOIN: &str = "\u{2293}";
/// NECESS — modal necessity □ (U+25A1).
pub const GLYPH_NECESS: &str = "\u{25A1}";
/// POSS — modal possibility ◇ (U+25C7).
pub const GLYPH_POSS: &str = "\u{25C7}";
/// KNOW — knowledge modality (U+24DA).
pub const GLYPH_KNOW: &str = "\u{24DA}";
/// BELIEVE — belief modality (U+24D1).
pub const GLYPH_BELIEVE: &str = "\u{24D1}";
/// IN — set membership (U+2208).
pub const GLYPH_IN: &str = "\u{2208}";
/// NOT_IN — set non-membership (U+2209).
pub const GLYPH_NOT_IN: &str = "\u{2209}";
/// SUBSET — subset-or-equal (U+2286).
pub const GLYPH_SUBSET: &str = "\u{2286}";
/// UNION (U+222A).
pub const GLYPH_UNION: &str = "\u{222A}";
/// INTERSECT (U+2229).
pub const GLYPH_INTERSECT: &str = "\u{2229}";
/// FOR-ALL — universal quantifier (U+2200).
pub const GLYPH_FORALL: &str = "\u{2200}";
/// EXISTS — existential quantifier (U+2203).
pub const GLYPH_EXISTS: &str = "\u{2203}";

// ─────────────────────────────────────────────────────────────────────────────
// CATEGORY 2 — CONSEQUENCE CLASS DESIGNATORS
// ─────────────────────────────────────────────────────────────────────────────

/// HAZARDOUS — requires human-in-the-loop precondition (U+26A0).
pub const GLYPH_HAZARDOUS: &str = "\u{26A0}";
/// REVERSIBLE — no HITL required (U+21BA).
pub const GLYPH_REVERSIBLE: &str = "\u{21BA}";
/// IRREVERSIBLE — requires HITL precondition (U+2298).
pub const GLYPH_IRREVERSIBLE: &str = "\u{2298}";

// ─────────────────────────────────────────────────────────────────────────────
// AUTHORIZATION GLYPHS
// ─────────────────────────────────────────────────────────────────────────────

/// Section sign — opcode marker for `I:§` (human operator confirmation).
pub const GLYPH_SECTION: &str = "\u{00A7}";

/// Wire-format glyph operator entry: (glyph -> readable name).
///
/// Cross-SDK byte-identical with Python `GLYPH_OPERATORS` keys + name field,
/// Go `GlyphOperators`, TypeScript `GLYPH_OPERATORS`.
pub fn glyph_operators() -> &'static BTreeMap<&'static str, &'static str> {
    static CACHE: OnceLock<BTreeMap<&'static str, &'static str>> = OnceLock::new();
    CACHE.get_or_init(|| {
        let mut m: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        m.insert("\u{2227}", "AND");
        m.insert("\u{2228}", "OR");
        m.insert("\u{00AC}", "NOT");
        m.insert("\u{2192}", "THEN");
        m.insert("\u{2194}", "IFF");
        m.insert("\u{2200}", "FOR-ALL");
        m.insert("\u{2203}", "EXISTS");
        m.insert("\u{2225}", "PARALLEL");
        m.insert(">", "PRIORITY");
        m.insert("~", "APPROX");
        m.insert("*", "WILDCARD");
        m.insert(":", "ASSIGN");
        m.insert(";", "SEQUENCE");
        m.insert("?", "QUERY");
        m.insert("@", "TARGET");
        m.insert("\u{27F3}", "REPEAT-EVERY");
        m.insert("\u{2260}", "NOT-EQUAL");
        m.insert("\u{2295}", "PRIORITY-ORDER");
        m
    })
}

/// Wire-format compound operator entry: (glyph sequence -> readable name).
///
/// Cross-SDK byte-identical with Python `COMPOUND_OPERATORS`, Go
/// `compoundOperators`, TypeScript `COMPOUND_OPERATORS`.
pub fn compound_operators() -> &'static BTreeMap<&'static str, &'static str> {
    static CACHE: OnceLock<BTreeMap<&'static str, &'static str>> = OnceLock::new();
    CACHE.get_or_init(|| {
        let mut m: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        m.insert("\u{00AC}\u{2192}", "UNLESS");
        m
    })
}

/// Consequence class table: (glyph -> readable name).
///
/// Cross-SDK byte-identical with Python `CONSEQUENCE_CLASSES`, Go
/// `ConsequenceClasses`, TypeScript `CONSEQUENCE_CLASSES`.
pub fn consequence_classes() -> &'static BTreeMap<&'static str, &'static str> {
    static CACHE: OnceLock<BTreeMap<&'static str, &'static str>> = OnceLock::new();
    CACHE.get_or_init(|| {
        let mut m: BTreeMap<&'static str, &'static str> = BTreeMap::new();
        m.insert("\u{26A0}", "HAZARDOUS");
        m.insert("\u{21BA}", "REVERSIBLE");
        m.insert("\u{2298}", "IRREVERSIBLE");
        m
    })
}

/// Returns the canonical v15 ASD basis: namespace -> opcode -> definition.
///
/// Built once on first call and cached for the lifetime of the process.
/// Cross-SDK byte-identical with Python ASD_BASIS, Go ASDFloorBasis,
/// TypeScript ASD_BASIS.
pub fn asd_basis() -> &'static BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> {
    static CACHE: OnceLock<BTreeMap<&'static str, BTreeMap<&'static str, &'static str>>> =
        OnceLock::new();
    CACHE.get_or_init(build_asd_basis)
}

fn build_asd_basis() -> BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> {
    let mut basis: BTreeMap<&'static str, BTreeMap<&'static str, &'static str>> = BTreeMap::new();

    // A — agent / coordination
    let mut a: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    a.insert("ACCEPT", "accept_proposed_action");
    a.insert("ACK", "positive_acknowledgment");
    a.insert("AR", "agentic_request");
    a.insert("ASD", "asd_version_identity_or_delta");
    a.insert("AUTH", "authorization_assertion");
    a.insert("CMP", "compress_compare");
    a.insert("CMPLY", "comply_with_proposed_action");
    a.insert("CMPR", "structured_comparison_returning_result");
    a.insert("COMP", "compliance_gate_assertion");
    a.insert("DA", "delegate_to_agent");
    a.insert("ERR", "error_handler");
    a.insert("MACRO", "registered_macro_invocation");
    a.insert("MDR", "mdr_corpus_version_identity_or_delta");
    a.insert("MEM", "memory_operation");
    a.insert("NACK", "negative_acknowledgment");
    a.insert("PERM", "permission_grant");
    a.insert("PING", "liveness_check");
    a.insert("PONG", "liveness_response");
    a.insert("PROPOSE", "propose_action_for_negotiation");
    a.insert("REJECT", "reject_proposed_action");
    a.insert("SUM", "summarize");
    a.insert("TRUST", "trust_assertion_about_agent_output");
    a.insert("TXN", "transaction_gate");
    a.insert("VERIFY", "request_output_verification");
    basis.insert("A", a);

    // B — building
    let mut b: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    b.insert("ALRM", "building_alarm");
    b.insert("AP", "access_point");
    b.insert("AREA", "building_sector_or_area");
    b.insert("HVAC", "hvac_system");
    b.insert("SAFE", "life_safety");
    b.insert("STRC", "structural");
    basis.insert("B", b);

    // C — compute / resource
    let mut c: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    c.insert("ALLOC", "resource_allocation");
    c.insert("CHKPT", "checkpoint_state");
    c.insert("FREE", "release_resource");
    c.insert("KILL", "terminate_process");
    c.insert("LIMIT", "resource_limit_enforcement");
    c.insert("MIGRT", "migrate_workload");
    c.insert("PAUSE", "pause_execution");
    c.insert("PRTY", "execution_priority");
    c.insert("QUOTA", "resource_quota");
    c.insert("RESUME", "resume_execution");
    c.insert("RSTRT", "restart");
    c.insert("SCALE", "scale_replicas");
    c.insert("SPAWN", "spawn_process_or_agent");
    c.insert("STAT", "resource_status");
    basis.insert("C", c);

    // D — data / transfer / query
    let mut d: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    d.insert("ABORT", "abort_transfer");
    d.insert("CHUNK", "file_chunk_payload");
    d.insert("CSUM", "checksum_verification");
    d.insert("DEL", "delete_data_irreversible");
    d.insert("FEED", "data_feed");
    d.insert("LOG", "log_entry");
    d.insert("PACK", "two_tier_corpus_encoding_for_at_rest_storage");
    d.insert("PULL", "request_payload_from_node");
    d.insert("PUSH", "push_payload_to_node");
    d.insert("Q", "query");
    d.insert("RESUME", "resume_interrupted_transfer");
    d.insert("RTN", "return_transmit");
    d.insert("STAT", "transfer_status_query");
    d.insert("UNPACK", "inference_free_semantic_retrieval_from_encoded_corpus");
    d.insert("XFER", "initiate_file_transfer");
    basis.insert("D", d);

    // E — environment
    let mut e: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    e.insert("EQ", "environmental_query");
    e.insert("GPS", "gps_coordinates");
    e.insert("HAZ", "obstacle_or_hazard");
    e.insert("HU", "humidity");
    e.insert("PU", "pressure");
    e.insert("TH", "temperature_humidity_composite");
    e.insert("UV", "ultraviolet");
    basis.insert("E", e);

    // F — federation
    let mut f: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    f.insert("AV", "authorization");
    f.insert("PRCD", "proceed_protocol");
    f.insert("QRY", "query_request");
    f.insert("WAIT", "wait_pause");
    basis.insert("F", f);

    // G — geo / position
    let mut g: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    g.insert("BEARING", "heading_bearing");
    g.insert("CONF", "position_confidence_rating");
    g.insert("DOP", "dilution_of_precision");
    g.insert("DR", "dead_reckoning_state");
    g.insert("ELEV", "elevation_query");
    g.insert("POS", "position_coordinates");
    g.insert("RANGE", "distance_calculation");
    g.insert("ROUT", "routing_query");
    g.insert("TRAIL", "trail_segment_reference");
    g.insert("WPT", "waypoint_reference");
    basis.insert("G", g);

    // H — health
    let mut h: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    h.insert("ALERT", "threshold_crossing_event");
    h.insert("BP", "blood_pressure");
    h.insert("CASREP", "casualty_report");
    h.insert("CPT", "CPT_procedure_code_accessor");
    h.insert("ECG", "electrocardiogram");
    h.insert("GLUC", "glucose");
    h.insert("HR", "heart_rate");
    h.insert("ICD", "ICD-10_diagnosis_code_accessor");
    h.insert("MEDREC", "medical_record_log_entry");
    h.insert("RR", "respiratory_rate");
    h.insert("SNOMED", "SNOMED_CT_concept_identifier_accessor");
    h.insert("SPO2", "oxygen_saturation");
    h.insert("TEMP", "body_temperature");
    h.insert("TRIAGE", "triage_classification");
    h.insert("VITALS", "composite_vitals_status");
    basis.insert("H", h);

    // I — identity
    let mut i_ns: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    i_ns.insert("AML", "anti_money_laundering_check");
    i_ns.insert("BIO", "biometric_result");
    i_ns.insert("CONS", "consent_and_scope_management");
    i_ns.insert("ID", "identity_assertion");
    i_ns.insert("KYC", "know_your_customer_check");
    i_ns.insert("PERM", "permission_grant");
    i_ns.insert("§", "human_operator_confirmation");
    basis.insert("I", i_ns);

    // J — cognitive / planning
    let mut j: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    j.insert("ABANDON", "abandon_plan");
    j.insert("BELIEF", "assert_belief_state");
    j.insert("BLOCK", "blocked_on_dependency");
    j.insert("COMMIT", "commit_to_plan");
    j.insert("DECOMP", "task_decomposition");
    j.insert("DONE", "goal_achieved");
    j.insert("GOAL", "declare_goal");
    j.insert("HANDOFF", "transfer_execution_with_full_state_context");
    j.insert("INTENT", "assert_intention");
    j.insert("PLAN", "transmit_plan_state");
    j.insert("REPLAN", "trigger_replanning_from_current_state");
    j.insert("STATUS", "execution_status");
    j.insert("STEP", "current_plan_step");
    j.insert("SUBGOAL", "declare_subgoal");
    basis.insert("J", j);

    // K — financial
    let mut k: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    k.insert("DIG", "digital_asset_operation");
    k.insert("ORD", "order_entry");
    k.insert("PAY", "payment_execution");
    k.insert("TRD", "trade_instruction");
    k.insert("XFR", "asset_transfer");
    basis.insert("K", k);

    // L — logging / compliance
    let mut l: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    l.insert("ALERT", "compliance_alert");
    l.insert("ATTEST", "compliance_attestation");
    l.insert("AUDIT", "audit_log_entry");
    l.insert("CHAIN", "chain_of_custody");
    l.insert("EXPORT", "log_export");
    l.insert("FORENS", "forensic_capture");
    l.insert("LOG", "write_audit_record");
    l.insert("LSIGN", "log_signature");
    l.insert("PURGE", "log_purge");
    l.insert("QUERY", "audit_trail_query");
    l.insert("REPORT", "compliance_report");
    l.insert("RETAIN", "log_retention_policy");
    l.insert("SEV", "severity_level");
    l.insert("TRAIL", "audit_trail_query");
    basis.insert("L", l);

    // M — municipal
    let mut m: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    m.insert("ALRT", "municipal_alert_alarm");
    m.insert("EVA", "evacuation");
    m.insert("RTE", "route");
    m.insert("TYP", "incident_type");
    basis.insert("M", m);

    // N — network
    let mut n: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    n.insert("BK", "backup_node");
    n.insert("CFG", "configure");
    n.insert("CMD", "command_node");
    n.insert("INET", "internet_uplink_capability_query");
    n.insert("Q", "query_discovery");
    n.insert("RLY", "primary_relay");
    n.insert("STS", "status");
    basis.insert("N", n);

    // O — operations
    let mut o: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    o.insert("BW", "available_bandwidth");
    o.insert("CHAN", "active_channel_type");
    o.insert("CONOPS", "concept_of_operations");
    o.insert("CONSTRAINT", "active_constraint_declaration");
    o.insert("DESC", "operational_deescalation");
    o.insert("EMCON", "emission_control_level");
    o.insert("ESCL", "operational_escalation");
    o.insert("FLOOR", "payload_floor_bytes");
    o.insert("IAP", "incident_action_plan");
    o.insert("LATENCY", "link_latency_class");
    o.insert("LINK", "link_quality");
    o.insert("LVL", "authority_level");
    o.insert("MESH", "mesh_topology_status");
    o.insert("MODE", "operational_mode");
    o.insert("PERIOD", "operational_period");
    o.insert("PHASE", "operational_phase");
    o.insert("POSTURE", "operational_posture");
    o.insert("READY", "readiness_condition");
    o.insert("SCOPE", "operational_scope");
    o.insert("TEMPO", "operational_tempo");
    o.insert("TYP", "incident_or_operation_type");
    o.insert("UPLINK", "uplink_availability");
    basis.insert("O", o);

    // P — procedure / maintenance
    let mut p: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    p.insert("CODE", "maintenance_code_reference_for_compliance_logging");
    p.insert("DEVICE", "device_class_being_maintained");
    p.insert("GUIDE", "procedure_guide_reference");
    p.insert("PART", "part_reference");
    p.insert("STAT", "completion_status");
    p.insert("STEP", "step_index_within_guide");
    basis.insert("P", p);

    // Q — quality / evaluation
    let mut q: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    q.insert("ANL", "analysis_of_agent_output");
    q.insert("BENCH", "benchmark_assertion");
    q.insert("CITE", "cite_source_for_claim");
    q.insert("CONF", "confidence_interval_assertion");
    q.insert("CORRECT", "correction_directive");
    q.insert("CRIT", "structured_critique_of_agent_output");
    q.insert("EVAL", "evaluation_result");
    q.insert("FAIL", "quality_gate_fail");
    q.insert("FB", "feedback_on_agent_output");
    q.insert("FLAG", "flag_output_unreliable");
    q.insert("GROUND", "grounding_assertion_against_source_document");
    q.insert("HALLU", "hallucination_detection_flag");
    q.insert("JDG", "judgment_of_agent_output");
    q.insert("PASS", "quality_gate_pass");
    q.insert("REFLECT", "self_reflection_on_output_quality");
    q.insert("REVISE", "request_revision_based_on_critique");
    q.insert("RPRT", "structured_report_of_agent_output");
    q.insert("SCORE", "quality_score_assertion");
    q.insert("VERIFY", "request_verification_of_claim_by_another_agent");
    basis.insert("Q", q);

    // R — robotics / actuation
    let mut r: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    r.insert("ACC", "accelerate_behavioral");
    r.insert("ACCEL", "accelerometer_data_stream");
    r.insert("BRK", "brake_actuator");
    r.insert("BT", "bluetooth_state");
    r.insert("CAM", "camera_activation");
    r.insert("CLOSE", "close_actuator");
    r.insert("COLLAB", "collaborative_mode");
    r.insert("DECEL", "decelerate_behavioral");
    r.insert("DISP", "display_brightness_or_state");
    r.insert("DPTH", "depth_control");
    r.insert("DRVE", "drive");
    r.insert("ESTOP", "emergency_stop");
    r.insert("FORM", "swarm_formation");
    r.insert("GPS", "gps_acquisition");
    r.insert("HANDOFF", "authority_handoff");
    r.insert("HAPTIC", "haptic_feedback_pattern");
    r.insert("HDNG", "heading");
    r.insert("LAND", "landing");
    r.insert("LOCK", "lock_actuator");
    r.insert("MIC", "microphone_activation");
    r.insert("MOV", "move");
    r.insert("NFC", "nfc_read_write");
    r.insert("NOTIF", "push_notification_to_device");
    r.insert("OPEN", "open_actuator");
    r.insert("RTH", "return_to_home_origin");
    r.insert("SCRN", "screen_capture");
    r.insert("SPKR", "speaker_audio_output");
    r.insert("SRFC", "surface_command_UUV");
    r.insert("STAT", "status");
    r.insert("STOP", "stop");
    r.insert("THR", "throttle_actuator");
    r.insert("TKOF", "takeoff");
    r.insert("TORCH", "flashlight_on_off");
    r.insert("VIBE", "vibration_pattern");
    r.insert("WIFI", "wifi_state");
    r.insert("WPT", "waypoint");
    r.insert("ZONE", "safety_zone_declaration");
    basis.insert("R", r);

    // S — security / crypto
    let mut s: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    s.insert("ATST", "attest");
    s.insert("CERT", "certificate_operation");
    s.insert("DEC", "decrypt");
    s.insert("ENC", "encrypt");
    s.insert("HASH", "hash");
    s.insert("HMAC", "hmac");
    s.insert("KEYEX", "key_exchange");
    s.insert("KEYGEN", "key_generation");
    s.insert("OPEN", "open_sealed_payload");
    s.insert("REVOK", "revoke");
    s.insert("ROTATE", "key_rotation");
    s.insert("SEAL", "seal_payload");
    s.insert("SIGN", "sign");
    s.insert("TRUST", "trust_assertion");
    s.insert("VFY", "verify_signature");
    basis.insert("S", s);

    // T — time
    let mut t: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    t.insert("AFTER", "execute_after_condition");
    t.insert("ALARM", "time_alarm");
    t.insert("BEFORE", "execute_before_deadline");
    t.insert("CRON", "cron_expression");
    t.insert("DELAY", "delay_execution");
    t.insert("DUR", "duration_constraint");
    t.insert("EPOCH", "unix_epoch_reference");
    t.insert("EXP", "expiration");
    t.insert("NOW", "current_timestamp_query");
    t.insert("REPEAT", "recurring_schedule");
    t.insert("SCHED", "schedule_event");
    t.insert("SYNC", "time_synchronization");
    t.insert("UNTIL", "execute_until_condition");
    t.insert("WIN", "time_window");
    basis.insert("T", t);

    // U — user / human-in-the-loop
    let mut u: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    u.insert("ACK", "human_acknowledgment");
    u.insert("ALERT", "urgent_operator_alert");
    u.insert("APPROVE", "request_human_approval");
    u.insert("ASSIGN", "assign_task_to_human_operator");
    u.insert("CONFIRM", "request_human_confirmation");
    u.insert("DELEGATE", "delegate_to_human");
    u.insert("DISPLAY", "display_information_to_operator");
    u.insert("ESCALATE", "escalate_to_human_decision_maker");
    u.insert("FEEDBACK", "request_human_feedback");
    u.insert("INPUT", "request_operator_input");
    u.insert("NOTIFY", "surface_message_to_operator");
    u.insert("OVERRIDE", "human_override_instruction");
    u.insert("REJECT", "human_rejection");
    u.insert("REVIEW", "request_human_review");
    basis.insert("U", u);

    // V — vehicle / vessel
    let mut v: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    v.insert("AIS", "ais_position_report");
    v.insert("CARGO", "cargo_manifest");
    v.insert("COURSE", "course_over_ground");
    v.insert("DOCK", "docking_operation");
    v.insert("ETA", "estimated_time_arrival");
    v.insert("ETD", "estimated_time_departure");
    v.insert("FLEET", "fleet_coordination");
    v.insert("HDG", "heading");
    v.insert("MAYDAY", "distress_signal");
    v.insert("MMSI", "maritime_mobile_service_identity");
    v.insert("PANPAN", "urgency_signal");
    v.insert("PORT", "port_of_call");
    v.insert("POS", "vehicle_position");
    v.insert("ROUTE", "routing_instruction");
    v.insert("SPEED", "speed_over_ground");
    v.insert("STATUS", "vessel_status");
    v.insert("UNDOCK", "undocking_operation");
    basis.insert("V", v);

    // W — weather
    let mut w: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    w.insert("ALERT", "weather_alert");
    w.insert("FCST", "forecast_product");
    w.insert("FIRE", "fire_weather_data");
    w.insert("FLOOD", "flood_data");
    w.insert("HURR", "hurricane_data");
    w.insert("METAR", "aviation_weather_observation");
    w.insert("PRECIP", "precipitation");
    w.insert("PRESS", "barometric_pressure");
    w.insert("TAF", "terminal_area_forecast");
    w.insert("TEMP", "ambient_temperature");
    w.insert("VIS", "visibility_report");
    w.insert("WARN", "weather_warning");
    w.insert("WATCH", "weather_watch");
    w.insert("WIND", "wind_speed_and_direction");
    basis.insert("W", w);

    // X — energy / grid
    let mut x: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    x.insert("CHG", "ev_charging_state");
    x.insert("DR", "demand_response_signal");
    x.insert("FAULT", "fault_event");
    x.insert("FREQ", "grid_frequency");
    x.insert("GRD", "grid_connection_status");
    x.insert("ISLND", "islanding_operation");
    x.insert("LOAD", "load_reading");
    x.insert("METER", "meter_reading");
    x.insert("PRICE", "energy_price_signal");
    x.insert("PROD", "generation_output");
    x.insert("RESTORE", "grid_restoration");
    x.insert("SHED", "load_shedding_instruction");
    x.insert("SOLAR", "solar_generation");
    x.insert("STORE", "storage_state");
    x.insert("VOLT", "voltage_level");
    x.insert("WND", "wind_generation");
    basis.insert("X", x);

    // Y — memory
    let mut y: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    y.insert("CLEAR", "clear_memory_tier");
    y.insert("COMMIT", "commit_working_to_long_term_memory");
    y.insert("EMBED", "generate_embedding_for_storage");
    y.insert("FETCH", "retrieve_by_key");
    y.insert("FORGET", "delete_from_memory");
    y.insert("INDEX", "index_document_for_retrieval");
    y.insert("PAGEOUT", "page_out_working_memory_to_external_store");
    y.insert("RECALL", "retrieve_episodic_memory_by_context");
    y.insert("RETRIEVE", "retrieve_from_LCS");
    y.insert("SEARCH", "semantic_vector_search");
    y.insert("SHARE", "share_memory_segment_with_another_agent");
    y.insert("STORE", "store_to_memory");
    y.insert("SUMM", "summarize_and_compress_memory_segment");
    y.insert("SYNC", "synchronize_memory_state_with_peer");
    y.insert("USG", "report_memory_utilization");
    basis.insert("Y", y);

    // Z — inference / model
    let mut z: BTreeMap<&'static str, &'static str> = BTreeMap::new();
    z.insert("BATCH", "batch_inference_request");
    z.insert("CACHE", "kv_cache_utilization_instruction");
    z.insert("CAPS", "capability_query");
    z.insert("CONF", "agent_reported_confidence");
    z.insert("COST", "inference_cost_report");
    z.insert("CTX", "context_window_utilization");
    z.insert("EMBED", "embedding_generation_request");
    z.insert("FINISH", "finish_reason");
    z.insert("INF", "invoke_inference");
    z.insert("LATENCY", "inference_latency_measurement");
    z.insert("MAXT", "max_tokens_parameter");
    z.insert("MDLUSED", "actual_model_used_in_inference_response");
    z.insert("MODEL", "specify_model_by_identifier");
    z.insert("RESP", "inference_response_payload_envelope");
    z.insert("ROUTE", "route_to_model_with_specified_capability");
    z.insert("STOP", "stop_sequence");
    z.insert("STREAM", "streaming_response_flag");
    z.insert("TEMP", "temperature_parameter");
    z.insert("TOKENS", "token_count_report");
    z.insert("TOPK", "top_k_sampling_parameter");
    z.insert("TOPP", "top_p_nucleus_sampling_parameter");
    basis.insert("Z", z);

    basis
}
