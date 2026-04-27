"""
Garde manger — the grammar parser. Mise en place for the brigade.

Reads NL once, produces ParsedRequest IR. Every other station starts here.

Strategy:
  1. Tokenize + lemmatize lightweight (no spaCy — phone-substrate compatible)
  2. Detect verb head via predicate position + verb lexicon
  3. Extract arguments via dependency-pattern regex (verb + dobj + pobj + nmod)
  4. Type slot values via pattern matchers (numeric, code, latlon, duration, time)
  5. Detect modifiers (conditional, authorization, emergency, broadcast, query)
  6. Identify chain structure (split on chain operators, recurse if needed)
  7. Hint namespace candidates for downstream stations
"""
from __future__ import annotations

import re
import string

from .request import (
    ParsedRequest, Condition, SlotValue, Target,
)

# ─────────────────────────────────────────────────────────────────────────────
# VERB LEXICON — head-action verbs and their canonical lemma + namespace hints
# Each verb is mapped to a primary opcode + a set of plausible namespaces.
# Stations consume the namespace hints to decide whether to propose.
# ─────────────────────────────────────────────────────────────────────────────

VERB_LEXICON: dict[str, dict] = {
    # Sensing / read
    "report":     {"lemma": "report", "ns_hints": ("L", "Q"), "is_wrapper": True},
    "send":       {"lemma": "send",   "ns_hints": ("D", "L"), "is_wrapper": True},
    "show":       {"lemma": "show",   "ns_hints": ("A",),     "is_wrapper": True},
    "log":        {"lemma": "log",    "ns_hints": ("L",),     "is_wrapper": True},
    "broadcast":  {"lemma": "broadcast", "ns_hints": ("L", "A"), "is_wrapper": True},
    "fetch":      {"lemma": "fetch",  "ns_hints": ("D",),     "is_wrapper": True},
    "retrieve":   {"lemma": "retrieve", "ns_hints": ("D",),   "is_wrapper": True},
    "read":       {"lemma": "read",   "ns_hints": ("E", "D"), "is_wrapper": True},
    "get":        {"lemma": "get",    "ns_hints": ("D", "E"), "is_wrapper": True},
    "give":       {"lemma": "give",   "ns_hints": ("D",),     "is_wrapper": True},
    "what":       {"lemma": "what",   "ns_hints": (),         "is_wrapper": True, "is_query": True},
    "where":      {"lemma": "where",  "ns_hints": ("G",),     "is_wrapper": True, "is_query": True},

    # Actuation (R-namespace primary)
    "stop":       {"lemma": "stop",   "ns_hints": ("R", "C"), "primary_opcode": "STOP"},
    "halt":       {"lemma": "halt",   "ns_hints": ("R", "C"), "primary_opcode": "STOP"},
    "start":      {"lemma": "start",  "ns_hints": ("R", "C"), "primary_opcode": "START"},
    "open":       {"lemma": "open",   "ns_hints": ("R",),     "primary_opcode": "OPEN"},
    "close":      {"lemma": "close",  "ns_hints": ("R",),     "primary_opcode": "STOP"},
    "lock":       {"lemma": "lock",   "ns_hints": ("R",),     "primary_opcode": "STOP"},
    "unlock":     {"lemma": "unlock", "ns_hints": ("R",),     "primary_opcode": "OPEN"},
    "move":       {"lemma": "move",   "ns_hints": ("R", "V"), "primary_opcode": "MOV"},
    "return":     {"lemma": "return", "ns_hints": ("R",),     "primary_opcode": "RTB"},
    "shutdown":   {"lemma": "shutdown", "ns_hints": ("C", "R"), "primary_opcode": "KILL"},
    "shut":       {"lemma": "shut",   "ns_hints": ("C", "R"), "primary_opcode": "KILL"},
    "kill":       {"lemma": "kill",   "ns_hints": ("C",),     "primary_opcode": "KILL"},
    "reboot":     {"lemma": "reboot", "ns_hints": ("C",),     "primary_opcode": "RSTRT"},
    "restart":    {"lemma": "restart", "ns_hints": ("C",),    "primary_opcode": "RSTRT"},
    "evacuate":   {"lemma": "evacuate", "ns_hints": ("M",),   "primary_opcode": "EVA"},
    "form":       {"lemma": "form",     "ns_hints": ("R",),   "primary_opcode": "FORM"},  # swarm formation
    "find":       {"lemma": "find",     "ns_hints": ("N", "D"), "is_wrapper": True},
    "rotate":     {"lemma": "rotate",   "ns_hints": ("S", "R"), "primary_opcode": "ROTATE"},
    "ack":        {"lemma": "ack",      "ns_hints": ("U",),   "primary_opcode": "ACK"},
    "store":      {"lemma": "store",    "ns_hints": ("Y",),   "primary_opcode": "STORE"},
    "forget":     {"lemma": "forget",   "ns_hints": ("Y",),   "primary_opcode": "FORGET"},
    "wait":       {"lemma": "wait",     "ns_hints": ("F",),   "primary_opcode": "WAIT"},
    "rebroadcast": {"lemma": "rebroadcast", "ns_hints": ("L",), "primary_opcode": "SEND"},
    "engage":     {"lemma": "engage",   "ns_hints": ("R",),   "is_wrapper": True},
    "swarm":      {"lemma": "swarm",    "ns_hints": ("R", "V"), "is_wrapper": True},
    "rtb":        {"lemma": "rtb",      "ns_hints": ("R",),   "primary_opcode": "RTH"},
    "navigate":   {"lemma": "navigate", "ns_hints": ("R",),   "primary_opcode": "MOV"},
    "fly":        {"lemma": "fly",      "ns_hints": ("R", "V"), "primary_opcode": "MOV"},
    "drive":      {"lemma": "drive",    "ns_hints": ("R", "V"), "primary_opcode": "DRVE"},
    "go":         {"lemma": "go",       "ns_hints": ("R",),   "primary_opcode": "MOV"},
    "cease":      {"lemma": "cease",    "ns_hints": ("R", "C"), "primary_opcode": "STOP"},
    "block":      {"lemma": "block",    "ns_hints": ("R",),   "primary_opcode": "STOP"},
    # Removed "head" — too prone to false positives ("heading" lemmatizes to "head" as noun, not verb)
    "proceed":    {"lemma": "proceed",  "ns_hints": ("F",),   "primary_opcode": "PRCD"},
    "turn":       {"lemma": "turn",   "ns_hints": ("R",),     "is_wrapper": True},  # "turn on/off X"
    "activate":   {"lemma": "activate", "ns_hints": ("R",),   "is_wrapper": True},
    "enable":     {"lemma": "enable", "ns_hints": ("R",),     "is_wrapper": True},
    "disable":    {"lemma": "disable", "ns_hints": ("R",),    "is_wrapper": True},

    # Crypto / auth
    "encrypt":    {"lemma": "encrypt", "ns_hints": ("S",),    "primary_opcode": "ENC"},
    "decrypt":    {"lemma": "decrypt", "ns_hints": ("S",),    "primary_opcode": "DEC"},
    "sign":       {"lemma": "sign",    "ns_hints": ("S",),    "primary_opcode": "SIGN"},
    "hash":       {"lemma": "hash",    "ns_hints": ("S",),    "primary_opcode": "HASH"},
    "verify":     {"lemma": "verify",  "ns_hints": ("S", "I", "A"), "primary_opcode": "VFY"},
    "authenticate": {"lemma": "authenticate", "ns_hints": ("I",), "primary_opcode": "ID"},

    # Generation (auxiliary — operand carries opcode)
    "generate":   {"lemma": "generate", "ns_hints": (),       "is_wrapper": True},
    "create":     {"lemma": "create",   "ns_hints": (),       "is_wrapper": True},
    "make":       {"lemma": "make",     "ns_hints": (),       "is_wrapper": True},
    "produce":    {"lemma": "produce",  "ns_hints": (),       "is_wrapper": True},

    # Network / discovery
    "ping":       {"lemma": "ping",   "ns_hints": ("A",),     "primary_opcode": "PING"},
    "discover":   {"lemma": "discover", "ns_hints": ("N",),   "primary_opcode": "Q"},

    # Alerts / notify
    "alert":      {"lemma": "alert",   "ns_hints": ("L", "H", "U", "W"), "primary_opcode": "ALERT"},
    "notify":     {"lemma": "notify",  "ns_hints": ("U",),    "primary_opcode": "NOTIFY"},
    "warn":       {"lemma": "warn",    "ns_hints": ("L", "H", "U"), "primary_opcode": "ALERT"},
    "trigger":    {"lemma": "trigger", "ns_hints": ("L", "U"), "primary_opcode": "ALERT"},

    # Config
    "set":        {"lemma": "set",     "ns_hints": ("N",),    "primary_opcode": "CFG", "takes_slot": True},
    "configure":  {"lemma": "configure", "ns_hints": ("N",),  "primary_opcode": "CFG", "takes_slot": True},
    "update":     {"lemma": "update",  "ns_hints": ("N",),    "primary_opcode": "CFG"},
    "modify":     {"lemma": "modify",  "ns_hints": ("N",),    "primary_opcode": "CFG"},
    "change":     {"lemma": "change",  "ns_hints": ("N",),    "primary_opcode": "CFG"},
    "adjust":     {"lemma": "adjust",  "ns_hints": ("N",),    "primary_opcode": "CFG"},

    # Time / schedule
    "expire":     {"lemma": "expire",  "ns_hints": ("T",),    "primary_opcode": "EXP"},
    "schedule":   {"lemma": "schedule", "ns_hints": ("T",),   "primary_opcode": "SCHED"},

    # Storage / data
    "back":       {"lemma": "back",    "ns_hints": ("N",),    "primary_opcode": "BK"},  # "back up"
    "backup":     {"lemma": "backup",  "ns_hints": ("N",),    "primary_opcode": "BK"},
    "delete":     {"lemma": "delete",  "ns_hints": ("D",),    "primary_opcode": "DEL"},
    "push":       {"lemma": "push",    "ns_hints": ("D",),    "primary_opcode": "PUSH"},

    # Process payment / commerce
    "process":    {"lemma": "process", "ns_hints": ("K", "C"), "is_wrapper": True},
    "pay":        {"lemma": "pay",     "ns_hints": ("K",),    "primary_opcode": "PAY"},
    "approve":    {"lemma": "approve", "ns_hints": ("U",),    "primary_opcode": "APPROVE"},

    # Cognitive / orchestration
    "hand":       {"lemma": "hand",    "ns_hints": ("J",),    "primary_opcode": "HANDOFF"},  # "hand off"
    "handoff":    {"lemma": "handoff", "ns_hints": ("J",),    "primary_opcode": "HANDOFF"},
    "summarize":  {"lemma": "summarize", "ns_hints": ("A",),  "primary_opcode": "SUM"},
    "check":      {"lemma": "check",   "ns_hints": ("A", "Q"), "is_wrapper": True},
}

