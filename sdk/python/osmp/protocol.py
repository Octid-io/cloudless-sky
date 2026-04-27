"""
OSMP Python Reference Implementation
Octid Semantic Mesh Protocol — Cloudless Sky Project

Source of truth: OSMP-semantic-dictionary-v15.csv | OSMP-SPEC-v1.0.2.md | SAL-grammar.ebnf
All opcode names, definitions, and namespace assignments are drawn directly from the
canonical semantic dictionary v15.0, not from any prior implementation.

Patent pending — inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import json
import lzma
import re
import struct
import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterator

try:
    import zstandard as zstd
    _HAS_ZSTD = True
except ImportError:
    _HAS_ZSTD = False


# ─────────────────────────────────────────────────────────────────────────────
# GLYPH OPERATOR TABLE — Category 1 (18 operators)
# Source: OSMP-semantic-dictionary-v15.csv Section 1, Category 1
# ─────────────────────────────────────────────────────────────────────────────

GLYPH_OPERATORS: dict[str, dict] = {
    "∧": {"unicode": "U+2227", "name": "AND",            "bytes": 3, "nl": ["and", "&", "also"]},
    "∨": {"unicode": "U+2228", "name": "OR",             "bytes": 3, "nl": ["or", "either", "alternatively"]},
    "¬": {"unicode": "U+00AC", "name": "NOT",            "bytes": 2, "nl": ["not", "except", "excluding", "without"]},
    "→": {"unicode": "U+2192", "name": "THEN",           "bytes": 3, "nl": ["if...then", "when...then", "provided that", "therefore"]},
    "↔": {"unicode": "U+2194", "name": "IFF",            "bytes": 3, "nl": ["if and only if", "iff", "exactly when"]},
    "∀": {"unicode": "U+2200", "name": "FOR-ALL",        "bytes": 3, "nl": ["for all", "every", "each", "all"]},
    "∃": {"unicode": "U+2203", "name": "EXISTS",         "bytes": 3, "nl": ["any", "there exists", "at least one", "some"]},
    "∥": {"unicode": "U+2225", "name": "PARALLEL",       "bytes": 3, "nl": ["simultaneously", "in parallel", "concurrently"]},
    ">": {"unicode": "U+003E", "name": "PRIORITY",       "bytes": 1, "nl": ["first", "prefer", "prioritize", "greater than"]},
    "~": {"unicode": "U+007E", "name": "APPROX",         "bytes": 1, "nl": ["approximately", "about", "roughly"]},
    "*": {"unicode": "U+002A", "name": "WILDCARD",       "bytes": 1, "nl": ["all", "any value", "broadcast"]},
    ":": {"unicode": "U+003A", "name": "ASSIGN",         "bytes": 1, "nl": ["equals", "is set to", "namespace-separator"]},
    ";": {"unicode": "U+003B", "name": "SEQUENCE",       "bytes": 1, "nl": ["then next", "followed by", "in sequence"]},
    "?": {"unicode": "U+003F", "name": "QUERY",          "bytes": 1, "nl": ["what is", "query", "report"]},
    "@": {"unicode": "U+0040", "name": "TARGET",         "bytes": 1, "nl": ["at", "on", "directed to"]},
    "⟳": {"unicode": "U+27F3", "name": "REPEAT-EVERY",  "bytes": 3, "nl": ["every", "repeat every", "recurring interval"]},
    "≠": {"unicode": "U+2260", "name": "NOT-EQUAL",      "bytes": 3, "nl": ["not equal to", "excluding value", "except value"]},
    "⊕": {"unicode": "U+2295", "name": "PRIORITY-ORDER", "bytes": 3, "nl": ["in priority order", "ranked", "strict ranked execution"]},
}

COMPOUND_OPERATORS: dict[str, dict] = {
    "¬→": {"unicode": "U+00AC U+2192", "name": "UNLESS", "nl": ["unless", "except when"]},
}

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 2 — CONSEQUENCE CLASS DESIGNATORS
# Source: dictionary v15Section 1 Category 2
# ─────────────────────────────────────────────────────────────────────────────

CONSEQUENCE_CLASSES: dict[str, dict] = {
    "⚠": {"unicode": "U+26A0", "name": "HAZARDOUS",    "hitl_required": True},
    "↺": {"unicode": "U+21BA", "name": "REVERSIBLE",   "hitl_required": False},
    "⊘": {"unicode": "U+2298", "name": "IRREVERSIBLE", "hitl_required": True},
}

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 3 — OUTCOME STATE DESIGNATORS
# ─────────────────────────────────────────────────────────────────────────────

OUTCOME_STATES: dict[str, dict] = {
    "⊤": {"unicode": "U+22A4", "name": "PASS-TRUE"},
    "⊥": {"unicode": "U+22A5", "name": "FAIL-FALSE"},
}

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 4 — PARAMETER AND SLOT DESIGNATORS
# ─────────────────────────────────────────────────────────────────────────────

PARAMETER_DESIGNATORS: dict[str, dict] = {
    "Δ": {"unicode": "U+0394", "name": "DELTA",        "bytes": 2},
    "⌂": {"unicode": "U+2302", "name": "HOME",         "bytes": 3},
    "⊗": {"unicode": "U+2297", "name": "ABORT-CANCEL", "bytes": 3},
    "τ": {"unicode": "U+03C4", "name": "TIMEOUT",      "bytes": 2},
    "∈": {"unicode": "U+2208", "name": "SCOPE-WITHIN", "bytes": 3},
    "∖": {"unicode": "U+2216", "name": "MISSING",      "bytes": 3},
}

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 5 — LOSS TOLERANCE POLICY DESIGNATORS
# ─────────────────────────────────────────────────────────────────────────────

LOSS_POLICIES: dict[str, dict] = {
    "Φ": {"unicode": "U+03A6", "name": "FAIL-SAFE",            "bytes": 2, "legacy": "FS"},
    "Γ": {"unicode": "U+0393", "name": "GRACEFUL-DEGRADATION", "bytes": 2, "legacy": "GD"},
    "Λ": {"unicode": "U+039B", "name": "ATOMIC",               "bytes": 2, "legacy": "AT"},
}

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 6 — DICTIONARY UPDATE MODE DESIGNATORS
# ─────────────────────────────────────────────────────────────────────────────

DICT_UPDATE_MODES: dict[str, dict] = {
    "+": {"unicode": "U+002B", "name": "ADDITIVE",  "bytes": 1},
    "←": {"unicode": "U+2190", "name": "REPLACE",   "bytes": 3},
    "†": {"unicode": "U+2020", "name": "DEPRECATE", "bytes": 3},
}

# ─────────────────────────────────────────────────────────────────────────────
# BAEL — Bandwidth-Agnostic Efficiency Layer
# ─────────────────────────────────────────────────────────────────────────────

class BAELMode(Enum):
    FULL_OSMP      = 0x00
    TCL_ONLY       = 0x02
    NL_PASSTHROUGH = 0x04

class BAELEncoder:
    NL_PASSTHROUGH_FLAG = 0x04

    @staticmethod
    def select_mode(nl_input: str, osmp_encoded: str, tcl_encoded: str = None) -> tuple:
        nl_b   = len(nl_input.encode("utf-8"))
        osmp_b = len(osmp_encoded.encode("utf-8"))
        tcl_b  = len(tcl_encoded.encode("utf-8")) if tcl_encoded else osmp_b + 1
        if nl_b <= osmp_b and nl_b <= tcl_b:
            return (BAELMode.NL_PASSTHROUGH, nl_input, BAELEncoder.NL_PASSTHROUGH_FLAG)
        elif tcl_encoded and tcl_b < osmp_b:
            return (BAELMode.TCL_ONLY, tcl_encoded, 0x00)
        else:
            return (BAELMode.FULL_OSMP, osmp_encoded, 0x00)

    @staticmethod
    def compression_floor_check(nl_input: str, osmp_encoded: str) -> dict:
        nl_b   = len(nl_input.encode("utf-8"))
        osmp_b = len(osmp_encoded.encode("utf-8"))
        mode, payload, flags = BAELEncoder.select_mode(nl_input, osmp_encoded)
        selected_b = len(payload.encode("utf-8"))
        reduction  = round((1 - selected_b / nl_b) * 100, 1) if nl_b > 0 else 0.0
        return {
            "nl_bytes": nl_b, "osmp_bytes": osmp_b,
            "selected_mode": mode.name, "selected_bytes": selected_b,
            "reduction_pct": reduction, "floor_applied": mode == BAELMode.NL_PASSTHROUGH,
            "flags": flags,
        }


# ─────────────────────────────────────────────────────────────────────────────
# OVERFLOW PROTOCOL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

LORA_FLOOR_BYTES      = 51
LORA_STANDARD_BYTES   = 255
FRAGMENT_HEADER_BYTES = 6
FLAG_TERMINAL         = 0b00000001
FLAG_CRITICAL         = 0b00000010
FLAG_EXTENDED_DEP     = 0b00001000   # Tier 3: payload prefix is u32 dependency bitmap


# ─────────────────────────────────────────────────────────────────────────────
# SLOT VALUE ENCODING TABLE
# Source: dictionary v15Section 2
# Single-character codes for all finite enumerated slot value sets.
# ─────────────────────────────────────────────────────────────────────────────

SLOT_VALUES: dict[str, dict[str, str]] = {
    "C:STAT":      {"A": "active", "D": "degraded", "E": "error", "I": "idle", "O": "offline"},
    "H:TRIAGE":    {"I": "immediate", "D": "delayed", "M": "minor", "B": "black", "X": "expectant"},
    "J:STATUS":    {"A": "active", "B": "blocked", "C": "complete", "F": "failed", "P": "paused"},
    "L:SEV":       {"0": "emergency", "1": "alert", "2": "critical", "3": "error",
                    "4": "warning", "5": "notice", "6": "informational", "7": "debug"},
    "O:LVL":       {"O": "OPCON", "T": "TACON", "A": "ADCON", "S": "support"},
    "O:BW_CLASS":  {"1": "51_bytes_SF12", "2": "127_bytes_SF11", "3": "255_bytes_LongFast",
                    "4": "1500_bytes_BLE", "5": "unlimited"},
    "O:CHAN":       {"L": "LoRa", "B": "BLE", "W": "WiFi", "C": "cellular",
                    "X": "wired", "T": "satellite", "M": "mesh_mixed"},
    "O:EMCON":     {"F": "full_emissions", "R": "reduced", "S": "silent"},
    "O:LATENCY":   {"1": "realtime_10ms", "2": "low_100ms", "3": "normal_1s",
                    "4": "high_10s", "5": "store_forward"},
    "O:LINK":      {"0": "none", "1": "critical", "2": "degraded",
                    "3": "marginal", "4": "good", "5": "nominal"},
    "O:MESH":      {"F": "full", "P": "partial", "I": "isolated", "B": "bridged"},
    "O:MODE":      {"N": "normal", "D": "degraded", "E": "emergency", "R": "recovery", "M": "maintenance"},
    "O:PHASE":     {"P": "prepare", "R": "respond", "M": "mitigate", "V": "recover"},
    "O:POSTURE":   {"D": "defensive", "N": "neutral", "S": "standby", "O": "offensive"},
    "O:READY":     {"5": "peacetime", "4": "increased_watch", "3": "round_the_clock",
                    "2": "next_step_nuclear_war", "1": "maximum_readiness"},
    "O:SCOPE":     {"G": "global", "N": "national", "R": "regional", "L": "local"},
    "O:TEMPO":     {"1": "routine", "2": "elevated", "3": "urgent", "4": "critical"},
    "O:TYP":       {"1": "national", "2": "regional_major", "3": "regional",
                    "4": "local_extended", "5": "minor_local"},
    "O:UPLINK":    {"A": "available", "U": "unavailable", "I": "intermittent"},
    "P:STAT":      {"C": "complete", "P": "pending", "F": "failed", "S": "skipped"},
    "R:COLLAB":    {"A": "active", "S": "standby", "O": "off"},
    "R:STAT":      {"A": "active", "I": "idle", "D": "degraded", "E": "emergency", "O": "offline"},
    "V:STATUS":    {"A": "active", "U": "underway", "M": "moored", "D": "degraded",
                    "E": "emergency", "I": "idle", "O": "offline"},
    "Y:STORE_TIER":{"W": "working", "L": "long_term", "E": "episodic", "S": "semantic"},
    "Z:FINISH":    {"S": "stop", "L": "length", "T": "tool_use", "E": "error", "C": "cancelled"},
    "K:DIR":       {"-$": "debit_payment_sent", "+$": "credit_payment_received"},
}


# ─────────────────────────────────────────────────────────────────────────────
# ASD BASIS SET — Guaranteed minimum operational vocabulary floor v1.0
# Source of truth: OSMP-semantic-dictionary-v15.csv Section 3
# Every opcode name and definition drawn directly from the canonical dictionary.
# DO NOT MODIFY opcode names or definitions — they are protocol wire format.
# ─────────────────────────────────────────────────────────────────────────────

ASD_FLOOR_VERSION = "1.0"

ASD_BASIS: dict[str, dict[str, str]] = {
    "A": {
        "ACCEPT":  "accept_proposed_action",
        "ACK":     "positive_acknowledgment",
        "AR":      "agentic_request",
        "ASD":     "asd_version_identity_or_delta",
        "AUTH":    "authorization_assertion",
        "CMP":     "compress_compare",
        "CMPLY":   "comply_with_proposed_action",
        "CMPR":    "structured_comparison_returning_result",
        "COMP":    "compliance_gate_assertion",
        "DA":      "delegate_to_agent",
        "ERR":     "error_handler",
        "MACRO":   "registered_macro_invocation",
        "MDR":     "mdr_corpus_version_identity_or_delta",
        "MEM":     "memory_operation",
        "NACK":    "negative_acknowledgment",
        "PERM":    "permission_grant",
        "PING":    "liveness_check",
        "PONG":    "liveness_response",
        "PROPOSE": "propose_action_for_negotiation",
        "REJECT":  "reject_proposed_action",
        "SUM":     "summarize",
        "TRUST":   "trust_assertion_about_agent_output",
        "TXN":     "transaction_gate",
        "VERIFY":  "request_output_verification",
    },
    "B": {
        "AP":   "access_point",
        "ALRM": "building_alarm",
        "AREA": "building_sector_or_area",
        "HVAC": "hvac_system",
        "SAFE": "life_safety",
        "STRC": "structural",
    },
    "C": {
        "ALLOC": "resource_allocation",
        "CHKPT": "checkpoint_state",
        "FREE":  "release_resource",
        "KILL":  "terminate_process",
        "LIMIT": "resource_limit_enforcement",
        "MIGRT": "migrate_workload",
        "PAUSE": "pause_execution",
        "PRTY":  "execution_priority",
        "QUOTA": "resource_quota",
        "RESUME":"resume_execution",
        "RSTRT": "restart",
        "SCALE": "scale_replicas",
        "SPAWN": "spawn_process_or_agent",
        "STAT":  "resource_status",
    },
    "D": {
        "ABORT":  "abort_transfer",
        "CHUNK":  "file_chunk_payload",
        "CSUM":   "checksum_verification",
        "FEED":   "data_feed",
        "LOG":    "log_entry",
        "PACK":   "two_tier_corpus_encoding_for_at_rest_storage",
        "PULL":   "request_payload_from_node",
        "PUSH":   "push_payload_to_node",
        "Q":      "query",
        "RESUME": "resume_interrupted_transfer",
        "RTN":    "return_transmit",
        "STAT":   "transfer_status_query",
        "UNPACK": "inference_free_semantic_retrieval_from_encoded_corpus",
        "XFER":   "initiate_file_transfer",
    },
    "E": {
        "EQ":  "environmental_query",
        "GPS": "gps_coordinates",
        "HU":  "humidity",
        "HAZ": "obstacle_or_hazard",
        "PU":  "pressure",
        "TH":  "temperature_humidity_composite",
        "UV":  "ultraviolet",
    },
    "F": {
        "AV":  "authorization",
        "PRCD": "proceed_protocol",
        "QRY":  "query_request",
        "WAIT": "wait_pause",
    },
    "G": {
        "BEARING": "heading_bearing",
        "CONF":    "position_confidence_rating",
        "DOP":     "dilution_of_precision",
        "DR":      "dead_reckoning_state",
        "ELEV":    "elevation_query",
        "POS":     "position_coordinates",
        "RANGE":   "distance_calculation",
        "ROUT":    "routing_query",
        "TRAIL":   "trail_segment_reference",
        "WPT":     "waypoint_reference",
    },
    "H": {
        # Layer 1 — ASD-resolvable semantic primitives
        "ALERT":  "threshold_crossing_event",
        "BP":     "blood_pressure",
        "CASREP": "casualty_report",
        "ECG":    "electrocardiogram",
        "GLUC":   "glucose",
        "HR":     "heart_rate",
        "MEDREC": "medical_record_log_entry",
        "RR":     "respiratory_rate",
        "SPO2":   "oxygen_saturation",
        "TEMP":   "body_temperature",
        "TRIAGE": "triage_classification",
        "VITALS": "composite_vitals_status",
        # Layer 2 — accessors into external open-ended registries
        # Slot value is the external code in brackets e.g. H:ICD[R00.1]
        # Slot values are exempt from the single-character encoding rule.
        # These opcodes are functional today with native code values.
        # MDR increases compression density; it does not gate functionality.
        "ICD":    "ICD-10_diagnosis_code_accessor",
        "SNOMED": "SNOMED_CT_concept_identifier_accessor",
        "CPT":    "CPT_procedure_code_accessor",
    },
    "I": {
        "AML":  "anti_money_laundering_check",
        "BIO":  "biometric_result",
        "CONS": "consent_and_scope_management",
        "ID":   "identity_assertion",
        "KYC":  "know_your_customer_check",
        "PERM": "permission_grant",
        "§":    "human_operator_confirmation",
    },
    "J": {
        "ABANDON": "abandon_plan",
        "BELIEF":  "assert_belief_state",
        "BLOCK":   "blocked_on_dependency",
        "COMMIT":  "commit_to_plan",
        "DECOMP":  "task_decomposition",
        "DONE":    "goal_achieved",
        "GOAL":    "declare_goal",
        "HANDOFF": "transfer_execution_with_full_state_context",
        "INTENT":  "assert_intention",
        "PLAN":    "transmit_plan_state",
        "REPLAN":  "trigger_replanning_from_current_state",
        "STATUS":  "execution_status",
        "STEP":    "current_plan_step",
        "SUBGOAL": "declare_subgoal",
    },
    "K": {
        "DIG": "digital_asset_operation",
        "ORD": "order_entry",
        "PAY": "payment_execution",
        "TRD": "trade_instruction",
        "XFR": "asset_transfer",
    },
    "L": {
        "ALERT":  "compliance_alert",
        "ATTEST": "compliance_attestation",
        "AUDIT":  "audit_log_entry",
        "CHAIN":  "chain_of_custody",
        "EXPORT": "log_export",
        "FORENS": "forensic_capture",
        "LOG":    "write_audit_record",
        "LSIGN":  "log_signature",
        "PURGE":  "log_purge",
        "QUERY":  "audit_trail_query",
        "REPORT": "compliance_report",
        "RETAIN": "log_retention_policy",
        "SEV":    "severity_level",
        "TRAIL":  "audit_trail_query",
    },
    "M": {
        "ALRT": "municipal_alert_alarm",
        "EVA":  "evacuation",
        "TYP":  "incident_type",
        "RTE":  "route",
    },
    "N": {
        "BK":   "backup_node",
        "CFG":  "configure",
        "CMD":  "command_node",
        "INET": "internet_uplink_capability_query",
        "RLY":  "primary_relay",
        "Q":    "query_discovery",
        "STS":  "status",
    },
    "O": {
        "BW":         "available_bandwidth",
        "LVL":        "authority_level",
        "CHAN":        "active_channel_type",
        "CONOPS":     "concept_of_operations",
        "CONSTRAINT": "active_constraint_declaration",
        "DESC":        "operational_deescalation",
        "EMCON":      "emission_control_level",
        "ESCL":       "operational_escalation",
        "FLOOR":      "payload_floor_bytes",
        "IAP":        "incident_action_plan",
        "LATENCY":    "link_latency_class",
        "LINK":       "link_quality",
        "MESH":       "mesh_topology_status",
        "MODE":       "operational_mode",
        "PERIOD":     "operational_period",
        "PHASE":      "operational_phase",
        "POSTURE":    "operational_posture",
        "READY":      "readiness_condition",
        "SCOPE":      "operational_scope",
        "TEMPO":      "operational_tempo",
        "TYP":        "incident_or_operation_type",
        "UPLINK":     "uplink_availability",
    },
    "P": {
        "CODE":   "maintenance_code_reference_for_compliance_logging",
        "DEVICE": "device_class_being_maintained",
        "GUIDE":  "procedure_guide_reference",
        "PART":   "part_reference",
        "STAT":   "completion_status",
        "STEP":   "step_index_within_guide",
    },
    "Q": {
        "ANL":     "analysis_of_agent_output",
        "BENCH":   "benchmark_assertion",
        "CITE":    "cite_source_for_claim",
        "CONF":    "confidence_interval_assertion",
        "CORRECT": "correction_directive",
        "CRIT":    "structured_critique_of_agent_output",
        "EVAL":    "evaluation_result",
        "FAIL":    "quality_gate_fail",
        "FB":      "feedback_on_agent_output",
        "FLAG":    "flag_output_unreliable",
        "GROUND":  "grounding_assertion_against_source_document",
        "HALLU":   "hallucination_detection_flag",
        "JDG":     "judgment_of_agent_output",
        "PASS":    "quality_gate_pass",
        "REFLECT": "self_reflection_on_output_quality",
        "REVISE":  "request_revision_based_on_critique",
        "RPRT":    "structured_report_of_agent_output",
        "SCORE":   "quality_score_assertion",
        "VERIFY":  "request_verification_of_claim_by_another_agent",
    },
    "R": {
        # Physical agent opcodes — consequence class mandatory on all R instructions
        "ACC":     "accelerate_behavioral",
        "BRK":     "brake_actuator",
        "COLLAB":  "collaborative_mode",
        "DECEL":   "decelerate_behavioral",
        "DPTH":    "depth_control",
        "DRVE":    "drive",
        "ESTOP":   "emergency_stop",
        "FORM":    "swarm_formation",
        "HANDOFF": "authority_handoff",
        "HDNG":    "heading",
        "LAND":    "landing",
        "MOV":     "move",
        "RTH":     "return_to_home_origin",
        "SRFC":    "surface_command_UUV",
        "STAT":    "status",
        "STOP":    "stop",
        "THR":     "throttle_actuator",
        "TKOF":    "takeoff",
        "WPT":     "waypoint",
        "ZONE":    "safety_zone_declaration",
        # Mobile device peripheral opcodes
        "ACCEL":  "accelerometer_data_stream",
        "BT":     "bluetooth_state",
        "CAM":    "camera_activation",
        "DISP":   "display_brightness_or_state",
        "GPS":    "gps_acquisition",
        "HAPTIC": "haptic_feedback_pattern",
        "MIC":    "microphone_activation",
        "NFC":    "nfc_read_write",
        "NOTIF":  "push_notification_to_device",
        "SCRN":   "screen_capture",
        "SPKR":   "speaker_audio_output",
        "TORCH":  "flashlight_on_off",
        "VIBE":   "vibration_pattern",
        "WIFI":   "wifi_state",
    },
    "S": {
        "ATST":   "attest",
        "CERT":   "certificate_operation",
        "DEC":    "decrypt",
        "ENC":    "encrypt",
        "HASH":   "hash",
        "HMAC":   "hmac",
        "KEYEX":  "key_exchange",
        "KEYGEN": "key_generation",
        "OPEN":   "open_sealed_payload",
        "REVOK":  "revoke",
        "ROTATE": "key_rotation",
        "SEAL":   "seal_payload",
        "SIGN":   "sign",
        "TRUST":  "trust_assertion",
        "VFY":    "verify_signature",
    },
    "T": {
        "AFTER":  "execute_after_condition",
        "ALARM":  "time_alarm",
        "BEFORE": "execute_before_deadline",
        "CRON":   "cron_expression",
        "DELAY":  "delay_execution",
        "DUR":    "duration_constraint",
        "EPOCH":  "unix_epoch_reference",
        "EXP":    "expiration",
        "NOW":    "current_timestamp_query",
        "REPEAT": "recurring_schedule",
        "SCHED":  "schedule_event",
        "SYNC":   "time_synchronization",
        "UNTIL":  "execute_until_condition",
        "WIN":    "time_window",
    },
    "U": {
        "ACK":      "human_acknowledgment",
        "ALERT":    "urgent_operator_alert",
        "APPROVE":  "request_human_approval",
        "ASSIGN":   "assign_task_to_human_operator",
        "CONFIRM":  "request_human_confirmation",
        "DELEGATE": "delegate_to_human",
        "DISPLAY":  "display_information_to_operator",
        "ESCALATE": "escalate_to_human_decision_maker",
        "FEEDBACK": "request_human_feedback",
        "INPUT":    "request_operator_input",
        "NOTIFY":   "surface_message_to_operator",
        "OVERRIDE": "human_override_instruction",
        "REJECT":   "human_rejection",
        "REVIEW":   "request_human_review",
    },
    "V": {
        "AIS":    "ais_position_report",
        "CARGO":  "cargo_manifest",
        "COURSE": "course_over_ground",
        "DOCK":   "docking_operation",
        "ETA":    "estimated_time_arrival",
        "ETD":    "estimated_time_departure",
        "FLEET":  "fleet_coordination",
        "HDG":    "heading",
        "MAYDAY": "distress_signal",
        "MMSI":   "maritime_mobile_service_identity",
        "PANPAN": "urgency_signal",
        "PORT":   "port_of_call",
        "POS":    "vehicle_position",
        "ROUTE":  "routing_instruction",
        "SPEED":  "speed_over_ground",
        "STATUS": "vessel_status",
        "UNDOCK": "undocking_operation",
    },
    "W": {
        "ALERT":  "weather_alert",
        "FCST":   "forecast_product",
        "FIRE":   "fire_weather_data",
        "FLOOD":  "flood_data",
        "HURR":   "hurricane_data",
        "METAR":  "aviation_weather_observation",
        "PRECIP": "precipitation",
        "PRESS":  "barometric_pressure",
        "TAF":    "terminal_area_forecast",
        "TEMP":   "ambient_temperature",
        "VIS":    "visibility_report",
        "WARN":   "weather_warning",
        "WATCH":  "weather_watch",
        "WIND":   "wind_speed_and_direction",
    },
    "X": {
        "DR":      "demand_response_signal",
        "CHG":     "ev_charging_state",
        "FAULT":   "fault_event",
        "FREQ":    "grid_frequency",
        "GRD":     "grid_connection_status",
        "ISLND":   "islanding_operation",
        "LOAD":    "load_reading",
        "METER":   "meter_reading",
        "PRICE":   "energy_price_signal",
        "RESTORE": "grid_restoration",
        "SHED":    "load_shedding_instruction",
        "SOLAR":   "solar_generation",
        "STORE":   "storage_state",
        "PROD":    "generation_output",
        "VOLT":    "voltage_level",
        "WND":     "wind_generation",
    },
    "Y": {
        "CLEAR":    "clear_memory_tier",
        "EMBED":    "generate_embedding_for_storage",
        "FETCH":    "retrieve_by_key",
        "FORGET":   "delete_from_memory",
        "INDEX":    "index_document_for_retrieval",
        "COMMIT":   "commit_working_to_long_term_memory",
        "PAGEOUT":  "page_out_working_memory_to_external_store",
        "RECALL":   "retrieve_episodic_memory_by_context",
        "RETRIEVE": "retrieve_from_LCS",
        "SEARCH":   "semantic_vector_search",
        "SHARE":    "share_memory_segment_with_another_agent",
        "USG":      "report_memory_utilization",
        "STORE":    "store_to_memory",
        "SUMM":     "summarize_and_compress_memory_segment",
        "SYNC":     "synchronize_memory_state_with_peer",
    },
    "Z": {
        # Z:INF is the canonical opcode — invoke_inference
        "BATCH":   "batch_inference_request",
        "CACHE":   "kv_cache_utilization_instruction",
        "CAPS":    "capability_query",
        "CONF":    "agent_reported_confidence",
        "COST":    "inference_cost_report",
        "CTX":     "context_window_utilization",
        "EMBED":   "embedding_generation_request",
        "FINISH":  "finish_reason",
        "INF":     "invoke_inference",
        "LATENCY": "inference_latency_measurement",
        "MAXT":    "max_tokens_parameter",
        "MDLUSED": "actual_model_used_in_inference_response",
        "MODEL":   "specify_model_by_identifier",
        "RESP":    "inference_response_payload_envelope",
        "ROUTE":   "route_to_model_with_specified_capability",
        "STOP":    "stop_sequence",
        "STREAM":  "streaming_response_flag",
        "TEMP":    "temperature_parameter",
        "TOKENS":  "token_count_report",
        "TOPK":    "top_k_sampling_parameter",
        "TOPP":    "top_p_nucleus_sampling_parameter",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTIVE SHARED DICTIONARY
# ─────────────────────────────────────────────────────────────────────────────

class AdaptiveSharedDictionary:
    """
    Version-pinned ASD with CRDT delta sync.

    ADDITIVE  = grow-only set  (Shapiro et al. G-Set)
    REPLACE   = LWW-register   (Shapiro et al. LWW-Register)
    DEPRECATE = tombstone      (Shapiro et al. 2P-Set)
    """

    class UpdateMode(Enum):
        ADDITIVE  = auto()
        REPLACE   = auto()
        DEPRECATE = auto()

    def __init__(self, floor_version: str = ASD_FLOOR_VERSION):
        self.floor_version = floor_version
        self._data: dict[str, dict[str, str]] = {
            ns: dict(ops) for ns, ops in ASD_BASIS.items()
        }
        self._tombstones: set[tuple[str, str]] = set()
        self._version_log: list[dict] = []

    def lookup(self, namespace: str, opcode: str) -> str | None:
        if (namespace, opcode) in self._tombstones:
            return None
        return self._data.get(namespace, {}).get(opcode)

    def apply_delta(self, namespace: str, opcode: str, definition: str,
                    mode: UpdateMode, version_pointer: str) -> None:
        self._version_log.append({"ns": namespace, "op": opcode,
                                  "def": definition, "mode": mode.name,
                                  "ver": version_pointer})
        if mode == self.UpdateMode.ADDITIVE:
            if namespace not in self._data:
                self._data[namespace] = {}
            if opcode not in self._data[namespace]:
                self._data[namespace][opcode] = definition
        elif mode == self.UpdateMode.REPLACE:
            if namespace not in self._data:
                self._data[namespace] = {}
            self._data[namespace][opcode] = definition
            self._tombstones.discard((namespace, opcode))
        elif mode == self.UpdateMode.DEPRECATE:
            self._tombstones.add((namespace, opcode))

    def fingerprint(self) -> str:
        content = json.dumps(self._data, sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()[:16]

    def namespaces(self) -> list[str]:
        return sorted(self._data.keys())


# ─────────────────────────────────────────────────────────────────────────────
# FRAME NEGOTIATION PROTOCOL (FNP) — Session Handshake State Machine
#
# Two-message capability advertisement + acknowledgment completing within
# 80 bytes total (40 + 38), designed for LoRa physical layer payload floor.
#
# Wire format:
#
#   FNP_ADV (Capability Advertisement, 40 bytes):
#     msg_type           1B   0x01
#     protocol_version   1B   0x01
#     fingerprint        8B   first 8 bytes of SHA-256(ASD content)
#     asd_version        u16  BE
#     namespace_bitmap   u32  BE (bit 0=A .. bit 25=Z, bit 26=Omega)
#     channel_capacity   1B   0x00=51B floor, 0x01=255B, 0x02=512B, 0x03=unconstrained
#     node_id           23B   null-padded UTF-8
#
#   FNP_ACK (Capability Acknowledgment, 38 bytes):
#     msg_type           1B   0x02 (ACK) or 0x03 (NACK)
#     match_status       1B   0x00=exact, 0x01=version_mismatch,
#                             0x02=fingerprint_mismatch
#     echo_fingerprint   8B   fingerprint from received ADV
#     own_fingerprint    8B   responder's own fingerprint
#     common_namespaces  u32  BE (intersection of both bitmaps)
#     neg_capacity       1B   negotiated capacity = min(adv, own)
#     node_id           15B   null-padded UTF-8
#
# Channel capacity negotiation: the session byte budget is the minimum
# of what both nodes declare.  BAEL selects encoding mode within this
# budget for every subsequent instruction.  This ensures the session
# scales within the lowest-capability link in the mesh path.
#
# State machine:
#   IDLE -> initiate() -> ADV_SENT
#   ADV_SENT -> receive ACK (match) -> ESTABLISHED
#   ADV_SENT -> receive ACK (mismatch) -> SYNC_NEEDED
#   ADV_SENT -> timeout -> IDLE
#   IDLE -> receive ADV -> send ACK -> ESTABLISHED or SYNC_NEEDED
#
# ─────────────────────────────────────────────────────────────────────────────

FNP_MSG_ADV  = 0x01
FNP_MSG_ACK  = 0x02
FNP_MSG_NACK = 0x03

# ADR-004: extended-form ADV signaled by msg_type bit 7 (high bit set).
# Extended form narrows node_id from 23 to 15 bytes and carries an 8-byte
# basis_fingerprint at offset 32. Total ADV size remains 40 bytes in both
# forms; only the field layout differs. See spec §9.1.
FNP_MSG_ADV_EXTENDED = 0x81
FNP_ADV_EXT_FLAG     = 0x80  # bit mask for the extended-form flag

FNP_MATCH_EXACT                = 0x00
FNP_MATCH_VERSION              = 0x01
FNP_MATCH_FINGERPRINT          = 0x02
FNP_MATCH_BASIS_MISMATCH       = 0x03  # ADR-004: ASD matches, bases differ (both extended)
FNP_MATCH_BASIS_EXT_VS_BASE    = 0x04  # ADR-004: ASD matches, base form vs extended (length mismatch)

# Channel capacity classes
FNP_CAP_FLOOR        = 0x00  # 51 bytes (LoRa SF12 BW125kHz)
FNP_CAP_STANDARD     = 0x01  # 255 bytes (LoRa SF11 BW250kHz / Meshtastic LongFast)
FNP_CAP_BLE          = 0x02  # 512 bytes (BLE)
FNP_CAP_UNCONSTRAINED = 0x03  # no limit (WiFi, HTTP, cloud)

FNP_CAP_BYTES = {
    FNP_CAP_FLOOR: 51,
    FNP_CAP_STANDARD: 255,
    FNP_CAP_BLE: 512,
    FNP_CAP_UNCONSTRAINED: 0,  # 0 = no limit
}

FNP_ADV_SIZE = 40
FNP_ACK_SIZE = 38
FNP_PROTOCOL_VERSION = 0x01

# Namespace bitmap: bit position = ord(letter) - ord('A'), bit 26 = Omega
_NS_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _namespace_bitmap(namespaces: list[str]) -> int:
    """Encode a list of namespace prefixes as a 32-bit bitmap."""
    bitmap = 0
    for ns in namespaces:
        if len(ns) == 1 and ns in _NS_LETTERS:
            bitmap |= 1 << (_NS_LETTERS.index(ns))
        elif ns == "\u03A9":  # Omega
            bitmap |= 1 << 26
    return bitmap


def _bitmap_to_namespaces(bitmap: int) -> list[str]:
    """Decode a 32-bit bitmap to a sorted list of namespace prefixes."""
    result = []
    for i, letter in enumerate(_NS_LETTERS):
        if bitmap & (1 << i):
            result.append(letter)
    if bitmap & (1 << 26):
        result.append("\u03A9")
    return result


def _fingerprint_bytes(asd: AdaptiveSharedDictionary) -> bytes:
    """Return the first 8 bytes of the ASD SHA-256 digest (binary)."""
    content = json.dumps(asd._data, sort_keys=True).encode()
    return hashlib.sha256(content).digest()[:8]


class FNPSession:
    """FNP session handshake state machine.

    Manages the two-message capability advertisement and acknowledgment
    exchange between two sovereign nodes.  After a successful handshake,
    provides the negotiated session state: whether dictionaries match,
    which namespaces are shared, and the remote node's identity.

    Usage (initiator):
        session = FNPSession(asd, "NODE_A")
        adv_packet = session.initiate()
        # ... transmit adv_packet, receive ack_packet ...
        session.receive(ack_packet)
        assert session.state == "ESTABLISHED"

    Usage (responder):
        session = FNPSession(asd, "NODE_B")
        ack_packet = session.receive(adv_packet)
        # ... transmit ack_packet ...
        assert session.state == "ESTABLISHED"
    """

    def __init__(self, asd: AdaptiveSharedDictionary, node_id: str,
                 asd_version: int = 1,
                 channel_capacity: int = FNP_CAP_FLOOR,
                 basis_fingerprint: bytes | None = None,
                 expected_basis_fingerprint: bytes | None = None,
                 require_sail: bool = False):
        """Construct an FNP session.

        Parameters
        ----------
        asd : AdaptiveSharedDictionary
            Local ASD instance, used for fingerprint and namespace bitmap.
        node_id : str
            Local node identifier (UTF-8). In base-form ADV the field
            reserves 23 bytes; in extended-form ADV (when basis_fingerprint
            is set) the field reserves 15 bytes. See spec §9.1.
        asd_version : int
            ASD version, big-endian u16 in the wire format.
        channel_capacity : int
            FNP_CAP_FLOOR / STANDARD / BLE / UNCONSTRAINED selector.
        basis_fingerprint : bytes | None
            ADR-004: 8-byte basis fingerprint for SAIL capability negotiation.
            When provided, this session uses extended-form ADV (msg_type
            0x81) and exchanges basis fingerprints with peers. When None,
            this session uses base-form ADV (msg_type 0x01) and is treated
            as base-ASD-only. Extended-form sessions interoperate with
            base-form peers via match_status 0x04 (ext-vs-base).
        expected_basis_fingerprint : bytes | None
            Optional: the basis fingerprint this node EXPECTS its peers to
            present. If a peer presents a different basis fingerprint, the
            session establishes in SAL-only mode and a degradation event
            is logged via `degradation_event`. Used for operator monitoring
            in homogeneous deployments.
        require_sail : bool
            ADR-004 operator policy flag. When True, sessions that would
            establish in SAL-only mode (basis mismatch) are refused
            locally. The flag does not propagate to peers.
        """
        self.asd = asd
        self.node_id = node_id
        self.asd_version = asd_version
        self.channel_capacity = channel_capacity
        self.basis_fingerprint = basis_fingerprint
        self.expected_basis_fingerprint = expected_basis_fingerprint
        self.require_sail = require_sail
        self.state = "IDLE"
        self.remote_node_id: str | None = None
        self.remote_fingerprint: bytes | None = None
        self.remote_basis_fingerprint: bytes | None = None
        self.common_namespaces: list[str] | None = None
        self.match_status: int | None = None
        self.negotiated_capacity: int | None = None
        self.degradation_event: dict | None = None
        self._own_fp = _fingerprint_bytes(asd)
        self._own_bitmap = _namespace_bitmap(asd.namespaces())

    @property
    def is_extended_form(self) -> bool:
        """True if this session uses extended-form ADV (basis_fingerprint set)."""
        return self.basis_fingerprint is not None

    @property
    def is_sail_capable(self) -> bool:
        """True if the negotiated session supports SAIL wire mode.

        Per ADR-004, SAIL is available only when the session reaches
        ESTABLISHED_SAIL — i.e., both ends agree on either base-form or a
        matching extended-form basis fingerprint.
        """
        return self.state == "ESTABLISHED_SAIL"

    # ── packet construction ──────────────────────────────────────────

    def _build_adv(self) -> bytes:
        """Build a 40-byte FNP_ADV packet (base or extended form per ADR-004)."""
        buf = bytearray(FNP_ADV_SIZE)
        buf[1] = FNP_PROTOCOL_VERSION
        buf[2:10] = self._own_fp
        struct.pack_into(">H", buf, 10, self.asd_version)
        struct.pack_into(">I", buf, 12, self._own_bitmap)
        buf[16] = self.channel_capacity

        if self.is_extended_form:
            # Extended form: msg_type bit 7 set, node_id narrowed to 15 bytes,
            # basis_fingerprint at offset 32. Spec §9.1.
            buf[0] = FNP_MSG_ADV_EXTENDED
            nid = self.node_id.encode("utf-8")[:15]
            buf[17 : 17 + len(nid)] = nid
            buf[32:40] = self.basis_fingerprint  # type: ignore[index]
        else:
            # Base form: msg_type 0x01, node_id reserves full 23 bytes.
            buf[0] = FNP_MSG_ADV
            nid = self.node_id.encode("utf-8")[:23]
            buf[17 : 17 + len(nid)] = nid

        return bytes(buf)

    def _build_ack(self, remote_fp: bytes, match: int,
                   common_bitmap: int, neg_cap: int) -> bytes:
        """Build a 38-byte FNP_ACK packet.

        ACK is unchanged in size from v1.0.2: the responder does not carry
        its own basis fingerprint on the wire (spec §9.2). Basis agreement
        is computed locally and reported via match_status.
        """
        buf = bytearray(FNP_ACK_SIZE)
        # SAIL-capable bases (match_status 0x00) send ACK; everything else
        # is a NACK in the original two-state model. Under ADR-004, basis
        # mismatches (0x03 / 0x04) are not failures — they are graded
        # capability — so they send ACK with the appropriate match_status.
        if match in (FNP_MATCH_EXACT, FNP_MATCH_BASIS_MISMATCH, FNP_MATCH_BASIS_EXT_VS_BASE):
            msg_type = FNP_MSG_ACK
        else:
            msg_type = FNP_MSG_NACK
        buf[0] = msg_type
        buf[1] = match
        buf[2:10] = remote_fp
        buf[10:18] = self._own_fp
        struct.pack_into(">I", buf, 18, common_bitmap)
        buf[22] = neg_cap
        nid = self.node_id.encode("utf-8")[:15]
        buf[23 : 23 + len(nid)] = nid
        return bytes(buf)

    # ── packet parsing ───────────────────────────────────────────────

    @staticmethod
    def _parse_adv(data: bytes) -> dict:
        if len(data) < FNP_ADV_SIZE or (data[0] & ~FNP_ADV_EXT_FLAG) != FNP_MSG_ADV:
            raise ValueError("Invalid FNP_ADV packet")
        is_extended = bool(data[0] & FNP_ADV_EXT_FLAG)
        result: dict = {
            "msg_type": data[0],
            "is_extended": is_extended,
            "protocol_version": data[1],
            "fingerprint": bytes(data[2:10]),
            "asd_version": struct.unpack(">H", data[10:12])[0],
            "namespace_bitmap": struct.unpack(">I", data[12:16])[0],
            "channel_capacity": data[16],
        }
        if is_extended:
            # Extended form: node_id is 15 bytes, basis_fingerprint follows.
            result["node_id"] = data[17:32].rstrip(b"\x00").decode("utf-8")
            result["basis_fingerprint"] = bytes(data[32:40])
        else:
            # Base form: node_id reserves the full 23 bytes.
            result["node_id"] = data[17:40].rstrip(b"\x00").decode("utf-8")
            result["basis_fingerprint"] = None
        return result

    @staticmethod
    def _parse_ack(data: bytes) -> dict:
        if len(data) < FNP_ACK_SIZE or data[0] not in (FNP_MSG_ACK, FNP_MSG_NACK):
            raise ValueError("Invalid FNP_ACK packet")
        return {
            "msg_type": data[0],
            "match_status": data[1],
            "echo_fingerprint": bytes(data[2:10]),
            "own_fingerprint": bytes(data[10:18]),
            "common_bitmap": struct.unpack(">I", data[18:22])[0],
            "negotiated_capacity": data[22],
            "node_id": data[23:38].rstrip(b"\x00").decode("utf-8"),
        }

    # ── state machine ────────────────────────────────────────────────

    def initiate(self) -> bytes:
        """Start a handshake by building and returning an FNP_ADV packet.

        Transitions: IDLE -> ADV_SENT

        Returns
        -------
        bytes : 40-byte FNP_ADV packet ready for transmission.
        """
        if self.state != "IDLE":
            raise RuntimeError(f"Cannot initiate from state {self.state}")
        self.state = "ADV_SENT"
        return self._build_adv()

    def receive(self, data: bytes) -> bytes | None:
        """Process a received FNP packet.

        If IDLE and an ADV is received, computes match status and returns
        an ACK packet for transmission.  Transitions to ESTABLISHED or
        SYNC_NEEDED.

        If ADV_SENT and an ACK is received, reads the match result.
        Transitions to ESTABLISHED or SYNC_NEEDED.  Returns None.

        Parameters
        ----------
        data : bytes, received packet (40 bytes for ADV, 38 for ACK).

        Returns
        -------
        bytes or None : ACK packet to transmit (when responding to ADV),
                        or None (when processing a received ACK).
        """
        msg_type = data[0]
        msg_type_base = msg_type & ~FNP_ADV_EXT_FLAG  # strip extended-form flag

        if msg_type_base == FNP_MSG_ADV and self.state == "IDLE":
            adv = self._parse_adv(data)
            self.remote_node_id = adv["node_id"]
            self.remote_fingerprint = adv["fingerprint"]
            self.remote_basis_fingerprint = adv["basis_fingerprint"]

            # Stage 1: ASD fingerprint match.
            if adv["fingerprint"] != self._own_fp:
                match = FNP_MATCH_FINGERPRINT
            elif adv["asd_version"] != self.asd_version:
                match = FNP_MATCH_VERSION
            else:
                # Stage 2: ADR-004 basis fingerprint capability grading.
                # ASD matches; now check basis agreement.
                remote_ext = adv["basis_fingerprint"] is not None
                local_ext = self.is_extended_form
                if remote_ext and local_ext:
                    # Both extended: compare basis fingerprints directly.
                    if adv["basis_fingerprint"] == self.basis_fingerprint:
                        match = FNP_MATCH_EXACT
                    else:
                        match = FNP_MATCH_BASIS_MISMATCH
                elif remote_ext != local_ext:
                    # Mixed: one side base form, other extended. Bases
                    # cannot match by length. Graded SAL-only.
                    match = FNP_MATCH_BASIS_EXT_VS_BASE
                else:
                    # Both base form: implicit single-corpus basis,
                    # determined entirely by the (matching) ASD fingerprint.
                    match = FNP_MATCH_EXACT

            common = self._own_bitmap & adv["namespace_bitmap"]
            self.common_namespaces = _bitmap_to_namespaces(common)
            self.match_status = match
            neg_cap = min(adv["channel_capacity"], self.channel_capacity)
            self.negotiated_capacity = neg_cap

            self._apply_match_to_state(match, adv["basis_fingerprint"])
            return self._build_ack(adv["fingerprint"], match, common, neg_cap)

        if msg_type_base in (FNP_MSG_ACK, FNP_MSG_NACK) and self.state == "ADV_SENT":
            ack = self._parse_ack(data)

            if ack["echo_fingerprint"] != self._own_fp:
                raise ValueError("FNP_ACK echo fingerprint mismatch")

            self.remote_node_id = ack["node_id"]
            self.remote_fingerprint = ack["own_fingerprint"]
            self.common_namespaces = _bitmap_to_namespaces(ack["common_bitmap"])
            self.match_status = ack["match_status"]
            self.negotiated_capacity = ack["negotiated_capacity"]
            # Note: the ACK does not carry the responder's basis fingerprint
            # (ADR-004 wire-cost decision in spec §9.2). The initiator
            # learns basis agreement via match_status, not via comparison.
            self._apply_match_to_state(ack["match_status"], None)
            return None

        raise ValueError(
            f"Unexpected msg_type 0x{msg_type:02x} in state {self.state}"
        )

    def _apply_match_to_state(self, match: int,
                               peer_basis_fp: bytes | None) -> None:
        """ADR-004 capability grading: choose ESTABLISHED_SAIL,
        ESTABLISHED_SAL_ONLY, SYNC_NEEDED, or refuse.

        Also records a degradation event when the peer's basis fingerprint
        differs from the locally configured `expected_basis_fingerprint`,
        for operator monitoring.
        """
        if match == FNP_MATCH_EXACT:
            self.state = "ESTABLISHED_SAIL"
        elif match in (FNP_MATCH_BASIS_MISMATCH, FNP_MATCH_BASIS_EXT_VS_BASE):
            # ADR-004 graded capability. Optional require_sail policy
            # converts this into a local refusal.
            if self.require_sail:
                self.state = "IDLE"
                self.degradation_event = {
                    "reason": "require_sail policy refused basis-mismatched session",
                    "match_status": match,
                    "remote_node_id": self.remote_node_id,
                    "remote_basis_fingerprint": (
                        peer_basis_fp.hex() if peer_basis_fp else None
                    ),
                }
                return
            self.state = "ESTABLISHED_SAL_ONLY"
            # Operator monitoring: log a degradation event when the
            # remote basis differs from the expected one.
            if (self.expected_basis_fingerprint is not None
                    and peer_basis_fp is not None
                    and peer_basis_fp != self.expected_basis_fingerprint):
                self.degradation_event = {
                    "reason": "remote basis fingerprint differs from expected",
                    "match_status": match,
                    "remote_node_id": self.remote_node_id,
                    "remote_basis_fingerprint": peer_basis_fp.hex(),
                    "expected_basis_fingerprint": (
                        self.expected_basis_fingerprint.hex()
                    ),
                }
        else:
            # FNP_MATCH_VERSION or FNP_MATCH_FINGERPRINT
            self.state = "SYNC_NEEDED"

    def timeout(self) -> None:
        """Handle handshake timeout.  Transitions ADV_SENT -> IDLE."""
        if self.state == "ADV_SENT":
            self.state = "IDLE"
            self.remote_node_id = None
            self.remote_fingerprint = None
            self.common_namespaces = None
            self.match_status = None
            self.negotiated_capacity = None

    def fallback(self, remote_id: str = "UNKNOWN") -> None:
        """Transition to FALLBACK when the remote peer does not speak OSMP.

        Called when:
        - ADV was sent but the response is not a valid FNP packet
        - The transport is known to be non-OSMP (e.g., plain JSON-RPC, NL)
        - Timeout occurred during negotiation attempt with a new peer

        Transitions: ADV_SENT -> FALLBACK, or IDLE -> FALLBACK (direct).

        The FALLBACK state means: this peer exists, we can talk to it,
        but it does not speak SAL. Outbound messages must be decoded to
        natural language at the boundary. Inbound messages are tagged
        NL_PASSTHROUGH.
        """
        if self.state in ("ADV_SENT", "IDLE"):
            self.state = "FALLBACK"
            self.remote_node_id = remote_id
            self.remote_fingerprint = None
            self.common_namespaces = []
            self.match_status = None
            self.negotiated_capacity = None

    def acquire(self) -> None:
        """Transition to ACQUIRED when the remote peer starts producing valid SAL.

        Called by SALBridge when the acquisition score exceeds threshold.
        The peer has learned SAL through contextual exposure and is now
        producing parseable SAL fragments in its responses.

        Transitions: FALLBACK -> ACQUIRED.
        """
        if self.state == "FALLBACK":
            self.state = "ACQUIRED"

    def regress(self) -> None:
        """Transition back to FALLBACK when an ACQUIRED peer stops producing valid SAL.

        LLMs are stochastic. Context windows rotate. System prompts change.
        An acquired peer may regress at any time.

        Transitions: ACQUIRED -> FALLBACK.
        """
        if self.state == "ACQUIRED":
            self.state = "FALLBACK"

    def is_legacy_peer(self) -> bool:
        """True if this session is in FALLBACK or ACQUIRED state (non-native OSMP)."""
        return self.state in ("FALLBACK", "ACQUIRED")

    def is_acquired(self) -> bool:
        """True if this session is in ACQUIRED state (peer learned SAL through exposure)."""
        return self.state == "ACQUIRED"


# ─────────────────────────────────────────────────────────────────────────────
# ASD VERSION MAPPING — u16 wire format interpreted as u8.u8 (MAJOR.MINOR)
#
# The FNP binary format carries asd_version as u16 big-endian at offset 10.
# That wire format is unchanged. The upper byte is MAJOR, lower byte is MINOR.
# MAJOR increments on breaking changes (REPLACE/RETRACT).
# MINOR increments on additive changes (ADD/DEPRECATE/EXTEND). Resets on MAJOR.
# Breaking-change detection from version number alone: compare upper bytes.
#
# Tripartite resolution flags
# ─────────────────────────────────────────────────────────────────────────────

def asd_version_pack(major: int, minor: int) -> int:
    """Pack MAJOR.MINOR into u16 for FNP wire format."""
    if not (0 <= major <= 255 and 0 <= minor <= 255):
        raise ValueError(f"Version {major}.{minor} out of u8.u8 range")
    return (major << 8) | minor


def asd_version_unpack(u16: int) -> tuple[int, int]:
    """Unpack u16 from FNP wire format into (major, minor)."""
    return (u16 >> 8, u16 & 0xFF)


def asd_version_str(u16: int) -> str:
    """Display string for SAL instructions: '2.7'."""
    major, minor = asd_version_unpack(u16)
    return f"{major}.{minor}"


def asd_version_parse(s: str) -> int:
    """Parse '2.7' into u16. Inverse of asd_version_str."""
    parts = s.split(".")
    if len(parts) != 2:
        raise ValueError(f"Invalid version string: {s}")
    return asd_version_pack(int(parts[0]), int(parts[1]))


def asd_version_is_breaking(old_u16: int, new_u16: int) -> bool:
    """True if the version change includes a MAJOR increment (breaking)."""
    return (new_u16 >> 8) > (old_u16 >> 8)


# ─────────────────────────────────────────────────────────────────────────────
# ASD DISTRIBUTION PROTOCOL (ADP) — SAL-layer dictionary synchronization
#
# Complements the binary FNP handshake with SAL-level instructions for:
#   - version identity exchange (mesh broadcast, gossip)
#   - delta request and delivery
#   - single-opcode micro-delta (task-relevant repair)
#   - hash verification
#   - MDR corpus version tracking
#
# All ADP instructions are A namespace SAL instructions using existing
# Category 6 glyph designators (+, ←, †) for delta operations.
#
# Priority hierarchy (scheduling, not protocol mechanism):
#   1. Mission traffic (any non-ADP instruction)
#   2. Micro-delta (task-relevant, A:ASD:DEF)
#   3. Background delta (A:ASD:DELTA)
#   4. Trickle charge request (A:ASD:REQ)
#
# ─────────────────────────────────────────────────────────────────────────────

# ADP instruction priorities (lower = higher priority)
ADP_PRIORITY_MISSION    = 0
ADP_PRIORITY_MICRO      = 1
ADP_PRIORITY_DELTA      = 2
ADP_PRIORITY_TRICKLE    = 3


@dataclass
class ADPDeltaOp:
    """A single operation within a delta payload."""
    namespace: str
    mode: str          # "+" | "\u2190" | "\u2020"
    opcode: str
    definition: str = ""  # empty for DEPRECATE

    @property
    def mode_name(self) -> str:
        return {"+": "ADDITIVE", "\u2190": "REPLACE", "\u2020": "DEPRECATE"}[self.mode]

    @property
    def is_breaking(self) -> bool:
        return self.mode == "\u2190"  # REPLACE

    def to_sal(self) -> str:
        return f"{self.namespace}{self.mode}[{self.opcode}]"


@dataclass
class ADPDelta:
    """A complete delta payload with version range and operations."""
    from_version: str   # "2.5"
    to_version: str     # "2.7"
    operations: list[ADPDeltaOp] = field(default_factory=list)

    @property
    def has_breaking(self) -> bool:
        return any(op.is_breaking for op in self.operations)

    def to_sal(self) -> str:
        ops = ":".join(op.to_sal() for op in self.operations)
        return f"A:ASD:DELTA[{self.from_version}\u2192{self.to_version}:{ops}]"


@dataclass
class PendingInstruction:
    """An instruction held in the semantic pending queue."""
    sal: str
    unresolved_namespace: str
    unresolved_opcode: str
    timestamp: float = 0.0


class ADPSession:
    """ASD Distribution Protocol session manager.

    Manages SAL-layer dictionary synchronization between sovereign nodes.
    Operates alongside FNPSession: FNP handles binary handshake, ADP handles
    SAL-level version exchange, delta delivery, and semantic pending queue.

    Usage:
        adp = ADPSession(asd, asd_version=asd_version_pack(2, 7))

        # Generate version identity for broadcast
        announce = adp.version_identity()

        # Process received version identity
        adp.receive_version("A:ASD[2.5:H2.1:K1.0]")

        # If mismatch, generate delta request
        req = adp.request_delta(target="2.7")

        # Apply received delta
        adp.apply_delta_sal("A:ASD:DELTA[2.5\u21922.7:H+[LACTATE]:H+[HRV]]")

        # Handle unknown opcode (semantic pending queue)
        result = adp.resolve_or_pend("H:LACTATE[4.2]")
        if result.pending:
            micro_req = result.micro_delta_request

    """

    def __init__(self, asd: AdaptiveSharedDictionary,
                 asd_version: int = asd_version_pack(1, 0),
                 namespace_versions: dict[str, str] | None = None):
        self.asd = asd
        self.asd_version = asd_version
        self.namespace_versions: dict[str, str] = namespace_versions or {}
        self.pending_queue: list[PendingInstruction] = []
        self.delta_log: list[str] = []
        self.remote_version: int | None = None
        self.remote_namespace_versions: dict[str, str] | None = None

    # ── Version identity ────────────────────────────────────────────────

    def version_identity(self, include_namespaces: bool = True) -> str:
        """Generate A:ASD version identity instruction.

        Returns SAL string, e.g. 'A:ASD[2.7:H2.3:K1.0]'
        """
        ver = asd_version_str(self.asd_version)
        if include_namespaces and self.namespace_versions:
            ns = "".join(f":{k}{v}" for k, v in
                         sorted(self.namespace_versions.items()))
            return f"A:ASD[{ver}{ns}]"
        return f"A:ASD[{ver}]"

    def version_query(self) -> str:
        """Generate version query broadcast: A:ASD?"""
        return "A:ASD?"

    def version_alert(self) -> str:
        """Generate version update announcement: A:ASD[M.m]\u26a0"""
        return f"A:ASD[{asd_version_str(self.asd_version)}]\u26a0"

    # ── Version parsing ─────────────────────────────────────────────────

    def receive_version(self, sal: str) -> dict:
        """Parse a received A:ASD version identity instruction.

        Returns dict with 'version', 'u16', 'namespaces', 'breaking'.
        """
        # Strip A:ASD[ and trailing ] or ]\u26a0
        inner = sal
        if inner.startswith("A:ASD["):
            inner = inner[6:]
        inner = inner.rstrip("]\u26a0")

        parts = inner.split(":")
        ver_str = parts[0]
        remote_u16 = asd_version_parse(ver_str)
        self.remote_version = remote_u16

        # Parse namespace versions if present
        ns_versions = {}
        for part in parts[1:]:
            # Format: H2.3 -> namespace H, version 2.3
            if len(part) >= 2 and part[0].isalpha():
                ns = part[0]
                ns_ver = part[1:]
                ns_versions[ns] = ns_ver
        self.remote_namespace_versions = ns_versions

        breaking = asd_version_is_breaking(self.asd_version, remote_u16)

        return {
            "version": ver_str,
            "u16": remote_u16,
            "namespaces": ns_versions,
            "breaking": breaking,
            "match": remote_u16 == self.asd_version,
        }

    # ── Delta request ───────────────────────────────────────────────────

    def request_delta(self, target: str | None = None,
                      namespace: str | None = None) -> str:
        """Generate delta request instruction.

        If namespace is specified, requests namespace-scoped delta.
        Otherwise requests full ASD delta.
        """
        my_ver = asd_version_str(self.asd_version)
        tgt = target or (asd_version_str(self.remote_version)
                         if self.remote_version else my_ver)
        if namespace and self.namespace_versions and self.remote_namespace_versions:
            my_ns = self.namespace_versions.get(namespace, "0.0")
            remote_ns = self.remote_namespace_versions.get(namespace, "0.0")
            return f"A:ASD:REQ[{namespace}{my_ns}\u2192{namespace}{remote_ns}]"
        return f"A:ASD:REQ[{my_ver}\u2192{tgt}]"

    # ── Delta construction ──────────────────────────────────────────────

    @staticmethod
    def build_delta(from_ver: str, to_ver: str,
                    operations: list[ADPDeltaOp]) -> ADPDelta:
        """Construct a delta payload."""
        return ADPDelta(from_version=from_ver, to_version=to_ver,
                        operations=operations)

    # ── Delta application ───────────────────────────────────────────────

    def apply_delta_sal(self, sal: str) -> dict:
        """Parse and apply a received A:ASD:DELTA instruction.

        Returns dict with 'applied', 'operations', 'breaking', 'queued'.
        Breaking deltas are logged but not applied if the session is active
        and uses affected namespaces.
        """
        self.delta_log.append(sal)

        # Parse: A:ASD:DELTA[from\u2192to:NS+[OP]:NS\u2190[OP]:NS\u2020[OP]]
        inner = sal
        if inner.startswith("A:ASD:DELTA["):
            inner = inner[12:]
        inner = inner.rstrip("]")

        # Split version range from operations
        arrow_idx = inner.find("\u2192")
        if arrow_idx < 0:
            return {"applied": False, "error": "No version range found"}

        # Find the end of to_version (next colon after arrow)
        after_arrow = inner[arrow_idx + 1:]  # \u2192 is 1 char
        colon_idx = after_arrow.find(":")
        if colon_idx < 0:
            return {"applied": False, "error": "No operations found"}

        from_ver = inner[:arrow_idx]
        to_ver = after_arrow[:colon_idx]
        ops_str = after_arrow[colon_idx + 1:]

        # Parse operations
        operations = []
        has_breaking = False
        mode_chars = {"+", "\u2190", "\u2020"}

        # Split on namespace boundaries (uppercase letter followed by mode char)
        current_pos = 0
        while current_pos < len(ops_str):
            # Find namespace letter
            if not ops_str[current_pos].isalpha():
                current_pos += 1
                continue

            ns = ops_str[current_pos]
            current_pos += 1

            if current_pos >= len(ops_str):
                break

            mode = ops_str[current_pos]
            if mode not in mode_chars:
                continue
            current_pos += 1

            # Extract [OPCODE]
            if current_pos < len(ops_str) and ops_str[current_pos] == "[":
                end_bracket = ops_str.find("]", current_pos)
                if end_bracket >= 0:
                    opcode = ops_str[current_pos + 1:end_bracket]
                    current_pos = end_bracket + 1
                else:
                    opcode = ops_str[current_pos + 1:]
                    current_pos = len(ops_str)
            else:
                continue

            op = ADPDeltaOp(namespace=ns, mode=mode, opcode=opcode)
            operations.append(op)
            if op.is_breaking:
                has_breaking = True

        # Apply operations to ASD
        applied = []
        for op in operations:
            asd_mode = {
                "+": AdaptiveSharedDictionary.UpdateMode.ADDITIVE,
                "\u2190": AdaptiveSharedDictionary.UpdateMode.REPLACE,
                "\u2020": AdaptiveSharedDictionary.UpdateMode.DEPRECATE,
            }[op.mode]
            self.asd.apply_delta(op.namespace, op.opcode, op.definition,
                                 asd_mode, to_ver)
            applied.append(f"{op.namespace}:{op.opcode}({op.mode_name})")

        # Attempt to resolve pending instructions
        resolved = self._resolve_pending()

        return {
            "applied": True,
            "from": from_ver,
            "to": to_ver,
            "operations": applied,
            "breaking": has_breaking,
            "pending_resolved": resolved,
        }

    # ── Micro-delta (single opcode definition) ──────────────────────────

    def request_definition(self, namespace: str, opcode: str) -> str:
        """Generate micro-delta request: A:ASD:DEF?[NS:OPCODE]"""
        return f"A:ASD:DEF?[{namespace}:{opcode}]"

    def send_definition(self, namespace: str, opcode: str,
                        definition: str, layer: int = 1) -> str:
        """Generate micro-delta response: A:ASD:DEF[NS:OP:def:layer]"""
        return f"A:ASD:DEF[{namespace}:{opcode}:{definition}:{layer}]"

    def apply_definition(self, sal: str) -> dict:
        """Parse and apply a received A:ASD:DEF instruction."""
        self.delta_log.append(sal)

        inner = sal
        if inner.startswith("A:ASD:DEF["):
            inner = inner[10:]
        inner = inner.rstrip("]")

        parts = inner.split(":")
        if len(parts) < 3:
            return {"applied": False, "error": "Insufficient fields"}

        namespace = parts[0]
        opcode = parts[1]
        definition = parts[2]
        layer = int(parts[3]) if len(parts) > 3 else 1

        self.asd.apply_delta(namespace, opcode, definition,
                             AdaptiveSharedDictionary.UpdateMode.ADDITIVE,
                             "micro")

        resolved = self._resolve_pending()

        return {
            "applied": True,
            "namespace": namespace,
            "opcode": opcode,
            "definition": definition,
            "layer": layer,
            "pending_resolved": resolved,
        }

    # ── Hash verification ───────────────────────────────────────────────

    def hash_identity(self, hex_length: int = 8) -> str:
        """Generate hash verification: A:ASD:HASH[M.m:hex]"""
        ver = asd_version_str(self.asd_version)
        fp = self.asd.fingerprint()[:hex_length]
        return f"A:ASD:HASH[{ver}:{fp}]"

    def verify_hash(self, sal: str) -> dict:
        """Verify a received A:ASD:HASH instruction against local state."""
        inner = sal
        if inner.startswith("A:ASD:HASH["):
            inner = inner[11:]
        inner = inner.rstrip("]")

        parts = inner.split(":")
        if len(parts) < 2:
            return {"match": False, "error": "Invalid hash instruction"}

        remote_ver = parts[0]
        remote_hash = parts[1]
        local_hash = self.asd.fingerprint()[:len(remote_hash)]

        return {
            "match": remote_hash == local_hash,
            "remote_version": remote_ver,
            "remote_hash": remote_hash,
            "local_hash": local_hash,
        }

    # ── MDR corpus versioning ───────────────────────────────────────────

    @staticmethod
    def mdr_identity(corpora: dict[str, str]) -> str:
        """Generate MDR version identity: A:MDR[ICD:2026:ATT:15.1]"""
        parts = ":".join(f"{k}:{v}" for k, v in sorted(corpora.items()))
        return f"A:MDR[{parts}]"

    @staticmethod
    def mdr_request(corpus: str, from_ver: str, to_ver: str) -> str:
        """Generate MDR delta request: A:MDR:REQ[ICD:2025\u21922026]"""
        return f"A:MDR:REQ[{corpus}:{from_ver}\u2192{to_ver}]"

    # ── Semantic pending queue ──────────────────────────────────────────

    def resolve_or_pend(self, sal: str) -> dict:
        """Check if an instruction's opcodes are resolvable. If not, pend it.

        This implements the semantic dependency resolution buffer from
        Instructions referencing undefined opcodes are held
        as semantically pending until the defining delta unit arrives.

        Returns dict with 'resolved', 'pending', optionally 'micro_delta_request'.
        """
        # Extract namespace and opcode from instruction
        ns, opcode = self._extract_ns_opcode(sal)
        if ns is None:
            return {"resolved": True, "pending": False}

        # Check if opcode exists in ASD
        definition = self.asd.lookup(ns, opcode)
        if definition is not None:
            return {"resolved": True, "pending": False, "definition": definition}

        # Opcode unresolved. Add to pending queue.
        import time
        pending = PendingInstruction(
            sal=sal,
            unresolved_namespace=ns,
            unresolved_opcode=opcode,
            timestamp=time.time(),
        )
        self.pending_queue.append(pending)

        return {
            "resolved": False,
            "pending": True,
            "unresolved": f"{ns}:{opcode}",
            "micro_delta_request": self.request_definition(ns, opcode),
            "queue_depth": len(self.pending_queue),
        }

    def _resolve_pending(self) -> list[str]:
        """Attempt to resolve pending instructions after a delta or def."""
        resolved = []
        still_pending = []
        for p in self.pending_queue:
            definition = self.asd.lookup(p.unresolved_namespace,
                                          p.unresolved_opcode)
            if definition is not None:
                resolved.append(p.sal)
            else:
                still_pending.append(p)
        self.pending_queue = still_pending
        return resolved

    @staticmethod
    def _extract_ns_opcode(sal: str) -> tuple[str | None, str | None]:
        """Extract namespace and opcode from a SAL instruction string."""
        if not sal or not sal[0].isalpha() or ":" not in sal:
            return None, None
        parts = sal.split(":")
        if len(parts) < 2:
            return None, None
        ns = parts[0]
        if len(ns) != 1:
            return None, None
        # Opcode is everything before [, ?, <, >, @, or end
        opcode_raw = parts[1]
        opcode = ""
        for ch in opcode_raw:
            if ch in "[]?<>@\u2227\u2228\u2192\u26a0":
                break
            opcode += ch
        return ns, opcode if opcode else None

    # ── Acknowledge ─────────────────────────────────────────────────────

    @staticmethod
    def acknowledge_version(version: str) -> str:
        """Generate version acknowledge: A:ACK[ASD:M.m]"""
        return f"A:ACK[ASD:{version}]"

    @staticmethod
    def acknowledge_hash() -> str:
        """Generate hash acknowledge: A:ACK[ASD:HASH]"""
        return "A:ACK[ASD:HASH]"

    @staticmethod
    def acknowledge_def() -> str:
        """Generate micro-delta acknowledge: A:ACK[ASD:DEF]"""
        return "A:ACK[ASD:DEF]"

    # ── Priority classification ─────────────────────────────────────────

    @staticmethod
    def classify_priority(sal: str) -> int:
        """Return the ADP priority level for a SAL instruction.

        0 = mission (non-ADP), 1 = micro-delta, 2 = background delta,
        3 = trickle charge request. Implementation uses this for scheduling.
        """
        if not sal.startswith("A:ASD") and not sal.startswith("A:MDR"):
            return ADP_PRIORITY_MISSION
        if "DEF" in sal:
            return ADP_PRIORITY_MICRO
        if "DELTA" in sal:
            return ADP_PRIORITY_DELTA
        return ADP_PRIORITY_TRICKLE


# ─────────────────────────────────────────────────────────────────────────────
# SAL ENCODER
# ─────────────────────────────────────────────────────────────────────────────

class SALEncoder:
    def __init__(self, asd: AdaptiveSharedDictionary | None = None):
        self.asd = asd or AdaptiveSharedDictionary()

    def encode_frame(self, namespace: str, opcode: str, target: str | None = None,
                     query_slot: str | None = None,
                     slots: dict[str, str | int | float] | None = None,
                     consequence_class: str | None = None) -> str:
        if namespace == "R" and consequence_class not in CONSEQUENCE_CLASSES:
            raise ValueError(
                f"R namespace requires consequence class (⚠/↺/⊘). Got: {consequence_class!r}")
        parts = [f"{namespace}:{opcode}"]
        if target is not None:
            parts.append(f"@{target}")
        if query_slot is not None:
            parts.append(f"?{query_slot}")
        if slots:
            for k, v in slots.items():
                parts.append(f":{k}:{v}")
        if consequence_class:
            parts.append(consequence_class)
        return "".join(parts)

    def encode_compound(self, left: str, operator: str, right: str) -> str:
        if operator not in GLYPH_OPERATORS and operator not in COMPOUND_OPERATORS:
            raise ValueError(f"Unknown operator: {operator!r}")
        return f"{left}{operator}{right}"

    def encode_parallel(self, instructions: list[str]) -> str:
        inner = "∧".join(f"?{i}" if not i.startswith("?") else i for i in instructions)
        return f"A∥[{inner}]"

    def encode_sequence(self, instructions: list[str]) -> str:
        return ";".join(instructions)

    def encode_broadcast(self, namespace: str, opcode: str) -> str:
        return f"{namespace}:{opcode}@*"


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITION VALIDATION (Section 12.5 of OSMP-SPEC-v1)
# ─────────────────────────────────────────────────────────────────────────────

# ── SAL Regex Building Blocks ────────────────────────────────────────────────
# Single source of truth for the namespace and opcode character classes used
# across the validator (Rule 4) and the regulatory_dependency parser (Rule 8).
# The § glyph is the human-authorization presence marker (I:§) and must be
# accepted as a valid opcode character; any regex that excludes it would
# silently miss frames involving I:§ and break dependency rules that
# reference human authorization as a precondition.
_NS_PATTERN     = r'[A-Z]{1,2}'           # Tier 1 (single char) and Tier 2 (two char)
_OPCODE_PATTERN = r'[A-Z§][A-Z0-9§]*'     # Opcode body, includes § for I:§

# Operators that split compound SAL instructions into frames
_FRAME_SPLIT_RE = re.compile(r'(->|[→∧∨↔∥;])')
# Pattern matching namespace:opcode after @ (prohibited: namespace-as-target)
_NS_TARGET_RE = re.compile(rf'@({_NS_PATTERN}):({_OPCODE_PATTERN})')
# Pattern extracting namespace:opcode from a SAL frame
_FRAME_NS_OP_RE = re.compile(rf'^({_NS_PATTERN}):({_OPCODE_PATTERN})')
# Pattern detecting SAL frames embedded in natural language (used by SALBridge).
# Uses a leading word boundary and relies on the greedy opcode pattern to
# absorb the full opcode body. No trailing boundary because § (the human-
# authorization marker) is a Unicode non-word character that breaks symmetric
# \b matching. This approach is cross-SDK identical: Python re, JavaScript,
# and Go RE2 all behave the same way for this regex.
_SAL_FRAME_RE_BRIDGE = re.compile(rf'\b({_NS_PATTERN}):({_OPCODE_PATTERN})')


# ── Regulatory Dependency Grammar (Rule 8) ───────────────────────────────────
# Dependency rules are SAL expressions stored in MDR corpora. Enforcement
# operates within the SAL grammar framework using the same glyph operators
# as the instructions they govern. No separate rule engine.

# Pattern for prerequisite expressions: NS:OPCODE or NS:OPCODE[SLOT]
_PREREQ_RE = re.compile(rf'({_NS_PATTERN}):({_OPCODE_PATTERN})(?:\[([^\]]+)\])?')
# Chain frame extraction: captures bracket [VAL] and colon :VAL notation
_CHAIN_FRAME_RE = re.compile(
    rf'({_NS_PATTERN}):({_OPCODE_PATTERN})(?:\[([^\]]+)\]|:([A-Z0-9][A-Z0-9_.]+))?'
)


@dataclass
class DependencyRule:
    """A single regulatory dependency rule from the MDR."""
    entry: str          # e.g. "F:BVLOS[P]"
    namespace: str      # e.g. "F"
    opcode: str         # e.g. "BVLOS"
    slot_value: str     # e.g. "P" or "" if no slot
    requires_raw: str   # e.g. "REQUIRES:F:REMID[S]∨F:REMID[M]"
    alternatives: list  # parsed: [[prereq_pattern, ...], ...]


def load_mdr_dependency_rules(mdr_path: str | Path) -> list[DependencyRule]:
    """Load regulatory dependency rules from an MDR corpus CSV Section B."""
    rules: list[DependencyRule] = []
    mdr_path = Path(mdr_path)
    if not mdr_path.exists():
        return rules

    with open(mdr_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_section_b = False
    for line in lines:
        stripped = line.strip()
        if "SECTION B" in stripped:
            in_section_b = True
            continue
        if stripped.startswith("SECTION ") and "SECTION B" not in stripped:
            if in_section_b:
                break
        if not in_section_b:
            continue
        if (not stripped or stripped.startswith("Format:")
                or stripped.startswith("===") or stripped.startswith("---")
                or stripped.startswith("Note:")
                or stripped.startswith("Dependency rules")):
            continue

        parts = stripped.split(",")
        if len(parts) < 5 or ":" not in parts[0]:
            continue

        dep_rule = parts[4].strip() if len(parts) > 4 else ""
        if not dep_rule.startswith("REQUIRES:"):
            continue

        ns_op = parts[0].strip()
        slot_value = parts[1].strip()
        ns_parts = ns_op.split(":")
        if len(ns_parts) < 2:
            continue

        namespace, opcode = ns_parts[0], ns_parts[1]
        entry = f"{namespace}:{opcode}[{slot_value}]" if slot_value else f"{namespace}:{opcode}"

        # Parse REQUIRES expression: strip prefix, split on ∨ (OR),
        # then split each alternative on ∧ (AND) for conjunctive prerequisites.
        # Result: [[conjunct, ...], ...] — at least ONE group where ALL conjuncts satisfied.
        expr = dep_rule[9:]  # strip "REQUIRES:"
        alternatives = [
            [conjunct.strip() for conjunct in alt.split("\u2227") if conjunct.strip()]
            for alt in expr.split("\u2228") if alt.strip()
        ]

        rules.append(DependencyRule(
            entry=entry, namespace=namespace, opcode=opcode,
            slot_value=slot_value, requires_raw=dep_rule,
            alternatives=alternatives,
        ))
    return rules


def _extract_chain_frames(sal: str) -> tuple[set[str], set[str]]:
    """Extract all frames from a SAL instruction chain.
    Normalizes both bracket (F:AV[Part107]) and colon (O:MODE:BVLOS)
    notation to NS:OPCODE[VALUE] for dependency rule matching."""
    chain_frames: set[str] = set()
    chain_opcodes: set[str] = set()
    for m in _CHAIN_FRAME_RE.finditer(sal):
        ns, opcode = m.group(1), m.group(2)
        bracket_val, colon_val = m.group(3), m.group(4)
        chain_opcodes.add(f"{ns}:{opcode}")
        val = bracket_val or colon_val
        if val:
            chain_frames.add(f"{ns}:{opcode}[{val}]")
    return chain_frames, chain_opcodes


def _prereq_satisfied(pattern: str, frames: set[str], opcodes: set[str]) -> bool:
    """Check if a prerequisite pattern is satisfied by the chain."""
    m = _PREREQ_RE.match(pattern)
    if not m:
        return False
    ns, opcode, slot = m.group(1), m.group(2), m.group(3)
    if slot:
        return f"{ns}:{opcode}[{slot}]" in frames
    return f"{ns}:{opcode}" in opcodes


def _validate_regulatory_dependencies(
    sal: str, dependency_rules: list[DependencyRule],
) -> list[CompositionIssue]:
    """Rule 8: Check instruction chain against MDR REQUIRES rules."""
    if not dependency_rules:
        return []

    chain_frames, chain_opcodes = _extract_chain_frames(sal)
    lookup: dict[str, DependencyRule] = {}
    for rule in dependency_rules:
        lookup[rule.entry] = rule
        if not rule.slot_value:
            lookup[f"{rule.namespace}:{rule.opcode}"] = rule

    issues: list[CompositionIssue] = []

    for frame in chain_frames:
        rule = lookup.get(frame)
        if rule is None:
            continue
        satisfied = any(
            all(_prereq_satisfied(p, chain_frames, chain_opcodes) for p in group)
            for group in rule.alternatives
        )
        if not satisfied:
            req_display = rule.requires_raw.replace("REQUIRES:", "")
            issues.append(CompositionIssue(
                rule="REGULATORY_DEPENDENCY", severity="error",
                message=f"{rule.entry} requires {req_display} as a regulatory prerequisite. "
                        f"The prerequisite is absent from the instruction chain.",
                frame=rule.entry,
            ))

    for bare in chain_opcodes:
        rule = lookup.get(bare)
        if rule is None or rule.slot_value:
            continue
        satisfied = any(
            all(_prereq_satisfied(p, chain_frames, chain_opcodes) for p in group)
            for group in rule.alternatives
        )
        if not satisfied:
            req_display = rule.requires_raw.replace("REQUIRES:", "")
            issues.append(CompositionIssue(
                rule="REGULATORY_DEPENDENCY", severity="error",
                message=f"{rule.entry} requires {req_display} as a regulatory prerequisite. "
                        f"The prerequisite is absent from the instruction chain.",
                frame=rule.entry,
            ))

    return issues


@dataclass
class CompositionIssue:
    """A single validation issue found in a composed instruction."""
    rule: str          # e.g. "HALLUCINATED_OPCODE", "NAMESPACE_AS_TARGET"
    severity: str      # "error" (blocks emission) or "warning" (advisory)
    message: str
    frame: str = ""    # the offending frame or substring, if applicable


@dataclass
class CompositionResult:
    """Result of composition validation."""
    valid: bool
    issues: list[CompositionIssue]
    sal: str
    nl: str = ""

    @property
    def errors(self) -> list[CompositionIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[CompositionIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def validate_composition(
    sal: str,
    nl: str = "",
    asd: AdaptiveSharedDictionary | None = None,
    r_safety_exempt: bool = True,
    dependency_rules: list[DependencyRule] | None = None,
) -> CompositionResult:
    """Validate a composed SAL instruction against eight deterministic rules.

    Rules enforced (Section 12.5 of OSMP-SPEC-v1):
      1. Hallucination check — every opcode must exist in the ASD
      2. Namespace-as-target — @ must not be followed by NS:OPCODE
      3. R namespace consequence class — mandatory except R:ESTOP
      4. I:§ precondition — ⚠ and ⊘ require I:§ in the chain
      5. Byte check — SAL bytes must not exceed NL bytes (exception: R safety chains)
      6. Slash rejection — / is not a SAL operator
      7. Mixed-mode check — no natural language text embedded in SAL frames
      8. Regulatory dependency — REQUIRES rules from MDR corpora

    Args:
        sal: The composed SAL instruction string.
        nl: The source natural language string (required for byte check).
        asd: ASD instance to validate against. Uses default if None.
        r_safety_exempt: If True, R namespace safety chains are exempt from byte check.

    Returns:
        CompositionResult with valid=True if no errors, issues list with details.
    """
    if asd is None:
        asd = AdaptiveSharedDictionary()

    issues: list[CompositionIssue] = []

    # ── Rule 6: Slash rejection ──────────────────────────────────────────
    if "/" in sal:
        issues.append(CompositionIssue(
            rule="SLASH_OPERATOR",
            severity="error",
            message="/ is not a SAL operator. Use → for THEN, ∧ for AND, ∨ for OR.",
            frame=sal,
        ))

    # ── Rule 2: Namespace-as-target ──────────────────────────────────────
    ns_target_matches = _NS_TARGET_RE.findall(sal)
    for ns, op in ns_target_matches:
        issues.append(CompositionIssue(
            rule="NAMESPACE_AS_TARGET",
            severity="error",
            message=f"@ target must be a node_id or *, not a namespace:opcode. Found @{ns}:{op}",
            frame=f"@{ns}:{op}",
        ))

    # ── Split into frames and validate each ──────────────────────────────
    parts = _FRAME_SPLIT_RE.split(sal)
    frames = [p.strip() for p in parts if p.strip() and p.strip() not in ("→", "∧", "∨", "↔", "∥", ";", "->")]

    has_r_namespace = False
    has_r_hazardous_or_irreversible = False
    has_i_section = False

    for frame in frames:
        m = _FRAME_NS_OP_RE.match(frame)
        if not m:
            # Frame doesn't start with NS:OP pattern — could be a slot value
            # or operator artifact. Skip unless it looks like embedded NL.
            if len(frame) > 20 and " " in frame:
                issues.append(CompositionIssue(
                    rule="MIXED_MODE",
                    severity="warning",
                    message=f"Frame appears to contain embedded natural language: '{frame[:40]}...'",
                    frame=frame,
                ))
            continue

        ns = m.group(1)
        op = m.group(2)

        # ── Rule 1: Hallucination check ──────────────────────────────────
        # Skip I:§ (it's a glyph-opcode, always valid)
        if not (ns == "I" and op == "§"):
            definition = asd.lookup(ns, op)
            if definition is None:
                issues.append(CompositionIssue(
                    rule="HALLUCINATED_OPCODE",
                    severity="error",
                    message=f"{ns}:{op} does not exist in the Adaptive Shared Dictionary.",
                    frame=frame,
                ))

        # ── Rules 3 & 4: R namespace consequence class and I:§ ───────────
        if ns == "R":
            has_r_namespace = True
            if op != "ESTOP":
                has_cc = any(cc in frame for cc in ("⚠", "↺", "⊘"))
                if not has_cc:
                    issues.append(CompositionIssue(
                        rule="CONSEQUENCE_CLASS_OMISSION",
                        severity="error",
                        message=f"R:{op} requires a consequence class designator (⚠/↺/⊘). R:ESTOP is the sole exception.",
                        frame=frame,
                    ))
                if "⚠" in frame or "⊘" in frame:
                    has_r_hazardous_or_irreversible = True

        if ns == "I" and op == "§":
            has_i_section = True

    # ── Rule 4 (chain-level): I:§ must precede ⚠/⊘ ──────────────────────
    if has_r_hazardous_or_irreversible and not has_i_section:
        issues.append(CompositionIssue(
            rule="AUTHORIZATION_OMISSION",
            severity="error",
            message="R namespace instructions with ⚠ (HAZARDOUS) or ⊘ (IRREVERSIBLE) require I:§ as a structural precondition in the instruction chain.",
        ))

    # ── Rule 5: Byte check ───────────────────────────────────────────────
    # Compression-positive guarantee: SAL MUST be shorter than NL. This is
    # protocol doctrine, not a channel preference — if SAL inflates, the
    # composer must sublimate further (drop wrapper opcodes, prefer the
    # most universal primitive) or fall back to NL_PASSTHROUGH. Composition
    # that produces a longer SAL than the input violates the protocol's
    # core promise.
    if nl:
        sal_bytes = len(sal.encode("utf-8"))
        nl_bytes = len(nl.encode("utf-8"))
        if sal_bytes >= nl_bytes:
            if r_safety_exempt and has_r_namespace:
                issues.append(CompositionIssue(
                    rule="BYTE_CHECK_EXEMPT",
                    severity="warning",
                    message=f"SAL ({sal_bytes}B) >= NL ({nl_bytes}B). Exempt: safety-complete R namespace chain.",
                ))
            else:
                issues.append(CompositionIssue(
                    rule="BYTE_INFLATION",
                    severity="error",
                    message=f"SAL ({sal_bytes}B) >= NL ({nl_bytes}B). Use NL_PASSTHROUGH. BAEL compression floor guarantee violated.",
                ))

    # ── Rule 8: Regulatory dependency grammar ─────────────────────────────
    if dependency_rules:
        dep_issues = _validate_regulatory_dependencies(sal, dependency_rules)
        issues.extend(dep_issues)

    errors = [i for i in issues if i.severity == "error"]
    return CompositionResult(
        valid=len(errors) == 0,
        issues=issues,
        sal=sal,
        nl=nl,
    )

# ── SAL Composer (NL to validated SAL pipeline) ───────────────────────────
#
# The composer implements the composition pipeline described in the spec:
# NL input -> intent extraction -> ASD lookup -> grammar assembly -> validate.
#
# The LLM's job (if present) is ONLY intent extraction: identify actions,
# conditions, targets, and parameters from natural language. Everything
# after intent extraction is deterministic code.
#
# Without an LLM, the composer falls back to keyword-based ASD matching.
# This produces correct SAL for inputs that map cleanly to ASD definitions.
# Ambiguous or complex inputs return None, signaling the caller to
# escalate or use NL passthrough.


@dataclass
class ComposedIntent:
    """Extracted intent from natural language, ready for ASD lookup."""
    actions: list[str]          # verbs/nouns: "alert", "heart rate", "temperature"
    conditions: list[str]       # threshold expressions: "above 130", "> 38"
    targets: list[str]          # node IDs or wildcards: "NODE1", "*"
    parameters: dict[str, str]  # slot values: {"bpm": "130"}
    raw: str                    # original NL input


class SALComposer:
    """Compose valid SAL from natural language using ASD lookup and grammar assembly.

    The composer NEVER generates SAL text via inference. It decomposes
    NL into intent, looks up opcodes in the ASD, assembles using grammar
    rules, and validates the result. The only inference step (if an LLM
    is provided) is intent extraction -- identifying action words from
    a sentence.

    Patent pending | License: Apache 2.0
    """

    # Condition operators mapped from NL to SAL
    _CONDITION_MAP: dict[str, str] = {
        "above": ">", "over": ">", "exceeds": ">", "greater than": ">",
        "more than": ">", "higher than": ">",
        "below": "<", "under": "<", "less than": "<", "lower than": "<",
        "equals": "=", "equal to": "=", "is": "=",
        "not": "\u00ac",  # NOT glyph
    }

    # Action words mapped to SAL operators
    _ACTION_MAP: dict[str, str] = {
        "then": "\u2192",      # THEN
        "and": "\u2227",       # AND
        "or": "\u2228",        # OR
        "if": "\u2192",        # conditional (THEN)
        "when": "\u2192",      # conditional
        "alert": "U:ALERT",    # common direct mapping
        "notify": "U:NOTIFY",
        "broadcast": "@*",
    }

    # Namespaces that produce/sense data (condition carriers in chains)
    _SENSING_NS: set[str] = {"E", "H", "W", "G", "X", "S", "D", "Z"}
    # Namespaces that consume/act on data (action targets in chains)
    _ACTION_NS: set[str] = {"U", "M", "R", "B", "J", "A", "K"}

    def __init__(self, asd: AdaptiveSharedDictionary | None = None,
                 macro_registry: 'MacroRegistry | None' = None):
        self.asd = asd or AdaptiveSharedDictionary()
        self.macro_registry = macro_registry
        self._encoder = SALEncoder(self.asd)
        self._keyword_index: dict[str, list[tuple[str, str]]] = {}
        self._phrase_index: dict[str, tuple[str, str]] = {}
        self._phrases_by_length: list[str] = []  # sorted longest-first
        self._build_keyword_index()
        self._build_phrase_index()

    def _build_keyword_index(self) -> None:
        """Build a reverse index from definition keywords to (namespace, opcode)."""
        for ns, ops in ASD_BASIS.items():
            for op, defn in ops.items():
                # Split definition into keywords
                words = defn.lower().replace("_", " ").split()
                for word in words:
                    if len(word) > 2:  # skip tiny words
                        if word not in self._keyword_index:
                            self._keyword_index[word] = []
                        self._keyword_index[word].append((ns, op))

    def _build_phrase_index(self) -> None:
        """Build a generation index: NL phrases -> (namespace, opcode).

        Auto-generated from ASD_BASIS definitions. Every underscore-joined
        definition becomes a phrase trigger. Multi-word phrases are matched
        longest-first to prevent fragmentation (e.g., "heart rate" matches
        as a phrase before "heart" and "rate" match individually).

        Only multi-word phrases are indexed here. Single-word lookups are
        handled by the keyword index. This prevents short opcode names
        (e.g., "th", "q", "dr") from matching inside common English words.
        """
        for ns, ops in ASD_BASIS.items():
            for op, defn in ops.items():
                phrase = defn.lower().replace("_", " ")
                # Only index multi-word phrases (2+ words)
                if " " in phrase:
                    self._phrase_index[phrase] = (ns, op)

        # ── Curated triggers ─────────────────────────────────────────
        # These extend the auto-generated set with mappings discovered
        # through cross-model composition testing. Each entry was found
        # by panel consensus or identified as a gap in the dictionary sweep.
        _CURATED: dict[str, tuple[str, str]] = {
            # Gap fixes (5 opcodes uncovered by auto-generation)
            "flow authorization": ("F", "AV"),
            "authorization proceed": ("F", "AV"),
            "emergency route": ("M", "RTE"),
            "municipal route": ("M", "RTE"),
            "incident route": ("M", "RTE"),
            "network status": ("N", "STS"),
            "node status": ("N", "STS"),
            "vessel heading": ("V", "HDG"),
            "ship heading": ("V", "HDG"),
            "maritime heading": ("V", "HDG"),
            # LLM-only hits (10 opcodes models resolved that tool missed)
            "restart process": ("C", "RSTRT"),
            "restart service": ("C", "RSTRT"),
            "data query": ("D", "Q"),
            "query data": ("D", "Q"),
            "audit query": ("L", "QUERY"),
            "query audit": ("L", "QUERY"),
            "robot heading": ("R", "HDNG"),
            "vehicle heading": ("V", "HDG"),
            "drone heading": ("V", "HDG"),
            "uav heading": ("V", "HDG"),
            "boat heading": ("V", "HDG"),
            "aircraft heading": ("V", "HDG"),
            "robot status": ("R", "STAT"),
            "device status": ("R", "STAT"),
            "robot waypoint": ("R", "WPT"),
            "attest payload": ("S", "ATST"),
            "attestation": ("S", "ATST"),
            "page out memory": ("Y", "PAGEOUT"),
            "store to memory": ("Y", "STORE"),
            "save to memory": ("Y", "STORE"),
            # Composition failure fixes (from CF-003, CF-006, CF-023)
            "generate key": ("S", "KEYGEN"),
            "generate keys": ("S", "KEYGEN"),
            "key pair": ("S", "KEYGEN"),
            "create keypair": ("S", "KEYGEN"),
            "sign payload": ("S", "SIGN"),
            "digital signature": ("S", "SIGN"),
            "push to node": ("D", "PUSH"),
            "send to node": ("D", "PUSH"),
            "send to": ("D", "PUSH"),
            "send it to": ("D", "PUSH"),
            "transmit to": ("D", "PUSH"),
            "deliver to": ("D", "PUSH"),
            "ping node": ("A", "PING"),
            "ping host": ("A", "PING"),
            "ping": ("A", "PING"),
            # Discovery / network query
            "discover peers": ("N", "Q"),
            "discover": ("N", "Q"),
            "find peers": ("N", "Q"),
            "list peers": ("N", "Q"),
            # Return / RTB
            "return to base": ("R", "RTB"),
            "return home": ("R", "RTB"),
            "rtb": ("R", "RTB"),
            "go home": ("R", "RTB"),
            # Mobile peripherals — turn on/activate/enable patterns
            "turn on camera": ("R", "CAM"),
            "turn on the camera": ("R", "CAM"),
            "activate camera": ("R", "CAM"),
            "enable camera": ("R", "CAM"),
            "start recording": ("R", "CAM"),
            "turn on flashlight": ("R", "TORCH"),
            "turn on the flashlight": ("R", "TORCH"),
            "turn on torch": ("R", "TORCH"),
            "activate flashlight": ("R", "TORCH"),
            "enable flashlight": ("R", "TORCH"),
            "turn on microphone": ("R", "MIC"),
            "activate microphone": ("R", "MIC"),
            "turn on speaker": ("R", "SPKR"),
            "play audio": ("R", "SPKR"),
            "vibrate": ("R", "VIBE"),
            "haptic feedback": ("R", "HAPTIC"),
            "activate haptic": ("R", "HAPTIC"),
            # Process control
            "shutdown": ("C", "KILL"),
            "shut down": ("C", "KILL"),
            "kill process": ("C", "KILL"),
            "terminate": ("C", "KILL"),
            # Time expiration
            "expire": ("T", "EXP"),
            "expires": ("T", "EXP"),
            "expiration": ("T", "EXP"),
            "ttl": ("T", "EXP"),
            "time to live": ("T", "EXP"),
            # Sensor read default (no sensor-type specifier)
            "read sensor": ("E", "TH"),
            "sensor read": ("E", "TH"),
            # Vitals
            "all vitals": ("H", "VITALS"),
            "vital signs": ("H", "VITALS"),
            "full vitals": ("H", "VITALS"),
            # Lock — semantic equivalence to STOP (no R:LOCK in v15)
            "lock door": ("R", "STOP"),
            "lock": ("R", "STOP"),
            # Clinical alert preference (vs L:ALERT compliance default)
            "heart rate alert": ("H", "ALERT"),
            "vitals alert": ("H", "ALERT"),
            "patient alert": ("H", "ALERT"),
            # UAV / drone targeting patterns
            "drone heading": ("V", "HDG"),
            "transfer task": ("J", "HANDOFF"),
            "hand off": ("J", "HANDOFF"),
            "task handoff": ("J", "HANDOFF"),
            "verify identity": ("I", "ID"),
            "identity check": ("I", "ID"),
            "run inference": ("Z", "INF"),
            "invoke model": ("Z", "INF"),
            "building fire": ("B", "ALRM"),
            "fire alarm": ("B", "ALRM"),
            # Operational abbreviations (mesh radio shorthand)
            "temp report": ("E", "TH"),
            "temp check": ("E", "TH"),
            "battery level": ("X", "STORE"),
            "battery status": ("X", "STORE"),
            "battery report": ("X", "STORE"),
            "signal strength": ("O", "LINK"),
            "link quality": ("O", "LINK"),
            "gps fix": ("E", "GPS"),
            "position report": ("G", "POS"),
            "node info": ("N", "STS"),
            "mesh status": ("O", "MESH"),
            "air quality": ("E", "EQ"),
            "wind speed": ("W", "WIND"),
            "heart rate check": ("H", "HR"),
            "blood pressure check": ("H", "BP"),
            "vitals check": ("H", "VITALS"),
            "oxygen level": ("H", "SPO2"),
        }
        for phrase, (ns, op) in _CURATED.items():
            self._phrase_index[phrase] = (ns, op)

        # ── Synonym sublimation table ─────────────────────────────────────
        # Single-word synonyms map English vocabulary down to canonical
        # protocol primitives. The reverse-meaning-tree pattern: many
        # English words collapse to one universal opcode. Add to this
        # table whenever a synonym misses the auto-generated keyword
        # index because the synonym word doesn't appear in any opcode
        # definition. Curated by domain cluster.
        _SYNONYMS: dict[str, tuple[str, str]] = {
            # Position / Geo cluster -> G:POS (primitive position)
            # NOTE: "coordinates" / "coords" intentionally NOT mapped here —
            # they are context-sensitive between G:POS (abstract position)
            # and E:GPS (raw lat/lon values when numbers follow). Let the
            # parametric extraction pipeline disambiguate.
            "position":      ("G", "POS"),
            "location":      ("G", "POS"),
            "place":         ("G", "POS"),
            "where":         ("G", "POS"),
            "spot":          ("G", "POS"),
            "whereabouts":   ("G", "POS"),
            "altitude":      ("G", "POS"),
            "elevation":     ("G", "POS"),
            "latlon":        ("G", "POS"),
            # Heading / Bearing cluster -> G:BEARING
            "heading":       ("G", "BEARING"),
            "bearing":       ("G", "BEARING"),
            "direction":     ("G", "BEARING"),
            "course":        ("G", "BEARING"),
            "azimuth":       ("G", "BEARING"),
            "compass":       ("G", "BEARING"),
            # Audio cluster -> R:SPKR (speaker output, mute = vol 0)
            "audio":         ("R", "SPKR"),
            "sound":         ("R", "SPKR"),
            "volume":        ("R", "SPKR"),
            "speaker":       ("R", "SPKR"),
            "loudness":      ("R", "SPKR"),
            # Temperature canonical -> E:TH (env sensor primitive)
            # H:TEMP for clinical context, Z:TEMP for LLM sampling parameter;
            # E:TH is the broad-base primitive that wins for generic input.
            "temp":          ("E", "TH"),
            "temperature":   ("E", "TH"),
            "thermometer":   ("E", "TH"),
            # Network / status synonyms
            "uptime":        ("N", "STS"),
            "alive":         ("N", "STS"),
            "online":        ("N", "STS"),
            # Authorization / approval (overrides U:ACK keyword default)
            "approves":      ("U", "APPROVE"),
            "approved":      ("U", "APPROVE"),
            "approval":      ("U", "APPROVE"),
            # Close → stop flow (vocab gap: no R:CLOSE in v15; semantic equivalence)
            "close":         ("R", "STOP"),
            "closes":        ("R", "STOP"),
            "shut":          ("R", "STOP"),
        }
        for word, (ns, op) in _SYNONYMS.items():
            # Synonym wins over auto-generated keyword index for that word
            self._phrase_index[word] = (ns, op)

        # Sort phrases longest-first for greedy matching
        self._phrases_by_length = sorted(
            self._phrase_index.keys(), key=len, reverse=True
        )

    def lookup_by_keyword(self, keyword: str) -> list[tuple[str, str, str]]:
        """Find opcodes matching a keyword. Returns [(namespace, opcode, definition)].

        Phase priority is preserved (direct-opcode > definition-keyword > fuzzy)
        but within each phase, results are sorted by canonicality:
        definition-starts-with-keyword wins, then shorter definition (more
        generic), then shorter opcode name. This ensures G:POS
        ("position_coordinates") beats G:CONF ("position_confidence_rating")
        for the keyword "position", without disturbing the strong-signal
        direct-opcode-match phase.
        """
        keyword = keyword.lower().strip()

        def _canon_score(entry: tuple[str, str, str]) -> tuple[int, int, int]:
            _ns, op, defn = entry
            defn_clean = defn.lower().replace("_", " ").split()
            starts_with = 0 if (defn_clean and defn_clean[0] == keyword) else 1
            return (starts_with, len(defn_clean), len(op))

        results: list[tuple[str, str, str]] = []

        # Phase 1: Direct opcode-name match (highest signal)
        phase1: list[tuple[str, str, str]] = []
        for ns, ops in ASD_BASIS.items():
            for op, defn in ops.items():
                if keyword == op.lower():
                    phase1.append((ns, op, defn))
        phase1.sort(key=_canon_score)
        results.extend(phase1)

        # Phase 2: Definition keyword match (sorted within phase)
        phase2: list[tuple[str, str, str]] = []
        for ns, op in self._keyword_index.get(keyword, []):
            defn = self.asd.lookup(ns, op) or ""
            entry = (ns, op, defn)
            if entry not in results and entry not in phase2:
                phase2.append(entry)
        phase2.sort(key=_canon_score)
        results.extend(phase2)

        # Phase 3: Fuzzy prefix match (sorted within phase). Only fires
        # when phases 1 and 2 produced nothing. Keyword must be a prefix of
        # at least one definition word (4+ char keywords only). This catches
        # "config" -> "configure" without matching "location" -> "allocation"
        # (location is not a prefix of allocation).
        if not results and len(keyword) >= 4:
            phase3: list[tuple[str, str, str]] = []
            for ns, ops in ASD_BASIS.items():
                for op, defn in ops.items():
                    defn_words = defn.lower().replace("_", " ").split()
                    if any(dw.startswith(keyword) for dw in defn_words):
                        phase3.append((ns, op, defn))
            phase3.sort(key=_canon_score)
            results.extend(phase3)

        return results

    def extract_intent_keywords(self, nl_text: str) -> ComposedIntent:
        """Extract intent from NL using phrase-first matching and keyword fallback.

        Pipeline:
          1. Extract numeric conditions and targets via regex
          2. Scan for multi-word phrase matches (longest-first) from the
             generation index built from ASD definitions
          3. Fall back to single-word keyword matching for unmatched positions
          4. Return structured ComposedIntent for grammar assembly

        The generation index ensures multi-word concepts like "heart rate",
        "blood pressure", "emergency stop" match as phrases before their
        component words are matched individually against wrong namespaces.
        """
        import re

        raw = nl_text.strip()
        raw_lower = raw.lower()
        # Tokenize: split on whitespace, strip punctuation from each token
        import string as _string
        words = [w.strip(_string.punctuation) for w in raw_lower.split()]
        words = [w for w in words if w]  # drop empty tokens
        actions: list[str] = []
        conditions: list[str] = []
        targets: list[str] = []
        parameters: dict[str, str] = {}

        # Extract numeric conditions (e.g., "above 130", "> 38")
        cond_pattern = re.compile(
            r'(above|over|below|under|exceeds?|greater than|less than|higher than|lower than)\s+(\d+\.?\d*)',
            re.IGNORECASE,
        )
        for match in cond_pattern.finditer(raw):
            op_word = match.group(1).lower()
            value = match.group(2)
            sal_op = self._CONDITION_MAP.get(op_word, ">")
            conditions.append(f"{sal_op}{value}")

        # Extract parametric values (e.g., "temperature 0.3" -> :0.3)
        param_pattern = re.compile(
            r'(?:temperature|top.?p|top.?k|max.?tokens?)\s+(\d+\.?\d*)',
            re.IGNORECASE,
        )
        for match in param_pattern.finditer(raw):
            parameters[match.group(0).split()[0].lower()] = match.group(1)

        # Extract scheduling intervals: "every N (seconds|minutes|hours|days)"
        # Produces parameters['schedule'] = "30s" / "5m" / "1h" / "1d"
        # When this fires, the composer prepends T:SCHED[Ns]→ to the resolved chain.
        sched_pattern = re.compile(
            r'every\s+(\d+\.?\d*)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\b',
            re.IGNORECASE,
        )
        m = sched_pattern.search(raw)
        if m:
            n, unit = m.group(1), m.group(2).lower()
            unit_short = (
                's' if unit.startswith('s') else
                'm' if unit.startswith('m') else
                'h' if unit.startswith('h') else
                'd' if unit.startswith('d') else 's'
            )
            parameters['schedule'] = f"{n}{unit_short}"

        # Extract explicit time anchors: "at HH:MM" / "at Nam" / "at Npm" / "tonight at X"
        # Produces parameters['at_time'] = "2AM" / "00:00" etc.
        at_pattern = re.compile(
            r'(?:at|by)\s+(\d{1,2}(?::\d{2})?(?:\s*[ap]m)?|midnight|noon)\b',
            re.IGNORECASE,
        )
        m = at_pattern.search(raw)
        if m:
            t = m.group(1).upper().replace(' ', '')
            parameters['at_time'] = t

        # Extract ICD/diagnostic codes (e.g., "code J93.0", "ICD J93.0")
        icd_pattern = re.compile(
            r'(?:code|icd|diagnosis|icd-10)\s+([A-Z]\d{2}\.?\d*)',
            re.IGNORECASE,
        )
        for match in icd_pattern.finditer(raw):
            # Normalize: remove dots for OSMP format (J93.0 -> J930)
            code = match.group(1).replace(".", "")
            parameters["icd"] = code

        # Extract targets — priority order, first-match wins:
        # 1. Structured entity patterns: "drone N", "node N", "patient N",
        #    "sensor N", "vehicle N", "gateway N", "turbine N", "valve V",
        #    "door D-N", "agent NAME". These bind the SUBJECT of the action
        #    as the target. Strong signal because the entity has a number/id.
        # 2. Action-verb + bare noun: "stop X", "close X", "open X", "lock X",
        #    "unlock X", "kill X", "reboot X" — X becomes the target.
        # 3. Generic preposition pattern: "on/at/to/@ X". Lowest priority
        #    because words like "coordinates" can pollute. Only fires if
        #    nothing else binds.
        entity_pattern = re.compile(
            r'\b(drone|node|patient|sensor|vehicle|vessel|gateway|turbine|server|valve|door|agent|host|relay|gate|building|cluster|peer|robot|device|station|tank|reactor)\s+([\w-]+)',
            re.IGNORECASE,
        )
        entity_targets = []
        for match in entity_pattern.finditer(raw):
            entity_kind, entity_id = match.group(1).lower(), match.group(2).upper()
            # The "id" must look like an identifier, not a common noun.
            # Real identifiers: numeric (17), alphanumeric with digits (D-7),
            # all-uppercase NATO-style names (BRAVO, ALPHA, FOXTROT).
            # Common nouns ("status", "position", "feedback") get rejected
            # because they're operands, not identifiers.
            is_identifier = (
                entity_id.isdigit()
                or any(c.isdigit() for c in entity_id)
                or (entity_id.isalpha() and entity_id.isupper() and len(entity_id) >= 3
                    and entity_id.lower() not in {
                        "the", "and", "but", "for", "from", "with", "that",
                        "this", "all", "any", "some", "the", "is", "are",
                        "status", "position", "heading", "feedback",
                        "control", "context", "service", "system",
                    })
            )
            if not is_identifier:
                continue
            # Drone/vehicle/UAV: kind-prefixed target (DRONE1, VEHICLE7, etc.)
            # Other entities: bare id (17, BRAVO).
            if entity_kind in {"drone", "vehicle", "vessel", "uav", "patient"}:
                entity_targets.append(f"{entity_kind.upper()}{entity_id}")
            else:
                entity_targets.append(entity_id)

        # Action-verb + bare noun: "stop pump" → @PUMP, "close valve" → @VALVE
        action_verb_pattern = re.compile(
            r'\b(stop|close|open|lock|unlock|kill|reboot|restart|shutdown|start|halt)\s+(?:the\s+)?(\w+)',
            re.IGNORECASE,
        )
        action_verb_targets = []
        for match in action_verb_pattern.finditer(raw):
            obj = match.group(2).upper()
            if obj.lower() not in {"the", "a", "an", "and", "everything", "this", "that", "it"}:
                action_verb_targets.append(obj)

        # Generic preposition pattern (lowest priority — lots of false positives like "coordinates")
        prep_pattern = re.compile(r'(?<!\w)(?:on|at|to|@)\s+(\w+)', re.IGNORECASE)
        prep_targets = []
        for match in prep_pattern.finditer(raw):
            t = match.group(1).upper()
            # Skip generic words that aren't real targets
            if t.lower() not in {"coordinates", "the", "a", "an", "this", "that"}:
                prep_targets.append(t)

        # Compose targets in priority order, dedupe
        for t in entity_targets + action_verb_targets + prep_targets:
            if t not in targets:
                targets.append(t)

        # ── Phase 1: Phrase-first matching (generation index) ────────────
        # Scan for multi-word phrases longest-first. Use word boundaries
        # to prevent partial matches (e.g., "th" inside "the").
        # Mark matched character positions so word matching doesn't overlap.
        import re as _re
        matched_spans: list[tuple[int, int]] = []
        for phrase in self._phrases_by_length:
            # Word-boundary match: phrase must be bounded by non-word chars or string edges
            pattern = r'(?<!\w)' + _re.escape(phrase) + r'(?!\w)'
            m = _re.search(pattern, raw_lower)
            if m:
                idx, end = m.start(), m.end()
                # Check this span doesn't overlap already-matched spans
                overlaps = any(
                    not (end <= s[0] or idx >= s[1])
                    for s in matched_spans
                )
                if not overlaps:
                    matched_spans.append((idx, end))
                    actions.append(phrase)

        # Build set of word positions consumed by phrase matches
        consumed_positions: set[int] = set()
        for span_start, span_end in matched_spans:
            # Map character spans to word positions
            char_pos = 0
            for i, word in enumerate(words):
                word_start = raw_lower.find(word, char_pos)
                word_end = word_start + len(word)
                if word_start >= span_start and word_end <= span_end:
                    consumed_positions.add(i)
                char_pos = word_end

        # ── Phase 2: Single-word keyword fallback ────────────────────────
        # Only process words not consumed by phrase matches.
        # Skip articles, pronouns, prepositions, AND wrapper verbs.
        #
        # Wrapper verbs (report/log/broadcast/fetch/retrieve/announce/publish/
        # submit/transmit) are linguistic packaging — they frame a query in
        # English, but in OSMP the opcode IS intrinsically the query/response.
        # Doctrine: opcodes do not need a separate "report" verb because the
        # frame itself denotes the report. Strip them so they never resolve
        # to L:REPORT/A:SHOW wrappers that bloat the SAL chain.
        _SKIP_WORDS = {
            'the', 'and', 'for', 'from', 'with', 'that', 'this', 'when',
            'then', 'turn', 'get', 'set', 'put', 'make', 'give', 'take',
            'show', 'tell', 'let', 'use', 'try', 'see', 'ask',
            'how', 'what', 'where', 'who', 'why', 'can', 'will', 'has',
            'have', 'does', 'did', 'are', 'was', 'been', 'being', 'many',
            'much', 'some', 'any', 'all', 'each', 'every', 'other',
            'about', 'into', 'over', 'after', 'before', 'between',
            'but', 'only', 'just', 'also', 'too', 'very', 'really',
            'it', 'its', "it's", 'me', 'my', 'your', 'our', 'their',
            'him', 'her', 'his', 'them', 'going', 'goes', 'went',
            'you', 'need', 'want', 'know', 'like', 'think', 'would',
            'post', 'photo', 'caption', 'book', 'order', 'send',
            # Wrapper verbs — opcode IS the query/response in OSMP
            'report', 'log', 'broadcast', 'fetch', 'retrieve',
            'announce', 'publish', 'submit', 'transmit',
            # Read-suffix nouns — they modify the actual operand, not opcode-bearing
            # ("humidity reading" -> operand is "humidity"; "blood pressure check" -> "blood pressure")
            'reading', 'check', 'level', 'feedback',
            # Generic referent nouns — they're objects of actions, not actions themselves
            'payload', 'data', 'message', 'request', 'response', 'content',
            'file', 'item', 'value', 'result', 'thing',
            'service', 'system', 'device', 'node', 'gateway', 'server',
            'task', 'context', 'process', 'pair', 'session',
            # Code-as-context — "code J93.0" is a parametric slot for ICD; the word itself isn't opcode-bearing
            'code', 'codes', 'identifier', 'id',
            # Activation verbs — generic "make this happen", not opcode-bearing on their own
            # (the OPERAND has the opcode: "activate haptic" -> R:HAPTIC, not "activate")
            'activate', 'enable', 'engage', 'launch', 'execute', 'run',
            # Auxiliary creator verbs — wrappers around the operand opcode
            # ("generate a key" -> S:KEYGEN via "key pair" or "key" lookup, not Y:EMBED via "generate")
            'generate', 'create', 'produce', 'make',
            # Approval / authorization verbs — handled by curated synonyms below or composition logic
            'sign-off', 'confirm', 'confirms',
            # Body parts when used generically as adjective-like context
            # ("heart rate" is a phrase that maps to H:HR; the index handles it)
        }
        # Build set of all 2-char opcode names for short-word matching
        _SHORT_OPCODES = set()
        for _ns, _ops in ASD_BASIS.items():
            for _op in _ops:
                if len(_op) <= 2:
                    _SHORT_OPCODES.add(_op.lower())

        for i, word in enumerate(words):
            if i in consumed_positions:
                continue
            # Allow short words (2 chars) if they're exact opcode names
            if len(word) == 2 and word.upper() not in {op.upper() for op in _SHORT_OPCODES}:
                continue
            if len(word) < 2:
                continue
            if word in _SKIP_WORDS:
                continue
            if len(word) > 2 or word in _SHORT_OPCODES:
                matches = self.lookup_by_keyword(word)
                if matches:
                    actions.append(word)

        return ComposedIntent(
            actions=actions,
            conditions=conditions,
            targets=targets,
            parameters=parameters,
            raw=raw,
        )

    # Chain separators detected in NL for split-then-compose.
    # Each separator maps to the SAL operator that joins the segments.
    # Order matters: longer/more-specific patterns first.
    _CHAIN_SEPARATORS: list[tuple[str, str]] = [
        # Sequential (strict order, non-conditional)
        (r',\s+then\s+', ';'),
        (r',\s+and\s+then\s+', ';'),
        (r'\s+then\s+', ';'),
        (r'\s+next\s+', ';'),
        # Conditional ("if X, then Y" or "if X above N, Y")
        # These are handled by condition extraction, not chain split
        # Conjunction (concurrent) — most-specific first
        (r',\s+and\s+', '\u2227'),
        # Bare " and " — splits action-and-action chains like
        # "stop pump and close valve". Greedy match risk: "temp and humidity"
        # also splits, which is correct (E:TH and E:HU). The risk is
        # phrasal "and" that should NOT split (e.g., "salt and pepper");
        # those typically don't carry opcodes anyway, so safe to split.
        (r'\s+and\s+', '\u2227'),
    ]

    def _try_chain_split(self, nl_text: str) -> str | None:
        """Try to split NL into chain segments and compose each independently.

        Returns a composed SAL chain (using ; or ∧) or None if the NL
        doesn't contain chain separators OR if any segment fails to compose.
        """
        import re as _re_split

        # Find the first matching separator pattern in the NL
        # If the NL contains conditional language ("if"), fall through
        # to the normal single-composition path
        nl_lower = nl_text.lower()
        if ' if ' in nl_lower or nl_lower.startswith('if '):
            return None  # conditional chains handled by existing logic

        # Try each separator pattern
        for pattern, operator in self._CHAIN_SEPARATORS:
            segments = _re_split.split(pattern, nl_text, flags=_re_split.IGNORECASE)
            if len(segments) >= 2:
                # Clean segments
                segments = [s.strip().rstrip('.,;') for s in segments if s.strip()]
                if len(segments) < 2:
                    continue

                # Compose each segment independently
                composed_segments = []
                for seg in segments:
                    if len(seg.encode("utf-8")) < 4:
                        return None  # segment too short
                    # Recursive compose with chain-split disabled to avoid infinite loop
                    seg_sal = self._compose_single(seg)
                    if seg_sal is None:
                        return None  # any segment fails → whole chain fails
                    composed_segments.append(seg_sal)

                if len(composed_segments) >= 2:
                    return operator.join(composed_segments)
                return None

        return None

    def _compose_single(self, nl_text: str,
                       intent: ComposedIntent | None = None) -> str | None:
        """Single-segment composition — used by chain-split and top-level compose."""
        return self._compose_impl(nl_text, intent)

    def compose(self, nl_text: str,
                intent: ComposedIntent | None = None) -> str | None:
        """Compose valid SAL from natural language.

        Composition pipeline (in priority order):
          1. Brigade composer (parser → IR → 26 namespace stations →
             orchestrator → validator). Hits 0 WRONG / 0 INVALID when
             stations resolve. Available since v2.4.
          2. Legacy chain-split path (preserved for inputs the brigade
             returns None for — e.g., novel chain shapes).
          3. Legacy single-segment _compose_impl (keyword-stacker fallback).

        The brigade is the safety floor; the legacy paths broaden coverage
        with explicit fallback when the brigade abstains.

        Returns validated SAL string or None if all paths return None.
        """
        # Brigade is the primary path — only when no caller-supplied intent
        if intent is None:
            try:
                # Lazy import to avoid module-load cycle on legacy consumers
                from .brigade import Orchestrator as _BrigadeOrch
                if not hasattr(self.__class__, "_brigade_singleton"):
                    self.__class__._brigade_singleton = _BrigadeOrch()
                brigade_sal = self.__class__._brigade_singleton.compose(nl_text)
                if brigade_sal is not None:
                    return brigade_sal
                # Brigade returned None — fall through to legacy paths.
                # Brigade's None means "no station resolved confidently" —
                # the legacy keyword stacker may still find something.
            except Exception:
                pass  # any brigade error → fall through, never break compose

            # Legacy chain-split (preserved)
            chain_sal = self._try_chain_split(nl_text)
            if chain_sal is not None:
                result = validate_composition(chain_sal, nl=nl_text)
                if result.valid:
                    return chain_sal

        return self._compose_impl(nl_text, intent)

    def _compose_impl(self, nl_text: str,
                      intent: ComposedIntent | None = None) -> str | None:
        """Core composition logic (was compose, now internal).

        If intent is provided (e.g., from an LLM extraction step), uses it
        directly. Otherwise falls back to keyword-based intent extraction.
        """
        if intent is None:
            intent = self.extract_intent_keywords(nl_text)

        # BAEL byte pre-check: if the NL input is very short, any SAL
        # encoding will be larger. Short inputs (< 6 bytes) can't compress.
        # The minimum SAL frame is 4 bytes (X:Y) + operator overhead.
        nl_bytes = len(nl_text.encode("utf-8"))
        if nl_bytes < 6:
            return None  # too short to compress — NL passthrough

        # Step 0: Exclusive-keyword overrides — when these tokens appear,
        # they select a single canonical opcode and short-circuit composition.
        # Doctrine: "emergency stop" / "stop everything immediately, emergency"
        # MUST emit R:ESTOP only — never chained with R:STOP↻ (those are
        # contradictory actions; the conjunction would fire both).
        nl_low = nl_text.lower()
        if "emergency" in nl_low and ("stop" in nl_low or "halt" in nl_low or "everything" in nl_low):
            return "R:ESTOP"

        # Step 1: Check macros first (composition priority hierarchy)
        if self.macro_registry:
            for macro in self.macro_registry.list_macros():
                for trigger in macro.triggers:
                    if trigger.lower() in intent.raw.lower():
                        # Found a macro match -- this is the preferred path
                        # Caller handles slot-fill separately
                        return f"A:MACRO[{macro.macro_id}]"

        # Step 2: ASD lookup for each action keyword/phrase
        resolved_opcodes: list[tuple[str, str]] = []
        has_phrase_match = False
        for action in intent.actions:
            # Phrase match against generation index first
            if action in self._phrase_index:
                ns, op = self._phrase_index[action]
                if (ns, op) not in resolved_opcodes:
                    resolved_opcodes.append((ns, op))
                has_phrase_match = True
                continue
            # Fall back to keyword lookup
            matches = self.lookup_by_keyword(action)
            if matches:
                ns, op, _ = matches[0]
                if (ns, op) not in resolved_opcodes:
                    resolved_opcodes.append((ns, op))

        # Parameter-driven opcode injection: when intent extraction found
        # parametric values, ensure the corresponding opcodes are resolved
        if intent.parameters.get("icd") and ("H", "ICD") not in resolved_opcodes:
            resolved_opcodes.insert(0, ("H", "ICD"))
        if intent.parameters.get("temperature") and ("Z", "TEMP") not in resolved_opcodes:
            resolved_opcodes.append(("Z", "TEMP"))
        if intent.parameters.get("top-p") and ("Z", "TOPP") not in resolved_opcodes:
            resolved_opcodes.append(("Z", "TOPP"))
        # Schedule parameter: when "every N (seconds|minutes|hours|days)"
        # fires, prepend T:SCHED so the resulting chain becomes
        # T:SCHED[interval]→<rest>
        if intent.parameters.get("schedule") and ("T", "SCHED") not in resolved_opcodes:
            resolved_opcodes.insert(0, ("T", "SCHED"))

        # Conditional-alert namespace preference: when a condition operates
        # on a sensing namespace AND L:ALERT (compliance default) is in the
        # resolved set, swap L:ALERT for the namespace-appropriate alert.
        # H sensing -> H:ALERT (clinical), W sensing -> W:ALERT (weather).
        # E sensing -> U:NOTIFY (operator notify, since L:ALERT is also valid for E).
        if intent.conditions and ("L", "ALERT") in resolved_opcodes:
            sensing_namespaces = {ns for ns, _ in resolved_opcodes if ns in {"H", "W", "E"}}
            if "H" in sensing_namespaces:
                resolved_opcodes = [
                    (("H", "ALERT") if (ns, op) == ("L", "ALERT") else (ns, op))
                    for ns, op in resolved_opcodes
                ]
            elif "W" in sensing_namespaces:
                resolved_opcodes = [
                    (("W", "ALERT") if (ns, op) == ("L", "ALERT") else (ns, op))
                    for ns, op in resolved_opcodes
                ]

        if not resolved_opcodes:
            return None  # nothing resolved -- NL passthrough

        # Confidence gate: prevent false positives from keyword noise.
        # Three levels of filtering based on match quality.
        if not has_phrase_match and not intent.conditions:
            def _is_strong_match(ns: str, op: str, actions: list[str]) -> bool:
                """A strong match: action word closely matches the opcode."""
                defn = ASD_BASIS.get(ns, {}).get(op, "")
                for action in actions:
                    a = action.upper()
                    # Direct opcode name match (e.g., "stop" == "STOP", "temp" == "TEMP")
                    if a == op:
                        return True
                    # Exact full definition match (e.g., "move" == "move")
                    defn_clean = defn.lower().replace("_", " ")
                    if action.lower() == defn_clean and len(action) >= 4:
                        return True
                    # Action is a prefix of a definition word (e.g., "temp" starts "temperature")
                    # Require 4+ chars to prevent short false positives ("post" ≠ "posture")
                    for dw in defn_clean.split():
                        if len(action) >= 4 and dw.startswith(action.lower()) and len(dw) >= len(action) + 2:
                            return True
                    # Opcode is prefix of action (e.g., "encrypt" starts with "ENC")
                    if len(op) >= 3 and a.startswith(op) and len(action) >= len(op) + 3:
                        return True
                return False

            def _definition_matches_context(ns: str, op: str, nl: str) -> bool:
                """Check if the definition's domain qualifiers appear in the NL.

                Catches false positives like "cost" -> Z:COST where the definition
                is "inference_cost_report" but the NL says "calculate the total cost"
                with no inference context.
                """
                defn = ASD_BASIS.get(ns, {}).get(op, "")
                defn_words = defn.lower().replace("_", " ").split()
                if len(defn_words) <= 1:
                    return True  # single-word definition, no qualifier to check
                nl_lower = nl.lower()
                # Check if definition qualifier words appear in the NL
                qualifier_words = [w for w in defn_words if len(w) > 3]
                exact_matches = 0
                prefix_matches = 0
                for qw in qualifier_words:
                    if qw in nl_lower:
                        exact_matches += 1
                    else:
                        for nl_word in nl_lower.split():
                            if len(nl_word) >= 4 and qw.startswith(nl_word):
                                prefix_matches += 1
                                break
                # Require 2 exact matches OR 1 exact + 1 prefix OR 1 prefix with strong signal
                if exact_matches >= 2:
                    return True
                if exact_matches >= 1 and prefix_matches >= 1:
                    return True
                if prefix_matches >= 1 and len(defn_words) <= 2:
                    return True  # short definition, prefix is enough
                return False

            if len(resolved_opcodes) == 1:
                ns, op = resolved_opcodes[0]
                if not _is_strong_match(ns, op, intent.actions):
                    return None
                if not _definition_matches_context(ns, op, nl_text):
                    return None
            elif len(resolved_opcodes) == 2:
                strong = sum(
                    1 for ns, op in resolved_opcodes
                    if _is_strong_match(ns, op, intent.actions)
                )
                if strong == 0:
                    return None
            elif len(resolved_opcodes) >= 3:
                # 3+ keyword matches with no phrase: require at least one
                # strong match (direct opcode name match or exact definition
                # match). If zero strong matches, it's keyword noise.
                strong = sum(
                    1 for ns, op in resolved_opcodes
                    if _is_strong_match(ns, op, intent.actions)
                )
                if strong == 0:
                    return None

        # OOV chain gap detection: if the NL contains step separators
        # ("then", "and then", comma-separated clauses) and any step
        # has no opcode match, the chain is incomplete. Passthrough
        # rather than silently dropping the unresolved step.
        if resolved_opcodes and not has_phrase_match:
            import re as _re_chain
            # Split on chain separators (commas, "then", "and then")
            segments = _re_chain.split(
                r',\s+then\s+|,\s+and\s+then\s+|\bthen\b|,\s+',
                nl_text.lower()
            )
            if len(segments) >= 3:
                # Multi-step chain: check each segment has a match
                unresolved = 0
                for seg in segments:
                    seg = seg.strip()
                    if not seg or len(seg) < 5:
                        continue
                    seg_has_match = False
                    for ns, op in resolved_opcodes:
                        defn = ASD_BASIS.get(ns, {}).get(op, "")
                        defn_words = defn.lower().replace("_", " ").split()
                        if any(w in seg for w in defn_words if len(w) > 3):
                            seg_has_match = True
                            break
                    if not seg_has_match:
                        unresolved += 1
                if unresolved > 0:
                    return None  # chain has OOV gap, passthrough

        # Step 3: Grammar assembly
        # Sort: sensing/data namespaces before action namespaces when
        # conditions are present (condition attaches to the sensing frame)
        if intent.conditions and len(resolved_opcodes) > 1:
            sensing = [(ns, op) for ns, op in resolved_opcodes
                       if ns in self._SENSING_NS]
            acting = [(ns, op) for ns, op in resolved_opcodes
                      if ns in self._ACTION_NS]
            other = [(ns, op) for ns, op in resolved_opcodes
                     if ns not in self._SENSING_NS and ns not in self._ACTION_NS]
            resolved_opcodes = sensing + other + acting

        frames: list[str] = []
        for ns, op in resolved_opcodes:
            frame = f"{ns}:{op}"

            # Attach parametric values (e.g., Z:TEMP:0.3)
            if ns == "H" and op == "ICD" and intent.parameters.get("icd"):
                frame += f"[{intent.parameters['icd']}]"
            elif ns == "Z" and op == "TEMP" and intent.parameters.get("temperature"):
                frame += f":{intent.parameters['temperature']}"
            elif ns == "Z" and op == "TOPP" and intent.parameters.get("top-p"):
                frame += f":{intent.parameters['top-p']}"
            elif ns == "T" and op == "SCHED" and intent.parameters.get("schedule"):
                frame += f"[{intent.parameters['schedule']}]"
            elif ns == "T" and op == "EXP" and intent.parameters.get("schedule"):
                # T:EXP[interval] for "expire in N hour"
                frame += f"[{intent.parameters['schedule']}]"

            # Attach target if available (skip common false positives)
            valid_targets = [t for t in intent.targets
                           if t not in ('THE', 'A', 'AN', 'THIS', 'THAT', 'MY', 'YOUR',
                                        'IT', 'THEM', 'HIM', 'HER', 'ME', 'EVERYTHING',
                                        'TEMPERATURE', 'IS', 'SOME', 'ALL')]
            if valid_targets:
                frame += f"@{valid_targets[0]}"
            # R namespace: add default consequence class (REVERSIBLE)
            # R:ESTOP is the sole exception (no CC required)
            if ns == "R" and op != "ESTOP":
                frame += "\u21ba"  # REVERSIBLE default
            frames.append(frame)

        # Attach conditions to the first frame if present
        if intent.conditions and frames:
            condition = intent.conditions[0]
            frames[0] = frames[0] + condition

        # Join frames with appropriate operator
        if len(frames) == 1:
            sal = frames[0]
        elif intent.conditions or intent.parameters.get("schedule"):
            # Conditional or scheduled chain: sequential ->
            sal = "\u2192".join(frames)
        else:
            # Conjunctive: action AND action
            sal = "\u2227".join(frames)

        # Step 4: Validate
        result = validate_composition(sal, nl=nl_text)
        if result.valid:
            return sal

        # If validation failed, try without conditions (simpler form)
        if intent.conditions and len(frames) > 1:
            sal_simple = "\u2227".join(
                f"{ns}:{op}" for ns, op in resolved_opcodes
            )
            result = validate_composition(sal_simple, nl=nl_text)
            if result.valid:
                return sal_simple

        # BAEL-aware single-frame fallback: when the chain busts the byte
        # floor (typical for short inputs like "report heading" producing
        # L:REPORT\u2227G:BEARING at 20B vs 14B NL), try the operand-only
        # frame. The wrapper (REPORT, SEND, SHOW, BROADCAST, LOG) is
        # implicit in the receiving context for sensor/data namespaces;
        # the domain opcode alone carries the meaning.
        #
        # WRAPPER opcodes that should NEVER stand alone in a fallback:
        # they would change the meaning (L:REPORT alone = "compliance
        # report", not "report a value").
        _WRAPPER_FRAMES = {
            ("L", "REPORT"), ("L", "SEND"), ("L", "LOG"),
            ("A", "SHOW"), ("A", "BROADCAST"),
            ("Q", "RPRT"),
        }
        # Only fall back to single-frame when AT LEAST ONE frame is a wrapper.
        # If all frames are operands, dropping any of them changes the
        # decoded action — that's a safety violation (e.g., T:SCHED→A:PING
        # collapsing to A:PING drops the schedule, fires continuously
        # instead of every N seconds). When all frames are essential,
        # passthrough is correct.
        if len(frames) > 1:
            has_wrapper = any((ns, op) in _WRAPPER_FRAMES for ns, op in resolved_opcodes)
            if has_wrapper:
                operand_pairs = [
                    (ns, op) for ns, op in resolved_opcodes
                    if (ns, op) not in _WRAPPER_FRAMES
                ]
                valid_singles: list[str] = []
                for ns, op in operand_pairs:
                    f = f"{ns}:{op}"
                    r = validate_composition(f, nl=nl_text)
                    if r.valid:
                        valid_singles.append(f)
                if valid_singles:
                    return min(valid_singles, key=lambda s: len(s.encode("utf-8")))

        return None  # composition failed validation

    def compose_or_passthrough(self, nl_text: str,
                               intent: ComposedIntent | None = None
                               ) -> tuple[str, bool]:
        """Compose SAL or return NL passthrough.

        Returns (output, is_sal) where is_sal indicates whether the output
        is composed SAL or original natural language.
        """
        sal = self.compose(nl_text, intent=intent)
        if sal is not None:
            return sal, True
        return nl_text, False


# ── Registered Macro Architecture ──────────────────────────────────────────
#
# A registered macro is a pre-validated multi-step SAL instruction chain
# template stored alongside regular opcodes. Macros eliminate the composition
# step for deterministic workflows: the agent's task is deterministic lookup
# and slot-fill, not opcode-by-opcode composition.
#
# Composition priority hierarchy (spec Section 11):
#   1. Macro invocation (pre-validated, no composition error surface)
#   2. Individual opcode composition (grammar-constrained)
#   3. Natural language passthrough (no compression)

@dataclass(frozen=True)
class SlotDefinition:
    """A typed parameter slot in a macro chain template."""
    name: str
    slot_type: str = "string"  # string, uint, float, enum, bool
    namespace: str | None = None  # optional namespace hint for Layer 2 accessors


@dataclass(frozen=True)
class MacroTemplate:
    """A pre-validated multi-step SAL instruction chain template.

    The chain_template contains namespace-prefixed opcodes connected by glyph
    operators, with {slot_name} placeholders at positions where the invoking
    agent supplies context-specific values.

    Example:
        macro_id = "MESH:DEV"
        chain_template = "X:STORE[bat:{battery_level}]∧X:VOLT[v:{voltage}]"
        slots = (SlotDefinition("battery_level", "uint"),
                 SlotDefinition("voltage", "float"))
    """
    macro_id: str
    chain_template: str
    slots: tuple[SlotDefinition, ...]
    description: str
    consequence_class: str | None = None
    triggers: tuple[str, ...] = ()


# Consequence class severity ordering for inheritance
_CC_SEVERITY: dict[str, int] = {
    "\u21ba": 1,  # REVERSIBLE
    "\u26a0": 2,  # HAZARDOUS
    "\u2298": 3,  # IRREVERSIBLE
}
_CC_BY_SEVERITY: dict[int, str] = {v: k for k, v in _CC_SEVERITY.items()}


class MacroRegistry:
    """Registry of pre-validated SAL instruction chain templates.

    Macros are an ASD extension: stored alongside regular opcodes, queried
    through the same lookup path, but with template expansion triggered when
    A:MACRO is detected.

    Patent pending
    License: Apache 2.0
    """

    def __init__(self, asd: AdaptiveSharedDictionary | None = None):
        self.asd = asd or AdaptiveSharedDictionary()
        self._macros: dict[str, MacroTemplate] = {}

    def register(self, template: MacroTemplate) -> None:
        """Register a macro template.

        Validates that every opcode in the chain exists in the ASD and that
        all slot placeholders have matching SlotDefinitions. Computes the
        inherited consequence class from the chain.
        """
        # Validate opcodes in chain exist in ASD
        chain = template.chain_template
        # Strip slot placeholders before opcode validation
        import re as _re
        clean = _re.sub(r'\{[^}]+\}', 'X', chain)
        parts = _FRAME_SPLIT_RE.split(clean)
        frames = [p.strip() for p in parts
                  if p.strip() and p.strip() not in ("\u2192", "\u2227", "\u2228", "\u2194", "\u2225", ";", "->")]
        for frame in frames:
            m = _FRAME_NS_OP_RE.match(frame)
            if m:
                ns, op = m.group(1), m.group(2)
                if self.asd.lookup(ns, op) is None:
                    raise ValueError(
                        f"Macro {template.macro_id}: opcode {ns}:{op} "
                        f"not found in ASD"
                    )

        # Validate slot placeholders have matching definitions
        placeholders = set(_re.findall(r'\{(\w+)\}', template.chain_template))
        defined_slots = {s.name for s in template.slots}
        missing = placeholders - defined_slots
        if missing:
            raise ValueError(
                f"Macro {template.macro_id}: slot placeholders {missing} "
                f"have no matching SlotDefinition"
            )
        extra = defined_slots - placeholders
        if extra:
            raise ValueError(
                f"Macro {template.macro_id}: SlotDefinitions {extra} "
                f"have no matching placeholder in chain template"
            )

        # Compute inherited consequence class
        cc = self._compute_inherited_cc(clean)

        # Store with computed CC if not explicitly set
        if template.consequence_class is None and cc is not None:
            template = MacroTemplate(
                macro_id=template.macro_id,
                chain_template=template.chain_template,
                slots=template.slots,
                description=template.description,
                consequence_class=cc,
                triggers=template.triggers,
            )

        self._macros[template.macro_id] = template

    def lookup(self, macro_id: str) -> MacroTemplate | None:
        """Look up a registered macro by ID."""
        return self._macros.get(macro_id)

    def expand(self, macro_id: str,
               slot_values: dict[str, str | int | float]) -> str:
        """Expand a macro with slot values.

        Returns the fully expanded SAL chain with all placeholders
        substituted. This is the "slot-fill" operation the patent describes.
        """
        template = self._macros.get(macro_id)
        if template is None:
            raise KeyError(f"Macro not found: {macro_id}")

        # Verify all required slots are provided
        required = {s.name for s in template.slots}
        provided = set(slot_values.keys())
        missing = required - provided
        if missing:
            raise ValueError(
                f"Macro {macro_id}: missing slot values: {missing}"
            )

        # Substitute placeholders
        result = template.chain_template
        for name, value in slot_values.items():
            result = result.replace(f"{{{name}}}", str(value))

        return result

    def encode_compact(self, macro_id: str,
                       slot_values: dict[str, str | int | float]) -> str:
        """Encode a macro invocation in compact wire format.

        Compact format: A:MACRO[macro_id]:slot1[val1]:slot2[val2]...
        Used when both nodes share the macro definition.
        """
        template = self._macros.get(macro_id)
        if template is None:
            raise KeyError(f"Macro not found: {macro_id}")

        parts = [f"A:MACRO[{macro_id}]"]
        for slot_def in template.slots:
            if slot_def.name in slot_values:
                parts.append(f":{slot_def.name}[{slot_values[slot_def.name]}]")

        result = "".join(parts)

        # Append inherited consequence class if present
        if template.consequence_class:
            result += template.consequence_class

        return result

    def encode_expanded(self, macro_id: str,
                        slot_values: dict[str, str | int | float]) -> str:
        """Encode a macro invocation in expanded wire format.

        Expanded format: the full chain with values substituted.
        Used when the receiving node doesn't have the macro definition.
        """
        return self.expand(macro_id, slot_values)

    def encode_with_annotation(self, macro_id: str,
                               slot_values: dict[str, str | int | float]
                               ) -> str:
        """Encode compact form with expansion annotation.

        The _EXP slot carries the fully expanded chain for monitoring.
        Non-authoritative: receiver always expands from local ASD.
        Included at unconstrained bandwidth, omitted at constrained.
        """
        compact = self.encode_compact(macro_id, slot_values)
        expanded = self.expand(macro_id, slot_values)
        # Insert _EXP before any trailing consequence class
        if compact[-1] in "\u21ba\u26a0\u2298":
            cc = compact[-1]
            base = compact[:-1]
            return f"{base}:_EXP[{expanded}]{cc}"
        return f"{compact}:_EXP[{expanded}]"

    def inherited_consequence_class(self, macro_id: str) -> str | None:
        """Get the inherited consequence class for a macro.

        Scans the chain template for R namespace instructions and returns
        the highest severity consequence class found.
        IRREVERSIBLE > HAZARDOUS > REVERSIBLE > None
        """
        template = self._macros.get(macro_id)
        if template is None:
            return None
        return template.consequence_class

    def _compute_inherited_cc(self, clean_chain: str) -> str | None:
        """Compute the highest consequence class from a chain's R frames."""
        max_severity = 0
        # Check for consequence class glyphs after R: frames
        parts = _FRAME_SPLIT_RE.split(clean_chain)
        for part in parts:
            part = part.strip()
            if not part or part in ("\u2192", "\u2227", "\u2228", "\u2194", "\u2225", ";", "->"):
                continue
            # Check if this frame is R namespace
            m = _FRAME_NS_OP_RE.match(part)
            if m and m.group(1) == "R":
                # Check for trailing consequence class
                for cc_glyph, severity in _CC_SEVERITY.items():
                    if cc_glyph in part:
                        max_severity = max(max_severity, severity)

        return _CC_BY_SEVERITY.get(max_severity)

    def list_macros(self) -> list[MacroTemplate]:
        """List all registered macros."""
        return list(self._macros.values())

    def load_corpus(self, corpus_path: str | Path) -> int:
        """Load macro definitions from a JSON corpus file.

        Returns the count of macros successfully loaded.
        """
        import json
        corpus_path = Path(corpus_path)
        with open(corpus_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for entry in data.get("macros", []):
            slots = tuple(
                SlotDefinition(
                    name=s["name"],
                    slot_type=s.get("slot_type", "string"),
                    namespace=s.get("namespace"),
                )
                for s in entry.get("slots", [])
            )
            template = MacroTemplate(
                macro_id=entry["macro_id"],
                chain_template=entry["chain_template"],
                slots=slots,
                description=entry.get("description", ""),
                triggers=tuple(entry.get("triggers", ())),
            )
            self.register(template)
            count += 1

        return count


@dataclass
class DecodedInstruction:
    namespace:             str
    opcode:                str
    opcode_meaning:        str | None
    target:                str | None
    query_slot:            str | None
    slots:                 dict[str, str]
    consequence_class:     str | None
    consequence_class_name: str | None
    raw:                   str


class SALDecoder:
    """
    Inference-free SAL decoder.
    All parsing is deterministic — structured output, no inference — no statistical models, no ambiguity resolution.
    Analog: HPACK static table decode (RFC 7541 §A).
    """

    def __init__(self, asd: AdaptiveSharedDictionary | None = None):
        self.asd = asd or AdaptiveSharedDictionary()

    def _resolve_short_form(self, opcode: str) -> str:
        """Resolve namespace for short-form frames by ASD lookup.
        Returns first matching namespace, or 'A' as default."""
        for ns, ops in ASD_BASIS.items():
            if opcode in ops:
                return ns
        return "A"

    def _first_stop(self, s: str, stops: list[str]) -> int:
        earliest = len(s)
        for sc in stops:
            idx = s.find(sc)
            if idx != -1 and idx < earliest:
                earliest = idx
        return earliest

    def decode_frame(self, encoded: str) -> DecodedInstruction:
        raw = encoded.strip()
        remaining = raw

        # Extract consequence class suffix (R namespace)
        cc = None
        cc_name = None
        for glyph, entry in CONSEQUENCE_CLASSES.items():
            if remaining.endswith(glyph):
                cc = glyph
                cc_name = entry["name"]
                runes = list(remaining)
                glyph_runes = list(glyph)
                remaining = "".join(runes[:-len(glyph_runes)])
                break

        # Detect explicit namespace (colon before first @ or ?)
        before_target = remaining.split("@")[0].split("?")[0]
        has_explicit_ns = ":" in before_target

        namespace: str
        if has_explicit_ns:
            first_colon = remaining.index(":")
            namespace = remaining[:first_colon]
            remaining = remaining[first_colon + 1:]
        else:
            pre = remaining.split("@")[0].split("?")[0]
            namespace = self._resolve_short_form(pre)

        # Extract opcode
        opcode_end = self._first_stop(remaining, ["@", "?", ":"])
        opcode = remaining[:opcode_end]
        remaining = remaining[opcode_end:]

        opcode_meaning = self.asd.lookup(namespace, opcode)

        # Extract target
        target = None
        if remaining.startswith("@"):
            remaining = remaining[1:]
            end = self._first_stop(remaining, ["?", ":", "∧", "∨", "→", "↔", ";", "∥"])
            target = remaining[:end]
            remaining = remaining[end:]

        # Extract query slot
        query_slot = None
        if remaining.startswith("?"):
            remaining = remaining[1:]
            end = self._first_stop(remaining, [":", "∧", "∨", "→", ";"])
            query_slot = remaining[:end]
            remaining = remaining[end:]

        # Extract slot assignments
        slots: dict[str, str] = {}
        while remaining.startswith(":"):
            remaining = remaining[1:]
            colon_idx = remaining.find(":")
            if colon_idx == -1:
                slots[remaining] = ""
                remaining = ""
                break
            slot_name = remaining[:colon_idx]
            remaining = remaining[colon_idx + 1:]
            val_end = self._first_stop(remaining, [":", "∧", "∨", "→", ";", "⚠", "↺", "⊘"])
            slots[slot_name] = remaining[:val_end]
            remaining = remaining[val_end:]

        return DecodedInstruction(
            namespace=namespace, opcode=opcode, opcode_meaning=opcode_meaning,
            target=target, query_slot=query_slot, slots=slots,
            consequence_class=cc, consequence_class_name=cc_name, raw=raw,
        )

    # Operator glyph to readable NL word mapping
    _OPERATOR_NL: dict[str, str] = {
        "\u2192": " then ",     # → THEN
        "->":     " then ",     # → ASCII shorthand
        "\u2227": " and ",      # ∧ AND
        "\u2228": " or ",       # ∨ OR
        "\u2194": " iff ",      # ↔ IFF
        "\u2225": " parallel ", # ∥ PARALLEL
        ";": ", then ",         # ; SEQUENCE
    }

    def decode_natural_language(self, encoded: str) -> str:
        """Decode a SAL string to human-readable natural language.

        Handles all chain operators (→ ∧ ∨ ↔ ∥ ;), not just semicolons.
        Each frame is decoded independently and operators are converted
        to readable English words. Multi-frame chains get a leading
        primary domain label based on the most frequent namespace.

        This is the single source of truth for SAL→NL conversion. The Tier 1
        ``osmp.decode()`` wrapper and the ``SALBridge`` outbound translator both
        delegate to this method without additional chain handling.
        """
        # Split on all chain operators, preserving the operators
        parts = _FRAME_SPLIT_RE.split(encoded)
        if not parts:
            return ""

        result_parts = []
        frame_count = 0
        ns_counts: dict[str, int] = {}
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part in self._OPERATOR_NL:
                result_parts.append(self._OPERATOR_NL[part])
            else:
                decoded = self._decode_single_frame(part)
                result_parts.append(decoded)
                frame_count += 1
                # Track namespace frequency for primary domain
                m = _FRAME_NS_OP_RE.match(part)
                if m:
                    ns = m.group(1)
                    ns_counts[ns] = ns_counts.get(ns, 0) + 1

        body = "".join(result_parts).strip()

        # For multi-namespace chains, prepend primary domain
        if frame_count > 1 and len(ns_counts) > 1:
            primary_ns = max(ns_counts, key=ns_counts.get)
            primary_domain = self._NS_DOMAIN.get(primary_ns, "")
            if primary_domain:
                return f"({primary_domain}) {body}"

        return body

    # Namespace to readable domain label for decode context
    _NS_DOMAIN: dict[str, str] = {
        "A": "protocol", "B": "building", "C": "compute", "D": "data",
        "E": "sensor", "F": "flow control", "G": "geospatial", "H": "clinical",
        "I": "identity", "J": "cognitive", "K": "financial", "L": "audit",
        "M": "emergency", "N": "network", "O": "operations", "P": "maintenance",
        "Q": "quality", "R": "physical", "S": "security", "T": "time",
        "U": "operator", "V": "maritime", "W": "weather", "X": "energy",
        "Y": "memory", "Z": "inference",
    }

    def _decode_single_frame(self, encoded: str) -> str:
        """Decode exactly one SAL frame to its human-readable NL form.

        Output includes domain context from the namespace and readable
        target descriptions. Format:
          [domain] action_description [condition] [at target] [slots]
        """
        import re as _re

        # Extract and strip condition from the raw frame before decode
        # (e.g., H:HR>130 → decode H:HR, condition >130)
        cond_match = _re.search(r'([><=!]+)(\d+\.?\d*)', encoded)
        clean_encoded = encoded
        if cond_match:
            clean_encoded = encoded[:cond_match.start()] + encoded[cond_match.end():]

        try:
            d = self.decode_frame(clean_encoded)
        except Exception:
            return f"[malformed: {encoded!r}]"

        # Domain context from namespace
        domain = self._NS_DOMAIN.get(d.namespace, "")
        # Use the definition text (spaces instead of underscores) as the NL form
        meaning = (d.opcode_meaning or d.opcode).replace("_", " ")

        parts = []
        if domain:
            parts.append(f"[{domain}]")
        parts.append(meaning)

        if cond_match:
            op_map = {">": "above", "<": "below", "=": "equals",
                      ">=": "at least", "<=": "at most", "!=": "not"}
            op_word = op_map.get(cond_match.group(1), cond_match.group(1))
            parts.append(f"{op_word} {cond_match.group(2)}")
        if d.target:
            parts.append(f"at {'all nodes' if d.target == '*' else d.target}")
        if d.query_slot:
            parts.append(f"query {d.query_slot}")
        for k, v in d.slots.items():
            parts.append(f"{k}={v}")
        if d.consequence_class_name:
            parts.append(f"[{d.consequence_class_name}]")
        return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# OVERFLOW PROTOCOL
# ─────────────────────────────────────────────────────────────────────────────

class LossPolicy(Enum):
    FAIL_SAFE            = "Φ"
    GRACEFUL_DEGRADATION = "Γ"
    ATOMIC               = "Λ"


@dataclass
class Fragment:
    msg_id:   int
    frag_idx: int
    frag_ct:  int
    flags:    int
    dep:      int
    payload:  bytes

    @property
    def is_terminal(self) -> bool:
        return bool(self.flags & FLAG_TERMINAL)

    @property
    def is_critical(self) -> bool:
        return bool(self.flags & FLAG_CRITICAL)

    def pack(self) -> bytes:
        return struct.pack(">HBBBB", self.msg_id, self.frag_idx,
                           self.frag_ct, self.flags, self.dep) + self.payload

    @classmethod
    def unpack(cls, data: bytes) -> "Fragment":
        if len(data) < FRAGMENT_HEADER_BYTES:
            raise ValueError(f"Fragment too short: {len(data)} bytes")
        msg_id, fi, fc, flags, dep = struct.unpack(">HBBBB", data[:6])
        return cls(msg_id=msg_id, frag_idx=fi, frag_ct=fc,
                   flags=flags, dep=dep, payload=data[6:])


class OverflowProtocol:
    """
    Three-tier fragmentation with loss tolerance.

    Tier 1: Single packet
    Tier 2: Sequential burst
    Tier 3: DAG decomposition

    Analog: QUIC receive buffer (RFC 9000 §2.2)
    """

    def __init__(self, mtu: int = LORA_STANDARD_BYTES,
                 policy: LossPolicy = LossPolicy.GRACEFUL_DEGRADATION,
                 timeout: int = 30):
        self.mtu = mtu
        self.policy = policy
        self.timeout = timeout
        self._msg_counter = 0
        self._buffer: dict[int, dict[int, Fragment]] = {}
        self._dag_reassembler = DAGReassembler(policy=policy)

    def _next_msg_id(self) -> int:
        self._msg_counter = (self._msg_counter + 1) % 65536
        return self._msg_counter

    def fragment(self, payload: bytes, critical: bool = False) -> list[Fragment]:
        available = self.mtu - FRAGMENT_HEADER_BYTES
        if len(payload) + FRAGMENT_HEADER_BYTES <= self.mtu:
            return [Fragment(
                msg_id=self._next_msg_id(), frag_idx=0, frag_ct=1,
                flags=FLAG_TERMINAL | (FLAG_CRITICAL if critical else 0),
                dep=0, payload=payload,
            )]
        chunks = [payload[i:i + available] for i in range(0, len(payload), available)]
        msg_id = self._next_msg_id()
        frags = []
        for idx, chunk in enumerate(chunks):
            is_last = idx == len(chunks) - 1
            flags = (FLAG_TERMINAL if is_last else 0) | (FLAG_CRITICAL if critical else 0)
            frags.append(Fragment(msg_id=msg_id, frag_idx=idx, frag_ct=len(chunks),
                                  flags=flags, dep=0, payload=chunk))
        return frags

    def fragment_dag(self, compound_sal: str,
                     critical: bool = False) -> list[Fragment]:
        """Tier 3: decompose a compound SAL instruction into a DAG of fragments.

        Use when the instruction contains conditional branches (→),
        parallel forks (∧, ∥), or sequential dependencies (;) that
        require dependency-aware execution order on the receiver.
        """
        fragmenter = DAGFragmenter(mtu=self.mtu)
        msg_id = self._next_msg_id()
        return fragmenter.fragmentize(compound_sal, msg_id, critical=critical)

    def receive(self, frag: Fragment) -> bytes | None:
        # R:ESTOP hard exception — execute immediately regardless of policy
        # Asymmetric harm: unnecessary stop is recoverable; failure to stop is not.
        if b"R:ESTOP" in frag.payload:
            return frag.payload

        mid = frag.msg_id
        if mid not in self._buffer:
            self._buffer[mid] = {}
        self._buffer[mid][frag.frag_idx] = frag
        received = self._buffer[mid]
        expected = frag.frag_ct

        if self.policy == LossPolicy.ATOMIC or frag.is_critical:
            if len(received) == expected:
                return self._reassemble(received, expected)
            return None
        elif self.policy == LossPolicy.GRACEFUL_DEGRADATION:
            if frag.is_terminal and len(received) == expected:
                return self._reassemble(received, expected)
            if frag.is_terminal:
                return self._reassemble_partial(received, expected)
            return None
        else:  # FAIL_SAFE
            if len(received) == expected:
                return self._reassemble(received, expected)
            return None

    def _reassemble(self, received: dict, expected: int) -> bytes:
        return b"".join(received[i].payload for i in range(expected))

    def _reassemble_partial(self, received: dict, expected: int) -> bytes:
        result = b""
        for i in range(expected):
            if i not in received:
                break
            result += received[i].payload
        return result

    def receive_dag(self, frag: Fragment) -> list[bytes] | None:
        """Tier 3 receive: buffer fragment and attempt DAG resolution.

        Returns ordered list of payloads in dependency-resolved execution
        order, or None if the message is not yet resolvable under the
        current loss tolerance policy.
        """
        return self._dag_reassembler.receive(frag)

    def nack(self, msg_id: int, expected_ct: int) -> str:
        have = set(self._buffer.get(msg_id, {}).keys())
        missing = sorted(set(range(expected_ct)) - have)
        return f"A:NACK[MSG:{msg_id}∖[{','.join(str(i) for i in missing)}]]"


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3 — DAG DECOMPOSITION
# Overflow Protocol Tier 3: directed acyclic graph fragmentation for
# instructions with conditional branches and dependency chains.
# Analog: Kahn's algorithm (1962) applied to lossy radio fragment streams.
#
# Spec section 8.1 Tier 3 definition.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DAGNode:
    """Single executable unit in a Tier 3 DAG."""
    index:   int            # fragment index (position in fragment list)
    payload: bytes          # SAL instruction bytes for this unit
    parents: list[int]      # indices of parent nodes (dependencies)


class DAGFragmenter:
    """
    Transmit-side Tier 3: decompose a compound SAL instruction into a DAG
    of executable units with dependency pointers.

    The SAL compound operators define the DAG structure:
      ;  (SEQUENCE)  — linear chain: right depends on left
      →  (THEN)      — conditional: right depends on left
      ∧  (AND)       — parallel: both depend on same parent (fork)
      ∥  (PARALLEL)  — parallel execution block

    Single-parent dependencies use the DEP header byte directly.
    Multi-parent dependencies (e.g., diamond join) set FLAGS bit 3
    (FLAG_EXTENDED_DEP) and prefix the payload with a 4-byte u32 bitmap
    where bit N = dependency on fragment N.

    Fragment header remains 6 bytes. Backward compatible: Tier 1/2
    fragments with DEP=0x00 and FLAGS bit 3 clear are unchanged.
    """

    def __init__(self, mtu: int = LORA_STANDARD_BYTES):
        self.mtu = mtu

    def parse(self, compound_sal: str) -> list[DAGNode]:
        """Parse a compound SAL string into DAGNodes.

        Recognizes ; → ∧ ∥ as structural operators.
        Atomic SAL frames become leaf nodes.
        """
        nodes: list[DAGNode] = []
        self._parse_expr(compound_sal.strip(), nodes, parent_indices=[])
        return nodes

    def _parse_expr(self, expr: str, nodes: list[DAGNode],
                    parent_indices: list[int]) -> list[int]:
        """Recursively parse SAL expression into DAG nodes.
        Returns list of tail node indices (nodes with no dependents yet)."""

        # Try splitting on ; (SEQUENCE) first — lowest precedence
        parts = self._split_top_level(expr, ";")
        if len(parts) > 1:
            tails = parent_indices
            for part in parts:
                tails = self._parse_expr(part.strip(), nodes, tails)
            return tails

        # Try → (THEN) — conditional chain
        parts = self._split_top_level(expr, "→")
        if len(parts) > 1:
            tails = parent_indices
            for part in parts:
                tails = self._parse_expr(part.strip(), nodes, tails)
            return tails

        # Try ∧ (AND) — parallel fork
        parts = self._split_top_level(expr, "∧")
        if len(parts) > 1:
            all_tails: list[int] = []
            for part in parts:
                branch_tails = self._parse_expr(part.strip(), nodes, parent_indices)
                all_tails.extend(branch_tails)
            return all_tails

        # Try ∥ inside A∥[...] — parallel execution block
        if expr.startswith("A∥[") and expr.endswith("]"):
            inner = expr[len("A∥["):-1]
            parts = self._split_top_level(inner, "∧")
            if len(parts) <= 1:
                # Single item in parallel block, treat as leaf
                parts = [inner]
            all_tails = []
            for part in parts:
                clean = part.strip()
                if clean.startswith("?"):
                    clean = clean[1:]
                branch_tails = self._parse_expr(clean, nodes, parent_indices)
                all_tails.extend(branch_tails)
            return all_tails

        # Atomic leaf node
        idx = len(nodes)
        nodes.append(DAGNode(
            index=idx,
            payload=expr.encode("utf-8"),
            parents=list(parent_indices),
        ))
        return [idx]

    @staticmethod
    def _split_top_level(expr: str, sep: str) -> list[str]:
        """Split expression on separator, respecting bracket depth."""
        parts: list[str] = []
        depth = 0
        current: list[str] = []
        i = 0
        chars = list(expr)
        sep_chars = list(sep)
        sep_len = len(sep_chars)

        while i < len(chars):
            ch = chars[i]
            if ch in ("[", "("):
                depth += 1
                current.append(ch)
                i += 1
            elif ch in ("]", ")"):
                depth -= 1
                current.append(ch)
                i += 1
            elif depth == 0 and chars[i:i + sep_len] == sep_chars:
                parts.append("".join(current))
                current = []
                i += sep_len
            else:
                current.append(ch)
                i += 1
        if current:
            parts.append("".join(current))
        return parts

    def fragmentize(self, compound_sal: str, msg_id: int,
                    critical: bool = False) -> list[Fragment]:
        """Full Tier 3 pipeline: parse → assign DEP → emit Fragments."""
        nodes = self.parse(compound_sal)
        if not nodes:
            return []

        frag_ct = len(nodes)
        frags: list[Fragment] = []

        for node in nodes:
            is_last = node.index == frag_ct - 1
            flags = (FLAG_TERMINAL if is_last else 0) | \
                    (FLAG_CRITICAL if critical else 0)

            if len(node.parents) == 0:
                # Root node: self-reference signals no dependency
                # DEP == frag_idx is unambiguous (cannot depend on self)
                dep = node.index
                payload = node.payload
            elif len(node.parents) == 1:
                # Single parent: use DEP byte directly
                dep = node.parents[0]
                payload = node.payload
            else:
                # Multi-parent: set extended dep flag, prefix with bitmap
                flags |= FLAG_EXTENDED_DEP
                dep = node.parents[0]  # primary dep in header for legacy readers
                bitmap = 0
                for p in node.parents:
                    bitmap |= (1 << p)
                payload = struct.pack(">I", bitmap) + node.payload

            frags.append(Fragment(
                msg_id=msg_id, frag_idx=node.index, frag_ct=frag_ct,
                flags=flags, dep=dep, payload=payload,
            ))

        return frags


class DAGReassembler:
    """
    Receive-side Tier 3: buffer fragments, resolve dependency DAG,
    execute in topological order under loss tolerance policy.

    Execution semantics:
      - Topological sort of received fragments whose full ancestor
        chains are present.
      - Under Gamma: execute maximal resolvable subgraph.
      - Under Lambda: execute nothing unless all fragments received.
      - Under Phi: discard everything if any fragment missing.
      - R:ESTOP overrides everything: executes immediately on receipt.
    """

    def __init__(self, policy: LossPolicy = LossPolicy.GRACEFUL_DEGRADATION):
        self.policy = policy
        self._buffer: dict[int, dict[int, Fragment]] = {}  # msg_id -> {frag_idx: Fragment}

    def receive(self, frag: Fragment) -> list[bytes] | None:
        """Buffer a fragment and attempt DAG resolution.

        Returns ordered list of payloads in execution order, or None if
        the message is not yet resolvable.
        """
        # R:ESTOP hard exception — immediate execution, no DAG resolution
        if b"R:ESTOP" in frag.payload:
            return [frag.payload]

        mid = frag.msg_id
        if mid not in self._buffer:
            self._buffer[mid] = {}
        self._buffer[mid][frag.frag_idx] = frag
        received = self._buffer[mid]
        expected = frag.frag_ct

        # Check completeness based on policy
        if self.policy == LossPolicy.FAIL_SAFE:
            if len(received) == expected:
                return self._resolve_dag(received, expected)
            return None

        elif self.policy == LossPolicy.ATOMIC:
            if len(received) == expected:
                return self._resolve_dag(received, expected)
            return None

        else:  # GRACEFUL_DEGRADATION
            if frag.is_terminal and len(received) == expected:
                return self._resolve_dag(received, expected)
            if frag.is_terminal:
                return self._resolve_dag_partial(received, expected)
            return None

    def _get_parents(self, frag: Fragment) -> list[int]:
        """Extract parent dependencies from a fragment.

        Root convention: DEP == frag_idx (self-reference) means no dependency.
        This is unambiguous because a fragment cannot depend on itself.
        """
        if frag.flags & FLAG_EXTENDED_DEP:
            # Multi-parent: first 4 bytes of payload are u32 bitmap
            if len(frag.payload) < 4:
                return []
            bitmap = struct.unpack(">I", frag.payload[:4])[0]
            return [i for i in range(32) if bitmap & (1 << i)]
        else:
            # Self-reference = root node (no dependency)
            if frag.dep == frag.frag_idx:
                return []
            return [frag.dep]

    def _get_payload(self, frag: Fragment) -> bytes:
        """Extract the actual payload, stripping dependency bitmap if present."""
        if frag.flags & FLAG_EXTENDED_DEP:
            return frag.payload[4:]
        return frag.payload

    def _resolve_dag(self, received: dict[int, Fragment],
                     expected: int) -> list[bytes]:
        """Full DAG resolution: all fragments present. Topological sort."""
        # Build adjacency: parent -> children
        order = self._topo_sort(received, set(received.keys()))
        return [self._get_payload(received[i]) for i in order]

    def _resolve_dag_partial(self, received: dict[int, Fragment],
                             expected: int) -> list[bytes]:
        """Graceful Degradation: execute maximal resolvable subgraph.

        A fragment is executable iff ALL its ancestors in the DAG
        have been received.
        """
        present = set(received.keys())
        # Find executable set: fragments whose full ancestor chain is present
        executable: set[int] = set()
        for idx in present:
            if self._ancestors_satisfied(received, idx, present):
                executable.add(idx)

        if not executable:
            return []

        order = self._topo_sort(received, executable)
        return [self._get_payload(received[i]) for i in order]

    def _ancestors_satisfied(self, received: dict[int, Fragment],
                             idx: int, present: set[int]) -> bool:
        """Check if all ancestors of fragment idx are in present set."""
        visited: set[int] = set()
        stack = [idx]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            if current not in present:
                return False
            if current in received:
                parents = self._get_parents(received[current])
                for p in parents:
                    if p not in visited:
                        stack.append(p)
        return True

    def _topo_sort(self, received: dict[int, Fragment],
                   node_set: set[int]) -> list[int]:
        """Kahn's algorithm over the executable node set."""
        # Build in-degree map restricted to node_set
        in_degree: dict[int, int] = {i: 0 for i in node_set}
        children: dict[int, list[int]] = {i: [] for i in node_set}

        for idx in node_set:
            parents = self._get_parents(received[idx])
            for p in parents:
                if p in node_set:
                    in_degree[idx] += 1
                    children[p].append(idx)

        # Seed with zero in-degree (root nodes)
        queue = sorted(i for i in node_set if in_degree[i] == 0)
        order: list[int] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for child in sorted(children.get(node, [])):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return order

    def nack(self, msg_id: int, expected_ct: int) -> str:
        """Generate NACK for missing fragments in a DAG message."""
        have = set(self._buffer.get(msg_id, {}).keys())
        missing = sorted(set(range(expected_ct)) - have)
        return f"A:NACK[MSG:{msg_id}∖[{','.join(str(i) for i in missing)}]]"


# ─────────────────────────────────────────────────────────────────────────────
# TWO-TIER COMPRESSOR — TCL + LZMA
# Analog: Zim file format (Kiwix offline Wikipedia distribution)
# ─────────────────────────────────────────────────────────────────────────────

class TwoTierCompressor:
    def compress(self, text: str) -> bytes:
        return lzma.compress(text.encode("utf-8"), preset=6)

    def decompress(self, data: bytes) -> str:
        return lzma.decompress(data).decode("utf-8")

    def compression_ratio(self, original: str, compressed: bytes) -> float:
        orig_b = len(original.encode("utf-8"))
        return 0.0 if orig_b == 0 else 1.0 - (len(compressed) / orig_b)


# ─────────────────────────────────────────────────────────────────────────────
# BLOCK COMPRESSOR — D:PACK/BLK profile (zstd, random-access, MCU target)
#
# Binary format: DBLK v1
#   Header (24 bytes):
#     magic         4B   "DBLK"
#     version       u16  BE, currently 1
#     flags         u16  BE, bit 0 = has trained dictionary
#     block_count   u32  BE
#     dict_offset   u32  BE, byte offset from file start
#     dict_size     u32  BE, 0 if no dictionary
#     blocks_offset u32  BE, byte offset to start of compressed block data
#   Block table (block_count * 44 bytes, immediately after header):
#     first_code    32B  null-padded UTF-8, first entry key in block
#     block_offset  u32  BE, relative to blocks_offset
#     block_csize   u32  BE, compressed size in bytes
#     entry_count   u16  BE
#     reserved      2B   zero
#   Dictionary section (dict_size bytes)
#   Block data section (concatenated compressed blocks)
#
# Each decompressed block contains sorted lines: "MDR_TOKEN\tSAL_TEXT\n"
# Resolution path:
#   1. Binary search block table by first_code
#   2. Read + decompress one block from flash
#   3. Linear scan within block for target code
#   4. Return SAL text
#
# Target: ESP32 class (520KB SRAM, 4-16MB flash)
# Peak decompression memory: ~38KB per block (one block at a time)
# ─────────────────────────────────────────────────────────────────────────────

DBLK_MAGIC = b"DBLK"
DBLK_VERSION = 1
DBLK_HEADER_SIZE = 24
DBLK_BTABLE_ENTRY_SIZE = 44
DBLK_FIRST_CODE_SIZE = 32
DBLK_DEFAULT_BLOCK_TARGET = 32 * 1024  # 32KB decompressed target
DBLK_ZSTD_LEVEL = 19
DBLK_DICT_SIZE = 32768


class BlockCompressor:
    """D:PACK/BLK profile: zstd block-level compression with random access.

    Designed for microcontroller targets where full-corpus decompression
    (as required by the LZMA profile) exceeds available SRAM.  Each code
    resolves by decompressing a single ~32KB block.
    """

    def __init__(
        self,
        block_target: int = DBLK_DEFAULT_BLOCK_TARGET,
        zstd_level: int = DBLK_ZSTD_LEVEL,
        dict_size: int = DBLK_DICT_SIZE,
        use_dict: bool = True,
    ):
        if not _HAS_ZSTD:
            raise ImportError(
                "zstandard package required for D:PACK/BLK profile. "
                "Install with: pip install zstandard"
            )
        self.block_target = block_target
        self.zstd_level = zstd_level
        self.dict_size_target = dict_size
        self.use_dict = use_dict

    # ── packing ──────────────────────────────────────────────────────────

    def pack(
        self,
        entries: list[tuple[str, str]],
    ) -> bytes:
        """Pack sorted (mdr_token, sal_text) entries into a DBLK binary.

        Parameters
        ----------
        entries : list of (mdr_token, sal_text) tuples, sorted by mdr_token.

        Returns
        -------
        bytes : complete DBLK binary.
        """
        # ── partition into blocks ────────────────────────────────────────
        blocks: list[list[tuple[str, str]]] = []
        current: list[tuple[str, str]] = []
        current_size = 0
        for code, sal in entries:
            entry_bytes = len(sal.encode("utf-8"))
            if current_size + entry_bytes > self.block_target and current:
                blocks.append(current[:])
                current = []
                current_size = 0
            current.append((code, sal))
            current_size += entry_bytes
        if current:
            blocks.append(current)

        # ── build raw block payloads ─────────────────────────────────────
        raw_payloads: list[bytes] = []
        for block_entries in blocks:
            lines = [f"{code}\t{sal}" for code, sal in block_entries]
            raw_payloads.append("\n".join(lines).encode("utf-8"))

        # ── train dictionary (optional) ──────────────────────────────────
        dict_data = None
        dict_bytes = b""
        if self.use_dict and len(raw_payloads) > 1:
            dict_data = zstd.train_dictionary(
                self.dict_size_target, raw_payloads
            )
            dict_bytes = dict_data.as_bytes()

        # ── compress blocks ──────────────────────────────────────────────
        cctx = zstd.ZstdCompressor(
            level=self.zstd_level,
            dict_data=dict_data,
        )
        compressed_payloads: list[bytes] = []
        for raw in raw_payloads:
            compressed_payloads.append(cctx.compress(raw))

        # ── assemble binary ──────────────────────────────────────────────
        block_count = len(blocks)
        btable_size = block_count * DBLK_BTABLE_ENTRY_SIZE
        dict_offset = DBLK_HEADER_SIZE + btable_size
        blocks_offset = dict_offset + len(dict_bytes)

        # header
        hdr = bytearray()
        hdr += DBLK_MAGIC
        hdr += struct.pack(">H", DBLK_VERSION)
        hdr += struct.pack(">H", 1 if dict_bytes else 0)  # flags
        hdr += struct.pack(">I", block_count)
        hdr += struct.pack(">I", dict_offset)
        hdr += struct.pack(">I", len(dict_bytes))
        hdr += struct.pack(">I", blocks_offset)

        # block table
        btable = bytearray()
        blk_offset = 0
        for i, block_entries in enumerate(blocks):
            fc = block_entries[0][0].encode("utf-8")[:DBLK_FIRST_CODE_SIZE].ljust(
                DBLK_FIRST_CODE_SIZE, b"\x00"
            )
            btable += fc
            btable += struct.pack(">I", blk_offset)
            btable += struct.pack(">I", len(compressed_payloads[i]))
            btable += struct.pack(">H", len(block_entries))
            btable += b"\x00\x00"
            blk_offset += len(compressed_payloads[i])

        return bytes(hdr) + bytes(btable) + dict_bytes + b"".join(
            compressed_payloads
        )

    # ── unpacking / single-code resolution ───────────────────────────────

    @staticmethod
    def _parse_header(data: bytes) -> dict:
        if data[:4] != DBLK_MAGIC:
            raise ValueError("Not a DBLK binary (bad magic)")
        return {
            "version": struct.unpack(">H", data[4:6])[0],
            "flags": struct.unpack(">H", data[6:8])[0],
            "block_count": struct.unpack(">I", data[8:12])[0],
            "dict_offset": struct.unpack(">I", data[12:16])[0],
            "dict_size": struct.unpack(">I", data[16:20])[0],
            "blocks_offset": struct.unpack(">I", data[20:24])[0],
        }

    @staticmethod
    def _find_block(data: bytes, hdr: dict, code: str) -> int:
        """Binary search block table, return block index."""
        code_b = code.encode("utf-8")
        lo, hi = 0, hdr["block_count"] - 1
        result = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            off = DBLK_HEADER_SIZE + mid * DBLK_BTABLE_ENTRY_SIZE
            fc = data[off : off + DBLK_FIRST_CODE_SIZE].rstrip(b"\x00")
            if fc <= code_b:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    def _decompress_block(self, data: bytes, hdr: dict, blk_idx: int) -> bytes:
        """Decompress a single block by index."""
        entry_off = DBLK_HEADER_SIZE + blk_idx * DBLK_BTABLE_ENTRY_SIZE
        fc_end = DBLK_FIRST_CODE_SIZE
        blk_offset = struct.unpack(">I", data[entry_off + fc_end : entry_off + fc_end + 4])[0]
        blk_csize = struct.unpack(">I", data[entry_off + fc_end + 4 : entry_off + fc_end + 8])[0]

        dict_data = None
        if hdr["flags"] & 1 and hdr["dict_size"] > 0:
            db = data[hdr["dict_offset"] : hdr["dict_offset"] + hdr["dict_size"]]
            dict_data = zstd.ZstdCompressionDict(db)

        dctx = zstd.ZstdDecompressor(dict_data=dict_data)
        start = hdr["blocks_offset"] + blk_offset
        return dctx.decompress(
            data[start : start + blk_csize],
            max_output_size=self.block_target + 8192,
        )

    @staticmethod
    def _search_block(raw: bytes, code: str) -> str | None:
        """Linear scan a decompressed block for a code."""
        for line in raw.decode("utf-8").split("\n"):
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[0] == code:
                return parts[1]
        return None

    def resolve(self, data: bytes, code: str) -> str | None:
        """Resolve a single MDR token to SAL text from a DBLK binary.

        Decompresses only the block containing the target code.
        When the block table first_code field truncates a long key,
        the binary search may overshoot by one block; if the code
        is not found in the candidate block, the previous block is
        checked before returning None.

        Input normalization
        -------------------
        For ICD-10-CM and similar code systems where the canonical CMS
        format strips decimal points from codes (J93.0 -> J930), this
        method tries the input verbatim first, then if not found and
        the input contains a ``.``, retries with the dot removed. This
        allows callers to pass either ``"J93.0"`` (the form a doctor or
        an LLM trained on real ICD documentation will produce) or
        ``"J930"`` (the canonical CMS dpack key) interchangeably.

        Parameters
        ----------
        data : bytes, the complete DBLK binary (or a memoryview/mmap).
        code : str, the MDR token to look up.

        Returns
        -------
        str or None : SAL description text, or None if not found.
        """
        hdr = self._parse_header(data)

        result = self._lookup_exact(data, hdr, code)
        if result is not None:
            return result

        # Dot normalization fallback: strip "." and retry. Covers the
        # ICD-10-CM real-form -> CMS-form mapping (J93.0 -> J930) and
        # any similar code system that uses dots for human readability
        # but stores undotted keys in the canonical corpus.
        if "." in code:
            normalized = code.replace(".", "")
            return self._lookup_exact(data, hdr, normalized)

        return None

    def _lookup_exact(self, data: bytes, hdr: dict, code: str) -> str | None:
        """Internal: exact-match block search with truncation fallback."""
        blk_idx = self._find_block(data, hdr, code)

        raw = self._decompress_block(data, hdr, blk_idx)
        result = self._search_block(raw, code)
        if result is not None:
            return result

        # Truncation fallback: try previous block
        if blk_idx > 0:
            raw = self._decompress_block(data, hdr, blk_idx - 1)
            return self._search_block(raw, code)
        return None

    def unpack_all(self, data: bytes) -> dict[str, str]:
        """Decompress all blocks and return full {mdr_token: sal_text} dict."""
        hdr = self._parse_header(data)
        result: dict[str, str] = {}

        for i in range(hdr["block_count"]):
            raw = self._decompress_block(data, hdr, i)
            for line in raw.decode("utf-8").split("\n"):
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    result[parts[0]] = parts[1]
        return result

    def stats(self, data: bytes) -> dict:
        """Return structural statistics for a DBLK binary."""
        hdr = self._parse_header(data)
        btable_bytes = hdr["block_count"] * DBLK_BTABLE_ENTRY_SIZE
        block_data_size = len(data) - hdr["blocks_offset"]
        return {
            "total_bytes": len(data),
            "header_bytes": DBLK_HEADER_SIZE,
            "btable_bytes": btable_bytes,
            "dict_bytes": hdr["dict_size"],
            "block_data_bytes": block_data_size,
            "block_count": hdr["block_count"],
            "block_target": self.block_target,
        }


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def utf8_bytes(s: str) -> int:
    return len(s.encode("utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────

def run_benchmark(vectors_path: str | None = None) -> dict:
    if vectors_path is None:
        vectors_path = str(
            Path(__file__).parent.parent.parent.parent /
            "protocol" / "test-vectors" / "canonical-test-vectors.json"
        )
    with open(vectors_path, encoding="utf-8") as f:
        data = json.load(f)

    decoder   = SALDecoder()
    results   = []
    passed    = 0
    must_total = 0
    threshold = data["compression_summary"]["conformance_threshold_pct"]

    print(f"\n{'='*72}")
    print(f"  OSMP BENCHMARK — Cloudless Sky Protocol v{data['version']}")
    print(f"  Measurement: {data['measurement_basis']}")
    print(f"  SDK: Python (reference)")
    print(f"{'='*72}\n")
    print(f"  {'ID':<10} {'NL Bytes':>8} {'OSMP Bytes':>10} {'Reduction':>10}  Status")
    print(f"  {'-'*60}")

    for vec in data["vectors"]:
        nl_b   = utf8_bytes(vec["natural_language"])
        osmp_b = utf8_bytes(vec["encoded"])
        red    = round((1 - osmp_b / nl_b) * 100, 1)
        conf   = red >= threshold
        status = "PASS" if conf else "LOW"

        if vec["must_pass"]:
            must_total += 1
            if conf:
                passed += 1

        decode_ok = False
        try:
            d = decoder.decode_frame(vec["encoded"])
            decode_ok = bool(d.namespace and d.opcode)
        except Exception:
            status = "FAIL (decode error)"

        marker = "✓" if conf and decode_ok else "✗"
        print(f"  {marker} {vec['id']:<8} {nl_b:>8} {osmp_b:>10} {red:>9.1f}%  {status}")
        results.append({
            "id": vec["id"], "nl_bytes": nl_b, "osmp_bytes": osmp_b,
            "reduction_pct": red, "conformant": conf,
            "decode_ok": decode_ok, "must_pass": vec["must_pass"],
        })

    reds = [r["reduction_pct"] for r in results]
    mean = sum(reds) / len(reds)
    decode_errors = sum(1 for r in results if not r["decode_ok"])
    conformant = mean >= threshold and decode_errors == 0
    verdict = "CONFORMANT ✓" if conformant else "NON-CONFORMANT ✗"

    print(f"\n{'─'*72}")
    print(f"  Vectors:        {len(results)}")
    print(f"  Must-pass:      {must_total}   Passed: {passed}")
    print(f"  Mean reduction: {mean:.1f}%")
    print(f"  Range:          {min(reds):.1f}% – {max(reds):.1f}%")
    print(f"  Conformance threshold: {threshold}%")
    print(f"  Decode errors:  {decode_errors}")
    print(f"\n  {verdict}  (mean {mean:.1f}% vs {threshold}% threshold)")
    print(f"{'='*72}\n")

    return {"conformant": conformant, "mean_reduction_pct": round(mean, 1),
            "decode_errors": decode_errors, "vectors": results}


def run_benchmark_entry():
    run_benchmark()


if __name__ == "__main__":
    enc = SALEncoder()
    dec = SALDecoder()

    demo_nl   = ("If heart rate at node 1 exceeds 120, assemble casualty report "
                 "and broadcast evacuation to all nodes.")
    demo_osmp = "H:HR@NODE1>120→H:CASREP∧M:EVA@*"

    print(f"\n  OSMP — Octid Semantic Mesh Protocol")
    print(f"  Cloudless Sky Project\n")
    print(f"  NL  ({utf8_bytes(demo_nl)} bytes):   {demo_nl}")
    print(f"  SAL ({utf8_bytes(demo_osmp)} bytes): {demo_osmp}")
    print(f"  Reduction: {round((1 - utf8_bytes(demo_osmp)/utf8_bytes(demo_nl))*100,1)}%\n")

    d = dec.decode_frame(demo_osmp)
    print(f"  Decoded: ns={d.namespace} op={d.opcode} "
          f"({d.opcode_meaning}) target={d.target}\n")

    vectors_path = (Path(__file__).parent.parent.parent.parent /
                    "protocol" / "test-vectors" / "canonical-test-vectors.json")
    if vectors_path.exists():
        run_benchmark(str(vectors_path))
    else:
        print(f"  Run from repo root: python3 -m osmp.protocol")
