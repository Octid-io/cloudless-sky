/**
 * OSMP SALBridge — Language propagation through contact.
 *
 * The bridge sits at the boundary between an OSMP-native swarm and non-OSMP
 * agents. It detects peers, falls back to NL, annotates outbound messages
 * with SAL equivalents, and monitors inbound messages for SAL acquisition.
 *
 * OSMP does not spread by installation. It spreads by contact.
 *
 * Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
 * License: Apache 2.0
 */

import { AdaptiveSharedDictionary } from "./asd.js";
import { FNPSession, FNP_CAP_UNCONSTRAINED } from "./fnp.js";
import type { FNPState } from "./fnp.js";

// ── SAL frame detection ────────────────────────────────────────────

import {
  SAL_FRAME_RE_BRIDGE as SAL_FRAME_RE,
  NS_PATTERN,
  OPCODE_PATTERN,
} from "./sal_patterns.js";

const DEFAULT_ACQUISITION_THRESHOLD = 5;
const DEFAULT_REGRESSION_THRESHOLD = 3;

// ── types ──────────────────────────────────────────────────────────

export interface AcquisitionMetrics {
  totalMessages: number;
  messagesWithSal: number;
  consecutiveSalHits: number;
  consecutiveSalMisses: number;
  peakConsecutiveHits: number;
  validFramesSeen: number;
  uniqueOpcodesSeen: Set<string>;
  firstSalSeenAt: number | null;
  lastSalSeenAt: number | null;
}

export interface BridgeEvent {
  timestamp: number;
  eventType: string;
  remoteId: string;
  sal: string | null;
  nl: string | null;
  framesDetected: number;
  detail: string;
}

export interface BridgeInbound {
  sal: string | null;
  nl: string | null;
  passthrough: boolean;
  peerId: string;
  state: FNPState;
  detectedFrames: string[];
}

export interface BridgeSummary {
  nodeId: string;
  annotate: boolean;
  acquisitionThreshold: number;
  regressionThreshold: number;
  peers: Record<string, {
    state: FNPState;
    totalMessages: number;
    messagesWithSal: number;
    acquisitionScore: number;
    uniqueOpcodesSeen: string[];
    peakConsecutiveHits: number;
  }>;
  totalEvents: number;
}

// ── helpers ────────────────────────────────────────────────────────

function newMetrics(): AcquisitionMetrics {
  return {
    totalMessages: 0,
    messagesWithSal: 0,
    consecutiveSalHits: 0,
    consecutiveSalMisses: 0,
    peakConsecutiveHits: 0,
    validFramesSeen: 0,
    uniqueOpcodesSeen: new Set(),
    firstSalSeenAt: null,
    lastSalSeenAt: null,
  };
}

function acquisitionScore(m: AcquisitionMetrics, threshold: number): number {
  if (m.totalMessages === 0) return 0;
  return Math.min(1.0, m.consecutiveSalHits / threshold);
}

// ── SALBridge ──────────────────────────────────────────────────────

export class SALBridge {
  readonly nodeId: string;
  readonly asd: AdaptiveSharedDictionary;
  readonly annotate: boolean;
  readonly acquisitionThreshold: number;
  readonly regressionThreshold: number;

  private sessions: Map<string, FNPSession> = new Map();
  private metrics: Map<string, AcquisitionMetrics> = new Map();
  private log: BridgeEvent[] = [];

  constructor(
    nodeId: string,
    asd?: AdaptiveSharedDictionary,
    annotate: boolean = true,
    acquisitionThreshold: number = DEFAULT_ACQUISITION_THRESHOLD,
    regressionThreshold: number = DEFAULT_REGRESSION_THRESHOLD,
  ) {
    this.nodeId = nodeId;
    this.asd = asd ?? new AdaptiveSharedDictionary();
    this.annotate = annotate;
    this.acquisitionThreshold = acquisitionThreshold;
    this.regressionThreshold = regressionThreshold;
  }

  // ── peer management ────────────────────────────────────────────

  registerPeer(peerId: string, attemptFnp: boolean = true): FNPState {
    const session = new FNPSession(this.asd, this.nodeId, 1, FNP_CAP_UNCONSTRAINED);
    this.sessions.set(peerId, session);
    this.metrics.set(peerId, newMetrics());

    if (!attemptFnp) {
      session.fallback(peerId);
      this.emit("fallback", peerId, { detail: "direct registration, no FNP attempt" });
    }

    return session.state;
  }

  peerState(peerId: string): FNPState | null {
    const session = this.sessions.get(peerId);
    return session ? session.state : null;
  }

  // ── outbound: SAL → whatever the peer speaks ───────────────────

