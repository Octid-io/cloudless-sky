/**
 * D:PACK/BLK resolve — read-only access to DBLK v1 binaries.
 *
 * Resolves a single key from a block-compressed corpus by decompressing
 * only the containing block.  Uses fzstd (82KB, pure JS, zero native deps)
 * for zstd decompression.
 *
 * DBLK v1 format: see OSMP-SPEC-v1.0.2.md §10.4.1
 *
 * Dependency: fzstd (npm install fzstd)
 *   Dict-free DBLK binaries only.  fzstd does not support external
 *   trained dictionaries.  Binaries built with BlockCompressor(use_dict=False)
 *   in the Python SDK are fully compatible.  Dict-free binaries are 0.1-1.5%
 *   larger than dict variants; the tradeoff is zero native dependencies in
 *   the TypeScript SDK.
 */
export interface BlkStats {
    totalBytes: number;
    headerBytes: number;
    btableBytes: number;
    dictBytes: number;
    blockDataBytes: number;
    blockCount: number;
}
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
export declare function resolveBlk(data: Uint8Array, code: string): string | null;
/**
 * Return structural statistics for a DBLK binary.
 */
export declare function statsBlk(data: Uint8Array): BlkStats;
