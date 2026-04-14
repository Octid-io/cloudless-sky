/**
 * OSMP Overflow Protocol — fragmentation and loss tolerance
 * Analog: QUIC receive buffer (RFC 9000 §2.2)
 * Patent pending | License: Apache 2.0
 */
import { Fragment, LossPolicy } from "./types.js";
export declare function packFragment(f: Fragment): Uint8Array;
export declare function unpackFragment(data: Uint8Array): Fragment;
export declare function isTerminal(f: Fragment): boolean;
export declare function isCritical(f: Fragment): boolean;
export declare class OverflowProtocol {
    private mtu;
    private policy;
    private _counter;
    private _buf;
    constructor(mtu?: number, policy?: LossPolicy, _timeout?: number);
    private nextId;
    fragment(payload: Uint8Array, critical?: boolean): Fragment[];
    receive(frag: Fragment): Uint8Array | null;
    private _reassemble;
    private _reassemblePartial;
    nack(msgId: number, expectedCt: number): string;
}
