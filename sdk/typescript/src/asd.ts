/**
 * OSMP AdaptiveSharedDictionary
 * Analog: QUIC static table (RFC 9204 §A) | CRDT delta modes (Shapiro et al.)
 * Patent pending | License: Apache 2.0
 */
import { createHash } from "crypto";
import { ASD_BASIS, ASD_FLOOR_VERSION } from "./glyphs.js";
import { DictUpdateMode, DeltaLogEntry } from "./types.js";

/** Escape a string matching Python json.dumps ensure_ascii=True. */
function pyQuote(s: string): string {
  let out = '"';
  for (const ch of s) {
    const cp = ch.codePointAt(0)!;
    if (ch === '"') out += '\\"';
    else if (ch === '\\') out += '\\\\';
    else if (cp < 0x20) out += `\\u${cp.toString(16).padStart(4, "0")}`;
    else if (cp > 0x7e) out += `\\u${cp.toString(16).padStart(4, "0")}`;
    else out += ch;
  }
  return out + '"';
}

export class AdaptiveSharedDictionary {
  readonly floorVersion: string;
  private _data: Record<string, Record<string, string>>;
  private _tombstones: Set<string>;
  private _versionLog: DeltaLogEntry[];

  constructor(floorVersion: string = ASD_FLOOR_VERSION) {
    this.floorVersion = floorVersion;
    this._data = {};
    for (const [ns, ops] of Object.entries(ASD_BASIS)) {
      this._data[ns] = { ...ops };
    }
    this._tombstones = new Set();
    this._versionLog = [];
  }

  lookup(namespace: string, opcode: string): string | null {
    if (this._tombstones.has(`${namespace}::${opcode}`)) return null;
    return this._data[namespace]?.[opcode] ?? null;
  }

  applyDelta(namespace: string, opcode: string, definition: string,
             mode: DictUpdateMode, versionPointer: string): void {
    this._versionLog.push({ ns: namespace, op: opcode, def: definition,
                            mode: mode, ver: versionPointer });
    const key = `${namespace}::${opcode}`;
    if (mode === DictUpdateMode.ADDITIVE) {
      if (!this._data[namespace]) this._data[namespace] = {};
      if (!(opcode in this._data[namespace])) this._data[namespace][opcode] = definition;
    } else if (mode === DictUpdateMode.REPLACE) {
      if (!this._data[namespace]) this._data[namespace] = {};
      this._data[namespace][opcode] = definition;
      this._tombstones.delete(key);
    } else if (mode === DictUpdateMode.DEPRECATE) {
      this._tombstones.add(key);
    }
  }

  fingerprint(): string {
    return createHash("sha256").update(this.canonicalJSON()).digest("hex").slice(0,16);
  }

  /** Canonical JSON matching Python json.dumps(data, sort_keys=True, ensure_ascii=True).
   *  Uses ", " and ": " separators; escapes non-ASCII to \\uXXXX.
   *  Required for cross-SDK FNP fingerprint wire compatibility. */
  canonicalJSON(): string {
    const nsList = this.namespaces();
    const parts: string[] = ["{"];
    for (let i = 0; i < nsList.length; i++) {
      if (i > 0) parts.push(", ");
      parts.push(pyQuote(nsList[i]), ": {");
      const ops = this._data[nsList[i]];
      const opKeys = Object.keys(ops).sort();
      for (let j = 0; j < opKeys.length; j++) {
        if (j > 0) parts.push(", ");
        parts.push(pyQuote(opKeys[j]), ": ", pyQuote(ops[opKeys[j]]));
      }
      parts.push("}");
    }
    parts.push("}");
    return parts.join("");
  }

  namespaces(): string[] { return Object.keys(this._data).sort(); }
  versionLog(): DeltaLogEntry[] { return [...this._versionLog]; }
}
