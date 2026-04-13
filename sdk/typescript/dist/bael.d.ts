/**
 * OSMP BAEL — Bandwidth-Agnostic Efficiency Layer
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
import { BAELResult } from "./types.js";
export declare function utf8Bytes(s: string): number;
export declare class BAELEncoder {
    static selectMode(nlInput: string, osmpEncoded: string, tclEncoded?: string): BAELResult;
    static compressionFloorCheck(nlInput: string, osmpEncoded: string): {
        nlBytes: number;
        osmpBytes: number;
        selectedMode: string;
        selectedBytes: number;
        reductionPct: number;
        floorApplied: boolean;
        flags: number;
    };
}
