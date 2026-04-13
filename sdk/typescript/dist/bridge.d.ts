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
import type { FNPState } from "./fnp.js";
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
export declare class SALBridge {
    readonly nodeId: string;
    readonly asd: AdaptiveSharedDictionary;
    readonly annotate: boolean;
    readonly acquisitionThreshold: number;
    readonly regressionThreshold: number;
    private sessions;
    private metrics;
    private log;
    constructor(nodeId: string, asd?: AdaptiveSharedDictionary, annotate?: boolean, acquisitionThreshold?: number, regressionThreshold?: number);
    registerPeer(peerId: string, attemptFnp?: boolean): FNPState;
    peerState(peerId: string): FNPState | null;
    send(sal: string, peerId: string): string;
    receive(message: string, peerId: string): BridgeInbound;
    getMetrics(peerId: string): AcquisitionMetrics | null;
    getLog(peerId?: string, lastN?: number): BridgeEvent[];
    getComparison(peerId: string): Array<{
        sal: string;
        nl: string;
        salBytes: number;
        nlBytes: number;
        reductionPct: number;
        timestamp: number;
    }>;
    summary(): BridgeSummary;
    private decodeToNl;
    private detectSalFrames;
    private isPureSal;
    private emit;
}
