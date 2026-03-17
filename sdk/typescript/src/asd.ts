/**
 * OSMP AdaptiveSharedDictionary
 * Analog: QUIC static table (RFC 9204 §A) | CRDT delta modes (Shapiro et al.)
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
import { createHash } from "crypto";
import { ASD_BASIS, ASD_FLOOR_VERSION } from "./glyphs.js";
import { DictUpdateMode, DeltaLogEntry } from "./types.js";

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
    const sorted = Object.fromEntries(
      Object.entries(this._data)
        .sort(([a],[b]) => a.localeCompare(b))
        .map(([ns,ops]) => [ns, Object.fromEntries(Object.entries(ops).sort())])
    );
    return createHash("sha256").update(JSON.stringify(sorted)).digest("hex").slice(0,16);
  }

  namespaces(): string[] { return Object.keys(this._data).sort(); }
  versionLog(): DeltaLogEntry[] { return [...this._versionLog]; }
}
