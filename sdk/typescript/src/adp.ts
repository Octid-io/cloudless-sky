/**
 * ASD Distribution Protocol (ADP) — SAL-layer dictionary synchronization
 *
 * Complements the binary FNP handshake with SAL-level instructions for
 * version identity exchange, delta delivery, micro-delta, hash verification,
 * and MDR corpus version tracking.
 *
 * Patent ref: OSMP-001-UTIL Claims 20-21, Section VII.F, X-L
 * License: Apache 2.0
 */

import { AdaptiveSharedDictionary } from "./asd.js";
import { DictUpdateMode } from "./types.js";

// ── Version mapping: u16 wire as u8.u8 (MAJOR.MINOR) ──────────────────────

export function asdVersionPack(major: number, minor: number): number {
  if (major < 0 || major > 255 || minor < 0 || minor > 255)
    throw new RangeError(`Version ${major}.${minor} out of u8.u8 range`);
  return (major << 8) | minor;
}

export function asdVersionUnpack(u16: number): [number, number] {
  return [u16 >> 8, u16 & 0xFF];
}

export function asdVersionStr(u16: number): string {
  const [major, minor] = asdVersionUnpack(u16);
  return `${major}.${minor}`;
}

export function asdVersionParse(s: string): number {
  const parts = s.split(".");
  if (parts.length !== 2) throw new Error(`Invalid version string: ${s}`);
  return asdVersionPack(parseInt(parts[0], 10), parseInt(parts[1], 10));
}

export function asdVersionIsBreaking(oldU16: number, newU16: number): boolean {
  return (newU16 >> 8) > (oldU16 >> 8);
}

// ── Priority constants ─────────────────────────────────────────────────────

export const ADP_PRIORITY_MISSION  = 0;
export const ADP_PRIORITY_MICRO    = 1;
export const ADP_PRIORITY_DELTA    = 2;
export const ADP_PRIORITY_TRICKLE  = 3;

// ── Delta operation ────────────────────────────────────────────────────────

export interface ADPDeltaOp {
  namespace: string;
  mode: string;      // "+" | "\u2190" | "\u2020"
  opcode: string;
  definition?: string;
}

const MODE_NAMES: Record<string, string> = {
  "+": "ADDITIVE", "\u2190": "REPLACE", "\u2020": "DEPRECATE"
};

export function deltaOpToSal(op: ADPDeltaOp): string {
  return `${op.namespace}${op.mode}[${op.opcode}]`;
}

export function deltaOpIsBreaking(op: ADPDeltaOp): boolean {
  return op.mode === "\u2190";
}

// ── Delta payload ──────────────────────────────────────────────────────────

export interface ADPDelta {
  fromVersion: string;
  toVersion: string;
  operations: ADPDeltaOp[];
}

export function deltaToSal(d: ADPDelta): string {
  const ops = d.operations.map(deltaOpToSal).join(":");
  return `A:ASD:DELTA[${d.fromVersion}\u2192${d.toVersion}:${ops}]`;
}

export function deltaHasBreaking(d: ADPDelta): boolean {
  return d.operations.some(deltaOpIsBreaking);
}

// ── Pending instruction ────────────────────────────────────────────────────

export interface PendingInstruction {
  sal: string;
  unresolvedNamespace: string;
  unresolvedOpcode: string;
  timestamp: number;
}

// ── ADP Session ────────────────────────────────────────────────────────────

export class ADPSession {
  asd: AdaptiveSharedDictionary;
  asdVersion: number;
  namespaceVersions: Record<string, string>;
  pendingQueue: PendingInstruction[];
  deltaLog: string[];
  remoteVersion: number | null;
  remoteNamespaceVersions: Record<string, string> | null;

  constructor(
    asd: AdaptiveSharedDictionary,
    asdVersion: number = asdVersionPack(1, 0),
    namespaceVersions: Record<string, string> = {}
  ) {
    this.asd = asd;
    this.asdVersion = asdVersion;
    this.namespaceVersions = namespaceVersions;
    this.pendingQueue = [];
    this.deltaLog = [];
    this.remoteVersion = null;
    this.remoteNamespaceVersions = null;
  }

  // ── Version identity ───────────────────────────────────────────────

  versionIdentity(includeNamespaces: boolean = true): string {
    const ver = asdVersionStr(this.asdVersion);
    if (includeNamespaces && Object.keys(this.namespaceVersions).length > 0) {
      const ns = Object.keys(this.namespaceVersions).sort()
        .map(k => `:${k}${this.namespaceVersions[k]}`).join("");
      return `A:ASD[${ver}${ns}]`;
    }
    return `A:ASD[${ver}]`;
  }

  versionQuery(): string { return "A:ASD?"; }

