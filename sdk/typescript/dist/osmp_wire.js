/**
 * OSMP Wire Modes — Semantic Assembly Isomorphic Language (SAIL) and Security Envelope (SEC)
 *
 * TypeScript implementation matching osmp_wire.py (Python reference).
 *
 * Modes:
 *   OSMP          — Mnemonic SAL (UTF-8 text, human-readable)
 *   OSMP-SAIL     — Semantic Assembly Isomorphic Language (compact binary, table-decoded)
 *   OSMP-SEC      — Mnemonic SAL + security envelope
 *   OSMP-SAIL-SEC — SAIL + security envelope (hardened mode)
 *
 * Dictionary: OSMP-semantic-dictionary-v15.csv
 */
import { createCipheriv, createDecipheriv, createHash, createPrivateKey, createPublicKey, randomBytes, sign as cryptoSign, verify as cryptoVerify, } from "crypto";
import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
// ─── Wire Mode Flags ─────────────────────────────────────────────────────────
export var WireMode;
(function (WireMode) {
    WireMode[WireMode["MNEMONIC"] = 0] = "MNEMONIC";
    WireMode[WireMode["SAIL"] = 1] = "SAIL";
    WireMode[WireMode["SEC"] = 2] = "SEC";
    WireMode[WireMode["SAIL_SEC"] = 3] = "SAIL_SEC";
})(WireMode || (WireMode = {}));
export function wireModeLabel(m) {
    return { 0: "OSMP", 1: "OSMP-SAIL", 2: "OSMP-SEC", 3: "OSMP-SAIL-SEC" }[m] ?? `?${m}`;
}
// ─── SAIL Token Table ────────────────────────────────────────────────────────
// Category 1: Logical/compositional
const TOK_AND = 0x80;
const TOK_OR = 0x81;
const TOK_NOT = 0x82;
const TOK_THEN = 0x83;
const TOK_IFF = 0x84;
const TOK_FOR_ALL = 0x85;
const TOK_EXISTS = 0x86;
const TOK_PARALLEL = 0x87;
const TOK_PRIORITY = 0x88;
const TOK_APPROX = 0x89;
const TOK_WILDCARD = 0x8A;
const TOK_ASSIGN = 0x8B;
const TOK_SEQUENCE = 0x8C;
const TOK_QUERY = 0x8D;
const TOK_TARGET = 0x8E;
const TOK_REPEAT_EVERY = 0x8F;
const TOK_NOT_EQUAL = 0x90;
const TOK_PRIORITY_ORDER = 0x91;
const TOK_UNLESS = 0x92;
// Category 2: Consequence class
const TOK_HAZARDOUS = 0xA0;
const TOK_REVERSIBLE = 0xA1;
const TOK_IRREVERSIBLE = 0xA2;
// Category 3: Outcome states
const TOK_PASS_TRUE = 0xA8;
const TOK_FAIL_FALSE = 0xA9;
// Category 4: Parameter/slot
const TOK_DELTA = 0xB0;
const TOK_HOME = 0xB1;
const TOK_ABORT_CANCEL = 0xB2;
const TOK_TIMEOUT = 0xB3;
const TOK_SCOPE_WITHIN = 0xB4;
const TOK_MISSING = 0xB5;
// Category 5: Loss tolerance
const TOK_FAIL_SAFE = 0xC0;
const TOK_GRACEFUL_DEG = 0xC1;
const TOK_ATOMIC = 0xC2;
// Category 6: Dictionary update
const TOK_ADDITIVE = 0xD0;
const TOK_REPLACE = 0xD1;
const TOK_DEPRECATE = 0xD2;
// Structural markers
const TOK_FRAME = 0xE0;
const TOK_BRACKET_OPEN = 0xE4;
const TOK_BRACKET_CLOSE = 0xE5;
// Value type tags
const TOK_VARINT = 0xF0;
const TOK_NEGINT = 0xF1;
const TOK_FLOAT16 = 0xF2;
const TOK_FLOAT32 = 0xF3;
const TOK_STRING = 0xF4;
const TOK_REF = 0xF5;
const TOK_END = 0xFF;
// ─── Glyph Maps ──────────────────────────────────────────────────────────────
const GLYPH_TO_TOKEN = {
    "\u2227": TOK_AND, "\u2228": TOK_OR, "\u00AC": TOK_NOT, "\u2192": TOK_THEN,
    "\u2194": TOK_IFF, "\u2200": TOK_FOR_ALL, "\u2203": TOK_EXISTS, "\u2225": TOK_PARALLEL,
    ">": TOK_PRIORITY, "~": TOK_APPROX, "*": TOK_WILDCARD,
    ":": TOK_ASSIGN, ";": TOK_SEQUENCE, "?": TOK_QUERY, "@": TOK_TARGET,
    "\u27F3": TOK_REPEAT_EVERY, "\u2260": TOK_NOT_EQUAL, "\u2295": TOK_PRIORITY_ORDER,
    "\u00AC\u2192": TOK_UNLESS,
    "\u26A0": TOK_HAZARDOUS, "\u21BA": TOK_REVERSIBLE, "\u2298": TOK_IRREVERSIBLE,
    "\u22A4": TOK_PASS_TRUE, "\u22A5": TOK_FAIL_FALSE,
    "\u0394": TOK_DELTA, "\u2302": TOK_HOME, "\u2297": TOK_ABORT_CANCEL,
    "\u03C4": TOK_TIMEOUT, "\u2208": TOK_SCOPE_WITHIN, "\u2216": TOK_MISSING,
    "\u03A6": TOK_FAIL_SAFE, "\u0393": TOK_GRACEFUL_DEG, "\u039B": TOK_ATOMIC,
    "+": TOK_ADDITIVE, "\u2190": TOK_REPLACE, "\u2020": TOK_DEPRECATE,
    "[": TOK_BRACKET_OPEN, "]": TOK_BRACKET_CLOSE,
};
const TOKEN_TO_GLYPH = {};
for (const [g, t] of Object.entries(GLYPH_TO_TOKEN))
    TOKEN_TO_GLYPH[t] = g;
