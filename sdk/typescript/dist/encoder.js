/**
 * OSMP SAL Encoder
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
import { AdaptiveSharedDictionary } from "./asd.js";
import { GLYPH_OPERATORS, COMPOUND_OPERATORS, CONSEQUENCE_CLASSES } from "./glyphs.js";
export class OSMPEncoder {
    asd;
    constructor(asd) { this.asd = asd ?? new AdaptiveSharedDictionary(); }
    encodeFrame(namespace, opcode, target, querySlot, slots, consequenceClass) {
        if (namespace === "R" && (!consequenceClass || !(consequenceClass in CONSEQUENCE_CLASSES)))
            throw new Error(`R namespace requires consequence class (⚠/↺/⊘). Got: ${JSON.stringify(consequenceClass)}`);
        const parts = [`${namespace}:${opcode}`];
        if (target !== undefined)
            parts.push(`@${target}`);
        if (querySlot !== undefined)
            parts.push(`?${querySlot}`);
        if (slots)
            for (const [k, v] of Object.entries(slots))
                parts.push(`:${k}:${v}`);
        if (consequenceClass)
            parts.push(consequenceClass);
        return parts.join("");
    }
    encodeCompound(left, operator, right) {
        if (!(operator in GLYPH_OPERATORS) && !(operator in COMPOUND_OPERATORS))
            throw new Error(`Unknown operator: ${JSON.stringify(operator)}`);
        return `${left}${operator}${right}`;
    }
    encodeParallel(instructions) {
        return `A\u2225[${instructions.map(i => i.startsWith("?") ? i : `?${i}`).join("\u2227")}]`;
    }
    encodeSequence(instructions) { return instructions.join(";"); }
    encodeBroadcast(namespace, opcode) { return `${namespace}:${opcode}@*`; }
}
//# sourceMappingURL=encoder.js.map