/**
 * OSMP Overflow Protocol — fragmentation and loss tolerance
 * Analog: QUIC receive buffer (RFC 9000 §2.2)
 * Patent pending | License: Apache 2.0
 */
import { Fragment, LossPolicy, FLAG_TERMINAL, FLAG_CRITICAL,
         FRAGMENT_HEADER_BYTES, LORA_STANDARD_BYTES } from "./types.js";

export function packFragment(f: Fragment): Uint8Array {
  const buf = Buffer.alloc(FRAGMENT_HEADER_BYTES + f.payload.length);
  buf.writeUInt16BE(f.msgId,0); buf.writeUInt8(f.fragIdx,2); buf.writeUInt8(f.fragCt,3);
  buf.writeUInt8(f.flags,4); buf.writeUInt8(f.dep,5); buf.set(f.payload, FRAGMENT_HEADER_BYTES);
  return new Uint8Array(buf);
}

export function unpackFragment(data: Uint8Array): Fragment {
  if (data.length < FRAGMENT_HEADER_BYTES) throw new Error(`Fragment too short: ${data.length}`);
  const buf = Buffer.from(data);
  return { msgId: buf.readUInt16BE(0), fragIdx: buf.readUInt8(2), fragCt: buf.readUInt8(3),
           flags: buf.readUInt8(4), dep: buf.readUInt8(5),
           payload: new Uint8Array(data.slice(FRAGMENT_HEADER_BYTES)) };
}

export function isTerminal(f: Fragment): boolean { return !!(f.flags & FLAG_TERMINAL); }
export function isCritical(f: Fragment): boolean  { return !!(f.flags & FLAG_CRITICAL); }

export class OverflowProtocol {
  private mtu: number; private policy: LossPolicy;
  private _counter = 0;
  private _buf = new Map<number, Map<number, Fragment>>();

  constructor(mtu = LORA_STANDARD_BYTES, policy = LossPolicy.GRACEFUL_DEGRADATION,
              _timeout = 30) { this.mtu = mtu; this.policy = policy; }

  private nextId(): number { this._counter = (this._counter+1)%65536; return this._counter; }

  fragment(payload: Uint8Array, critical=false): Fragment[] {
    const avail = this.mtu - FRAGMENT_HEADER_BYTES;
    const baseFlags = FLAG_TERMINAL | (critical ? FLAG_CRITICAL : 0);
    if (payload.length + FRAGMENT_HEADER_BYTES <= this.mtu)
      return [{ msgId: this.nextId(), fragIdx:0, fragCt:1, flags: baseFlags, dep:0, payload }];
    const chunks: Uint8Array[] = [];
    for (let i=0; i<payload.length; i+=avail) chunks.push(payload.slice(i,i+avail));
    const msgId = this.nextId(); const fragCt = chunks.length;
    return chunks.map((chunk,idx) => ({
      msgId, fragIdx:idx, fragCt,
      flags: (idx===fragCt-1?FLAG_TERMINAL:0)|(critical?FLAG_CRITICAL:0),
      dep:0, payload:chunk,
    }));
  }

  receive(frag: Fragment): Uint8Array | null {
    if (Buffer.from(frag.payload).toString("utf8").includes("R:ESTOP")) return frag.payload;
    const mid = frag.msgId;
    if (!this._buf.has(mid)) this._buf.set(mid, new Map());
    this._buf.get(mid)!.set(frag.fragIdx, frag);
    const rcv = this._buf.get(mid)!; const exp = frag.fragCt;
    if (this.policy === LossPolicy.ATOMIC || isCritical(frag)) {
      return rcv.size===exp ? this._reassemble(rcv,exp) : null;
    } else if (this.policy === LossPolicy.GRACEFUL_DEGRADATION) {
      if (isTerminal(frag) && rcv.size===exp) return this._reassemble(rcv,exp);
      if (isTerminal(frag)) return this._reassemblePartial(rcv,exp);
      return null;
    } else {
      return rcv.size===exp ? this._reassemble(rcv,exp) : null;
    }
  }

  private _reassemble(rcv: Map<number,Fragment>, exp: number): Uint8Array {
    const parts = Array.from({length:exp},(_,i)=>rcv.get(i)!.payload);
    const total = parts.reduce((s,p)=>s+p.length,0);
    const out = new Uint8Array(total); let off=0;
    for (const p of parts) { out.set(p,off); off+=p.length; }
    return out;
  }

  private _reassemblePartial(rcv: Map<number,Fragment>, exp: number): Uint8Array {
    const parts: Uint8Array[] = [];
    for (let i=0;i<exp;i++) { if(!rcv.has(i)) break; parts.push(rcv.get(i)!.payload); }
    const total = parts.reduce((s,p)=>s+p.length,0);
    const out = new Uint8Array(total); let off=0;
    for (const p of parts) { out.set(p,off); off+=p.length; }
    return out;
  }

  nack(msgId: number, expectedCt: number): string {
    const have = new Set(this._buf.get(msgId)?.keys()??[]);
    const missing = Array.from({length:expectedCt},(_,i)=>i).filter(i=>!have.has(i));
    return `A:NACK[MSG:${msgId}\u2216[${missing.join(",")}]]`;
  }
}