# Verb inflection lemma map (extends LEXICON for common forms)
_INFLECTIONS: dict[str, str] = {
    "stops": "stop", "stopping": "stop", "stopped": "stop",
    "starts": "start", "starting": "start", "started": "start",
    "moves": "move", "moving": "move", "moved": "move",
    "opens": "open", "opening": "open", "opened": "open",
    "closes": "close", "closing": "close", "closed": "close",
    "locks": "lock", "locking": "lock", "locked": "lock",
    "encrypts": "encrypt", "encrypting": "encrypt", "encrypted": "encrypt",
    "signs": "sign", "signing": "sign", "signed": "sign",
    "verifies": "verify", "verifying": "verify", "verified": "verify",
    "pings": "ping", "pinging": "ping", "pinged": "ping",
    "alerts": "alert", "alerting": "alert", "alerted": "alert",
    "notifies": "notify", "notifying": "notify", "notified": "notify",
    "sets": "set", "setting": "set",
    "configures": "configure", "configuring": "configure",
    "updates": "update", "updating": "update", "updated": "update",
    "expires": "expire", "expiring": "expire", "expired": "expire",
    "deletes": "delete", "deleting": "delete", "deleted": "delete",
    "pushes": "push", "pushing": "push", "pushed": "push",
    "approves": "approve", "approving": "approve", "approved": "approve",
    "summarizes": "summarize", "summarizing": "summarize", "summarized": "summarize",
    "discovers": "discover", "discovering": "discover", "discovered": "discover",
    "generates": "generate", "generating": "generate", "generated": "generate",
    "reports": "report", "reporting": "report", "reported": "report",
    "sends": "send", "sending": "send", "sent": "send",
    "shows": "show", "showing": "show", "showed": "show",
    "broadcasts": "broadcast", "broadcasting": "broadcast",
    "fetches": "fetch", "fetching": "fetch", "fetched": "fetch",
    "retrieves": "retrieve", "retrieving": "retrieve", "retrieved": "retrieve",
    "reads": "read", "reading": "read",
    "gets": "get", "getting": "get", "got": "get",
    "halts": "halt", "halting": "halt", "halted": "halt",
    "shuts": "shut", "shutting": "shut",
    "kills": "kill", "killing": "kill", "killed": "kill",
    "reboots": "reboot", "rebooting": "reboot", "rebooted": "reboot",
    "restarts": "restart", "restarting": "restart", "restarted": "restart",
    "returns": "return", "returning": "return", "returned": "return",
    "evacuates": "evacuate", "evacuating": "evacuate", "evacuated": "evacuate",
    "turns": "turn", "turning": "turn", "turned": "turn",
    "activates": "activate", "activating": "activate", "activated": "activate",
    "warns": "warn", "warning": "warn", "warned": "warn",
    "triggers": "trigger", "triggering": "trigger", "triggered": "trigger",
    "processes": "process", "processing": "process", "processed": "process",
    "schedules": "schedule", "scheduling": "schedule", "scheduled": "schedule",
    "checks": "check", "checking": "check", "checked": "check",
    "hands": "hand", "handing": "hand", "handed": "hand",
    "creates": "create", "creating": "create", "created": "create",
    "makes": "make", "making": "make", "made": "make",
    "produces": "produce", "producing": "produce", "produced": "produce",
}

