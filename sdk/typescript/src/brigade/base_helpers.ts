/**
 * Brigade base helpers — opcode-existence check via active ASD.
 *
 * Faithful TS port of sdk/python/osmp/brigade/base_helpers.py.
 */

import { ASD_BASIS } from "../glyphs.js";

export function opcodeExists(namespace: string, opcode: string): boolean {
  return Boolean(ASD_BASIS[namespace] && opcode in ASD_BASIS[namespace]);
}

export function allOpcodes(namespace: string): string[] {
  return Object.keys(ASD_BASIS[namespace] || {});
}