// ─── Namespace Index ─────────────────────────────────────────────────────────
const NS_TO_INDEX = {};
const INDEX_TO_NS = {};
for (let i = 0; i < 26; i++) {
    const ch = String.fromCharCode(65 + i);
    NS_TO_INDEX[ch] = i;
    INDEX_TO_NS[i] = ch;
}
// ─── Varint ──────────────────────────────────────────────────────────────────
function encodeVarint(value) {
    const parts = [];
    while (value > 0x7F) {
        parts.push((value & 0x7F) | 0x80);
        value >>>= 7;
    }
    parts.push(value & 0x7F);
    return new Uint8Array(parts);
}
function decodeVarint(data, offset) {
    let value = 0, shift = 0, pos = offset;
    while (pos < data.length) {
        const b = data[pos++];
        value |= (b & 0x7F) << shift;
        if ((b & 0x80) === 0)
            return [value, pos];
        shift += 7;
    }
    return [value, pos];
}
function buildOpcodeTables(dictPath) {
    let path = dictPath;
    if (!path) {
        const candidates = [
            join(dirname(__filename), "..", "..", "..", "protocol", "OSMP-semantic-dictionary-v15.csv"),
            join("protocol", "OSMP-semantic-dictionary-v15.csv"),
        ];
        for (const c of candidates) {
            if (existsSync(c)) {
                path = c;
                break;
            }
        }
    }
    if (!path || !existsSync(path)) {
        throw new Error("Semantic dictionary not found. Pass dictPath explicitly.");
    }
    const lines = readFileSync(path, "utf-8").split("\n");
    let s3Start = -1;
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes("SECTION 3")) {
            s3Start = i;
            break;
        }
    }
    if (s3Start < 0)
        throw new Error("SECTION 3 not found in dictionary");
    const nsOpcodes = {};
    for (let i = s3Start; i < lines.length; i++) {
        const parts = lines[i].split(",");
        if (parts.length >= 5) {
            const prefix = parts[1].trim();
            const opcode = parts[3].trim();
            if (prefix && /^[A-Z]{1,2}$/.test(prefix) && opcode && opcode !== "Opcode") {
                if (!nsOpcodes[prefix])
                    nsOpcodes[prefix] = [];
                nsOpcodes[prefix].push(opcode);
            }
        }
    }
    const opToIdx = {};
    const idxToOp = {};
    for (const ns of Object.keys(nsOpcodes)) {
        const sorted = [...new Set(nsOpcodes[ns])].sort();
        opToIdx[ns] = {};
        idxToOp[ns] = {};
        sorted.forEach((op, i) => {
            opToIdx[ns][op] = i;
            idxToOp[ns][i] = op;
        });
    }
    return [opToIdx, idxToOp];
}
function validateCorpusEntry(e) {
    const idBytes = Buffer.byteLength(e.corpusId, "utf-8");
    if (idBytes < 1 || idBytes > 255) {
        throw new Error(`corpus_id must be 1-255 UTF-8 bytes, got ${idBytes}`);
    }
    if (e.corpusHash.length !== 32) {
        throw new Error(`corpus_hash must be exactly 32 bytes (SHA-256), got ${e.corpusHash.length}`);
    }
}
export class DictionaryBasis {
    _entries;
    _fingerprint = null;
    constructor(entries) {
        if (!entries || entries.length === 0) {
            throw new Error("DictionaryBasis must contain at least one entry");
        }
        for (const e of entries)
            validateCorpusEntry(e);
        // Defensive copy with frozen entries to mirror Python's frozen dataclass.
        this._entries = entries.map(e => Object.freeze({
            corpusId: e.corpusId,
            corpusHash: Buffer.from(e.corpusHash),
        }));
    }
    get entries() {
        return this._entries;
    }
    get length() {
        return this._entries.length;
    }
    isBaseOnly() {
        return this._entries.length === 1;
    }
    /**
     * Canonical wire form per spec §9.3.
     * For each entry in basis order:
     *   corpus_id_length (1 byte) || corpus_id (UTF-8 bytes) || corpus_hash (32 bytes)
     */
    canonicalSerialization() {
        const parts = [];
        for (const e of this._entries) {
            const idBytes = Buffer.from(e.corpusId, "utf-8");
            parts.push(Buffer.from([idBytes.length]));
            parts.push(idBytes);
            parts.push(e.corpusHash);
        }
        return Buffer.concat(parts);
    }
    /**
     * 8-byte basis fingerprint per spec §9.3.
     * First 8 bytes of SHA-256 over the canonical serialization.
     */
    fingerprint() {
        if (this._fingerprint === null) {
            const digest = createHash("sha256").update(this.canonicalSerialization()).digest();
            this._fingerprint = digest.subarray(0, 8);
        }
        return this._fingerprint;
    }
    equals(other) {
        if (this._entries.length !== other._entries.length)
            return false;
        for (let i = 0; i < this._entries.length; i++) {
            const a = this._entries[i];
            const b = other._entries[i];
            if (a.corpusId !== b.corpusId)
                return false;
            if (!a.corpusHash.equals(b.corpusHash))
                return false;
        }
        return true;
    }
    /**
     * Construct a basis from corpus files on disk.
     */
    static fromPaths(asdPath, asdId, mdrCorpora) {
        if (!existsSync(asdPath)) {
            throw new Error(`Base ASD not found: ${asdPath}`);
        }
        const entries = [];
        const asdHash = DictionaryBasis._hashFile(asdPath);
        const id = asdId ?? DictionaryBasis._deriveAsdId(asdPath);
        entries.push({ corpusId: id, corpusHash: asdHash });
        if (mdrCorpora) {
            for (const c of mdrCorpora) {
                if (!existsSync(c.path)) {
                    throw new Error(`MDR corpus not found: ${c.path}`);
                }
                entries.push({ corpusId: c.corpusId, corpusHash: DictionaryBasis._hashFile(c.path) });
            }
        }
        return new DictionaryBasis(entries);
    }
    /**
     * Construct the default base-ASD-only basis from canonical default locations.
     */
    static default(dictPath) {
        let path = dictPath;
        if (!path) {
            const candidates = [
                join(dirname(__filename), "..", "..", "..", "protocol", "OSMP-semantic-dictionary-v15.csv"),
                join("protocol", "OSMP-semantic-dictionary-v15.csv"),
            ];
            for (const c of candidates) {
                if (existsSync(c)) {
                    path = c;
                    break;
                }
            }
        }
        if (!path || !existsSync(path)) {
            throw new Error("Base ASD not found in any default location. Pass dictPath explicitly or use DictionaryBasis.fromPaths.");
        }
        return DictionaryBasis.fromPaths(path);
    }
    static _hashFile(path) {
        const data = readFileSync(path);
        return createHash("sha256").update(data).digest();
    }
    static _deriveAsdId(asdPath) {
        try {
            const head = readFileSync(asdPath, "utf-8").split("\n").slice(0, 20).join("\n");
            const m = head.match(/v(\d{2})/);
            if (m)
                return `asd-v${m[1]}`;
        }
        catch { /* fall through */ }
        return "asd-v15";
    }
}
// ─── Intern Table ────────────────────────────────────────────────────────────
function extractAsdOpcodes(strings, dictPath) {
    let path = dictPath;
    if (!path) {
        const candidates = [
            join(dirname(__filename), "..", "..", "..", "protocol", "OSMP-semantic-dictionary-v15.csv"),
            join("protocol", "OSMP-semantic-dictionary-v15.csv"),
        ];
        for (const c of candidates) {
            if (existsSync(c)) {
                path = c;
                break;
            }
        }
    }
    if (!path || !existsSync(path))
        return;
    const lines = readFileSync(path, "utf-8").split("\n");
    let inS3 = false;
    for (const line of lines) {
        if (line.includes("SECTION 3")) {
            inS3 = true;
            continue;
        }
        if (line.includes("SECTION 4"))
            break;
        if (!inS3)
            continue;
        const parts = line.split(",");
        if (parts.length >= 5) {
            const prefix = parts[1].trim();
            const opcode = parts[3].trim();
            if (prefix && /^[A-Z]{1,2}$/.test(prefix) && opcode && opcode !== "Opcode") {
                strings.add(opcode);
            }
        }
    }
}
function buildInternTable(basis, dictPath) {
    /**
     * Construct the SAIL intern table from a Dictionary Basis (ADR-004).
     *
     * The intern table is a pure function of the basis: two basis instances
     * with equal entries produce byte-identical intern tables. Index
     * assignment is deterministic over (basis order, deduplicated first-seen,
     * length-descending sort, cost filter).
     *
     * Future corpus types declare their own extraction rules per the
     * corpus's sidecar manifest. This implementation supports the base ASD
     * CSV extractor as the only shipping rule. Historical "Phase 2" MDR CSV
     * SECTION B parsing is removed; it produced zero observable intern
     * entries on every shipped MDR.
     */
    const strings = new Set();
    if (basis !== null) {
        for (const entry of basis.entries) {
            if (entry.corpusId.startsWith("asd-")) {
                extractAsdOpcodes(strings, dictPath);
            }
            // MDR corpus extraction rules deferred until corpora ship sidecar manifests.
        }
    }
    else {
        extractAsdOpcodes(strings, dictPath);
    }
    // Filter: only keep strings where interning saves bytes
    const sorted = [...strings].sort((a, b) => b.length - a.length || a.localeCompare(b));
    const result = [];
    for (const s of sorted) {
        const idx = result.length;
        const refCost = idx < 128 ? 2 : idx < 16384 ? 3 : 4;
        if (s.length > refCost)
            result.push(s);
    }
    return result;
}
// ─── SAIL Codec ──────────────────────────────────────────────────────────────
function isAlnumExt(ch) {
    return /[a-zA-Z0-9._-]/.test(ch);
}
export class SAILCodec {
    opToIdx;
    idxToOp;
    strToRef;
    refToStr;
    basis;
    constructor(dictPath, basis) {
        [this.opToIdx, this.idxToOp] = buildOpcodeTables(dictPath);
        // If no basis was supplied, construct the default base-ASD-only basis
        // so codec.basis is always well-defined and basisFingerprint() always
        // returns a value.
        let resolvedBasis = basis;
        if (!resolvedBasis) {
            try {
                resolvedBasis = DictionaryBasis.default(dictPath);
            }
            catch {
                // Last-resort fallback when the dictionary cannot be located on
                // disk: synthesize a basis from a placeholder hash so the codec
                // is still constructible. Tests that exercise basisFingerprint()
                // must supply a real basis or a valid dictPath.
                const placeholder = createHash("sha256").update(Buffer.from("asd-unknown")).digest();
                resolvedBasis = new DictionaryBasis([
                    { corpusId: "asd-unknown", corpusHash: placeholder },
                ]);
            }
        }
        this.basis = resolvedBasis;
        const internTable = buildInternTable(resolvedBasis, dictPath);
        this.strToRef = new Map(internTable.map((s, i) => [s, i]));
        this.refToStr = new Map(internTable.map((s, i) => [i, s]));
    }
    /** 8-byte basis fingerprint for FNP capability negotiation (spec §9.3). */
    basisFingerprint() {
        return this.basis.fingerprint();
    }
    tryNamespaceOpcode(sal, pos) {
        const colonPos = sal.indexOf(":", pos);
        if (colonPos <= pos || colonPos - pos > 2)
            return null;
        const ns = sal.slice(pos, colonPos);
        if (!(ns in NS_TO_INDEX))
            return null;
        let opEnd = colonPos + 1;
        while (opEnd < sal.length && (/[A-Z0-9]/.test(sal[opEnd]) || sal.charCodeAt(opEnd) === 0xA7))
            opEnd++;
        const opcode = sal.slice(colonPos + 1, opEnd);
        if (!opcode || !(ns in this.opToIdx) || !(opcode in this.opToIdx[ns]))
            return null;
        return [new Uint8Array([TOK_FRAME, NS_TO_INDEX[ns], this.opToIdx[ns][opcode]]), opEnd];
    }
    encodeToken(token) {
        const refIdx = this.strToRef.get(token);
        if (refIdx !== undefined) {
            const refBytes = new Uint8Array([TOK_REF, ...encodeVarint(refIdx)]);
            if (refBytes.length < token.length)
                return refBytes;
        }
        return new TextEncoder().encode(token);
    }
    encode(sal) {
        const out = [];
        let pos = 0;
        const n = sal.length;
        while (pos < n) {
            const ch = sal[pos];
            const code = sal.charCodeAt(pos);
            // Compound operator
            if (pos + 1 < n && sal.charCodeAt(pos) === 0xAC && sal.charCodeAt(pos + 1) === 0x2192) {
                out.push(TOK_UNLESS);
                pos += 2;
                continue;
            }
            // Multi-byte Unicode glyphs
            if (code >= 0x80 && ch in GLYPH_TO_TOKEN) {
                out.push(GLYPH_TO_TOKEN[ch]);
                pos++;
                continue;
            }
            // Namespace:opcode
            if (/[A-Z]/.test(ch)) {
                const result = this.tryNamespaceOpcode(sal, pos);
                if (result) {
                    out.push(...result[0]);
                    pos = result[1];
                    continue;
                }
            }
            // ASCII structural tokens
            if ("@?;*~".includes(ch)) {
                out.push(GLYPH_TO_TOKEN[ch]);
                pos++;
                continue;
            }
            if (ch === ":") {
                out.push(TOK_ASSIGN);
                pos++;
                continue;
            }
            if (ch === ">") {
                out.push(TOK_PRIORITY);
                pos++;
                continue;
            }
            if (ch === "+") {
                out.push(TOK_ADDITIVE);
                pos++;
                continue;
            }
            if (ch === "[") {
                out.push(TOK_BRACKET_OPEN);
                pos++;
                continue;
            }
            if (ch === "]") {
                out.push(TOK_BRACKET_CLOSE);
                pos++;
                continue;
            }
            // Alphanumeric run
            if (isAlnumExt(ch) || (ch === "-" && pos + 1 < n && /[0-9]/.test(sal[pos + 1]))) {
                const runStart = pos;
                while (pos < n && isAlnumExt(sal[pos]))
                    pos++;
                if (sal[runStart] === "-") {
                    pos = runStart + 1;
                    while (pos < n && isAlnumExt(sal[pos]))
                        pos++;
                }
                const token = sal.slice(runStart, pos);
                // Check if pure numeric
                const isNeg = token.startsWith("-");
                const numPart = isNeg ? token.slice(1) : token;
                let isPureNumeric = numPart.length > 0;
                let hasDot = false;
                for (const c of numPart) {
                    if (c === ".") {
                        if (hasDot) {
                            isPureNumeric = false;
                            break;
                        }
                        hasDot = true;
                    }
                    else if (!/[0-9]/.test(c)) {
                        isPureNumeric = false;
                        break;
                    }
                }
                if (isPureNumeric) {
                    const hasLeadingZero = !isNeg && numPart.length > 1 && numPart[0] === "0";
                    if (hasDot || hasLeadingZero) {
                        out.push(...this.encodeToken(token));
                    }
                    else {
                        const ival = parseInt(numPart);
                        out.push(isNeg ? TOK_NEGINT : TOK_VARINT);
                        out.push(...encodeVarint(ival));
                    }
                }
                else {
                    out.push(...this.encodeToken(token));
                }
                continue;
            }
            // Remaining ASCII
            if (code < 0x80) {
                out.push(...this.encodeToken(ch));
                pos++;
                continue;
            }
            // Unicode glyph fallback
            if (ch in GLYPH_TO_TOKEN) {
                out.push(GLYPH_TO_TOKEN[ch]);
                pos++;
                continue;
            }
            // Unknown - encode as UTF-8
            out.push(...new TextEncoder().encode(ch));
            pos++;
        }
        out.push(TOK_END);
        return new Uint8Array(out);
    }
    decode(data) {
        const parts = [];
        let pos = 0;
        const n = data.length;
        while (pos < n) {
            const b = data[pos];
            if (b === TOK_END)
                break;
            if (b === TOK_FRAME) {
                pos++;
                if (pos + 1 >= n)
                    break;
                const nsIdx = data[pos++];
                const opIdx = data[pos++];
                const ns = INDEX_TO_NS[nsIdx] ?? `?${nsIdx}`;
                const opcode = this.idxToOp[ns]?.[opIdx] ?? `?${opIdx}`;
                parts.push(`${ns}:${opcode}`);
                continue;
            }
            if (b === TOK_REF) {
                pos++;
                const [refIdx, newPos] = decodeVarint(data, pos);
                pos = newPos;
                parts.push(this.refToStr.get(refIdx) ?? `?REF${refIdx}`);
                continue;
            }
            if (b === TOK_STRING) {
                pos++;
                const [strLen, newPos] = decodeVarint(data, pos);
                pos = newPos;
                if (pos + strLen <= n) {
                    parts.push(new TextDecoder().decode(data.slice(pos, pos + strLen)));
                    pos += strLen;
                }
                continue;
            }
            if (b in TOKEN_TO_GLYPH) {
                parts.push(TOKEN_TO_GLYPH[b]);
                pos++;
                continue;
            }
            if (b === TOK_VARINT) {
                pos++;
                const [v, p] = decodeVarint(data, pos);
                pos = p;
                parts.push(String(v));
                continue;
            }
            if (b === TOK_NEGINT) {
                pos++;
                const [v, p] = decodeVarint(data, pos);
                pos = p;
                parts.push(`-${v}`);
                continue;
            }
            if (b === TOK_FLOAT16 && pos + 2 < n) {
                pos++;
                const buf = Buffer.from(data.slice(pos, pos + 2));
                const fval = buf.readUInt16BE(0);
                // IEEE 754 half-precision decode
                const sign = (fval >> 15) & 1;
                const exp = (fval >> 10) & 0x1F;
                const mant = fval & 0x3FF;
                let val;
                if (exp === 0)
                    val = (mant / 1024) * Math.pow(2, -14);
                else if (exp === 31)
                    val = mant === 0 ? Infinity : NaN;
                else
                    val = Math.pow(2, exp - 15) * (1 + mant / 1024);
                if (sign)
                    val = -val;
                parts.push(val.toPrecision(4));
                pos += 2;
                continue;
            }
            if (b === TOK_FLOAT32 && pos + 4 < n) {
                pos++;
                const buf = Buffer.from(data.slice(pos, pos + 4));
                parts.push(String(buf.readFloatBE(0)));
                pos += 4;
                continue;
            }
            if (b < 0x80) {
                parts.push(String.fromCharCode(b));
                pos++;
                continue;
            }
            pos++;
        }
        return parts.join("");
    }
}
// ─── SEC Codec ───────────────────────────────────────────────────────────────
const SEC_VERSION_1 = 0x00;
const NODE_ID_LONG = 0x04;
export class SecCodec {
    /**
     * Security envelope encoder/decoder.
     *
     * Uses real cryptographic primitives via Node.js stdlib crypto:
     *   - Ed25519 (RFC 8032) for sender authentication via 64-byte signatures
     *   - ChaCha20-Poly1305 (RFC 7539, RFC 8439) for AEAD payload integrity
     *     with a 16-byte authentication tag
     *   - 12-byte nonces derived deterministically from the envelope header
     *     padded with the canonical OSMP nonce salt
     *
     * The wire format is byte-identical to the Python and Go SecCodec
     * implementations so cross-SDK envelopes interoperate natively.
     *
     * Key management is external (MDR node identity service). For ephemeral
     * sessions or local testing, omit the key arguments and the constructor
     * will generate fresh keys via crypto.randomBytes.
     */
    // 12 bytes — pads short headers up to ChaCha20-Poly1305 nonce length
    static NONCE_SALT = Buffer.from("OSMP-SEC-v1\x00", "binary");
    nodeId;
    signingKeySeed;
    symmetricKey;
    ed25519PrivateKey;
    ed25519PublicKey;
    verifyPublicKeyDefault;
    seqCounter = 0;
    constructor(nodeId, signingKey, symmetricKey, verifyKey) {
        if (nodeId.length !== 2 && nodeId.length !== 4) {
            throw new Error("nodeId must be 2 or 4 bytes");
        }
        this.nodeId = nodeId;
        // Ed25519 signing key (32-byte seed)
        const seed = signingKey ?? randomBytes(32);
        if (seed.length !== 32) {
            throw new Error(`signingKey must be 32 bytes (Ed25519 seed), got ${seed.length}`);
        }
        this.signingKeySeed = seed;
        this.ed25519PrivateKey = SecCodec.ed25519PrivateFromSeed(seed);
        this.ed25519PublicKey = createPublicKey(this.ed25519PrivateKey);
        // ChaCha20-Poly1305 symmetric key (32 bytes)
        const sym = symmetricKey ?? randomBytes(32);
        if (sym.length !== 32) {
            throw new Error(`symmetricKey must be 32 bytes (ChaCha20-Poly1305), got ${sym.length}`);
        }
        this.symmetricKey = sym;
        // Default verify key: our own public key (loopback). For inter-node
        // verification, callers pass the peer's public key.
        if (verifyKey !== undefined) {
            if (verifyKey.length !== 32) {
                throw new Error(`verifyKey must be 32 bytes (Ed25519 public key), got ${verifyKey.length}`);
            }
            this.verifyPublicKeyDefault = SecCodec.ed25519PublicFromBytes(verifyKey);
        }
        else {
            this.verifyPublicKeyDefault = this.ed25519PublicKey;
        }
    }
    /** Wrap a 32-byte raw Ed25519 seed in the PKCS#8 DER prefix Node expects. */
    static ed25519PrivateFromSeed(seed) {
        // PKCS#8 v1 prefix for Ed25519: 0x302e020100300506032b657004220420 (16 bytes)
        const PKCS8_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");
        const der = Buffer.concat([PKCS8_PREFIX, seed]);
        return createPrivateKey({ key: der, format: "der", type: "pkcs8" });
    }
    /** Wrap a 32-byte raw Ed25519 public key in the SPKI DER prefix Node expects. */
    static ed25519PublicFromBytes(pub) {
        // SPKI prefix for Ed25519: 0x302a300506032b6570032100 (12 bytes)
        const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");
        const der = Buffer.concat([SPKI_PREFIX, pub]);
        return createPublicKey({ key: der, format: "der", type: "spki" });
    }
    /** Return the 32-byte raw Ed25519 public key for distributing to peers. */
    get publicSigningKey() {
        const der = this.ed25519PublicKey.export({ format: "der", type: "spki" });
        // SPKI DER for Ed25519 is 12 bytes of prefix + 32 bytes of public key
        return Buffer.from(der.subarray(der.length - 32));
    }
    nextSeq() { return ++this.seqCounter; }
    /** Derive a 12-byte ChaCha20-Poly1305 nonce from the envelope header. */
    deriveNonce(header) {
        if (header.length >= 12)
            return Buffer.from(header.subarray(0, 12));
        return Buffer.concat([header, SecCodec.NONCE_SALT]).subarray(0, 12);
    }
    seal(ad, payload) {
        const nonce = this.deriveNonce(ad);
        const cipher = createCipheriv("chacha20-poly1305", this.symmetricKey, nonce, {
            authTagLength: 16,
        });
        cipher.setAAD(ad, { plaintextLength: payload.length });
        const ciphertext = Buffer.concat([cipher.update(payload), cipher.final()]);
        const tag = cipher.getAuthTag();
        return [ciphertext, tag];
    }
    open(ad, payload, authTag) {
        try {
            const nonce = this.deriveNonce(ad);
            const decipher = createDecipheriv("chacha20-poly1305", this.symmetricKey, nonce, {
                authTagLength: 16,
            });
            decipher.setAAD(ad, { plaintextLength: payload.length });
            decipher.setAuthTag(authTag);
            return Buffer.concat([decipher.update(payload), decipher.final()]);
        }
        catch {
            return null;
        }
    }
    sign(message) {
        // Ed25519 in Node: pass null algorithm, the key implies the algorithm
        return cryptoSign(null, message, this.ed25519PrivateKey);
    }
    verify(message, signature, verifyKey) {
        let pub;
        if (verifyKey !== undefined) {
            try {
                pub = SecCodec.ed25519PublicFromBytes(verifyKey);
            }
            catch {
                return false;
            }
        }
        else {
            pub = this.verifyPublicKeyDefault;
        }
        try {
            return cryptoVerify(null, message, pub, signature);
        }
        catch {
            return false;
        }
    }
    pack(payload, wireMode = WireMode.SEC) {
        let modeByte = wireMode & 0x03;
        if (this.nodeId.length === 4)
            modeByte |= NODE_ID_LONG;
        modeByte |= SEC_VERSION_1;
        const seq = this.nextSeq();
        const seqBuf = Buffer.alloc(4);
        seqBuf.writeUInt32BE(seq);
        const header = Buffer.concat([Buffer.from([modeByte]), this.nodeId, seqBuf]);
        const [sealed, authTag] = this.seal(header, payload);
        const signInput = Buffer.concat([header, sealed, authTag]);
        const signature = this.sign(signInput);
        return Buffer.concat([header, sealed, authTag, signature]);
    }
    unpack(data) {
        if (data.length < 87)
            return null;
        let pos = 0;
        const modeByte = data[pos++];
        const wireMode = (modeByte & 0x03);
        const nodeIdLen = (modeByte & NODE_ID_LONG) ? 4 : 2;
        const nodeId = data.subarray(pos, pos + nodeIdLen);
        pos += nodeIdLen;
        const seqCounter = data.readUInt32BE(pos);
        pos += 4;
        const header = data.subarray(0, pos);
        const payloadEnd = data.length - 16 - 64;
        if (payloadEnd < pos)
            return null;
        const payload = data.subarray(pos, payloadEnd);
        const authTag = data.subarray(payloadEnd, payloadEnd + 16);
        const signature = data.subarray(payloadEnd + 16, payloadEnd + 80);
        const verified = this.open(header, Buffer.from(payload), Buffer.from(authTag));
        if (!verified)
            return null;
        const signInput = Buffer.concat([header, payload, authTag]);
        if (!this.verify(signInput, Buffer.from(signature)))
            return null;
        return { mode: wireMode, nodeId: Buffer.from(nodeId), seqCounter, payload: Buffer.from(verified), authTag: Buffer.from(authTag), signature: Buffer.from(signature) };
    }
}
// ─── Unified Wire Codec ──────────────────────────────────────────────────────
export class OSMPWireCodec {
    sail;
    sec;
    constructor(opts) {
        this.sail = new SAILCodec(opts?.dictPath, opts?.basis);
        this.sec = new SecCodec(opts?.nodeId ?? Buffer.from([0x00, 0x01]), opts?.signingKey, opts?.symmetricKey);
    }
    /** The Dictionary Basis bound to this codec (ADR-004). */
    get basis() {
        return this.sail.basis;
    }
    /** 8-byte basis fingerprint for FNP capability negotiation (spec §9.3). */
    basisFingerprint() {
        return this.sail.basisFingerprint();
    }
    encode(sal, mode = WireMode.MNEMONIC) {
        switch (mode) {
            case WireMode.MNEMONIC: return Buffer.from(sal, "utf-8");
            case WireMode.SAIL: return Buffer.from(this.sail.encode(sal));
            case WireMode.SEC: return this.sec.pack(Buffer.from(sal, "utf-8"), WireMode.SEC);
            case WireMode.SAIL_SEC: return this.sec.pack(Buffer.from(this.sail.encode(sal)), WireMode.SAIL_SEC);
            default: throw new Error(`Unknown wire mode: ${mode}`);
        }
    }
    decode(data, mode = WireMode.MNEMONIC) {
        switch (mode) {
            case WireMode.MNEMONIC: return data.toString("utf-8");
            case WireMode.SAIL: return this.sail.decode(new Uint8Array(data));
            case WireMode.SEC: {
                const env = this.sec.unpack(data);
                if (!env)
                    throw new Error("Security envelope verification failed");
                return env.payload.toString("utf-8");
            }
            case WireMode.SAIL_SEC: {
                const env = this.sec.unpack(data);
                if (!env)
                    throw new Error("Security envelope verification failed");
                return this.sail.decode(new Uint8Array(env.payload));
            }
            default: throw new Error(`Unknown wire mode: ${mode}`);
        }
    }
    measure(sal) {
        const mnemonicBytes = Buffer.byteLength(sal, "utf-8");
        const results = { _mnemonic_bytes: mnemonicBytes };
        for (const mode of [WireMode.MNEMONIC, WireMode.SAIL, WireMode.SEC, WireMode.SAIL_SEC]) {
            try {
                const encoded = this.encode(sal, mode);
                const decoded = this.decode(encoded, mode);
                results[wireModeLabel(mode)] = {
                    bytes: encoded.length,
                    reduction_vs_mnemonic: mnemonicBytes > 0 ? Math.round((1 - encoded.length / mnemonicBytes) * 1000) / 10 : 0,
                    roundtrip: decoded === sal,
                };
            }
            catch (e) {
                results[wireModeLabel(mode)] = { error: e.message };
            }
        }
        return results;
    }
}
export default OSMPWireCodec;
//# sourceMappingURL=osmp_wire.js.map