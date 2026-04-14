/**
 * OSMP Tier 3 — DAG Decomposition
 * Overflow Protocol Tier 3: directed acyclic graph fragmentation for
 * instructions with conditional branches and dependency chains.
 * Analog: Kahn's algorithm (1962) applied to lossy radio fragment streams.
 *
 * Spec section 8.1 Tier 3 definition.
 * License: Apache 2.0
 */
import { Fragment, LossPolicy } from "./types.js";
/** Single executable unit in a Tier 3 DAG. */
export interface DAGNode {
    index: number;
    payload: Uint8Array;
    parents: number[];
}
export declare class DAGFragmenter {
    private mtu;
    constructor(mtu?: number);
    /** Parse a compound SAL string into DAGNodes. */
    parse(compoundSal: string): DAGNode[];
    private _parseExpr;
    /** Full Tier 3 pipeline: parse → assign DEP → emit Fragments. */
    fragmentize(compoundSal: string, msgId: number, critical?: boolean): Fragment[];
}
export declare class DAGReassembler {
    private policy;
    private _buf;
    constructor(policy?: LossPolicy);
    /** Buffer fragment and attempt DAG resolution. */
    receive(frag: Fragment): Uint8Array[] | null;
    private _getParents;
    private _getPayload;
    private _resolveDAG;
    private _resolveDAGPartial;
    private _ancestorsSatisfied;
    private _topoSort;
    nack(msgId: number, expectedCt: number): string;
}
