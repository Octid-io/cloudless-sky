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
 * FNP state machine reference
 */

import { AdaptiveSharedDictionary } from "./asd.js";

// ── constants ───────────────────────────────────────────────────────

export const FNP_MSG_ADV  = 0x01;
export const FNP_MSG_ACK  = 0x02;
export const FNP_MSG_NACK = 0x03;

// ADR-004: extended-form ADV signaled by msg_type bit 7 (high bit set).
// Extended form narrows node_id from 23 to 15 bytes and carries an 8-byte
// basis_fingerprint at offset 32. Total ADV size remains 40 bytes in both
// forms; only the field layout differs. See spec §9.1.
export const FNP_MSG_ADV_EXTENDED = 0x81;
export const FNP_ADV_EXT_FLAG     = 0x80;  // bit mask for the extended-form flag

export const FNP_MATCH_EXACT             = 0x00;
export const FNP_MATCH_VERSION           = 0x01;
export const FNP_MATCH_FINGERPRINT       = 0x02;
export const FNP_MATCH_BASIS_MISMATCH    = 0x03;  // ADR-004: ASD matches, bases differ (both extended)
export const FNP_MATCH_BASIS_EXT_VS_BASE = 0x04;  // ADR-004: ASD matches, base form vs extended (length mismatch)

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

