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
 * Dictionary: OSMP-semantic-dictionary-v14.csv
 */

import { createHmac, randomBytes, timingSafeEqual } from "crypto";
import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";

// ─── Wire Mode Flags ─────────────────────────────────────────────────────────

export enum WireMode {
  MNEMONIC  = 0x00,
  SAIL      = 0x01,
  SEC       = 0x02,
  SAIL_SEC  = 0x03,
}

export function wireModeLabel(m: WireMode): string {
  return { 0: "OSMP", 1: "OSMP-SAIL", 2: "OSMP-SEC", 3: "OSMP-SAIL-SEC" }[m] ?? `?${m}`;
}

// ─── SAIL Token Table ────────────────────────────────────────────────────────

// Category 1: Logical/compositional
const TOK_AND            = 0x80;
const TOK_OR             = 0x81;
const TOK_NOT            = 0x82;
const TOK_THEN           = 0x83;
const TOK_IFF            = 0x84;
const TOK_FOR_ALL        = 0x85;
const TOK_EXISTS         = 0x86;
const TOK_PARALLEL       = 0x87;
const TOK_PRIORITY       = 0x88;
const TOK_APPROX         = 0x89;
const TOK_WILDCARD       = 0x8A;
const TOK_ASSIGN         = 0x8B;
const TOK_SEQUENCE       = 0x8C;
const TOK_QUERY          = 0x8D;
const TOK_TARGET         = 0x8E;
const TOK_REPEAT_EVERY   = 0x8F;
const TOK_NOT_EQUAL      = 0x90;
const TOK_PRIORITY_ORDER = 0x91;
const TOK_UNLESS         = 0x92;

// Category 2: Consequence class
const TOK_HAZARDOUS      = 0xA0;
const TOK_REVERSIBLE     = 0xA1;
const TOK_IRREVERSIBLE   = 0xA2;

// Category 3: Outcome states
const TOK_PASS_TRUE      = 0xA8;
const TOK_FAIL_FALSE     = 0xA9;

// Category 4: Parameter/slot
const TOK_DELTA          = 0xB0;
const TOK_HOME           = 0xB1;
const TOK_ABORT_CANCEL   = 0xB2;
const TOK_TIMEOUT        = 0xB3;
const TOK_SCOPE_WITHIN   = 0xB4;
const TOK_MISSING        = 0xB5;

// Category 5: Loss tolerance
const TOK_FAIL_SAFE      = 0xC0;
const TOK_GRACEFUL_DEG   = 0xC1;
const TOK_ATOMIC         = 0xC2;

// Category 6: Dictionary update
const TOK_ADDITIVE       = 0xD0;
const TOK_REPLACE        = 0xD1;
const TOK_DEPRECATE      = 0xD2;

// Structural markers
const TOK_FRAME          = 0xE0;
const TOK_BRACKET_OPEN   = 0xE4;
const TOK_BRACKET_CLOSE  = 0xE5;

// Value type tags
const TOK_VARINT         = 0xF0;
const TOK_NEGINT         = 0xF1;
const TOK_FLOAT16        = 0xF2;
const TOK_FLOAT32        = 0xF3;
const TOK_STRING         = 0xF4;
const TOK_REF            = 0xF5;
const TOK_END            = 0xFF;

// ─── Glyph Maps ──────────────────────────────────────────────────────────────

