/**
 * FNP — Frame Negotiation Protocol
 *
 * Two-message capability advertisement + acknowledgment completing within
 * 78 bytes total (40 ADV + 38 ACK), designed for LoRa physical layer floor.
 *
 * Negotiates three properties in two packets:
 *   1. Dictionary alignment (ASD fingerprint match)
 *   2. Namespace intersection (shared domain capabilities)
 *   3. Channel capacity (byte budget for the session)
 *
 * Patent ref: OSMP-001-UTIL Section II.C, FIG. 5
 */

import { AdaptiveSharedDictionary } from "./asd.js";

// ── constants ───────────────────────────────────────────────────────

export const FNP_MSG_ADV  = 0x01;
export const FNP_MSG_ACK  = 0x02;
export const FNP_MSG_NACK = 0x03;

export const FNP_MATCH_EXACT       = 0x00;
export const FNP_MATCH_VERSION     = 0x01;
export const FNP_MATCH_FINGERPRINT = 0x02;

export const FNP_CAP_FLOOR         = 0x00;  // 51 bytes (LoRa SF12)
export const FNP_CAP_STANDARD      = 0x01;  // 255 bytes (LoRa SF11)
export const FNP_CAP_BLE           = 0x02;  // 512 bytes
export const FNP_CAP_UNCONSTRAINED = 0x03;  // no limit

export const FNP_CAP_BYTES: Record<number, number> = {
  [FNP_CAP_FLOOR]: 51,
  [FNP_CAP_STANDARD]: 255,
  [FNP_CAP_BLE]: 512,
  [FNP_CAP_UNCONSTRAINED]: 0,
};

export const FNP_ADV_SIZE = 40;
export const FNP_ACK_SIZE = 38;
export const FNP_PROTOCOL_VERSION = 0x01;

const NS_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

// ── types ───────────────────────────────────────────────────────────

export type FNPState = "IDLE" | "ADV_SENT" | "ESTABLISHED" | "SYNC_NEEDED" | "FALLBACK" | "ACQUIRED";

export interface FNPSessionInfo {
  state: FNPState;
  remoteNodeId: string | null;
  remoteFingerprint: Uint8Array | null;
  commonNamespaces: string[] | null;
  matchStatus: number | null;
  negotiatedCapacity: number | null;
}

// ── helpers ─────────────────────────────────────────────────────────

function namespaceBitmap(namespaces: string[]): number {
  let bitmap = 0;
  for (const ns of namespaces) {
    if (ns.length === 1 && NS_LETTERS.includes(ns)) {
      bitmap |= 1 << NS_LETTERS.indexOf(ns);
    } else if (ns === "\u03A9") {
      bitmap |= 1 << 26;
    }
  }
  return bitmap;
}

function bitmapToNamespaces(bitmap: number): string[] {
  const result: string[] = [];
  for (let i = 0; i < NS_LETTERS.length; i++) {
    if (bitmap & (1 << i)) result.push(NS_LETTERS[i]);
  }
  if (bitmap & (1 << 26)) result.push("\u03A9");
  return result;
}