  send(sal: string, peerId: string): string {
    let session = this.sessions.get(peerId);
    if (!session) {
      this.registerPeer(peerId, false);
      session = this.sessions.get(peerId)!;
    }

    // Native OSMP or ACQUIRED peer — send SAL directly
    if (session.state === "ESTABLISHED" || session.state === "ESTABLISHED_SAIL" || session.state === "ESTABLISHED_SAL_ONLY" || session.state === "SYNC_NEEDED") {
      this.emit("send_sal", peerId, { sal, detail: "native OSMP peer" });
      return sal;
    }

    if (session.state === "ACQUIRED") {
      this.emit("send_sal", peerId, { sal, detail: "acquired peer, sending SAL" });
      return sal;
    }

    // FALLBACK — decode to NL
    const nl = this.decodeToNl(sal);

    if (this.annotate) {
      const annotated = `${nl}\n[SAL: ${sal}]`;
      this.emit("annotate", peerId, { sal, nl, detail: "annotated outbound for context seeding" });
      return annotated;
    }

    this.emit("passthrough", peerId, { sal, nl, detail: "outbound decoded to NL, no annotation" });
    return nl;
  }

  // ── inbound: whatever the peer sends → SAL or NL_PASSTHROUGH ──

  receive(message: string, peerId: string): BridgeInbound {
    let session = this.sessions.get(peerId);
    if (!session) {
      this.registerPeer(peerId, false);
      session = this.sessions.get(peerId)!;
    }

    const m = this.metrics.get(peerId)!;

    // Native OSMP peer — pass through as SAL
    if (session.state === "ESTABLISHED" || session.state === "ESTABLISHED_SAIL" || session.state === "ESTABLISHED_SAL_ONLY" || session.state === "SYNC_NEEDED") {
      return { sal: message, nl: null, passthrough: false, peerId, state: session.state, detectedFrames: [] };
    }

    // Scan for SAL fragments
    const detected = this.detectSalFrames(message);

    if (detected.length > 0) {
      // Record hit
      const now = Date.now();
      m.totalMessages++;
      m.messagesWithSal++;
      m.consecutiveSalHits++;
      m.consecutiveSalMisses = 0;
      m.validFramesSeen += detected.length;
      for (const [ns, op] of detected) m.uniqueOpcodesSeen.add(`${ns}:${op}`);
      if (m.consecutiveSalHits > m.peakConsecutiveHits) m.peakConsecutiveHits = m.consecutiveSalHits;
      if (m.firstSalSeenAt === null) m.firstSalSeenAt = now;
      m.lastSalSeenAt = now;

      this.emit("detect_sal", peerId, {
        sal: message,
        framesDetected: detected.length,
        detail: `valid SAL frames: ${detected.map(([ns, op]) => `${ns}:${op}`).join(", ")}`,
      });

      // Check acquisition transition
      if (session.state === "FALLBACK" && m.consecutiveSalHits >= this.acquisitionThreshold) {
        session.acquire();
        this.emit("acquire", peerId, {
          detail: `acquisition threshold met (${this.acquisitionThreshold} consecutive hits, ${m.uniqueOpcodesSeen.size} unique opcodes)`,
        });
      }

      // If entire message is pure SAL, return as SAL
      if (this.isPureSal(message)) {
        return { sal: message, nl: null, passthrough: false, peerId, state: session.state, detectedFrames: [] };
      }

      // Mixed content
      return {
        sal: null, nl: message, passthrough: true, peerId, state: session.state,
        detectedFrames: detected.map(([ns, op]) => `${ns}:${op}`),
      };
    } else {
      // Record miss
      m.totalMessages++;
      m.consecutiveSalHits = 0;
      m.consecutiveSalMisses++;

      // Check regression
      if (session.state === "ACQUIRED" && m.consecutiveSalMisses >= this.regressionThreshold) {
        session.regress();
        this.emit("regress", peerId, {
          detail: `regression threshold met (${this.regressionThreshold} consecutive misses)`,
        });
      }

      return { sal: null, nl: message, passthrough: true, peerId, state: session.state, detectedFrames: [] };
    }
  }

  // ── metrics and logging ────────────────────────────────────────

  getMetrics(peerId: string): AcquisitionMetrics | null {
    return this.metrics.get(peerId) ?? null;
  }

  getLog(peerId?: string, lastN?: number): BridgeEvent[] {
    let events = this.log;
    if (peerId !== undefined) events = events.filter(e => e.remoteId === peerId);
    if (lastN !== undefined) events = events.slice(-lastN);
    return events;
  }