export type FNPState = "IDLE" | "ADV_SENT" | "ESTABLISHED" | "ESTABLISHED_SAIL" | "ESTABLISHED_SAL_ONLY" | "SYNC_NEEDED" | "FALLBACK" | "ACQUIRED";

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

  // ADR-004 basis manifest support
  basisFingerprint: Uint8Array | null;
  expectedBasisFingerprint: Uint8Array | null;
  requireSail: boolean;
  remoteBasisFingerprint: Uint8Array | null = null;
  degradationEvent: Record<string, any> | null = null;

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
    opts: {
      basisFingerprint?: Uint8Array;
      expectedBasisFingerprint?: Uint8Array;
      requireSail?: boolean;
    } = {},
  ) {
    this.asd = asd;
    this.nodeId = nodeId;
    this.asdVersion = asdVersion;
    this.channelCapacity = channelCapacity;
    this.ownFp = fingerprintBytes(asd);
    this.ownBitmap = namespaceBitmap(asd.namespaces());
    this.basisFingerprint = opts.basisFingerprint ?? null;
    this.expectedBasisFingerprint = opts.expectedBasisFingerprint ?? null;
    this.requireSail = opts.requireSail ?? false;
  }

  /** True if this session uses extended-form ADV (basis_fingerprint set). */
  get isExtendedForm(): boolean {
    return this.basisFingerprint !== null;
  }

  /** True if the negotiated session supports SAIL wire mode (ADR-004). */
  get isSailCapable(): boolean {
    return this.state === "ESTABLISHED_SAIL";
  }

  // ── packet construction ─────────────────────────────────────────

  private buildAdv(): Uint8Array {
    const buf = new Uint8Array(FNP_ADV_SIZE);
    const view = new DataView(buf.buffer);
    buf[1] = FNP_PROTOCOL_VERSION;
    buf.set(this.ownFp, 2);
    view.setUint16(10, this.asdVersion);
    view.setUint32(12, this.ownBitmap);
    buf[16] = this.channelCapacity;

    if (this.isExtendedForm) {
      // Extended form: msg_type bit 7 set, node_id narrowed to 15 bytes,
      // basis_fingerprint at offset 32. Spec §9.1.
      buf[0] = FNP_MSG_ADV_EXTENDED;
      const nid = new TextEncoder().encode(this.nodeId).slice(0, 15);
      buf.set(nid, 17);
      buf.set(this.basisFingerprint!, 32);
    } else {
      // Base form: msg_type 0x01, node_id reserves the full 23 bytes.
      buf[0] = FNP_MSG_ADV;
      const nid = new TextEncoder().encode(this.nodeId).slice(0, 23);
      buf.set(nid, 17);
    }
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
    // ADR-004: basis-graded matches (0x03 / 0x04) are NOT failures, they
    // are graded capability and use ACK rather than NACK.
    const isAck = (
      match === FNP_MATCH_EXACT ||
      match === FNP_MATCH_BASIS_MISMATCH ||
      match === FNP_MATCH_BASIS_EXT_VS_BASE
    );
    buf[0] = isAck ? FNP_MSG_ACK : FNP_MSG_NACK;
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

  static parseAdv(data: Uint8Array): {
    msgType: number;
    isExtended: boolean;
    protocolVersion: number;
    fingerprint: Uint8Array;
    asdVersion: number;
    namespaceBitmap: number;
    channelCapacity: number;
    nodeId: string;
    basisFingerprint: Uint8Array | null;
  } {
    const baseType = data[0] & ~FNP_ADV_EXT_FLAG;
    if (data.length < FNP_ADV_SIZE || baseType !== FNP_MSG_ADV) {
      throw new Error("Invalid FNP_ADV packet");
    }
    const isExtended = (data[0] & FNP_ADV_EXT_FLAG) !== 0;
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    const result = {
      msgType: data[0],
      isExtended,
      protocolVersion: data[1],
      fingerprint: data.slice(2, 10),
      asdVersion: view.getUint16(10),
      namespaceBitmap: view.getUint32(12),
      channelCapacity: data[16],
      nodeId: "",
      basisFingerprint: null as Uint8Array | null,
    };
    if (isExtended) {
      result.nodeId = new TextDecoder().decode(data.slice(17, 32)).replace(/\0+$/, "");
      result.basisFingerprint = data.slice(32, 40);
    } else {
      result.nodeId = new TextDecoder().decode(data.slice(17, 40)).replace(/\0+$/, "");
    }
    return result;
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
    const msgTypeBase = msgType & ~FNP_ADV_EXT_FLAG;

    if (msgTypeBase === FNP_MSG_ADV && this.state === "IDLE") {
      const adv = FNPSession.parseAdv(data);
      this.remoteNodeId = adv.nodeId;
      this.remoteFingerprint = adv.fingerprint;
      this.remoteBasisFingerprint = adv.basisFingerprint;

      let match: number;
      if (!compareBytes(adv.fingerprint, this.ownFp)) {
        match = FNP_MATCH_FINGERPRINT;
      } else if (adv.asdVersion !== this.asdVersion) {
        match = FNP_MATCH_VERSION;
      } else {
        // ADR-004 basis fingerprint capability grading.
        const remoteExt = adv.basisFingerprint !== null;
        const localExt = this.isExtendedForm;
        if (remoteExt && localExt) {
          match = compareBytes(adv.basisFingerprint!, this.basisFingerprint!)
            ? FNP_MATCH_EXACT
            : FNP_MATCH_BASIS_MISMATCH;
        } else if (remoteExt !== localExt) {
          match = FNP_MATCH_BASIS_EXT_VS_BASE;
        } else {
          match = FNP_MATCH_EXACT;
        }
      }

      const common = this.ownBitmap & adv.namespaceBitmap;
      this.commonNamespaces = bitmapToNamespaces(common);
      this.matchStatus = match;

      const negCap = Math.min(adv.channelCapacity, this.channelCapacity);
      this.negotiatedCapacity = negCap;

      this.applyMatchToState(match, adv.basisFingerprint);
      return this.buildAck(adv.fingerprint, match, common, negCap);
    }

    if ((msgTypeBase === FNP_MSG_ACK || msgTypeBase === FNP_MSG_NACK) && this.state === "ADV_SENT") {
      const ack = FNPSession.parseAck(data);

      if (!compareBytes(ack.echoFingerprint, this.ownFp)) {
        throw new Error("FNP_ACK echo fingerprint mismatch");
      }

      this.remoteNodeId = ack.nodeId;
      this.remoteFingerprint = ack.ownFingerprint;
      this.commonNamespaces = bitmapToNamespaces(ack.commonBitmap);
      this.matchStatus = ack.matchStatus;
      this.negotiatedCapacity = ack.negotiatedCapacity;
      // ACK does not carry remote basis fingerprint per ADR-004 spec §9.2;
      // initiator learns basis agreement via match_status.
      this.applyMatchToState(ack.matchStatus, null);
      return null;
    }

    throw new Error(`Unexpected msg_type 0x${msgType.toString(16)} in state ${this.state}`);
  }

  private applyMatchToState(match: number, peerBasisFp: Uint8Array | null): void {
    if (match === FNP_MATCH_EXACT) {
      this.state = "ESTABLISHED_SAIL";
      return;
    }
    if (match === FNP_MATCH_BASIS_MISMATCH || match === FNP_MATCH_BASIS_EXT_VS_BASE) {
      if (this.requireSail) {
        this.state = "IDLE";
        this.degradationEvent = {
          reason: "require_sail policy refused basis-mismatched session",
          match_status: match,
          remote_node_id: this.remoteNodeId,
          remote_basis_fingerprint: peerBasisFp ? Buffer.from(peerBasisFp).toString("hex") : null,
        };
        return;
      }
      this.state = "ESTABLISHED_SAL_ONLY";
      if (
        this.expectedBasisFingerprint !== null &&
        peerBasisFp !== null &&
        !compareBytes(peerBasisFp, this.expectedBasisFingerprint)
      ) {
        this.degradationEvent = {
          reason: "remote basis fingerprint differs from expected",
          match_status: match,
          remote_node_id: this.remoteNodeId,
          remote_basis_fingerprint: Buffer.from(peerBasisFp).toString("hex"),
          expected_basis_fingerprint: Buffer.from(this.expectedBasisFingerprint).toString("hex"),
        };
      }
      return;
    }
    // FNP_MATCH_VERSION or FNP_MATCH_FINGERPRINT
    this.state = "SYNC_NEEDED";
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