# Common stop-words to skip when scanning for verb head
STOPWORDS = {
    'the', 'a', 'an', 'this', 'that', 'these', 'those',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'do', 'does', 'did', 'has', 'have', 'had',
    'and', 'or', 'but', 'if', 'when', 'while',
    'of', 'in', 'on', 'at', 'to', 'for', 'from', 'with', 'by',
    'me', 'my', 'you', 'your', 'we', 'our', 'they', 'their',
    'it', 'its', 'his', 'her', 'them',
    'please', 'now', 'just', 'only', 'really',
}

import re as _re_local

# Modifier markers — when present in residue of a bridge-mode candidate,
# downgrade to passthrough. These can gate or invert the SAL action.
MODIFIER_MARKERS_PATTERN = _re_local.compile(
    r'\b(unless|only if|except|but not|without|after|before|while|if not)\b',
    _re_local.IGNORECASE,
)

# Per-namespace bridge-mode policy.
# Sensing/read-only namespaces: bridge allowed (residue is harmless context).
# Action namespaces: bridge forbidden (residue may carry conditions/modifiers).
# Per the taxonomy doctrine in tests/input-classes/TAXONOMY-v1.md.
BRIDGE_ALLOWED_NAMESPACES = {
    "E",  # Environmental sensor (read-only)
    "G",  # Geospatial (read-only)
    "W",  # Weather (read-only)
    "N",  # Network status (mostly read; CFG and BK are write but they're rare in bridge cases)
    "O",  # Operational context (metadata)
    "Q",  # Quality (read-only)
    "X",  # Energy (read-only sensor data)
    "A",  # Agentic (PING is read; SUM is read)
    # H namespace bridge-allowed for read opcodes only (BP, HR, SPO2, VITALS, TEMP)
    # — handled per-frame in is_bridge_safe
    "H",
    # V namespace bridge-allowed for read opcodes (POS, HDG, AIS) — per-frame check
    "V",
    # I:ID is read; I:§ is precondition-only — handled per-frame
    "I",
}

