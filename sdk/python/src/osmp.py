"""
OSMP Python Reference Implementation
Octid Semantic Mesh Protocol — Cloudless Sky Project

Source of truth: OSMP-semantic-dictionary-v12.csv | OSMP-SPEC-v1.md | SAL-grammar.ebnf
All opcode names, definitions, and namespace assignments are drawn directly from the
canonical semantic dictionary v12.0, not from any prior implementation.

Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import json
import lzma
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
# Source: OSMP-semantic-dictionary-v12.csv Section 1, Category 1
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
# Source: dictionary v12 Section 1 Category 2
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


# ─────────────────────────────────────────────────────────────────────────────
# SLOT VALUE ENCODING TABLE
# Source: dictionary v12 Section 2
# Single-character codes for all finite enumerated slot value sets.
# ─────────────────────────────────────────────────────────────────────────────

SLOT_VALUES: dict[str, dict[str, str]] = {
    "C:STAT":      {"A": "active", "D": "degraded", "E": "error", "I": "idle", "O": "offline"},
    "H:TRIAGE":    {"I": "immediate", "D": "delayed", "M": "minor", "B": "black", "X": "expectant"},
    "J:STATUS":    {"A": "active", "B": "blocked", "C": "complete", "F": "failed", "P": "paused"},
    "L:SEV":       {"0": "emergency", "1": "alert", "2": "critical", "3": "error",
                    "4": "warning", "5": "notice", "6": "informational", "7": "debug"},
    "O:AUTH":      {"O": "OPCON", "T": "TACON", "A": "ADCON", "S": "support"},
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
    "O:TYPE":      {"1": "national", "2": "regional_major", "3": "regional",
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
# Source of truth: OSMP-semantic-dictionary-v12.csv Section 3
# Every opcode name and definition drawn directly from the canonical dictionary.
# DO NOT MODIFY opcode names or definitions — they are protocol wire format.
# ─────────────────────────────────────────────────────────────────────────────

ASD_FLOOR_VERSION = "1.0"

ASD_BASIS: dict[str, dict[str, str]] = {
    "A": {
        "ACCEPT":  "accept_proposed_action",
        "ACK":     "positive_acknowledgment",
        "AR":      "agentic_request",
        "AUTH":    "authorization_assertion",
        "CMP":     "compress_compare",
        "CMPR":    "structured_comparison_returning_result",
        "COMP":    "compliance_gate_assertion",
        "DA":      "delegate_to_agent",
        "ERR":     "error_handler",
        "MEM":     "memory_operation",
        "NACK":    "negative_acknowledgment",
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
        "BA":   "building_alert",
        "BS":   "building_sector",
        "HVAC": "hvac_system",
        "L":    "life_safety",
        "X":    "structural",
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
        "RT":     "return_transmit",
        "STAT":   "transfer_status_query",
        "UNPACK": "inference_free_semantic_retrieval_from_encoded_corpus",
        "XFER":   "initiate_file_transfer",
    },
    "E": {
        "EQ":  "environmental_query",
        "GPS": "gps_coordinates",
        "HU":  "humidity",
        "OBS": "obstacle",
        "PU":  "pressure",
        "TH":  "temperature_humidity_composite",
        "UV":  "ultraviolet",
    },
    "F": {
        "AV":  "authorization",
        "PRO": "proceed_protocol",
        "Q":   "query_request",
        "W":   "wait",
    },
    "G": {
        "BEARING": "heading_bearing",
        "CONF":    "position_confidence_rating",
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
        "A":   "alert_alarm",
        "EVA": "evacuation",
        "IT":  "incident_type",
        "MA":  "municipal_alert",
        "RT":  "route",
    },
    "N": {
        "BK":   "backup_node",
        "CFG":  "configure",
        "CMD":  "command_node",
        "INET": "internet_uplink_capability_query",
        "PR":   "primary_relay",
        "Q":    "query_discovery",
        "S":    "status",
    },
    "O": {
        "AUTH":       "authority_level",
        "BW":         "available_bandwidth",
        "CHAN":        "active_channel_type",
        "CONOPS":     "concept_of_operations",
        "CONSTRAINT": "active_constraint_declaration",
        "DESC":        "operational_deescalation",
        "EMCON":      "emission_control_level",
        "ESC":        "operational_escalation",
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
        "TYPE":       "incident_type",
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
        "BENCH":   "benchmark_assertion",
        "CITE":    "cite_source_for_claim",
        "CONF":    "confidence_interval_assertion",
        "CORRECT": "correction_directive",
        "CRIT":    "structured_critique_of_agent_output",
        "EVAL":    "evaluation_result",
        "FAIL":    "quality_gate_fail",
        "FLAG":    "flag_output_unreliable",
        "GROUND":  "grounding_assertion_against_source_document",
        "HALLU":   "hallucination_detection_flag",
        "PASS":    "quality_gate_pass",
        "REFLECT": "self_reflection_on_output_quality",
        "REVISE":  "request_revision_based_on_critique",
        "SCORE":   "quality_score_assertion",
        "VERIFY":  "request_verification_of_claim_by_another_agent",
    },
    "R": {
        # Physical agent opcodes — consequence class mandatory on all R instructions
        "COLLAB":  "collaborative_mode",
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
        "EV":      "ev_charging_state",
        "FAULT":   "fault_event",
        "FREQ":    "grid_frequency",
        "GEN":     "generation_output",
        "GRID":    "grid_connection_status",
        "ISLND":   "islanding_operation",
        "LOAD":    "load_reading",
        "METER":   "meter_reading",
        "PRICE":   "energy_price_signal",
        "RESTORE": "grid_restoration",
        "SHED":    "load_shedding_instruction",
        "SOLAR":   "solar_generation",
        "STORE":   "storage_state",
        "VOLT":    "voltage_level",
        "WIND":    "wind_generation",
    },
    "Y": {
        "CLEAR":    "clear_memory_tier",
        "EMBED":    "generate_embedding_for_storage",
        "FETCH":    "retrieve_by_key",
        "FORGET":   "delete_from_memory",
        "INDEX":    "index_document_for_retrieval",
        "PAGE":     "page_out_working_memory_to_external_store",
        "PROMOTE":  "promote_working_to_long_term_memory",
        "RECALL":   "retrieve_episodic_memory_by_context",
        "RETRIEVE": "retrieve_from_LCS",
        "SEARCH":   "semantic_vector_search",
        "SHARE":    "share_memory_segment_with_another_agent",
        "STAT":     "report_memory_utilization",
        "STORE":    "store_to_memory",
        "SUMM":     "summarize_and_compress_memory_segment",
        "SYNC":     "synchronize_memory_state_with_peer",
    },
    "Z": {
        # Z:INF is the canonical opcode — invoke_inference
        "BATCH":   "batch_inference_request",
        "CACHE":   "kv_cache_utilization_instruction",
        "CAP":     "capability_query",
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
# SAL DECODER
# ─────────────────────────────────────────────────────────────────────────────

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
    All parsing is table lookup — no statistical models, no ambiguity resolution.
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

    def decode_natural_language(self, encoded: str) -> str:
        try:
            d = self.decode_frame(encoded)
        except Exception:
            return f"[malformed: {encoded!r}]"
        parts = [f"{d.namespace}:{d.opcode_meaning or d.opcode}"]
        if d.target:
            parts.append("→*" if d.target == "*" else f"→{d.target}")
        if d.query_slot:
            parts.append(f"?{d.query_slot}")
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
    Tier 3: DAG decomposition (spec-defined, implementation pending)

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

    def nack(self, msg_id: int, expected_ct: int) -> str:
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

        Parameters
        ----------
        data : bytes, the complete DBLK binary (or a memoryview/mmap).
        code : str, the MDR token to look up.

        Returns
        -------
        str or None : SAL description text, or None if not found.
        """
        hdr = self._parse_header(data)
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
            Path(__file__).parent.parent.parent /
            "protocol" / "test-vectors" / "canonical-test-vectors.json"
        )
    with open(vectors_path) as f:
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

    vectors_path = (Path(__file__).parent.parent.parent /
                    "protocol" / "test-vectors" / "canonical-test-vectors.json")
    if vectors_path.exists():
        run_benchmark(str(vectors_path))
    else:
        print(f"  Run from repo root: python3 sdk/python/src/osmp.py")
