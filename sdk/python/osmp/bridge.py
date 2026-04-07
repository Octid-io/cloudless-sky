"""
OSMP SALBridge — Language propagation through contact.

The bridge sits at the boundary between an OSMP-native swarm and non-OSMP
agents. It does four things:

  1. Detects whether the remote peer speaks OSMP (via FNP negotiation).
  2. If not, enters FALLBACK mode: decodes outbound SAL to natural language,
     tags inbound natural language as NL_PASSTHROUGH.
  3. Annotates outbound messages with SAL equivalents, seeding the remote
     agent's context window with SAL patterns.
  4. Monitors inbound messages for valid SAL fragments. When the remote agent
     starts producing valid SAL (few-shot acquisition), transitions to
     ACQUIRED state and begins sending pure SAL.

OSMP does not spread by installation. It spreads by contact.

Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from osmp.protocol import (
    AdaptiveSharedDictionary,
    FNPSession,
    SALDecoder,
    SALEncoder,
    validate_composition,
    FNP_CAP_UNCONSTRAINED,
)


# ─────────────────────────────────────────────────────────────────────────────
# ACQUISITION SCORING
# ─────────────────────────────────────────────────────────────────────────────

# SAL frame pattern: at least Namespace:Opcode (e.g., H:HR, A:ACK, M:EVA)
from osmp.protocol import _SAL_FRAME_RE_BRIDGE as _SAL_FRAME_RE
from osmp.protocol import _NS_PATTERN, _OPCODE_PATTERN

# Default threshold: 5 consecutive messages with valid SAL before ACQUIRED
DEFAULT_ACQUISITION_THRESHOLD = 5

# Consecutive misses before ACQUIRED regresses to FALLBACK
DEFAULT_REGRESSION_THRESHOLD = 3


@dataclass
class AcquisitionMetrics:
    """Tracks SAL acquisition progress for a single remote peer."""

    total_messages: int = 0
    messages_with_sal: int = 0
    consecutive_sal_hits: int = 0
    consecutive_sal_misses: int = 0
    peak_consecutive_hits: int = 0
    valid_frames_seen: int = 0
    unique_opcodes_seen: set = field(default_factory=set)
    first_sal_seen_at: float | None = None
    last_sal_seen_at: float | None = None

    @property
    def acquisition_score(self) -> float:
        """0.0 to 1.0, based on consecutive valid SAL production."""
        if self.total_messages == 0:
            return 0.0
        return min(1.0, self.consecutive_sal_hits / DEFAULT_ACQUISITION_THRESHOLD)

    def record_hit(self, frames: list[tuple[str, str]]) -> None:
        """Record that a message contained valid SAL frames."""
        now = time.time()
        self.total_messages += 1
        self.messages_with_sal += 1
        self.consecutive_sal_hits += 1
        self.consecutive_sal_misses = 0
        self.valid_frames_seen += len(frames)
        for ns, op in frames:
            self.unique_opcodes_seen.add(f"{ns}:{op}")
        if self.consecutive_sal_hits > self.peak_consecutive_hits:
            self.peak_consecutive_hits = self.consecutive_sal_hits
        if self.first_sal_seen_at is None:
            self.first_sal_seen_at = now
        self.last_sal_seen_at = now

    def record_miss(self) -> None:
        """Record that a message contained no valid SAL."""
        self.total_messages += 1
        self.consecutive_sal_hits = 0
        self.consecutive_sal_misses += 1


@dataclass
class BridgeEvent:
    """Log entry for bridge activity."""

    timestamp: float
    event_type: str       # "fallback", "annotate", "detect_sal", "acquire", "regress", "send_sal", "passthrough"
    remote_id: str
    sal: str | None = None
    nl: str | None = None
    frames_detected: int = 0
    detail: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# SALBridge
# ─────────────────────────────────────────────────────────────────────────────

class SALBridge:
    """Boundary translator between OSMP-native agents and non-OSMP peers.

    The bridge wraps a transport callable and presents a SAL interface.
    Internal agents always speak SAL. The bridge handles negotiation,
    fallback, annotation, and acquisition automatically.

    Parameters
    ----------
    node_id : str
        Identity of this OSMP node.
    asd : AdaptiveSharedDictionary, optional
        Shared dictionary. Uses default if not provided.
    annotate : bool
        If True (default), outbound NL messages to FALLBACK peers include
        SAL annotations that seed the remote context window.
    acquisition_threshold : int
        Number of consecutive messages with valid SAL before transitioning
        from FALLBACK to ACQUIRED. Default 5.
    regression_threshold : int
        Number of consecutive messages without SAL before transitioning
        from ACQUIRED back to FALLBACK. Default 3.

    Usage
    -----
        bridge = SALBridge("MY_NODE")

        # Register a non-OSMP peer
        bridge.register_peer("GPT_AGENT_1")

        # Send SAL — bridge decodes to NL for non-OSMP peers
        outbound = bridge.send("H:HR@NODE1>120;H:CASREP;M:EVA@*", "GPT_AGENT_1")
        # outbound = "heart_rate at NODE1 exceeds 120; casualty_report; evacuation at broadcast
        #             [SAL: H:HR@NODE1>120;H:CASREP;M:EVA@*]"

        # Receive response — bridge checks for SAL acquisition
        inbound = bridge.receive("Heart rate acknowledged, dispatching medic", "GPT_AGENT_1")
        # inbound.sal = None, inbound.nl = "Heart rate acknowledged, dispatching medic"
        # inbound.passthrough = True

        # ... after enough exposure, the remote agent starts producing SAL ...
        inbound = bridge.receive("A:ACK;M:EVA@MED", "GPT_AGENT_1")
        # inbound.sal = "A:ACK;M:EVA@MED", inbound.passthrough = False
    """

    def __init__(
        self,
        node_id: str,
        asd: AdaptiveSharedDictionary | None = None,
        annotate: bool = True,
        acquisition_threshold: int = DEFAULT_ACQUISITION_THRESHOLD,
        regression_threshold: int = DEFAULT_REGRESSION_THRESHOLD,
    ):
        self.node_id = node_id
        self.asd = asd or AdaptiveSharedDictionary()
        self.annotate = annotate
        self.acquisition_threshold = acquisition_threshold
        self.regression_threshold = regression_threshold
        self._encoder = SALEncoder(self.asd)
        self._decoder = SALDecoder(self.asd)
        self._sessions: dict[str, FNPSession] = {}
        self._metrics: dict[str, AcquisitionMetrics] = {}
        self._log: list[BridgeEvent] = []

    # ── peer management ──────────────────────────────────────────────

    def register_peer(self, peer_id: str, attempt_fnp: bool = True) -> str:
        """Register a remote peer and optionally attempt FNP negotiation.

        If attempt_fnp is False, immediately enters FALLBACK (use for
        peers known to be non-OSMP, e.g., plain JSON-RPC endpoints).

        Returns the session state after registration.
        """
        session = FNPSession(
            self.asd, self.node_id,
            channel_capacity=FNP_CAP_UNCONSTRAINED,
        )
        self._sessions[peer_id] = session
        self._metrics[peer_id] = AcquisitionMetrics()

        if not attempt_fnp:
            session.fallback(peer_id)
            self._emit("fallback", peer_id, detail="direct registration, no FNP attempt")

        return session.state

    def negotiate(self, peer_id: str, response_data: bytes | None = None) -> tuple[bytes | None, str]:
        """Attempt or continue FNP negotiation with a peer.

        Call with response_data=None to initiate (returns ADV packet).
        Call with response_data=<received bytes> to process the response.

        If the response is not a valid FNP packet, transitions to FALLBACK.

        Returns (packet_to_send_or_None, session_state).
        """
        session = self._sessions.get(peer_id)
        if session is None:
            self.register_peer(peer_id)
            session = self._sessions[peer_id]

        if response_data is None:
            # Initiate
            try:
                adv = session.initiate()
                return adv, session.state
            except RuntimeError:
                return None, session.state

        # Process response
        try:
            result = session.receive(response_data)
            return result, session.state
        except (ValueError, Exception):
            # Response is not valid FNP — this peer doesn't speak OSMP
            session.fallback(peer_id)
            self._emit("fallback", peer_id,
                        detail="invalid FNP response, entering FALLBACK")
            return None, session.state

    def peer_state(self, peer_id: str) -> str | None:
        """Return the FNP session state for a peer, or None if unregistered."""
        session = self._sessions.get(peer_id)
        return session.state if session else None

    # ── outbound: SAL → whatever the peer speaks ─────────────────────

    def send(self, sal: str, peer_id: str) -> str:
        """Translate outbound SAL for the target peer.

        - ESTABLISHED peer: returns SAL unchanged.
        - ACQUIRED peer: returns SAL unchanged (peer understands it).
        - FALLBACK peer: decodes to NL, optionally annotated with SAL.
        - Unknown peer: auto-registers as FALLBACK, then translates.

        Returns the message string to transmit to the peer.
        """
        session = self._sessions.get(peer_id)
        if session is None:
            self.register_peer(peer_id, attempt_fnp=False)
            session = self._sessions[peer_id]

        # Native OSMP peer — send SAL directly
        if session.state in ("ESTABLISHED", "SYNC_NEEDED"):
            self._emit("send_sal", peer_id, sal=sal, detail="native OSMP peer")
            return sal

        # ACQUIRED peer — send SAL directly (they learned it)
        if session.state == "ACQUIRED":
            self._emit("send_sal", peer_id, sal=sal, detail="acquired peer, sending SAL")
            return sal

        # FALLBACK peer — decode to NL
        nl = self._decode_to_nl(sal)

        if self.annotate:
            annotated = f"{nl}\n[SAL: {sal}]"
            self._emit("annotate", peer_id, sal=sal, nl=nl,
                        detail="annotated outbound for context seeding")
            return annotated

        self._emit("passthrough", peer_id, sal=sal, nl=nl,
                    detail="outbound decoded to NL, no annotation")
        return nl

    # ── inbound: whatever the peer sends → SAL or NL_PASSTHROUGH ────

    def receive(self, message: str, peer_id: str) -> BridgeInbound:
        """Process an inbound message from a peer.

        Scans for valid SAL fragments. Updates acquisition metrics.
        Transitions FALLBACK → ACQUIRED when threshold is met.
        Transitions ACQUIRED → FALLBACK on regression.

        Returns a BridgeInbound with the parsed result.
        """
        session = self._sessions.get(peer_id)
        if session is None:
            self.register_peer(peer_id, attempt_fnp=False)
            session = self._sessions[peer_id]

        metrics = self._metrics[peer_id]

        # For native OSMP peers, pass through as SAL
        if session.state in ("ESTABLISHED", "SYNC_NEEDED"):
            return BridgeInbound(sal=message, nl=None, passthrough=False,
                                 peer_id=peer_id, state=session.state)

        # Scan for SAL fragments
        detected_frames = self._detect_sal_frames(message)

        if detected_frames:
            metrics.record_hit(detected_frames)
            self._emit("detect_sal", peer_id,
                        sal=message, frames_detected=len(detected_frames),
                        detail=f"valid SAL frames: {[f'{ns}:{op}' for ns,op in detected_frames]}")

            # Check for acquisition transition
            if (session.state == "FALLBACK"
                    and metrics.consecutive_sal_hits >= self.acquisition_threshold):
                session.acquire()
                self._emit("acquire", peer_id,
                            detail=f"acquisition threshold met ({self.acquisition_threshold} "
                                   f"consecutive hits, {len(metrics.unique_opcodes_seen)} unique opcodes)")

            # If the entire message parses as valid SAL, return it as SAL
            if self._is_pure_sal(message):
                return BridgeInbound(sal=message, nl=None, passthrough=False,
                                     peer_id=peer_id, state=session.state)

            # Mixed content — return both
            return BridgeInbound(sal=None, nl=message, passthrough=True,
                                 peer_id=peer_id, state=session.state,
                                 detected_frames=[f"{ns}:{op}" for ns, op in detected_frames])
        else:
            metrics.record_miss()

            # Check for regression
            if (session.state == "ACQUIRED"
                    and metrics.consecutive_sal_misses >= self.regression_threshold):
                session.regress()
                self._emit("regress", peer_id,
                            detail=f"regression threshold met ({self.regression_threshold} "
                                   f"consecutive misses)")

            return BridgeInbound(sal=None, nl=message, passthrough=True,
                                 peer_id=peer_id, state=session.state)

    # ── metrics and logging ──────────────────────────────────────────

    def get_metrics(self, peer_id: str) -> AcquisitionMetrics | None:
        """Return acquisition metrics for a peer."""
        return self._metrics.get(peer_id)

    def get_log(self, peer_id: str | None = None,
                last_n: int | None = None) -> list[BridgeEvent]:
        """Return bridge event log, optionally filtered by peer and count."""
        events = self._log
        if peer_id is not None:
            events = [e for e in events if e.remote_id == peer_id]
        if last_n is not None:
            events = events[-last_n:]
        return events

    def get_comparison(self, peer_id: str) -> list[dict]:
        """Return side-by-side SAL vs NL for all annotated messages to a peer.

        This is the measurement data for the efficiency comparison.
        Each entry contains: sal, nl, sal_bytes, nl_bytes, reduction_pct.
        """
        comparisons = []
        for event in self._log:
            if event.remote_id == peer_id and event.event_type == "annotate":
                sal_bytes = len(event.sal.encode("utf-8")) if event.sal else 0
                nl_bytes = len(event.nl.encode("utf-8")) if event.nl else 0
                reduction = (1 - sal_bytes / nl_bytes) * 100 if nl_bytes > 0 else 0
                comparisons.append({
                    "sal": event.sal,
                    "nl": event.nl,
                    "sal_bytes": sal_bytes,
                    "nl_bytes": nl_bytes,
                    "reduction_pct": round(reduction, 1),
                    "timestamp": event.timestamp,
                })
        return comparisons

    def summary(self) -> dict:
        """Return a summary of all bridge activity across all peers."""
        peers = {}
        for peer_id in self._sessions:
            session = self._sessions[peer_id]
            metrics = self._metrics.get(peer_id, AcquisitionMetrics())
            peers[peer_id] = {
                "state": session.state,
                "total_messages": metrics.total_messages,
                "messages_with_sal": metrics.messages_with_sal,
                "acquisition_score": round(metrics.acquisition_score, 2),
                "unique_opcodes_seen": sorted(metrics.unique_opcodes_seen),
                "peak_consecutive_hits": metrics.peak_consecutive_hits,
            }
        return {
            "node_id": self.node_id,
            "annotate": self.annotate,
            "acquisition_threshold": self.acquisition_threshold,
            "regression_threshold": self.regression_threshold,
            "peers": peers,
            "total_events": len(self._log),
        }

    # ── internal ─────────────────────────────────────────────────────

    def _decode_to_nl(self, sal: str) -> str:
        """Decode a SAL string to natural language using the ASD.

        Single-frame and ;-separated chains are both handled natively by
        ``SALDecoder.decode_natural_language``. No splitting workaround needed.
        """
        return self._decoder.decode_natural_language(sal)

    def _detect_sal_frames(self, message: str) -> list[tuple[str, str]]:
        """Scan a message for valid SAL frames.

        Returns list of (namespace, opcode) tuples that resolve in the ASD.
        Only counts frames where the opcode actually exists in the dictionary.
        """
        candidates = _SAL_FRAME_RE.findall(message)
        valid = []
        for ns, op in candidates:
            definition = self.asd.lookup(ns, op)
            if definition is not None:
                valid.append((ns, op))
        return valid

    def _is_pure_sal(self, message: str) -> bool:
        """Check if a message is entirely valid SAL (no NL mixed in).

        A message is pure SAL if removing every valid SAL frame, every
        chain operator, and every whitespace character leaves nothing
        behind. This is a stricter test than the substring search the
        previous implementation used: an NL message containing a
        ``"please use I:§ before proceeding"`` substring is NOT pure
        SAL even though it contains a valid SAL frame.

        Finding 48: previously this method used ``_SAL_FRAME_RE.search``
        which returned True for any string containing a SAL match
        anywhere, causing natural-language inbound messages to be
        misclassified as pure SAL and routed through the wrong code
        path in ``receive``.
        """
        stripped = message.strip()
        if not stripped:
            return False

        # Strip every valid SAL frame from the message. After this,
        # only operators, whitespace, and (if any) NL prose should
        # remain. Pure SAL has nothing left after also stripping
        # operators and whitespace.
        residue = stripped
        # Iteratively remove every match of the SAL frame regex with
        # its surrounding @target, ?query, :slot, [bracket], and
        # consequence class tail. We use a single comprehensive
        # frame pattern for the strip step so we don't leave behind
        # tail elements that would confuse the residue check.
        frame_with_tail_re = re.compile(
            r"\b" + _NS_PATTERN + r":" + _OPCODE_PATTERN
            + r"(?:@[A-Za-z0-9_*\-]+)?"
            + r"(?:\?[A-Za-z0-9_]+)?"
            + r"(?:\[[^\]]*\])?"
            + r"(?::[A-Za-z0-9_]+(?::[A-Za-z0-9_.\-]+)?)*"
            + r"(?:[\u26a0\u21ba\u2298])?"
        )
        residue = frame_with_tail_re.sub("", residue)
        # Strip chain operators, parentheses, and whitespace
        residue = re.sub(r"[\u2227\u2228\u00ac\u2192\u2194\u2225\u27f3"
                         r"\u2260\u2295;\s()]", "", residue)
        if residue:
            # Anything left is NL prose — not pure SAL
            return False

        # Second pass: every recognized frame must validate cleanly
        # under the composition rules (no warnings either, since
        # MIXED_MODE warnings indicate borderline cases the strip
        # logic didn't catch).
        frames = [f.strip() for f in stripped.split(";") if f.strip()]
        for frame in frames:
            if not _SAL_FRAME_RE.search(frame):
                return False
            result = validate_composition(frame, "", self.asd)
            if not result.valid:
                return False
            # MIXED_MODE warnings indicate the frame contains NL prose
            # the strip pass didn't catch — treat as not pure SAL
            for issue in result.warnings:
                if issue.rule == "MIXED_MODE":
                    return False
        return True

    def _emit(self, event_type: str, remote_id: str, **kwargs) -> None:
        """Append a bridge event to the log."""
        self._log.append(BridgeEvent(
            timestamp=time.time(),
            event_type=event_type,
            remote_id=remote_id,
            sal=kwargs.get("sal"),
            nl=kwargs.get("nl"),
            frames_detected=kwargs.get("frames_detected", 0),
            detail=kwargs.get("detail", ""),
        ))


# ─────────────────────────────────────────────────────────────────────────────
# INBOUND RESULT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BridgeInbound:
    """Result of bridge.receive().

    Attributes
    ----------
    sal : str or None
        SAL representation if the message was valid SAL.
    nl : str or None
        Natural language content if the message was NL or mixed.
    passthrough : bool
        True if this is an NL_PASSTHROUGH (unencoded external input).
    peer_id : str
        Identity of the sending peer.
    state : str
        FNP session state at time of receipt.
    detected_frames : list[str]
        Any valid SAL frames detected in a mixed-content message.
    """

    sal: str | None
    nl: str | None
    passthrough: bool
    peer_id: str
    state: str
    detected_frames: list[str] = field(default_factory=list)