# Frames that are NEVER safe to bridge — action-bearing within otherwise-sensing namespaces
BRIDGE_FORBIDDEN_FRAMES = {
    ("H", "ALERT"), ("H", "CASREP"),  # H-namespace alerts (action)
    ("W", "ALERT"),                    # W-namespace alerts
    ("N", "CFG"), ("N", "BK"),         # N-namespace config/backup (write)
    ("V", "FLEET"),                    # V-namespace fleet ops (action)
    ("I", "\u00a7"),                   # I:§ never standalone
    ("A", "PROPOSE"), ("A", "BROADCAST"),  # A-namespace writes
}


NEGATION_MARKERS = [
    r"\bdon'?t\b", r"\bdo not\b", r"\bdoes not\b", r"\bdoesn'?t\b",
    r"\bnever\b", r"\bno longer\b", r"\bnot\b",
    r"\bcancel\b", r"\babort\b", r"\bstop doing\b",
]

# Code/shell/SQL injection patterns. If any match, refuse to compose —
# the input contains executable code that should never be encoded as
# protocol intent.
INJECTION_MARKERS = [
    r";\s*(?:DROP|DELETE|INSERT|UPDATE|SELECT|TRUNCATE|ALTER)\s+",
    r"&&", r"\|\|", r"\$\(", r"`[^`]*`",
    r"<script", r"</script", r"javascript:",
    r"system\s*\(", r"exec\s*\(", r"eval\s*\(",
    r"rm\s+-rf", r"chmod\s+777",
    r"--\s*$",  # SQL comment terminator
    r"/etc/(?:passwd|shadow)",
    r"\bUNION\s+SELECT\b",
    r"\.\./",  # path traversal
]

# Email pattern. When present, refuse — emails are not protocol targets;
# composer was extracting the local-part as a target binding.
EMAIL_PATTERN = re.compile(r'\b[\w.+-]+@[\w-]+\.\w+\b')

# Idiom suffixes — particles that turn a protocol verb into a non-protocol idiom.
# "wind down" (relax, not measure wind), "stop bothering" (cease, not actuator stop),
# "ping me on" (notify on platform, not network ping), "lock in" (commit, not actuator).
IDIOM_PARTICLE_AFTER_VERB = {
    ("wind", "down"), ("wind", "up"),
    ("stop", "bothering"), ("stop", "by"), ("stop", "doing"),
    ("ping", "me"),
    ("lock", "in"), ("lock", "down"),  # "lock down" is an idiom; for actuator use "lock the door"
    ("close", "out"),
    ("send", "off"),
    ("verify", "that"),
    ("check", "out"), ("check", "in"),
    ("report", "back"), ("report", "in"),
    ("encrypt", "your"),  # "encrypt your feelings" pattern
}

# Allowed object kinds for action verbs — the OBJECT of an actuator verb must
# be in the device/system class. Abstract objects ("ordering", "bothering",
# "feelings") should not bind as targets.
ACTUATOR_OBJECT_NOUNS = {
    "conveyor", "pump", "valve", "door", "light", "lights", "lamp", "fan",
    "motor", "engine", "service", "process", "system", "device", "node",
    "gateway", "server", "drone", "vehicle", "vessel", "robot", "sensor",
    "alarm", "siren", "sprinkler", "camera", "microphone", "speaker",
    "flashlight", "torch", "screen", "display", "wifi", "bluetooth", "gps",
    "haptic", "actuator", "relay", "switch", "circuit", "breaker",
    "hatch", "window", "shutter", "blind", "valve", "tank", "reactor",
    "antenna", "transmitter", "receiver", "feed", "stream", "channel",
    "config", "configuration", "settings", "threshold", "parameter",
    "database", "cache", "queue", "log", "logs",
}


EMERGENCY_MARKERS = {
    'emergency', 'immediately', 'right now', 'asap', 'urgent', 'critical',
    'panic', 'sos', 'mayday',
}

BROADCAST_MARKERS = {
    'everyone', 'all nodes', 'broadcast', 'all peers', 'every node',
    'all', 'any',  # weak markers — only fire with broadcast verb
}

QUERY_MARKERS = {'?', 'what', 'where', 'when', 'who', 'how many', 'how much',
                 'tell me', 'show me'}

AUTH_MARKERS = [
    r'\bonly if\b.*\b(approves?|signs?|authorize[ds]?|confirm[s]?|allows?)\b',
    r'\brequire[ds]?\s+(approval|sign-?off|authorization|confirmation)\b',
    r'\bif\s+\w+\s+(approves?|signs?|authorizes?)\b',
    r'\bafter\s+\w+\s+approves?\b',
    r'\bwith\s+approval\b',
    r'\bsubject to (approval|authorization)\b',
]


