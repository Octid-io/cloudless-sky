/**
 * OSMP TypeScript SDK — npm: osmp-protocol
 *
 * Tier 1 API: Two functions. Zero setup.
 *
 *     import { encode, decode } from "osmp-protocol";
 *
 *     const sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"]);
 *     const text = decode("H:HR@NODE1>120;H:CASREP;M:EVA@*");
 *
 * Patent pending -- inventor Clay Holberg
 * License: Apache 2.0
 */
import { AdaptiveSharedDictionary as ASD } from "./asd.js";
import { OSMPEncoder } from "./encoder.js";
import { OSMPDecoder } from "./decoder.js";
import { validateComposition as _validateComposition } from "./validate.js";
// ── Lazy singleton ──────────────────────────────────────────────────────────
let _asd = null;
let _enc = null;
let _dec = null;
function _init() {
    if (_asd)
        return;
    _asd = new ASD();
    _enc = new OSMPEncoder(_asd);
    _dec = new OSMPDecoder(_asd);
}
// ── Tier 1 Functions ────────────────────────────────────────────────────────
/**
 * Encode to SAL.
 *
 * Accepts a list of opcode strings, joined with ; (sequence operator).
 * If given a string that looks like SAL, returns it as-is (passthrough).
 *
 * @example
 * encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
 * // => "H:HR@NODE1>120;H:CASREP;M:EVA@*"
 */
export function encode(input) {
    _init();
    if (Array.isArray(input)) {
        return _enc.encodeSequence(input);
    }
    if (typeof input === "string") {
        if (input.includes(":") && /[A-Z]/.test(input))
            return input;
        return input;
    }
    throw new TypeError(`encode() accepts string[] or string, got ${typeof input}. ` +
        `Example: encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])`);
}
/**
 * Decode SAL to natural language. Zero inference.
 * Each frame is resolved by ASD dictionary lookup.
 *
 * @example
 * decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
 * // => "H:heart_rate ->NODE1 >120; H:casualty_report; M:evacuation ->*"
 */
export function decode(sal) {
    _init();
    return sal
        .split(";")
        .map(f => f.trim())
        .filter(f => f.length > 0)
        .map(f => decodeFrameNL(_dec, f))
        .join("; ");
}
function decodeFrameNL(dec, frame) {
    let d;
    try {
        d = dec.decodeFrame(frame);
    }
    catch {
        return `[malformed: "${frame}"]`;
    }
    const meaning = d.opcodeMeaning || d.opcode;
    const parts = [`${d.namespace}:${meaning}`];
    if (d.target)
        parts.push(d.target === "*" ? "\u2192*" : `\u2192${d.target}`);
    if (d.querySlot)
        parts.push(`?${d.querySlot}`);
    for (const [k, v] of Object.entries(d.slots))
        parts.push(`${k}=${v}`);
    if (d.consequenceClassName)
        parts.push(`[${d.consequenceClassName}]`);
    return parts.join(" ");
}
/**
 * Validate a SAL instruction chain against all eight composition rules.
 */
export function validate(sal, nl = "", dependencyRules) {
    _init();
    return _validateComposition(sal, nl, _asd, false, dependencyRules);
}
/**
 * Look up an opcode definition in the ASD.
 * Accepts "H:HR" format. Returns the definition string, or null if not found.
 */
export function lookup(nsOpcode) {
    _init();
    if (!nsOpcode.includes(":"))
        return null;
    const [ns, op] = nsOpcode.split(":", 2);
    return _asd.lookup(ns, op) || null;
}
/**
 * Return UTF-8 byte count of a SAL string.
 */
export function byteSize(sal) {
    return new TextEncoder().encode(sal).byteLength;
}
// ── Tier 2/3 Re-exports ────────────────────────────────────────────────────
export { AdaptiveSharedDictionary } from "./asd.js";
export { validateComposition } from "./validate.js";
export { OSMPEncoder } from "./encoder.js";
export { OSMPDecoder } from "./decoder.js";
export { OverflowProtocol, packFragment, unpackFragment, isTerminal, isCritical } from "./overflow.js";
export { DAGFragmenter, DAGReassembler } from "./dag.js";
export { BAELEncoder, utf8Bytes } from "./bael.js";
export { runBenchmark } from "./benchmark.js";
export { ASD_BASIS, ASD_FLOOR_VERSION, GLYPH_OPERATORS, COMPOUND_OPERATORS, CONSEQUENCE_CLASSES, OUTCOME_STATES, PARAMETER_DESIGNATORS, LOSS_POLICIES, DICT_UPDATE_MODES } from "./glyphs.js";
export { resolveBlk, statsBlk } from "./dpack.js";
export { LossPolicy, BAELMode, DictUpdateMode, FLAG_TERMINAL, FLAG_CRITICAL, FLAG_EXTENDED_DEP, FLAG_NL_PASSTHROUGH, FRAGMENT_HEADER_BYTES, LORA_FLOOR_BYTES, LORA_STANDARD_BYTES } from "./types.js";
export { FNPSession, FNP_MSG_ADV, FNP_MSG_ACK, FNP_MSG_NACK, FNP_MATCH_EXACT, FNP_MATCH_VERSION, FNP_MATCH_FINGERPRINT, FNP_CAP_FLOOR, FNP_CAP_STANDARD, FNP_CAP_BLE, FNP_CAP_UNCONSTRAINED, FNP_CAP_BYTES, FNP_ADV_SIZE, FNP_ACK_SIZE } from "./fnp.js";
export { ADPSession, asdVersionPack, asdVersionUnpack, asdVersionStr, asdVersionParse, asdVersionIsBreaking, deltaToSal, deltaHasBreaking, deltaOpToSal, deltaOpIsBreaking, ADP_PRIORITY_MISSION, ADP_PRIORITY_MICRO, ADP_PRIORITY_DELTA, ADP_PRIORITY_TRICKLE } from "./adp.js";
export { SALBridge } from "./bridge.js";
export { SALComposer } from "./sal_composer.js";
//# sourceMappingURL=index.js.map