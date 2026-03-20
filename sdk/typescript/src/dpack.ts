/**
 * D:PACK/BLK resolve — read-only access to DBLK v1 binaries.
 *
 * Resolves a single key from a block-compressed corpus by decompressing
 * only the containing block.  Uses fzstd (82KB, pure JS, zero native deps)
 * for zstd decompression.
 *
 * DBLK v1 format: see OSMP-SPEC-v1.md §10.4.1
 *
 * Dependency: fzstd (npm install fzstd)
 *   Dict-free DBLK binaries only.  fzstd does not support external
 *   trained dictionaries.  Binaries built with BlockCompressor(use_dict=False)
 *   in the Python SDK are fully compatible.  Dict-free binaries are 0.1-1.5%
 *   larger than dict variants; the tradeoff is zero native dependencies in
 *   the TypeScript SDK.
 */

import { decompress } from "fzstd";

// ── constants ───────────────────────────────────────────────────────

const DBLK_MAGIC = 0x44424c4b; // "DBLK"
const DBLK_HEADER_SIZE = 24;
const DBLK_FIRST_CODE_SIZE = 32;
const DBLK_BTABLE_ENTRY_SIZE = 44; // 32 + 4 + 4 + 2 + 2
const MAX_DECOMPRESS_SIZE = 40960; // 32KB target + 8KB headroom

// ── types ───────────────────────────────────────────────────────────

export interface BlkStats {
  totalBytes: number;
  headerBytes: number;
  btableBytes: number;
  dictBytes: number;
  blockDataBytes: number;
  blockCount: number;
}

// ── header parsing ──────────────────────────────────────────────────

interface DblkHeader {
  version: number;
  flags: number;
  blockCount: number;
  dictOffset: number;
  dictSize: number;
  blocksOffset: number;
}

function parseHeader(data: Uint8Array): DblkHeader {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const magic = view.getUint32(0);
  if (magic !== DBLK_MAGIC) {
    throw new Error(`Not a DBLK binary (magic: 0x${magic.toString(16)})`);
  }
  return {
    version: view.getUint16(4),
    flags: view.getUint16(6),
    blockCount: view.getUint32(8),
    dictOffset: view.getUint32(12),
    dictSize: view.getUint32(16),
    blocksOffset: view.getUint32(20),
  };
}

// ── block table binary search ───────────────────────────────────────

function compareBytes(a: Uint8Array, b: Uint8Array): number {
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

function findBlock(data: Uint8Array, hdr: DblkHeader, code: string): number {
  const codeBytes = new TextEncoder().encode(code);
  let lo = 0;
  let hi = hdr.blockCount - 1;
  let result = 0;

  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    const off = DBLK_HEADER_SIZE + mid * DBLK_BTABLE_ENTRY_SIZE;

    // extract first_code, strip null padding
    let fcLen = DBLK_FIRST_CODE_SIZE;
    while (fcLen > 0 && data[off + fcLen - 1] === 0) fcLen--;
    const fc = data.subarray(off, off + fcLen);

    if (compareBytes(fc, codeBytes) <= 0) {
      result = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return result;
}

// ── block decompression + search ────────────────────────────────────

function decompressBlock(
  data: Uint8Array,
  hdr: DblkHeader,
  blockIdx: number
): Uint8Array {
  const entryOff = DBLK_HEADER_SIZE + blockIdx * DBLK_BTABLE_ENTRY_SIZE;
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const blkOffset = view.getUint32(entryOff + DBLK_FIRST_CODE_SIZE);
  const blkCsize = view.getUint32(entryOff + DBLK_FIRST_CODE_SIZE + 4);

  const start = hdr.blocksOffset + blkOffset;
  const compressed = data.subarray(start, start + blkCsize);

  return decompress(compressed);
}

function searchBlock(decompressed: Uint8Array, code: string): string | null {
  const text = new TextDecoder().decode(decompressed);
  const lines = text.split("\n");
  for (const line of lines) {
    const tab = line.indexOf("\t");
    if (tab > 0 && line.slice(0, tab) === code) {
      return line.slice(tab + 1);
    }
  }
  return null;
}

// ── public API ──────────────────────────────────────────────────────

/**
 * Resolve a single key from a DBLK binary.
 *
 * Decompresses only the block containing the target key.
 * When the 32-byte first_code truncation causes the binary search
 * to overshoot, the previous block is checked as a fallback.
 *
 * @param data  Complete DBLK binary as Uint8Array
 * @param code  Key to look up (MDR token or type name)
 * @returns     SAL description text, or null if not found
 */
export function resolveBlk(data: Uint8Array, code: string): string | null {
  const hdr = parseHeader(data);

  if (hdr.flags & 1 && hdr.dictSize > 0) {
    throw new Error(
      "This DBLK binary uses a trained dictionary. " +
        "The TypeScript SDK requires dict-free binaries " +
        "(built with BlockCompressor(use_dict=False) in Python)."
    );
  }

  const blkIdx = findBlock(data, hdr, code);

  const raw = decompressBlock(data, hdr, blkIdx);
  const result = searchBlock(raw, code);
  if (result !== null) return result;

  // Truncation fallback: try previous block
  if (blkIdx > 0) {
    const prev = decompressBlock(data, hdr, blkIdx - 1);
    return searchBlock(prev, code);
  }

  return null;
}

/**
 * Return structural statistics for a DBLK binary.
 */
export function statsBlk(data: Uint8Array): BlkStats {
  const hdr = parseHeader(data);
  const btableBytes = hdr.blockCount * DBLK_BTABLE_ENTRY_SIZE;
  return {
    totalBytes: data.length,
    headerBytes: DBLK_HEADER_SIZE,
    btableBytes,
    dictBytes: hdr.dictSize,
    blockDataBytes: data.length - hdr.blocksOffset,
    blockCount: hdr.blockCount,
  };
}