  versionAlert(): string {
    return `A:ASD[${asdVersionStr(this.asdVersion)}]\u26a0`;
  }

  // ── Version parsing ────────────────────────────────────────────────

  receiveVersion(sal: string): {
    version: string; u16: number;
    namespaces: Record<string, string>;
    breaking: boolean; match: boolean;
  } {
    let inner = sal;
    if (inner.startsWith("A:ASD[")) inner = inner.slice(6);
    inner = inner.replace(/[\]\u26a0]+$/, "");

    const parts = inner.split(":");
    const verStr = parts[0];
    const remoteU16 = asdVersionParse(verStr);
    this.remoteVersion = remoteU16;

    const nsVersions: Record<string, string> = {};
    for (let i = 1; i < parts.length; i++) {
      const part = parts[i];
      if (part.length >= 2 && /[A-Z]/.test(part[0])) {
        nsVersions[part[0]] = part.slice(1);
      }
    }
    this.remoteNamespaceVersions = nsVersions;

    return {
      version: verStr,
      u16: remoteU16,
      namespaces: nsVersions,
      breaking: asdVersionIsBreaking(this.asdVersion, remoteU16),
      match: remoteU16 === this.asdVersion,
    };
  }

  // ── Delta request ──────────────────────────────────────────────────

  requestDelta(target?: string, namespace?: string): string {
    const myVer = asdVersionStr(this.asdVersion);
    const tgt = target || (this.remoteVersion !== null
      ? asdVersionStr(this.remoteVersion) : myVer);
    if (namespace && this.remoteNamespaceVersions) {
      const myNs = this.namespaceVersions[namespace] || "0.0";
      const remoteNs = this.remoteNamespaceVersions[namespace] || "0.0";
      return `A:ASD:REQ[${namespace}${myNs}\u2192${namespace}${remoteNs}]`;
    }
    return `A:ASD:REQ[${myVer}\u2192${tgt}]`;
  }

  // ── Delta application ──────────────────────────────────────────────

  applyDeltaSal(sal: string): {
    applied: boolean; from?: string; to?: string;
    operations?: string[]; breaking?: boolean;
    pendingResolved?: string[]; error?: string;
  } {
    this.deltaLog.push(sal);

    let inner = sal;
    if (inner.startsWith("A:ASD:DELTA[")) inner = inner.slice(12);
    inner = inner.replace(/\]+$/, "");

    const arrowIdx = inner.indexOf("\u2192");
    if (arrowIdx < 0) return { applied: false, error: "No version range" };

    const afterArrow = inner.slice(arrowIdx + 1);
    const colonIdx = afterArrow.indexOf(":");
    if (colonIdx < 0) return { applied: false, error: "No operations" };

    const fromVer = inner.slice(0, arrowIdx);
    const toVer = afterArrow.slice(0, colonIdx);
    const opsStr = afterArrow.slice(colonIdx + 1);

    const operations: string[] = [];
    let hasBreaking = false;
    const modeChars = new Set(["+", "\u2190", "\u2020"]);

    let pos = 0;
    while (pos < opsStr.length) {
      if (!/[A-Z]/.test(opsStr[pos])) { pos++; continue; }
      const ns = opsStr[pos]; pos++;
      if (pos >= opsStr.length) break;
      const mode = opsStr[pos];
      if (!modeChars.has(mode)) continue;
      pos++;
      if (pos < opsStr.length && opsStr[pos] === "[") {
        const endBracket = opsStr.indexOf("]", pos);
        const opcode = endBracket >= 0
          ? opsStr.slice(pos + 1, endBracket)
          : opsStr.slice(pos + 1);
        pos = endBracket >= 0 ? endBracket + 1 : opsStr.length;

        const asdMode = mode === "+"
          ? DictUpdateMode.ADDITIVE
          : mode === "\u2190"
            ? DictUpdateMode.REPLACE
            : DictUpdateMode.DEPRECATE;
        this.asd.applyDelta(ns, opcode, "", asdMode, toVer);
        if (mode === "\u2190") hasBreaking = true;
        operations.push(`${ns}:${opcode}(${MODE_NAMES[mode]})`);
      }
    }

    const resolved = this.resolvePending();

    return {
      applied: true, from: fromVer, to: toVer,
      operations, breaking: hasBreaking,
      pendingResolved: resolved,
    };
  }

  // ── Micro-delta ────────────────────────────────────────────────────

  requestDefinition(namespace: string, opcode: string): string {
    return `A:ASD:DEF?[${namespace}:${opcode}]`;
  }

  sendDefinition(namespace: string, opcode: string,
                  definition: string, layer: number = 1): string {
    return `A:ASD:DEF[${namespace}:${opcode}:${definition}:${layer}]`;
  }

  applyDefinition(sal: string): {
    applied: boolean; namespace?: string; opcode?: string;
    definition?: string; layer?: number;
    pendingResolved?: string[]; error?: string;
  } {
    this.deltaLog.push(sal);
    let inner = sal;
    if (inner.startsWith("A:ASD:DEF[")) inner = inner.slice(10);
    inner = inner.replace(/\]+$/, "");

    const parts = inner.split(":");
    if (parts.length < 3) return { applied: false, error: "Insufficient fields" };

    const [namespace, opcode, definition] = parts;
    const layer = parts.length > 3 ? parseInt(parts[3], 10) : 1;

    this.asd.applyDelta(namespace, opcode, definition,
                         DictUpdateMode.ADDITIVE, "micro");

    const resolved = this.resolvePending();

    return {
      applied: true, namespace, opcode, definition, layer,
      pendingResolved: resolved,
    };
  }

  // ── Hash verification ──────────────────────────────────────────────

  hashIdentity(hexLength: number = 8): string {
    const ver = asdVersionStr(this.asdVersion);
    const fp = this.asd.fingerprint().slice(0, hexLength);
    return `A:ASD:HASH[${ver}:${fp}]`;
  }

  verifyHash(sal: string): { match: boolean; remoteHash?: string; localHash?: string } {
    let inner = sal;
    if (inner.startsWith("A:ASD:HASH[")) inner = inner.slice(11);
    inner = inner.replace(/\]+$/, "");
    const parts = inner.split(":");
    if (parts.length < 2) return { match: false };
    const remoteHash = parts[1];
    const localHash = this.asd.fingerprint().slice(0, remoteHash.length);
    return { match: remoteHash === localHash, remoteHash, localHash };
  }

  // ── MDR corpus versioning ──────────────────────────────────────────

  static mdrIdentity(corpora: Record<string, string>): string {
    const parts = Object.keys(corpora).sort()
      .map(k => `${k}:${corpora[k]}`).join(":");
    return `A:MDR[${parts}]`;
  }

  static mdrRequest(corpus: string, fromVer: string, toVer: string): string {
    return `A:MDR:REQ[${corpus}:${fromVer}\u2192${toVer}]`;
  }

  // ── Semantic pending queue ─────────────────────────────────────────

  resolveOrPend(sal: string): {
    resolved: boolean; pending: boolean;
    definition?: string; unresolved?: string;
    microDeltaRequest?: string; queueDepth?: number;
  } {
    const [ns, opcode] = ADPSession.extractNsOpcode(sal);
    if (ns === null) return { resolved: true, pending: false };

    const definition = this.asd.lookup(ns, opcode!);
    if (definition !== null)
      return { resolved: true, pending: false, definition };

    this.pendingQueue.push({
      sal, unresolvedNamespace: ns,
      unresolvedOpcode: opcode!,
      timestamp: Date.now(),
    });

    return {
      resolved: false, pending: true,
      unresolved: `${ns}:${opcode}`,
      microDeltaRequest: this.requestDefinition(ns, opcode!),
      queueDepth: this.pendingQueue.length,
    };
  }

  private resolvePending(): string[] {
    const resolved: string[] = [];
    const stillPending: PendingInstruction[] = [];
    for (const p of this.pendingQueue) {
      if (this.asd.lookup(p.unresolvedNamespace, p.unresolvedOpcode) !== null)
        resolved.push(p.sal);
      else
        stillPending.push(p);
    }
    this.pendingQueue = stillPending;
    return resolved;
  }

  private static extractNsOpcode(sal: string): [string | null, string | null] {
    if (!sal || !/^[A-Z]/.test(sal) || !sal.includes(":"))
      return [null, null];
    const parts = sal.split(":");
    if (parts.length < 2 || parts[0].length !== 1) return [null, null];
    let opcode = "";
    for (const ch of parts[1]) {
      if ("[]?<>@\u2227\u2228\u2192\u26a0".includes(ch)) break;
      opcode += ch;
    }
    return [parts[0], opcode || null];
  }

  // ── Acknowledge ────────────────────────────────────────────────────

  static acknowledgeVersion(version: string): string {
    return `A:ACK[ASD:${version}]`;
  }
  static acknowledgeHash(): string { return "A:ACK[ASD:HASH]"; }
  static acknowledgeDef(): string { return "A:ACK[ASD:DEF]"; }

  // ── Priority classification ────────────────────────────────────────

  static classifyPriority(sal: string): number {
    if (!sal.startsWith("A:ASD") && !sal.startsWith("A:MDR"))
      return ADP_PRIORITY_MISSION;
    if (sal.includes("DEF")) return ADP_PRIORITY_MICRO;
    if (sal.includes("DELTA")) return ADP_PRIORITY_DELTA;
    return ADP_PRIORITY_TRICKLE;
  }
}