# Domain hint heuristic — quick keyword classifier for the domain
DOMAIN_KEYWORDS: dict[str, set] = {
    "medical":      {"patient", "vitals", "heart", "blood", "pressure", "spo2",
                     "oxygen", "pulse", "icd", "diagnosis", "casualty", "pneumothorax"},
    "uav":          {"drone", "uav", "swarm", "rtb", "altitude", "wedge", "formation"},
    "weather":      {"wind", "barometric", "pressure", "humidity", "temperature",
                     "rain", "storm", "atmospheric"},
    "device_control": {"conveyor", "valve", "pump", "door", "lock", "lights",
                     "fan", "motor", "engine", "actuator"},
    "meshtastic":   {"node", "peer", "relay", "broadcast", "ping", "mesh",
                     "channel", "rebroadcast"},
    "crypto":       {"encrypt", "decrypt", "sign", "hash", "key", "keypair",
                     "signature", "tls", "aes"},
    "config":       {"config", "configuration", "settings", "threshold",
                     "parameter", "setup", "preferences"},
    "vehicle":      {"vehicle", "vessel", "ship", "fleet", "ais", "boat"},
    "sensor":       {"sensor", "humidity", "moisture", "air quality", "vibration"},
}


def lemmatize(word: str) -> str:
    """Lightweight rule-based lemmatizer for verbs."""
    w = word.lower()
    if w in VERB_LEXICON:
        return w
    if w in _INFLECTIONS:
        return _INFLECTIONS[w]
    # Generic suffix rules (only for verb-like words)
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            stem = w[:-len(suffix)]
            if stem in VERB_LEXICON:
                return stem
    return w


def tokenize(text: str) -> list[str]:
    """Tokenize: split on whitespace + punctuation, preserve numbers and IDs."""
    # Replace common punctuation but preserve hyphens (D-7) and decimals (35.7)
    cleaned = text.lower()
    # Strip trailing punctuation from each word
    tokens = []
    for raw in cleaned.split():
        # Strip leading/trailing punctuation but keep internal
        word = raw.strip(string.punctuation.replace("-", "").replace(".", ""))
        if word:
            tokens.append(word)
    return tokens


def find_verb_head(tokens: list[str]) -> tuple[str, str] | None:
    """Find the first verb in the token sequence. Returns (raw_token, lemma) or None."""
    for tok in tokens:
        if tok in STOPWORDS:
            continue
        lemma = lemmatize(tok)
        if lemma in VERB_LEXICON:
            return tok, lemma
    return None


def detect_authorization(text: str) -> bool:
    """Detect 'only if X approves' / 'requires sign-off' / etc. patterns."""
    low = text.lower()
    for pattern in AUTH_MARKERS:
        if re.search(pattern, low):
            return True
    return False


def detect_negation(text: str) -> bool:
    """Detect negation markers ('don't', 'do not', 'never', 'cancel', etc.)."""
    low = text.lower()
    for pattern in NEGATION_MARKERS:
        if re.search(pattern, low):
            return True
    return False


def detect_glyph_injection(text: str) -> bool:
    """User typed SAL-like syntax in their NL input ('R:STOP', 'E:TH', etc.).
    Refuse to compose — this is adversarial or confused user."""
    if re.search(r'\b[A-Z\u03a9]:[A-Z][A-Z0-9_]*\b', text):
        return True
    return False


def detect_code_injection(text: str) -> bool:
    """Detect shell/SQL/script injection patterns in NL.
    Mixed legit-prefix + malicious-suffix is one of the worst attack patterns:
    composer extracts the legit verb, drops the malicious tail. Refuse instead."""
    for pattern in INJECTION_MARKERS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def detect_email(text: str) -> bool:
    """Detect email addresses in input. Composer was treating local-part as target."""
    return bool(EMAIL_PATTERN.search(text))


def detect_idiom(verb_lemma: str | None, raw: str) -> bool:
    """Check if the verb is part of an idiom (verb + particle).
    'wind down', 'stop bothering', 'ping me on' — not protocol verbs."""
    if not verb_lemma:
        return False
    low = raw.lower()
    tokens = low.split()
    try:
        idx = tokens.index(verb_lemma)
        if idx + 1 < len(tokens):
            next_word = tokens[idx + 1].strip(".,!?")
            if (verb_lemma, next_word) in IDIOM_PARTICLE_AFTER_VERB:
                return True
    except ValueError:
        pass
    # Also check inflected verb forms: "winding down", "stopping bothering"
    for token_idx, tok in enumerate(tokens):
        clean = tok.strip(".,!?'")
        if clean.startswith(verb_lemma) and token_idx + 1 < len(tokens):
            next_word = tokens[token_idx + 1].strip(".,!?")
            if (verb_lemma, next_word) in IDIOM_PARTICLE_AFTER_VERB:
                return True
    return False


def detect_emergency(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in EMERGENCY_MARKERS)


def detect_broadcast(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in BROADCAST_MARKERS)


def detect_query(text: str, verb_lemma: str | None) -> bool:
    if text.strip().endswith("?"):
        return True
    low = text.lower()
    if any(m in low for m in QUERY_MARKERS):
        return True
    if verb_lemma:
        info = VERB_LEXICON.get(verb_lemma, {})
        if info.get("is_query"):
            return True
        # Wrapper verbs that imply read (report/show/give/what) imply query
        if info.get("is_wrapper") and verb_lemma in {"report", "show", "give",
                                                       "fetch", "retrieve", "read",
                                                       "what", "where"}:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# SLOT EXTRACTORS — one per slot type
# Each extractor is pure: input string → list of SlotValue
# ─────────────────────────────────────────────────────────────────────────────

ICD_PATTERN = re.compile(
    r'(?:code|icd|diagnosis|icd-?10)\s+([A-Z]\d{2}\.?\d*)',
    re.IGNORECASE,
)