function fingerprintBytes(asd: AdaptiveSharedDictionary): Uint8Array {
  const hex = asd.fingerprint();
  const bytes = new Uint8Array(8);
  for (let i = 0; i < 8; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

function compareBytes(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

// ── FNPSession ──────────────────────────────────────────────────────

/**
 * FNP session handshake state machine.
 *
 * Manages the two-message capability advertisement and acknowledgment
 * exchange between two sovereign nodes. After a successful handshake,
 * provides the negotiated session state: whether dictionaries match,
 * which namespaces are shared, the channel byte budget, and the remote
 * node's identity.
 *
 * Usage (initiator):
 *   const session = new FNPSession(asd, "NODE_A");
 *   const adv = session.initiate();
 *   // ... transmit adv, receive ackPacket ...
 *   session.receive(ackPacket);
 *   // session.state === "ESTABLISHED"
 *
 * Usage (responder):
 *   const session = new FNPSession(asd, "NODE_B");
 *   const ack = session.receive(advPacket);
 *   // ... transmit ack ...
 *   // session.state === "ESTABLISHED"
 */
export class FNPSession {
  private asd: AdaptiveSharedDictionary;
  private nodeId: string;
  private asdVersion: number;
  private channelCapacity: number;
  private ownFp: Uint8Array;
  private ownBitmap: number;

  state: FNPState = "IDLE";
  remoteNodeId: string | null = null;
  remoteFingerprint: Uint8Array | null = null;
  commonNamespaces: string[] | null = null;
  matchStatus: number | null = null;
  negotiatedCapacity: number | null = null;

  constructor(
    asd: AdaptiveSharedDictionary,
    nodeId: string,
    asdVersion: number = 1,
    channelCapacity: number = FNP_CAP_FLOOR,
  ) {
    this.asd = asd;
    this.nodeId = nodeId;
    this.asdVersion = asdVersion;
    this.channelCapacity = channelCapacity;
    this.ownFp = fingerprintBytes(asd);
    this.ownBitmap = namespaceBitmap(asd.namespaces());
  }

  // ── packet construction ─────────────────────────────────────────

  private buildAdv(): Uint8Array {
    const buf = new Uint8Array(FNP_ADV_SIZE);
    const view = new DataView(buf.buffer);
    buf[0] = FNP_MSG_ADV;
    buf[1] = FNP_PROTOCOL_VERSION;
    buf.set(this.ownFp, 2);
    view.setUint16(10, this.asdVersion);
    view.setUint32(12, this.ownBitmap);
    buf[16] = this.channelCapacity;
    const nid = new TextEncoder().encode(this.nodeId).slice(0, 23);
    buf.set(nid, 17);
    return buf;
  }

  private buildAck(
    remoteFp: Uint8Array,
    match: number,
    commonBitmap: number,
    negCap: number,
  ): Uint8Array {
    const buf = new Uint8Array(FNP_ACK_SIZE);
    const view = new DataView(buf.buffer);
    buf[0] = match === FNP_MATCH_EXACT ? FNP_MSG_ACK : FNP_MSG_NACK;
    buf[1] = match;
    buf.set(remoteFp, 2);
    buf.set(this.ownFp, 10);
    view.setUint32(18, commonBitmap);
    buf[22] = negCap;
    const nid = new TextEncoder().encode(this.nodeId).slice(0, 15);
    buf.set(nid, 23);
    return buf;
  }

  // ── packet parsing ──────────────────────────────────────────────

  private static parseAdv(data: Uint8Array): {
    protocolVersion: number;
    fingerprint: Uint8Array;
    asdVersion: number;
    namespaceBitmap: number;
    channelCapacity: number;
    nodeId: string;
  } {
    if (data.length < FNP_ADV_SIZE || data[0] !== FNP_MSG_ADV) {
      throw new Error("Invalid FNP_ADV packet");
    }
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    return {
      protocolVersion: data[1],
      fingerprint: data.slice(2, 10),
      asdVersion: view.getUint16(10),
      namespaceBitmap: view.getUint32(12),
      channelCapacity: data[16],
      nodeId: new TextDecoder().decode(data.slice(17, 40)).replace(/\0+$/, ""),
    };
  }

  private static parseAck(data: Uint8Array): {
    msgType: number;
    matchStatus: number;
    echoFingerprint: Uint8Array;
    ownFingerprint: Uint8Array;
    commonBitmap: number;
    negotiatedCapacity: number;
    nodeId: string;
  } {
    if (data.length < FNP_ACK_SIZE || (data[0] !== FNP_MSG_ACK && data[0] !== FNP_MSG_NACK)) {
      throw new Error("Invalid FNP_ACK packet");
    }
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    return {
      msgType: data[0],
      matchStatus: data[1],
      echoFingerprint: data.slice(2, 10),
      ownFingerprint: data.slice(10, 18),
      commonBitmap: view.getUint32(18),
      negotiatedCapacity: data[22],
      nodeId: new TextDecoder().decode(data.slice(23, 38)).replace(/\0+$/, ""),
    };
  }

  // ── state machine ───────────────────────────────────────────────

  /** Start a handshake. Returns a 40-byte ADV packet. IDLE -> ADV_SENT. */
  initiate(): Uint8Array {
    if (this.state !== "IDLE") {
      throw new Error(`Cannot initiate from state ${this.state}`);
    }
    this.state = "ADV_SENT";
    return this.buildAdv();
  }

  /**
   * Process a received FNP packet.
   *
   * If IDLE and ADV received: returns ACK packet to transmit.
   * If ADV_SENT and ACK received: processes result, returns null.
   */
  receive(data: Uint8Array): Uint8Array | null {
    const msgType = data[0];

    if (msgType === FNP_MSG_ADV && this.state === "IDLE") {
      const adv = FNPSession.parseAdv(data);
      this.remoteNodeId = adv.nodeId;
      this.remoteFingerprint = adv.fingerprint;

      let match: number;
      if (compareBytes(adv.fingerprint, this.ownFp)) {
        match = adv.asdVersion === this.asdVersion
          ? FNP_MATCH_EXACT
          : FNP_MATCH_VERSION;
      } else {
        match = FNP_MATCH_FINGERPRINT;
      }

      const common = this.ownBitmap & adv.namespaceBitmap;
      this.commonNamespaces = bitmapToNamespaces(common);
      this.matchStatus = match;

      const negCap = Math.min(adv.channelCapacity, this.channelCapacity);
      this.negotiatedCapacity = negCap;

      this.state = match === FNP_MATCH_EXACT ? "ESTABLISHED" : "SYNC_NEEDED";
      return this.buildAck(adv.fingerprint, match, common, negCap);
    }

    if ((msgType === FNP_MSG_ACK || msgType === FNP_MSG_NACK) && this.state === "ADV_SENT") {
      const ack = FNPSession.parseAck(data);

      if (!compareBytes(ack.echoFingerprint, this.ownFp)) {
        throw new Error("FNP_ACK echo fingerprint mismatch");
      }

      this.remoteNodeId = ack.nodeId;
      this.remoteFingerprint = ack.ownFingerprint;
      this.commonNamespaces = bitmapToNamespaces(ack.commonBitmap);
      this.matchStatus = ack.matchStatus;
      this.negotiatedCapacity = ack.negotiatedCapacity;
      this.state = ack.matchStatus === FNP_MATCH_EXACT ? "ESTABLISHED" : "SYNC_NEEDED";
      return null;
    }

    throw new Error(`Unexpected msg_type 0x${msgType.toString(16)} in state ${this.state}`);
  }

  /** Handle timeout. ADV_SENT -> IDLE. */
  timeout(): void {
    if (this.state === "ADV_SENT") {
      this.state = "IDLE";
      this.remoteNodeId = null;
      this.remoteFingerprint = null;
      this.commonNamespaces = null;
      this.matchStatus = null;
      this.negotiatedCapacity = null;
    }
  }

  /**
   * Transition to FALLBACK when the remote peer does not speak OSMP.
   *
   * Called when:
   * - ADV was sent but the response is not a valid FNP packet
   * - The transport is known to be non-OSMP (e.g., plain JSON-RPC, NL)
   * - Timeout occurred during negotiation attempt with a new peer
   *
   * Transitions: ADV_SENT -> FALLBACK, or IDLE -> FALLBACK (direct).
   */
  fallback(remoteId: string = "UNKNOWN"): void {
    if (this.state === "ADV_SENT" || this.state === "IDLE") {
      this.state = "FALLBACK";
      this.remoteNodeId = remoteId;
      this.remoteFingerprint = null;
      this.commonNamespaces = [];
      this.matchStatus = null;
      this.negotiatedCapacity = null;
    }
  }

  /**
   * Transition to ACQUIRED when the remote peer starts producing valid SAL.
   * Called by SALBridge when the acquisition score exceeds threshold.
   * Transitions: FALLBACK -> ACQUIRED.
   */
  acquire(): void {
    if (this.state === "FALLBACK") {
      this.state = "ACQUIRED";
    }
  }

  /**
   * Transition back to FALLBACK when an ACQUIRED peer stops producing valid SAL.
   * Transitions: ACQUIRED -> FALLBACK.
   */
  regress(): void {
    if (this.state === "ACQUIRED") {
      this.state = "FALLBACK";
    }
  }

  /** True if this session is in FALLBACK or ACQUIRED state. */
  isLegacyPeer(): boolean {
    return this.state === "FALLBACK" || this.state === "ACQUIRED";
  }

  /** True if this session is in ACQUIRED state. */
  isAcquired(): boolean {
    return this.state === "ACQUIRED";
  }
}