const GLYPH_TO_TOKEN: Record<string, number> = {
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

const TOKEN_TO_GLYPH: Record<number, string> = {};
for (const [g, t] of Object.entries(GLYPH_TO_TOKEN)) TOKEN_TO_GLYPH[t] = g;

// ─── Namespace Index ─────────────────────────────────────────────────────────

const NS_TO_INDEX: Record<string, number> = {};
const INDEX_TO_NS: Record<number, string> = {};
for (let i = 0; i < 26; i++) {
  const ch = String.fromCharCode(65 + i);
  NS_TO_INDEX[ch] = i;
  INDEX_TO_NS[i] = ch;
}

// ─── Varint ──────────────────────────────────────────────────────────────────

function encodeVarint(value: number): Uint8Array {
  const parts: number[] = [];
  while (value > 0x7F) {
    parts.push((value & 0x7F) | 0x80);
    value >>>= 7;
  }
  parts.push(value & 0x7F);
  return new Uint8Array(parts);
}

function decodeVarint(data: Uint8Array, offset: number): [number, number] {
  let value = 0, shift = 0, pos = offset;
  while (pos < data.length) {
    const b = data[pos++];
    value |= (b & 0x7F) << shift;
    if ((b & 0x80) === 0) return [value, pos];
    shift += 7;
  }
  return [value, pos];
}

// ─── Dictionary Loader ───────────────────────────────────────────────────────

type OpcodeIndex = Record<string, Record<string, number>>;
type IndexOpcode = Record<string, Record<number, string>>;

function buildOpcodeTables(dictPath?: string): [OpcodeIndex, IndexOpcode] {
  let path = dictPath;
  if (!path) {
    const candidates = [
      join(dirname(__filename), "..", "..", "..", "protocol", "OSMP-semantic-dictionary-v14.csv"),
      join("protocol", "OSMP-semantic-dictionary-v14.csv"),
    ];
    for (const c of candidates) {
      if (existsSync(c)) { path = c; break; }
    }
  }
  if (!path || !existsSync(path)) {
    throw new Error("Semantic dictionary not found. Pass dictPath explicitly.");
  }
  const lines = readFileSync(path, "utf-8").split("\n");
  let s3Start = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes("SECTION 3")) { s3Start = i; break; }
  }
  if (s3Start < 0) throw new Error("SECTION 3 not found in dictionary");

  const nsOpcodes: Record<string, string[]> = {};
  for (let i = s3Start; i < lines.length; i++) {
    const parts = lines[i].split(",");
    if (parts.length >= 5) {
      const prefix = parts[1].trim();
      const opcode = parts[3].trim();
      if (prefix && /^[A-Z]{1,2}$/.test(prefix) && opcode && opcode !== "Opcode") {
        if (!nsOpcodes[prefix]) nsOpcodes[prefix] = [];
        nsOpcodes[prefix].push(opcode);
      }
    }
  }

  const opToIdx: OpcodeIndex = {};
  const idxToOp: IndexOpcode = {};
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

// ─── Intern Table ────────────────────────────────────────────────────────────