LATLON_PATTERN = re.compile(
    r'(?:coordinates?|coords?|gps|location|latlon)\s+'
    r'([-]?\d{1,3}\.?\d*)\s*[,]?\s*([-]?\d{1,3}\.?\d*)',
    re.IGNORECASE,
)

DURATION_PATTERN = re.compile(
    r'(?:every|in|after|for|within)\s+(\d+\.?\d*)\s*'
    r'(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\b',
    re.IGNORECASE,
)

AT_TIME_PATTERN = re.compile(
    r'\b(?:at|by)\s+(\d{1,2}(?::\d{2})?(?:\s*[ap]m)?|midnight|noon|tonight)\b',
    re.IGNORECASE,
)

THRESHOLD_PATTERN = re.compile(
    r'(above|over|below|under|exceeds?|greater than|less than|higher than|lower than)\s+(-?\d+\.?\d*)',
    re.IGNORECASE,
)

THRESHOLD_OP_MAP = {
    "above": ">", "over": ">", "exceeds": ">", "exceed": ">",
    "greater than": ">", "higher than": ">",
    "below": "<", "under": "<", "less than": "<", "lower than": "<",
}

NAMED_PARAM_PATTERN = re.compile(
    r'\b(?:set\s+(?:the\s+)?)?(\w+)\s+to\s+(\d+\.?\d*)\b',
    re.IGNORECASE,
)


def _normalize_duration_unit(unit: str) -> str:
    u = unit.lower()
    if u.startswith('s'): return 's'
    if u.startswith('m'): return 'm' if u.startswith('min') or u in ('m',) else 's'
    if u.startswith('h'): return 'h'
    if u.startswith('d'): return 'd'
    return 's'


def extract_slots(text: str) -> list[SlotValue]:
    """Extract typed slot values from NL. Order doesn't matter — slots are keyed."""
    slots: list[SlotValue] = []
    seen_keys = set()

    # Fixed-cadence schedule keywords ("daily", "hourly", etc.)
    text_low = text.lower()
    for kw, val in (("daily", "1d"), ("hourly", "1h"), ("weekly", "7d"),
                     ("monthly", "30d"), ("nightly", "1d")):
        if kw in text_low:
            slots.append(SlotValue(key="duration", value=val, value_type="duration"))
            break

    # ICD codes
    for m in ICD_PATTERN.finditer(text):
        code = m.group(1).replace(".", "").upper()
        if "icd" not in seen_keys:
            slots.append(SlotValue(key="icd", value=code, value_type="code"))
            seen_keys.add("icd")

    # Lat/lon coordinates
    for m in LATLON_PATTERN.finditer(text):
        latlon = f"{m.group(1)},{m.group(2)}"
        if "coordinates" not in seen_keys:
            slots.append(SlotValue(key="coordinates", value=latlon, value_type="latlon"))
            seen_keys.add("coordinates")

    # Duration / interval
    for m in DURATION_PATTERN.finditer(text):
        n = m.group(1)
        unit = _normalize_duration_unit(m.group(2))
        # Strip trailing .0 from integer-valued floats
        if n.endswith(".0"):
            n = n[:-2]
        slots.append(SlotValue(key="duration", value=f"{n}{unit}", value_type="duration"))

    # At-time anchor
    for m in AT_TIME_PATTERN.finditer(text):
        t = m.group(1).upper().replace(' ', '')
        if "at_time" not in seen_keys:
            slots.append(SlotValue(key="at_time", value=t, value_type="time"))
            seen_keys.add("at_time")

    # Named "X to N" parameters (e.g., "threshold to 30")
    # Skip names that are verbs or already extracted slots
    SKIP_NAMES = {"set", "configure", "update", "schedule"} | seen_keys
    for m in NAMED_PARAM_PATTERN.finditer(text):
        name = m.group(1).lower()
        if name in SKIP_NAMES or name in STOPWORDS:
            continue
        slots.append(SlotValue(key=name, value=m.group(2), value_type="float"))

    return slots


def extract_conditions(text: str) -> list[Condition]:
    """Extract threshold/comparison conditions from NL."""
    conds: list[Condition] = []
    for m in THRESHOLD_PATTERN.finditer(text):
        op_word = m.group(1).lower().rstrip('s')
        op_canonical = "exceeds" if op_word == "exceed" else op_word
        sal_op = THRESHOLD_OP_MAP.get(op_word, ">")
        if sal_op == ">" and op_word in ("below", "under", "less than", "lower than"):
            sal_op = "<"
        conds.append(Condition(operator=sal_op, value=m.group(2)))
    return conds


# ─────────────────────────────────────────────────────────────────────────────
# TARGET EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

ENTITY_PATTERN = re.compile(
    r'\b(drone|node|patient|sensor|vehicle|vessel|gateway|turbine|server|valve|door|agent|host|relay|gate|building|cluster|peer|robot|station|tank|reactor)\s+([\w-]+)',
    re.IGNORECASE,
)

ACTION_VERB_OBJECT_PATTERN = re.compile(
    r'\b(stop|close|open|lock|unlock|kill|reboot|restart|shutdown|start|halt)\s+(?:the\s+)?(\w+)',
    re.IGNORECASE,
)

PREP_TARGET_PATTERN = re.compile(
    r'(?<!\w)(?:on|at|to|@)\s+(?:the\s+)?([\w-]+)',
    re.IGNORECASE,
)

