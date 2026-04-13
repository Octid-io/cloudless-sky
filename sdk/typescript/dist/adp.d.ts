/**
 * ASD Distribution Protocol (ADP) — SAL-layer dictionary synchronization
 *
 * Complements the binary FNP handshake with SAL-level instructions for
 * version identity exchange, delta delivery, micro-delta, hash verification,
 * and MDR corpus version tracking.
 *
 * Patent ref: OSMP-001-UTIL Claims 20-21, Section VII.F, X-L
 * License: Apache 2.0
 */
import { AdaptiveSharedDictionary } from "./asd.js";
export declare function asdVersionPack(major: number, minor: number): number;
export declare function asdVersionUnpack(u16: number): [number, number];
export declare function asdVersionStr(u16: number): string;
export declare function asdVersionParse(s: string): number;
export declare function asdVersionIsBreaking(oldU16: number, newU16: number): boolean;
export declare const ADP_PRIORITY_MISSION = 0;
export declare const ADP_PRIORITY_MICRO = 1;
export declare const ADP_PRIORITY_DELTA = 2;
export declare const ADP_PRIORITY_TRICKLE = 3;
export interface ADPDeltaOp {
    namespace: string;
    mode: string;
    opcode: string;
    definition?: string;
}
export declare function deltaOpToSal(op: ADPDeltaOp): string;
export declare function deltaOpIsBreaking(op: ADPDeltaOp): boolean;
export interface ADPDelta {
    fromVersion: string;
    toVersion: string;
    operations: ADPDeltaOp[];
}
export declare function deltaToSal(d: ADPDelta): string;
export declare function deltaHasBreaking(d: ADPDelta): boolean;
export interface PendingInstruction {
    sal: string;
    unresolvedNamespace: string;
    unresolvedOpcode: string;
    timestamp: number;
}
export declare class ADPSession {
    asd: AdaptiveSharedDictionary;
    asdVersion: number;
    namespaceVersions: Record<string, string>;
    pendingQueue: PendingInstruction[];
    deltaLog: string[];
    remoteVersion: number | null;
    remoteNamespaceVersions: Record<string, string> | null;
    constructor(asd: AdaptiveSharedDictionary, asdVersion?: number, namespaceVersions?: Record<string, string>);
    versionIdentity(includeNamespaces?: boolean): string;
    versionQuery(): string;
    versionAlert(): string;
    receiveVersion(sal: string): {
        version: string;
        u16: number;
        namespaces: Record<string, string>;
        breaking: boolean;
        match: boolean;
    };
    requestDelta(target?: string, namespace?: string): string;
    applyDeltaSal(sal: string): {
        applied: boolean;
        from?: string;
        to?: string;
        operations?: string[];
        breaking?: boolean;
        pendingResolved?: string[];
        error?: string;
    };
    requestDefinition(namespace: string, opcode: string): string;
    sendDefinition(namespace: string, opcode: string, definition: string, layer?: number): string;
    applyDefinition(sal: string): {
        applied: boolean;
        namespace?: string;
        opcode?: string;
        definition?: string;
        layer?: number;
        pendingResolved?: string[];
        error?: string;
    };
    hashIdentity(hexLength?: number): string;
    verifyHash(sal: string): {
        match: boolean;
        remoteHash?: string;
        localHash?: string;
    };
    static mdrIdentity(corpora: Record<string, string>): string;
    static mdrRequest(corpus: string, fromVer: string, toVer: string): string;
    resolveOrPend(sal: string): {
        resolved: boolean;
        pending: boolean;
        definition?: string;
        unresolved?: string;
        microDeltaRequest?: string;
        queueDepth?: number;
    };
    private resolvePending;
    private static extractNsOpcode;
    static acknowledgeVersion(version: string): string;
    static acknowledgeHash(): string;
    static acknowledgeDef(): string;
    static classifyPriority(sal: string): number;
}