function buildInternTable(dictPath?: string, mdrPaths?: string[]): string[] {
  /**
   * Dynamically construct intern table from dictionary and MDR content.
   * Phase 1: Opcode names from base dictionary Section 3.
   * Phase 2: Slot values from each loaded MDR corpus Section B.
   * Zero static data. Every string originates from a loaded file.
   */
  const strings = new Set<string>();

  // Phase 1: Opcode names from base dictionary
  let path = dictPath;
  if (!path) {
    const candidates = [
      join(dirname(__filename), "..", "..", "..", "protocol", "OSMP-semantic-dictionary-v14.csv"),
      join("protocol", "OSMP-semantic-dictionary-v14.csv"),
    ];
    for (const c of candidates) {
      if (existsSync(c)) { path = c; break; }
    }
  }

  if (path && existsSync(path)) {
    const lines = readFileSync(path, "utf-8").split("\n");
    let inS3 = false;
    for (const line of lines) {
      if (line.includes("SECTION 3")) { inS3 = true; continue; }
      if (line.includes("SECTION 4")) break;
      if (!inS3) continue;
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

  // Phase 2: Slot values from each MDR corpus Section B
  if (mdrPaths) {
    for (const mdrPath of mdrPaths) {
      if (!existsSync(mdrPath)) continue;
      const mdrLines = readFileSync(mdrPath, "utf-8").split("\n");
      let inSB = false;
      for (const line of mdrLines) {
        const trimmed = line.trim();
        if (trimmed.includes("SECTION B")) { inSB = true; continue; }
        if (inSB && trimmed.startsWith("SECTION ") && !trimmed.includes("SECTION B")) break;
        if (!inSB) continue;
        if (!trimmed || trimmed.startsWith("Format:") || trimmed.startsWith("===")
            || trimmed.startsWith("---") || trimmed.startsWith("Note:")) continue;

        const parts = trimmed.split(",");
        if (parts.length >= 2 && parts[0].includes(":")) {
          const slotValue = parts[1].trim();
          if (slotValue) strings.add(slotValue);
        }
        // Extract bracket references from dependency rules
        if (parts.length >= 5) {
          const depRule = parts[4] || "";
          const matches = depRule.match(/\[([^\]]+)\]/g);
          if (matches) {
            for (const m of matches) strings.add(m.slice(1, -1));
          }
        }
      }
    }
  }

  // Filter: only keep strings where interning saves bytes
  const sorted = [...strings].sort((a, b) => b.length - a.length || a.localeCompare(b));
  const result: string[] = [];
  for (const s of sorted) {
    const idx = result.length;
    const refCost = idx < 128 ? 2 : idx < 16384 ? 3 : 4;
    if (s.length > refCost) result.push(s);
  }
  return result;
}


// ─── SAIL Codec ──────────────────────────────────────────────────────────────

function isAlnumExt(ch: string): boolean {
  return /[a-zA-Z0-9._-]/.test(ch);
}

export class SAILCodec {
  private opToIdx: OpcodeIndex;
  private idxToOp: IndexOpcode;
  private strToRef: Map<string, number>;
  private refToStr: Map<number, string>;

  constructor(dictPath?: string, mdrPaths?: string[]) {
    [this.opToIdx, this.idxToOp] = buildOpcodeTables(dictPath);
    const internTable = buildInternTable(dictPath, mdrPaths);
    this.strToRef = new Map(internTable.map((s, i) => [s, i]));
    this.refToStr = new Map(internTable.map((s, i) => [i, s]));
  }

  private tryNamespaceOpcode(sal: string, pos: number): [Uint8Array, number] | null {
    const colonPos = sal.indexOf(":", pos);
    if (colonPos <= pos || colonPos - pos > 2) return null;
    const ns = sal.slice(pos, colonPos);
    if (!(ns in NS_TO_INDEX)) return null;
    let opEnd = colonPos + 1;
    while (opEnd < sal.length && (/[A-Z0-9]/.test(sal[opEnd]) || sal.charCodeAt(opEnd) === 0xA7)) opEnd++;
    const opcode = sal.slice(colonPos + 1, opEnd);
    if (!opcode || !(ns in this.opToIdx) || !(opcode in this.opToIdx[ns])) return null;
    return [new Uint8Array([TOK_FRAME, NS_TO_INDEX[ns], this.opToIdx[ns][opcode]]), opEnd];
  }

  private encodeToken(token: string): Uint8Array {
    const refIdx = this.strToRef.get(token);
    if (refIdx !== undefined) {
      const refBytes = new Uint8Array([TOK_REF, ...encodeVarint(refIdx)]);
      if (refBytes.length < token.length) return refBytes;
    }
    return new TextEncoder().encode(token);
  }

  encode(sal: string): Uint8Array {
    const out: number[] = [];
    let pos = 0;
    const n = sal.length;

    while (pos < n) {
      const ch = sal[pos];
      const code = sal.charCodeAt(pos);

      // Compound operator
      if (pos + 1 < n && sal.charCodeAt(pos) === 0xAC && sal.charCodeAt(pos + 1) === 0x2192) {
        out.push(TOK_UNLESS); pos += 2; continue;
      }

      // Multi-byte Unicode glyphs
      if (code >= 0x80 && ch in GLYPH_TO_TOKEN) {
        out.push(GLYPH_TO_TOKEN[ch]); pos++; continue;
      }

      // Namespace:opcode
      if (/[A-Z]/.test(ch)) {
        const result = this.tryNamespaceOpcode(sal, pos);
        if (result) { out.push(...result[0]); pos = result[1]; continue; }
      }

      // ASCII structural tokens
      if ("@?;*~".includes(ch)) { out.push(GLYPH_TO_TOKEN[ch]); pos++; continue; }
      if (ch === ":") { out.push(TOK_ASSIGN); pos++; continue; }
      if (ch === ">") { out.push(TOK_PRIORITY); pos++; continue; }
      if (ch === "+") { out.push(TOK_ADDITIVE); pos++; continue; }
      if (ch === "[") { out.push(TOK_BRACKET_OPEN); pos++; continue; }
      if (ch === "]") { out.push(TOK_BRACKET_CLOSE); pos++; continue; }

      // Alphanumeric run
      if (isAlnumExt(ch) || (ch === "-" && pos + 1 < n && /[0-9]/.test(sal[pos + 1]))) {
        const runStart = pos;
        while (pos < n && isAlnumExt(sal[pos])) pos++;
        if (sal[runStart] === "-") { pos = runStart + 1; while (pos < n && isAlnumExt(sal[pos])) pos++; }
        const token = sal.slice(runStart, pos);

        // Check if pure numeric
        const isNeg = token.startsWith("-");
        const numPart = isNeg ? token.slice(1) : token;
        let isPureNumeric = numPart.length > 0;
        let hasDot = false;
        for (const c of numPart) {
          if (c === ".") { if (hasDot) { isPureNumeric = false; break; } hasDot = true; }
          else if (!/[0-9]/.test(c)) { isPureNumeric = false; break; }
        }

        if (isPureNumeric) {
          const hasLeadingZero = !isNeg && numPart.length > 1 && numPart[0] === "0";
          if (hasDot || hasLeadingZero) {
            out.push(...this.encodeToken(token));
          } else {
            const ival = parseInt(numPart);
            out.push(isNeg ? TOK_NEGINT : TOK_VARINT);
            out.push(...encodeVarint(ival));
          }
        } else {
          out.push(...this.encodeToken(token));
        }
        continue;
      }

      // Remaining ASCII
      if (code < 0x80) { out.push(...this.encodeToken(ch)); pos++; continue; }

      // Unicode glyph fallback
      if (ch in GLYPH_TO_TOKEN) { out.push(GLYPH_TO_TOKEN[ch]); pos++; continue; }

      // Unknown - encode as UTF-8
      out.push(...new TextEncoder().encode(ch)); pos++;
    }

    out.push(TOK_END);
    return new Uint8Array(out);
  }

  decode(data: Uint8Array): string {
    const parts: string[] = [];
    let pos = 0;
    const n = data.length;

    while (pos < n) {
      const b = data[pos];
      if (b === TOK_END) break;

      if (b === TOK_FRAME) {
        pos++;
        if (pos + 1 >= n) break;
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

      if (b in TOKEN_TO_GLYPH) { parts.push(TOKEN_TO_GLYPH[b]); pos++; continue; }

      if (b === TOK_VARINT) { pos++; const [v, p] = decodeVarint(data, pos); pos = p; parts.push(String(v)); continue; }
      if (b === TOK_NEGINT) { pos++; const [v, p] = decodeVarint(data, pos); pos = p; parts.push(`-${v}`); continue; }

      if (b === TOK_FLOAT16 && pos + 2 < n) {
        pos++;
        const buf = Buffer.from(data.slice(pos, pos + 2));
        const fval = buf.readUInt16BE(0);
        // IEEE 754 half-precision decode
        const sign = (fval >> 15) & 1;
        const exp = (fval >> 10) & 0x1F;
        const mant = fval & 0x3FF;
        let val: number;
        if (exp === 0) val = (mant / 1024) * Math.pow(2, -14);
        else if (exp === 31) val = mant === 0 ? Infinity : NaN;
        else val = Math.pow(2, exp - 15) * (1 + mant / 1024);
        if (sign) val = -val;
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

      if (b < 0x80) { parts.push(String.fromCharCode(b)); pos++; continue; }

      pos++;
    }

    return parts.join("");
  }
}

// ─── SEC Codec ───────────────────────────────────────────────────────────────

const SEC_VERSION_1 = 0x00;
const NODE_ID_LONG  = 0x04;

export interface SecEnvelope {
  mode: WireMode;
  nodeId: Buffer;
  seqCounter: number;
  payload: Buffer;
  authTag: Buffer;
  signature: Buffer;
}

export class SecCodec {
  private nodeId: Buffer;
  private signingKey: Buffer;
  private symmetricKey: Buffer;
  private seqCounter: number = 0;

  constructor(nodeId: Buffer, signingKey?: Buffer, symmetricKey?: Buffer) {
    if (nodeId.length !== 2 && nodeId.length !== 4) throw new Error("nodeId must be 2 or 4 bytes");
    this.nodeId = nodeId;
    this.signingKey = signingKey ?? randomBytes(32);
    this.symmetricKey = symmetricKey ?? randomBytes(32);
  }

  private nextSeq(): number { return ++this.seqCounter; }

  private seal(ad: Buffer, payload: Buffer): [Buffer, Buffer] {
    const tag = createHmac("sha256", this.symmetricKey).update(Buffer.concat([ad, payload])).digest().subarray(0, 16);
    return [payload, tag];
  }

  private open(ad: Buffer, payload: Buffer, authTag: Buffer): Buffer | null {
    const expected = createHmac("sha256", this.symmetricKey).update(Buffer.concat([ad, payload])).digest().subarray(0, 16);
    return timingSafeEqual(authTag, expected) ? payload : null;
  }

  private sign(message: Buffer): Buffer {
    const sig = createHmac("sha256", this.signingKey).update(message).digest();
    return Buffer.concat([sig, sig]); // 64 bytes placeholder
  }

  private verify(message: Buffer, signature: Buffer, verifyKey?: Buffer): boolean {
    const key = verifyKey ?? this.signingKey;
    const expected = createHmac("sha256", key).update(message).digest();
    const expectedSig = Buffer.concat([expected, expected]);
    return timingSafeEqual(signature, expectedSig);
  }

  pack(payload: Buffer, wireMode: WireMode = WireMode.SEC): Buffer {
    let modeByte = wireMode & 0x03;
    if (this.nodeId.length === 4) modeByte |= NODE_ID_LONG;
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

  unpack(data: Buffer): SecEnvelope | null {
    if (data.length < 87) return null;
    let pos = 0;
    const modeByte = data[pos++];
    const wireMode = (modeByte & 0x03) as WireMode;
    const nodeIdLen = (modeByte & NODE_ID_LONG) ? 4 : 2;
    const nodeId = data.subarray(pos, pos + nodeIdLen); pos += nodeIdLen;
    const seqCounter = data.readUInt32BE(pos); pos += 4;
    const header = data.subarray(0, pos);
    const payloadEnd = data.length - 16 - 64;
    if (payloadEnd < pos) return null;
    const payload = data.subarray(pos, payloadEnd);
    const authTag = data.subarray(payloadEnd, payloadEnd + 16);
    const signature = data.subarray(payloadEnd + 16, payloadEnd + 80);

    const verified = this.open(header, Buffer.from(payload), Buffer.from(authTag));
    if (!verified) return null;

    const signInput = Buffer.concat([header, payload, authTag]);
    if (!this.verify(signInput, Buffer.from(signature))) return null;

    return { mode: wireMode, nodeId: Buffer.from(nodeId), seqCounter, payload: Buffer.from(verified), authTag: Buffer.from(authTag), signature: Buffer.from(signature) };
  }
}

// ─── Unified Wire Codec ──────────────────────────────────────────────────────

export class OSMPWireCodec {
  private sail: SAILCodec;
  private sec: SecCodec;

  constructor(opts?: { dictPath?: string; mdrPaths?: string[]; nodeId?: Buffer; signingKey?: Buffer; symmetricKey?: Buffer }) {
    this.sail = new SAILCodec(opts?.dictPath, opts?.mdrPaths);
    this.sec = new SecCodec(opts?.nodeId ?? Buffer.from([0x00, 0x01]), opts?.signingKey, opts?.symmetricKey);
  }

  encode(sal: string, mode: WireMode = WireMode.MNEMONIC): Buffer {
    switch (mode) {
      case WireMode.MNEMONIC: return Buffer.from(sal, "utf-8");
      case WireMode.SAIL:     return Buffer.from(this.sail.encode(sal));
      case WireMode.SEC:      return this.sec.pack(Buffer.from(sal, "utf-8"), WireMode.SEC);
      case WireMode.SAIL_SEC: return this.sec.pack(Buffer.from(this.sail.encode(sal)), WireMode.SAIL_SEC);
      default: throw new Error(`Unknown wire mode: ${mode}`);
    }
  }

  decode(data: Buffer, mode: WireMode = WireMode.MNEMONIC): string {
    switch (mode) {
      case WireMode.MNEMONIC: return data.toString("utf-8");
      case WireMode.SAIL:     return this.sail.decode(new Uint8Array(data));
      case WireMode.SEC: {
        const env = this.sec.unpack(data);
        if (!env) throw new Error("Security envelope verification failed");
        return env.payload.toString("utf-8");
      }
      case WireMode.SAIL_SEC: {
        const env = this.sec.unpack(data);
        if (!env) throw new Error("Security envelope verification failed");
        return this.sail.decode(new Uint8Array(env.payload));
      }
      default: throw new Error(`Unknown wire mode: ${mode}`);
    }
  }

  measure(sal: string): Record<string, any> {
    const mnemonicBytes = Buffer.byteLength(sal, "utf-8");
    const results: Record<string, any> = { _mnemonic_bytes: mnemonicBytes };
    for (const mode of [WireMode.MNEMONIC, WireMode.SAIL, WireMode.SEC, WireMode.SAIL_SEC]) {
      try {
        const encoded = this.encode(sal, mode);
        const decoded = this.decode(encoded, mode);
        results[wireModeLabel(mode)] = {
          bytes: encoded.length,
          reduction_vs_mnemonic: mnemonicBytes > 0 ? Math.round((1 - encoded.length / mnemonicBytes) * 1000) / 10 : 0,
          roundtrip: decoded === sal,
        };
      } catch (e: any) {
        results[wireModeLabel(mode)] = { error: e.message };
      }
    }
    return results;
  }
}

export default OSMPWireCodec;