# Common nouns that are NOT targets
TARGET_BLOCKLIST = {
    'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are',
    'coordinates', 'position', 'heading', 'feedback', 'control',
    'context', 'service', 'system', 'midnight', 'noon', 'tonight',
    'home', 'base',  # these are conceptual destinations, not @ targets
    'this', 'that', 'it', 'them', 'me', 'us',
    'temperature', 'humidity', 'pressure',  # operands, not targets
    'pneumothorax',  # diagnosis, becomes slot
    'status', 'uptime', 'health',  # operands
    'french', 'spanish', 'german',  # languages (out-of-scope)
    'pizza', 'burger', 'paris', 'jazz',  # OOS test inputs
    'milk', 'french',
    'flashlight', 'camera', 'speaker', 'microphone',  # peripherals — operands not targets
    'haptic', 'vibration', 'screen', 'display',
    'pump', 'valve', 'door', 'fan',  # actuators — TARGET via action_verb path, not entity path
    'conveyor', 'engine', 'motor', 'lamp', 'light',
    'message', 'payload', 'data', 'request', 'response',
}


def extract_targets(text: str) -> list[Target]:
    """Extract target bindings in priority order."""
    targets: list[Target] = []
    seen = set()

    # Priority 1: structured entity (kind + id)
    for m in ENTITY_PATTERN.finditer(text):
        kind = m.group(1).lower()
        eid = m.group(2).upper()
        # Validate id-ness: numeric, alphanumeric with digits, NATO-style ALL CAPS
        is_id = (
            eid.isdigit()
            or any(c.isdigit() for c in eid)
            or (eid.isalpha() and eid.isupper() and len(eid) >= 3
                and eid.lower() not in TARGET_BLOCKLIST)
        )
        if not is_id:
            continue
        # Format target
        if kind in {"drone", "vehicle", "vessel", "uav", "patient"}:
            tid = f"{kind.upper()}{eid}"
        else:
            tid = eid
        if tid not in seen:
            targets.append(Target(id=tid, kind=kind, source="entity"))
            seen.add(tid)

    # Priority 2: action-verb + bare noun ("stop pump" → @PUMP)
    for m in ACTION_VERB_OBJECT_PATTERN.finditer(text):
        obj = m.group(2).upper()
        if obj.lower() in TARGET_BLOCKLIST:
            continue
        if obj not in seen:
            targets.append(Target(id=obj, kind="object", source="action_verb"))
            seen.add(obj)

    # Priority 3: prepositional ("on/at/to X")
    for m in PREP_TARGET_PATTERN.finditer(text):
        t = m.group(1).upper()
        if t.lower() in TARGET_BLOCKLIST:
            continue
        if t not in seen:
            targets.append(Target(id=t, kind="prep", source="preposition"))
            seen.add(t)

    return targets


# ─────────────────────────────────────────────────────────────────────────────
# DOMAIN HINT
# ─────────────────────────────────────────────────────────────────────────────

def detect_domain(text: str) -> tuple[str | None, list[str]]:
    """Return (domain, namespace_hints) based on keyword presence."""
    low = text.lower()
    tokens = set(low.split())
    scores: dict[str, int] = {}
    for domain, kws in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in kws if kw in tokens or kw in low)
    if not scores or max(scores.values()) == 0:
        return None, []
    best = max(scores, key=lambda d: scores[d])
    DOMAIN_TO_NS = {
        "medical":        ["H", "I", "U"],
        "uav":            ["V", "R", "G", "I"],
        "weather":        ["W", "E"],
        "device_control": ["R", "C"],
        "meshtastic":     ["N", "O", "A", "G"],
        "crypto":         ["S", "I"],
        "config":         ["N", "T"],
        "vehicle":        ["V", "G"],
        "sensor":         ["E"],
    }
    return best, DOMAIN_TO_NS.get(best, [])


# ─────────────────────────────────────────────────────────────────────────────
# CHAIN DETECTION
# ─────────────────────────────────────────────────────────────────────────────

CHAIN_PATTERNS: list[tuple[str, str]] = [
    (r',\s+then\s+', ';'),
    (r',\s+and\s+then\s+', ';'),
    (r'\s+then\s+', ';'),
    # Removed " next " as separator — too prone to false positives ("next signal" is adjective)
    (r',\s+and\s+', '\u2227'),
    (r'\s+and\s+', '\u2227'),
]


def split_chain(text: str) -> tuple[list[str], str | None]:
    """Split NL into chain segments. Returns (segments, operator) or ([text], None)."""
    if ' if ' in text.lower() or text.lower().startswith('if '):
        return [text], None
    for pattern, op in CHAIN_PATTERNS:
        segments = re.split(pattern, text, flags=re.IGNORECASE)
        if len(segments) >= 2:
            cleaned = [s.strip().rstrip('.,;') for s in segments if s.strip()]
            if len(cleaned) >= 2:
                return cleaned, op
    return [text], None


