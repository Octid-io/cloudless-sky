/**
 * OSMP Tier 3 — DAG Decomposition
 * Overflow Protocol Tier 3: directed acyclic graph fragmentation for
 * instructions with conditional branches and dependency chains.
 * Analog: Kahn's algorithm (1962) applied to lossy radio fragment streams.
 *
 * Patent: OSMP-001-UTIL claims, spec §8.1 Tier 3 definition.
 * License: Apache 2.0
 */
import { LossPolicy, FLAG_TERMINAL, FLAG_CRITICAL, FLAG_EXTENDED_DEP, LORA_STANDARD_BYTES } from "./types.js";
import { isTerminal } from "./overflow.js";
// ── Helpers ──────────────────────────────────────────────────────────────────
const encoder = new TextEncoder();
function splitTopLevel(expr, sep) {
    const parts = [];
    let depth = 0;
    let current = "";
    let i = 0;
    while (i < expr.length) {
        const ch = expr[i];
        if (ch === "[" || ch === "(") {
            depth++;
            current += ch;
            i++;
        }
        else if (ch === "]" || ch === ")") {
            depth--;
            current += ch;
            i++;
        }
        else if (depth === 0 && expr.slice(i, i + sep.length) === sep) {
            parts.push(current);
            current = "";
            i += sep.length;
        }
        else {
            current += ch;
            i++;
        }
    }
    if (current.length > 0)
        parts.push(current);
    return parts;
}
// ── DAGFragmenter ────────────────────────────────────────────────────────────
export class DAGFragmenter {
    mtu;
    constructor(mtu = LORA_STANDARD_BYTES) { this.mtu = mtu; }
    /** Parse a compound SAL string into DAGNodes. */
    parse(compoundSal) {
        const nodes = [];
        this._parseExpr(compoundSal.trim(), nodes, []);
        return nodes;
    }
    _parseExpr(expr, nodes, parentIndices) {
        // ; (SEQUENCE) — lowest precedence
        let parts = splitTopLevel(expr, ";");
        if (parts.length > 1) {
            let tails = parentIndices;
            for (const part of parts)
                tails = this._parseExpr(part.trim(), nodes, tails);
            return tails;
        }
        // → (THEN) — conditional chain
        parts = splitTopLevel(expr, "→");
        if (parts.length > 1) {
            let tails = parentIndices;
            for (const part of parts)
                tails = this._parseExpr(part.trim(), nodes, tails);
            return tails;
        }
        // ∧ (AND) — parallel fork
        parts = splitTopLevel(expr, "∧");
        if (parts.length > 1) {
            const allTails = [];
            for (const part of parts) {
                const branchTails = this._parseExpr(part.trim(), nodes, parentIndices);
                allTails.push(...branchTails);
            }
            return allTails;
        }
        // A∥[...] — parallel execution block
        if (expr.startsWith("A∥[") && expr.endsWith("]")) {
            const inner = expr.slice("A∥[".length, -1);
            parts = splitTopLevel(inner, "∧");
            if (parts.length <= 1)
                parts = [inner];
            const allTails = [];
            for (let part of parts) {
                part = part.trim();
                if (part.startsWith("?"))
                    part = part.slice(1);
                const branchTails = this._parseExpr(part, nodes, parentIndices);
                allTails.push(...branchTails);
            }
            return allTails;
        }
        // Atomic leaf node
        const idx = nodes.length;
        nodes.push({ index: idx, payload: encoder.encode(expr), parents: [...parentIndices] });
        return [idx];
    }
    /** Full Tier 3 pipeline: parse → assign DEP → emit Fragments. */
    fragmentize(compoundSal, msgId, critical = false) {
        const nodes = this.parse(compoundSal);
        if (nodes.length === 0)
            return [];
        const fragCt = nodes.length;
        const frags = [];
        for (const node of nodes) {
            const isLast = node.index === fragCt - 1;
            let flags = (isLast ? FLAG_TERMINAL : 0) | (critical ? FLAG_CRITICAL : 0);
            let dep;
            let payload;
            if (node.parents.length === 0) {
                dep = node.index; // self-reference = root
                payload = node.payload;
            }
            else if (node.parents.length === 1) {
                dep = node.parents[0];
                payload = node.payload;
            }
            else {
                flags |= FLAG_EXTENDED_DEP;
                dep = node.parents[0]; // primary dep for legacy readers
                let bitmap = 0;
                for (const p of node.parents)
                    bitmap |= (1 << p);
                const bitmapBuf = new Uint8Array(4);
                new DataView(bitmapBuf.buffer).setUint32(0, bitmap, false); // big-endian
                payload = new Uint8Array(4 + node.payload.length);
                payload.set(bitmapBuf, 0);
                payload.set(node.payload, 4);
            }
            frags.push({ msgId, fragIdx: node.index, fragCt, flags, dep, payload });
        }
        return frags;
    }
}
// ── DAGReassembler ───────────────────────────────────────────────────────────
export class DAGReassembler {
    policy;
    _buf = new Map();
    constructor(policy = LossPolicy.GRACEFUL_DEGRADATION) { this.policy = policy; }
    /** Buffer fragment and attempt DAG resolution. */
    receive(frag) {
        // R:ESTOP hard exception
        if (new TextDecoder().decode(frag.payload).includes("R:ESTOP"))
            return [frag.payload];
        const mid = frag.msgId;
        if (!this._buf.has(mid))
            this._buf.set(mid, new Map());
        this._buf.get(mid).set(frag.fragIdx, frag);
        const rcv = this._buf.get(mid);
        const exp = frag.fragCt;
        if (this.policy === LossPolicy.FAIL_SAFE) {
            return rcv.size === exp ? this._resolveDAG(rcv) : null;
        }
        else if (this.policy === LossPolicy.ATOMIC) {
            return rcv.size === exp ? this._resolveDAG(rcv) : null;
        }
        else { // GRACEFUL_DEGRADATION
            if (isTerminal(frag) && rcv.size === exp)
                return this._resolveDAG(rcv);
            if (isTerminal(frag))
                return this._resolveDAGPartial(rcv);
            return null;
        }
    }
    _getParents(frag) {
        if (frag.flags & FLAG_EXTENDED_DEP) {
            if (frag.payload.length < 4)
                return [];
            const bitmap = new DataView(frag.payload.buffer, frag.payload.byteOffset, 4).getUint32(0, false);
            const parents = [];
            for (let i = 0; i < 32; i++)
                if (bitmap & (1 << i))
                    parents.push(i);
            return parents;
        }
        // Self-reference = root
        if (frag.dep === frag.fragIdx)
            return [];
        return [frag.dep];
    }
    _getPayload(frag) {
        if (frag.flags & FLAG_EXTENDED_DEP)
            return frag.payload.slice(4);
        return frag.payload;
    }
    _resolveDAG(rcv) {
        const nodeSet = new Set(rcv.keys());
        const order = this._topoSort(rcv, nodeSet);
        return order.map(i => this._getPayload(rcv.get(i)));
    }
    _resolveDAGPartial(rcv) {
        const present = new Set(rcv.keys());
        const executable = new Set();
        for (const idx of present) {
            if (this._ancestorsSatisfied(rcv, idx, present))
                executable.add(idx);
        }
        if (executable.size === 0)
            return [];
        const order = this._topoSort(rcv, executable);
        return order.map(i => this._getPayload(rcv.get(i)));
    }
    _ancestorsSatisfied(rcv, idx, present) {
        const visited = new Set();
        const stack = [idx];
        while (stack.length > 0) {
            const current = stack.pop();
            if (visited.has(current))
                continue;
            visited.add(current);
            if (!present.has(current))
                return false;
            const frag = rcv.get(current);
            if (frag)
                for (const p of this._getParents(frag))
                    if (!visited.has(p))
                        stack.push(p);
        }
        return true;
    }
    _topoSort(rcv, nodeSet) {
        const inDeg = new Map();
        const children = new Map();
        for (const i of nodeSet) {
            inDeg.set(i, 0);
            children.set(i, []);
        }
        for (const idx of nodeSet) {
            const parents = this._getParents(rcv.get(idx));
            for (const p of parents) {
                if (nodeSet.has(p)) {
                    inDeg.set(idx, (inDeg.get(idx) ?? 0) + 1);
                    children.get(p).push(idx);
                }
            }
        }
        const queue = [...nodeSet].filter(i => (inDeg.get(i) ?? 0) === 0).sort((a, b) => a - b);
        const order = [];
        while (queue.length > 0) {
            const node = queue.shift();
            order.push(node);
            for (const ch of (children.get(node) ?? []).sort((a, b) => a - b)) {
                const d = (inDeg.get(ch) ?? 1) - 1;
                inDeg.set(ch, d);
                if (d === 0)
                    queue.push(ch);
            }
        }
        return order;
    }
    nack(msgId, expectedCt) {
        const have = new Set(this._buf.get(msgId)?.keys() ?? []);
        const missing = Array.from({ length: expectedCt }, (_, i) => i).filter(i => !have.has(i));
        return `A:NACK[MSG:${msgId}\u2216[${missing.join(",")}]]`;
    }
}
//# sourceMappingURL=dag.js.map