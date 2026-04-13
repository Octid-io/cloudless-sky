/**
 * FNP — Frame Negotiation Protocol
 *
 * Two-message capability advertisement + acknowledgment completing within
 * 78 bytes total (40 ADV + 38 ACK), designed for LoRa physical layer floor.
 *
 * Negotiates three properties in two packets:
 *   1. Dictionary alignment (ASD fingerprint match)
 *   2. Namespace intersection (shared domain capabilities)
 *   3. Channel capacity (byte budget for the session)
 *
 * Patent ref: OSMP-001-UTIL Section II.C, FIG. 5
 */
import { AdaptiveSharedDictionary } from "./asd.js";
export declare const FNP_MSG_ADV = 1;
export declare const FNP_MSG_ACK = 2;
export declare const FNP_MSG_NACK = 3;
export declare const FNP_MSG_ADV_EXTENDED = 129;
export declare const FNP_ADV_EXT_FLAG = 128;
export declare const FNP_MATCH_EXACT = 0;
export declare const FNP_MATCH_VERSION = 1;
export declare const FNP_MATCH_FINGERPRINT = 2;
export declare const FNP_MATCH_BASIS_MISMATCH = 3;
export declare const FNP_MATCH_BASIS_EXT_VS_BASE = 4;
export declare const FNP_CAP_FLOOR = 0;
export declare const FNP_CAP_STANDARD = 1;
export declare const FNP_CAP_BLE = 2;
export declare const FNP_CAP_UNCONSTRAINED = 3;
export declare const FNP_CAP_BYTES: Record<number, number>;
export declare const FNP_ADV_SIZE = 40;
export declare const FNP_ACK_SIZE = 38;
export declare const FNP_PROTOCOL_VERSION = 1;
export type FNPState = "IDLE" | "ADV_SENT" | "ESTABLISHED" | "ESTABLISHED_SAIL" | "ESTABLISHED_SAL_ONLY" | "SYNC_NEEDED" | "FALLBACK" | "ACQUIRED";
export interface FNPSessionInfo {
    state: FNPState;
    remoteNodeId: string | null;
    remoteFingerprint: Uint8Array | null;
    commonNamespaces: string[] | null;
    matchStatus: number | null;
    negotiatedCapacity: number | null;
}
/**
 * FNP session handshake state machine.
 *
 * Manages the two-message capability advertisement and acknowledgment
 * exchange between two sovereign nodes. After a successful handshake,
 * provides the negotiated session state: whether dictionaries match,
 * which namespaces are shared, the channel byte budget, and the remote
 * node's identity.
 *
 * Usage (initiator):
 *   const session = new FNPSession(asd, "NODE_A");
 *   const adv = session.initiate();
 *   // ... transmit adv, receive ackPacket ...
 *   session.receive(ackPacket);
 *   // session.state === "ESTABLISHED"
 *
 * Usage (responder):
 *   const session = new FNPSession(asd, "NODE_B");
 *   const ack = session.receive(advPacket);
 *   // ... transmit ack ...
 *   // session.state === "ESTABLISHED"
 */
export declare class FNPSession {
    private asd;
    private nodeId;
    private asdVersion;
    private channelCapacity;
    private ownFp;
    private ownBitmap;
    basisFingerprint: Uint8Array | null;
    expectedBasisFingerprint: Uint8Array | null;
    requireSail: boolean;
    remoteBasisFingerprint: Uint8Array | null;
    degradationEvent: Record<string, any> | null;
    state: FNPState;
    remoteNodeId: string | null;
    remoteFingerprint: Uint8Array | null;
    commonNamespaces: string[] | null;
    matchStatus: number | null;
    negotiatedCapacity: number | null;
    constructor(asd: AdaptiveSharedDictionary, nodeId: string, asdVersion?: number, channelCapacity?: number, opts?: {
        basisFingerprint?: Uint8Array;
        expectedBasisFingerprint?: Uint8Array;
        requireSail?: boolean;
    });
    /** True if this session uses extended-form ADV (basis_fingerprint set). */
    get isExtendedForm(): boolean;
    /** True if the negotiated session supports SAIL wire mode (ADR-004). */
    get isSailCapable(): boolean;
    private buildAdv;
    private buildAck;
    static parseAdv(data: Uint8Array): {
        msgType: number;
        isExtended: boolean;
        protocolVersion: number;
        fingerprint: Uint8Array;
        asdVersion: number;
        namespaceBitmap: number;
        channelCapacity: number;
        nodeId: string;
        basisFingerprint: Uint8Array | null;
    };
    private static parseAck;
    /** Start a handshake. Returns a 40-byte ADV packet. IDLE -> ADV_SENT. */
    initiate(): Uint8Array;
    /**
     * Process a received FNP packet.
     *
     * If IDLE and ADV received: returns ACK packet to transmit.
     * If ADV_SENT and ACK received: processes result, returns null.
     */
    receive(data: Uint8Array): Uint8Array | null;
    private applyMatchToState;
    /** Handle timeout. ADV_SENT -> IDLE. */
    timeout(): void;
    /**
     * Transition to FALLBACK when the remote peer does not speak OSMP.
     *
     * Called when:
     * - ADV was sent but the response is not a valid FNP packet
     * - The transport is known to be non-OSMP (e.g., plain JSON-RPC, NL)
     * - Timeout occurred during negotiation attempt with a new peer
     *
     * Transitions: ADV_SENT -> FALLBACK, or IDLE -> FALLBACK (direct).
     */
    fallback(remoteId?: string): void;
    /**
     * Transition to ACQUIRED when the remote peer starts producing valid SAL.
     * Called by SALBridge when the acquisition score exceeds threshold.
     * Transitions: FALLBACK -> ACQUIRED.
     */
    acquire(): void;
    /**
     * Transition back to FALLBACK when an ACQUIRED peer stops producing valid SAL.
     * Transitions: ACQUIRED -> FALLBACK.
     */
    regress(): void;
    /** True if this session is in FALLBACK or ACQUIRED state. */
    isLegacyPeer(): boolean;
    /** True if this session is in ACQUIRED state. */
    isAcquired(): boolean;
}