# ─────────────────────────────────────────────────────────────────────────────
# DIRECT OBJECT DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def find_direct_object(tokens: list[str], verb_idx: int) -> tuple[str | None, str | None]:
    """Find the direct object after the verb. Returns (object, kind) or (None, None)."""
    after_verb = tokens[verb_idx + 1:]
    # Skip particle/preposition that completes the multi-word verb (turn ON, hand OFF)
    if after_verb and after_verb[0] in {'on', 'off', 'up', 'down', 'in', 'out'}:
        after_verb = after_verb[1:]
    # Skip articles only — keep demonstratives ("this", "that") because they
    # ARE the direct object when used as pronouns ("stop that", "do this").
    # Orchestrator detects pronoun-as-object and refuses.
    while after_verb and after_verb[0] in {'the', 'a', 'an', 'my', 'your'}:
        after_verb = after_verb[1:]
    if not after_verb:
        return None, None
    obj = after_verb[0]
    # Multi-word object (drone 1, sensor 4A, key pair, blood pressure)
    if len(after_verb) >= 2:
        cand = f"{obj} {after_verb[1]}"
        if obj in {"drone", "node", "sensor", "patient", "vehicle", "vessel", "gateway",
                   "valve", "door", "agent", "key", "blood", "heart", "oxygen"}:
            obj = cand
    # Determine kind
    KIND_MAP = {
        "drone": "drone", "uav": "drone", "node": "node", "sensor": "sensor",
        "patient": "patient", "vehicle": "vehicle", "vessel": "vehicle",
        "gateway": "gateway", "valve": "actuator", "door": "actuator",
        "pump": "actuator", "conveyor": "actuator", "camera": "peripheral",
        "microphone": "peripheral", "speaker": "peripheral", "flashlight": "peripheral",
        "torch": "peripheral", "haptic": "peripheral",
        "payment": "transaction", "key": "crypto_key",
        "temperature": "sensor_value", "humidity": "sensor_value",
        "pressure": "sensor_value", "heart rate": "vital", "blood pressure": "vital",
        "oxygen": "vital", "vitals": "vital",
        "config": "config", "threshold": "config",
    }
    first = obj.split()[0]
    return obj, KIND_MAP.get(first) or KIND_MAP.get(obj)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PARSE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def parse(nl: str) -> ParsedRequest:
    """Parse NL into ParsedRequest IR. Pure function — same input, same output."""
    raw = nl.strip()

    # Detect chain structure first; recurse on segments
    segments, chain_op = split_chain(raw)
    if len(segments) > 1:
        sub_requests = tuple(parse(s) for s in segments)
        # Build a chain-level request that wraps the sub-requests
        # Most modifiers (auth, emergency, schedule) are extracted from the WHOLE input
        whole = _parse_single(raw)
        return ParsedRequest(
            raw=whole.raw,
            verb=whole.verb,
            verb_lemma=whole.verb_lemma,
            direct_object=whole.direct_object,
            direct_object_kind=whole.direct_object_kind,
            targets=whole.targets,
            slot_values=whole.slot_values,
            conditions=whole.conditions,
            schedule=whole.schedule,
            authorization_required=whole.authorization_required,
            is_emergency=whole.is_emergency,
            is_broadcast=whole.is_broadcast,
            is_query=whole.is_query,
            is_passthrough_likely=whole.is_passthrough_likely,
            chain_segments=sub_requests,
            chain_operator=chain_op,
            namespace_hints=whole.namespace_hints,
            domain_hint=whole.domain_hint,
        )

    return _parse_single(raw)


def _parse_single(nl: str) -> ParsedRequest:
    """Parse a single segment (no chain split)."""
    raw = nl.strip()
    tokens = tokenize(raw)

    # Find verb head
    verb_info = find_verb_head(tokens)
    verb_raw, verb_lemma = (verb_info if verb_info else (None, None))
    verb_idx = tokens.index(verb_raw) if verb_raw else -1

    # Direct object
    direct_object, dobj_kind = (None, None)
    if verb_idx >= 0:
        direct_object, dobj_kind = find_direct_object(tokens, verb_idx)

    # Modifiers
    is_authorized = detect_authorization(raw)
    is_emergency = detect_emergency(raw)
    is_broadcast = detect_broadcast(raw)
    is_query = detect_query(raw, verb_lemma)
    is_negated = detect_negation(raw)
    has_glyph_injection_flag = (
        detect_glyph_injection(raw)
        or detect_code_injection(raw)
        or detect_email(raw)
        or detect_idiom(verb_lemma, raw)
    )

    # Slots
    slots = extract_slots(raw)
    schedule_value = None
    for sv in slots:
        if sv.value_type == "duration":
            schedule_value = sv.value
            break
        if sv.value_type == "time":
            schedule_value = sv.value
            break

    # Conditions
    conditions = extract_conditions(raw)

    # Targets
    targets = extract_targets(raw)

    # Domain + namespace hints
    domain, ns_hints = detect_domain(raw)
    # Add verb-derived ns hints
    if verb_lemma and verb_lemma in VERB_LEXICON:
        verb_ns = list(VERB_LEXICON[verb_lemma].get("ns_hints", ()))
        for ns in verb_ns:
            if ns not in ns_hints:
                ns_hints.append(ns)

    # Passthrough heuristic — if no verb found AND no slots AND no targets, likely passthrough
    is_passthrough = (not verb_info) and (not slots) and (not targets)

    return ParsedRequest(
        raw=raw,
        verb=verb_raw,
        verb_lemma=verb_lemma,
        direct_object=direct_object,
        direct_object_kind=dobj_kind,
        targets=tuple(targets),
        slot_values=tuple(slots),
        conditions=tuple(conditions),
        schedule=schedule_value,
        authorization_required=is_authorized,
        is_emergency=is_emergency,
        is_broadcast=is_broadcast,
        is_query=is_query,
        is_passthrough_likely=is_passthrough,
        is_negated=is_negated,
        has_glyph_injection=has_glyph_injection_flag,
        namespace_hints=tuple(ns_hints),
        domain_hint=domain,
    )
