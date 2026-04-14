/**
 * OSMP SAL Encoder
 * Patent pending | License: Apache 2.0
 */
import { AdaptiveSharedDictionary } from "./asd.js";
export declare class OSMPEncoder {
    private asd;
    constructor(asd?: AdaptiveSharedDictionary);
    encodeFrame(namespace: string, opcode: string, target?: string, querySlot?: string, slots?: Record<string, string | number>, consequenceClass?: string): string;
    encodeCompound(left: string, operator: string, right: string): string;
    encodeParallel(instructions: string[]): string;
    encodeSequence(instructions: string[]): string;
    encodeBroadcast(namespace: string, opcode: string): string;
}