  getComparison(peerId: string): Array<{
    sal: string; nl: string; salBytes: number; nlBytes: number; reductionPct: number; timestamp: number;
  }> {
    return this.log
      .filter(e => e.remoteId === peerId && e.eventType === "annotate" && e.sal && e.nl)
      .map(e => {
        const salBytes = new TextEncoder().encode(e.sal!).length;
        const nlBytes = new TextEncoder().encode(e.nl!).length;
        const reduction = nlBytes > 0 ? (1 - salBytes / nlBytes) * 100 : 0;
        return { sal: e.sal!, nl: e.nl!, salBytes, nlBytes, reductionPct: Math.round(reduction * 10) / 10, timestamp: e.timestamp };
      });
  }

  summary(): BridgeSummary {
    const peers: BridgeSummary["peers"] = {};
    for (const [peerId, session] of this.sessions) {
      const m = this.metrics.get(peerId) ?? newMetrics();
      peers[peerId] = {
        state: session.state,
        totalMessages: m.totalMessages,
        messagesWithSal: m.messagesWithSal,
        acquisitionScore: Math.round(acquisitionScore(m, this.acquisitionThreshold) * 100) / 100,
        uniqueOpcodesSeen: [...m.uniqueOpcodesSeen].sort(),
        peakConsecutiveHits: m.peakConsecutiveHits,
      };
    }
    return {
      nodeId: this.nodeId,
      annotate: this.annotate,
      acquisitionThreshold: this.acquisitionThreshold,
      regressionThreshold: this.regressionThreshold,
      peers,
      totalEvents: this.log.length,
    };
  }

  // ── internal ───────────────────────────────────────────────────

  private decodeToNl(sal: string): string {
    const frames = sal.split(";").map(f => f.trim()).filter(Boolean);
    return frames.map(f => {
      const match = f.match(/^([A-Z]):([A-Z]+)/);
      if (!match) return f;
      const def = this.asd.lookup(match[1], match[2]);
      return def ? `${def} ${f.slice(match[0].length)}`.trim() : f;
    }).join("; ");
  }

  private detectSalFrames(message: string): Array<[string, string]> {
    const valid: Array<[string, string]> = [];
    const re = new RegExp(SAL_FRAME_RE.source, "g");
    let m: RegExpExecArray | null;
    while ((m = re.exec(message)) !== null) {
      const [, ns, op] = m;
      if (this.asd.lookup(ns, op) !== null) {
        valid.push([ns, op]);
      }
    }
    return valid;
  }

  private isPureSal(message: string): boolean {
    // Finding 48: a message is pure SAL if removing every valid SAL
    // frame (with @target, slots, brackets, consequence class tail),
    // every chain operator, and every whitespace character leaves
    // nothing behind. The previous implementation used .test() on a
    // substring regex, which returned true for natural-language
    // messages that happened to contain a SAL frame anywhere in them.
    const stripped = message.trim();
    if (!stripped) return false;

    // Comprehensive frame-with-tail pattern. Matches a single complete
    // SAL frame including any @target, ?query, :slot, [bracket], and
    // consequence class glyph tail.
    const frameWithTail = new RegExp(
      "\\b" + NS_PATTERN + ":" + OPCODE_PATTERN
      + "(?:@[A-Za-z0-9_*\\-]+)?"
      + "(?:\\?[A-Za-z0-9_]+)?"
      + "(?:\\[[^\\]]*\\])?"
      + "(?::[A-Za-z0-9_]+(?::[A-Za-z0-9_.\\-]+)?)*"
      + "(?:[\\u26a0\\u21ba\\u2298])?",
      "g",
    );
    let residue = stripped.replace(frameWithTail, "");
    // Strip chain operators, parentheses, and whitespace
    residue = residue.replace(
      /[\u2227\u2228\u00ac\u2192\u2194\u2225\u27f3\u2260\u2295;\s()]/g,
      "",
    );
    if (residue.length > 0) {
      // NL prose remains — not pure SAL
      return false;
    }

    // Second pass: every recognized frame must contain a real SAL
    // frame regex match. This catches the trivial empty-string case
    // and any pathological inputs the strip pass might let through.
    const frames = stripped.split(";").map(f => f.trim()).filter(Boolean);
    for (const frame of frames) {
      if (!new RegExp(SAL_FRAME_RE.source).test(frame)) return false;
    }
    return true;
  }

  private emit(eventType: string, remoteId: string, opts: {
    sal?: string; nl?: string; framesDetected?: number; detail?: string;
  } = {}): void {
    this.log.push({
      timestamp: Date.now(),
      eventType,
      remoteId,
      sal: opts.sal ?? null,
      nl: opts.nl ?? null,
      framesDetected: opts.framesDetected ?? 0,
      detail: opts.detail ?? "",
    });
  }
}
