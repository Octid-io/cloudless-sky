/**
 * OSMP SAL Decoder — inference-free table lookup
 * Analog: HPACK static table decode (RFC 7541 §A)
 * Patent pending | License: Apache 2.0
 */
import { AdaptiveSharedDictionary } from "./asd.js";
import { ASD_BASIS, CONSEQUENCE_CLASSES } from "./glyphs.js";
export class OSMPDecoder {
    asd;
    constructor(asd) { this.asd = asd ?? new AdaptiveSharedDictionary(); }
    resolveShortForm(opcode) {
        for (const [ns, ops] of Object.entries(ASD_BASIS))
            if (opcode in ops)
                return ns;
        return "A";
    }
    firstStop(s, stops) {
        let e = s.length;
        for (const sc of stops) {
            const i = s.indexOf(sc);
            if (i !== -1 && i < e)
                e = i;
        }
        return e;
    }
    decodeFrame(encoded) {
        const raw = encoded.trim();
        let remaining = raw;
        let consequenceClass = null;
        let consequenceClassName = null;
        for (const [glyph, entry] of Object.entries(CONSEQUENCE_CLASSES)) {
            if (remaining.endsWith(glyph)) {
                consequenceClass = glyph;
                consequenceClassName = entry.name;
                const runes = [...remaining];
                const gr = [...glyph];
                remaining = runes.slice(0, runes.length - gr.length).join("");
                break;
            }
        }
        const beforeTarget = remaining.split("@")[0].split("?")[0];
        const hasExplicitNS = beforeTarget.includes(":");
        let namespace;
        if (hasExplicitNS) {
            const ci = remaining.indexOf(":");
            namespace = remaining.slice(0, ci);
            remaining = remaining.slice(ci + 1);
        }
        else {
            namespace = this.resolveShortForm(remaining.split("@")[0].split("?")[0]);
        }
        const opEnd = this.firstStop(remaining, ["@", "?", ":"]);
        const opcode = remaining.slice(0, opEnd);
        remaining = remaining.slice(opEnd);
        const opcodeMeaning = this.asd.lookup(namespace, opcode);
        let target = null;
        if (remaining.startsWith("@")) {
            remaining = remaining.slice(1);
            const e = this.firstStop(remaining, ["?", ":", "\u2227", "\u2228", "\u2192", "\u2194", ";", "\u2225"]);
            target = remaining.slice(0, e);
            remaining = remaining.slice(e);
        }
        let querySlot = null;
        if (remaining.startsWith("?")) {
            remaining = remaining.slice(1);
            const e = this.firstStop(remaining, [":", "\u2227", "\u2228", "\u2192", ";"]);
            querySlot = remaining.slice(0, e);
            remaining = remaining.slice(e);
        }
        const slots = {};
        while (remaining.startsWith(":")) {
            remaining = remaining.slice(1);
            const ci = remaining.indexOf(":");
            if (ci === -1) {
                slots[remaining] = "";
                remaining = "";
                break;
            }
            const sn = remaining.slice(0, ci);
            remaining = remaining.slice(ci + 1);
            const ve = this.firstStop(remaining, [":", "\u2227", "\u2228", "\u2192", ";", "\u26a0", "\u21ba", "\u2298"]);
            slots[sn] = remaining.slice(0, ve);
            remaining = remaining.slice(ve);
        }
        return { namespace, opcode, opcodeMeaning, target, querySlot, slots,
            consequenceClass, consequenceClassName, raw };
    }
}
//# sourceMappingURL=decoder.js.map