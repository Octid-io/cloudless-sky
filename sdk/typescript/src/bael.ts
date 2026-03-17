/**
 * OSMP BAEL — Bandwidth-Agnostic Efficiency Layer
 * Patent: OSMP-001-UTIL (pending) | License: Apache 2.0
 */
import { BAELMode, BAELResult, FLAG_NL_PASSTHROUGH } from "./types.js";

export function utf8Bytes(s: string): number { return Buffer.byteLength(s,"utf8"); }

export class BAELEncoder {
  static selectMode(nlInput: string, osmpEncoded: string, tclEncoded?: string): BAELResult {
    const nl   = utf8Bytes(nlInput);
    const osmp = utf8Bytes(osmpEncoded);
    const tcl  = tclEncoded !== undefined ? utf8Bytes(tclEncoded) : osmp + 1;
    if (nl <= osmp && nl <= tcl)
      return { mode: BAELMode.NL_PASSTHROUGH, payload: nlInput, flagsByte: FLAG_NL_PASSTHROUGH };
    if (tclEncoded !== undefined && tcl < osmp)
      return { mode: BAELMode.TCL_ONLY, payload: tclEncoded, flagsByte: 0x00 };
    return { mode: BAELMode.FULL_OSMP, payload: osmpEncoded, flagsByte: 0x00 };
  }

  static compressionFloorCheck(nlInput: string, osmpEncoded: string) {
    const nl   = utf8Bytes(nlInput);
    const osmp = utf8Bytes(osmpEncoded);
    const r    = BAELEncoder.selectMode(nlInput, osmpEncoded);
    const sel  = utf8Bytes(r.payload);
    const red  = nl > 0 ? Math.round((1 - sel/nl)*1000)/10 : 0;
    return { nlBytes:nl, osmpBytes:osmp, selectedMode:BAELMode[r.mode],
             selectedBytes:sel, reductionPct:red,
             floorApplied: r.mode===BAELMode.NL_PASSTHROUGH, flags:r.flagsByte };
  }
}
