/**
 * OSMP SAL Decoder — inference-free table lookup
 * Analog: HPACK static table decode (RFC 7541 §A)
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
import { AdaptiveSharedDictionary } from "./asd.js";
import { DecodedInstruction } from "./types.js";
export declare class OSMPDecoder {
    private asd;
    constructor(asd?: AdaptiveSharedDictionary);
    private resolveShortForm;
    private firstStop;
    decodeFrame(encoded: string): DecodedInstruction;
}
