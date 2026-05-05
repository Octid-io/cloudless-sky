//! D:PACK — two-tier corpus encoding for at-rest storage.
//!
//! Encodes a corpus of `(key, value)` entries as a DBLK-shaped binary with a
//! header, a sorted block index, and per-block raw payloads. The lookup path
//! does inference-free retrieval: binary-search the block index, scan a
//! single block, return the value. The full corpus never needs to be
//! decoded for a single key.
//!
//! Wire layout (DBLK v1, big-endian):
//!   Header (24 bytes):
//!     magic         4B   "DBLK"
//!     version       u16  currently 1
//!     flags         u16  bit 0 = trained dictionary present
//!                        bit 1 = blocks are raw (uncompressed) — Rust default
//!     block_count   u32
//!     dict_offset   u32  byte offset from file start
//!     dict_size     u32  zero when no dict
//!     blocks_offset u32  byte offset to first block payload
//!   Block table (block_count × 44 bytes):
//!     first_code    32B  null-padded UTF-8, first key in block
//!     block_offset  u32  relative to blocks_offset
//!     block_size    u32  raw size in bytes
//!     entry_count   u16
//!     reserved      2B   zero
//!   Block payloads (concatenated):
//!     each block is sorted "key\tvalue\n" lines, raw bytes when bit 1 of
//!     flags is set.
//!
//! Cross-SDK: the Go and TypeScript SDKs read the dictionary-compressed
//! variant of this same binary layout (flags bit 0 set, blocks zstd
//! compressed). The Rust encode/decode here uses bit 1 (raw blocks) so the
//! SDK does not pull in a zstd dependency while still honoring the layout
//! and the inference-free lookup contract.
//!
//! License: Apache-2.0

const DBLK_MAGIC: u32 = 0x4442_4c4b; // "DBLK"
const DBLK_VERSION: u16 = 1;
const DBLK_HEADER_SIZE: usize = 24;
const DBLK_BTABLE_ENTRY_SIZE: usize = 44;
const DBLK_FIRST_CODE_SIZE: usize = 32;
const DBLK_DEFAULT_BLOCK_TARGET: usize = 32 * 1024;
const DBLK_FLAG_RAW: u16 = 0x0002;

/// D:PACK binary writer.
///
/// `block_target` is the target uncompressed block size in bytes (default
/// 32 KiB). Blocks are written raw (uncompressed) so the SDK has no zstd
/// dependency.
#[derive(Debug, Clone)]
pub struct DPackEncoder {
    /// Target raw bytes per block before a block break.
    pub block_target: usize,
}

impl Default for DPackEncoder {
    fn default() -> Self {
        DPackEncoder {
            block_target: DBLK_DEFAULT_BLOCK_TARGET,
        }
    }
}

impl DPackEncoder {
    /// Construct an encoder with the default 32 KiB block target.
    pub fn new() -> Self {
        DPackEncoder::default()
    }

    /// Construct with a custom block target.
    pub fn with_block_target(block_target: usize) -> Self {
        DPackEncoder { block_target }
    }

    /// Encode a raw corpus into a D:PACK binary.
    ///
    /// `corpus` is parsed as UTF-8 lines of `key\tvalue`. Empty lines and
    /// any line missing a tab are skipped. The resulting binary preserves
    /// the input row order — callers that need binary-search lookup must
    /// pre-sort the input by key.
    pub fn encode(&self, corpus: &[u8]) -> Vec<u8> {
        let entries = parse_corpus(corpus);
        self.encode_entries(&entries)
    }

    /// Encode a list of `(key, value)` entries directly. Entries should be
    /// sorted by `key` for the lookup path to function correctly.
    pub fn encode_entries(&self, entries: &[(String, String)]) -> Vec<u8> {
        // Partition into blocks by cumulative raw size.
        let mut blocks: Vec<Vec<&(String, String)>> = Vec::new();
        let mut current: Vec<&(String, String)> = Vec::new();
        let mut current_size: usize = 0;
        for e in entries {
            let entry_bytes = e.1.len();
            if current_size + entry_bytes > self.block_target && !current.is_empty() {
                blocks.push(std::mem::take(&mut current));
                current_size = 0;
            }
            current.push(e);
            current_size += entry_bytes;
        }
        if !current.is_empty() {
            blocks.push(current);
        }

        // Build raw block payloads.
        let mut raw_payloads: Vec<Vec<u8>> = Vec::with_capacity(blocks.len());
        for block in &blocks {
            let lines: Vec<String> = block
                .iter()
                .map(|(k, v)| format!("{k}\t{v}"))
                .collect();
            raw_payloads.push(lines.join("\n").into_bytes());
        }

        let block_count = blocks.len() as u32;
        let btable_size = block_count as usize * DBLK_BTABLE_ENTRY_SIZE;
        let dict_offset = (DBLK_HEADER_SIZE + btable_size) as u32;
        let dict_size: u32 = 0;
        let blocks_offset = dict_offset + dict_size;
        let flags: u16 = DBLK_FLAG_RAW;

        let mut out: Vec<u8> = Vec::new();

        // Header.
        out.extend_from_slice(&DBLK_MAGIC.to_be_bytes());
        out.extend_from_slice(&DBLK_VERSION.to_be_bytes());
        out.extend_from_slice(&flags.to_be_bytes());
        out.extend_from_slice(&block_count.to_be_bytes());
        out.extend_from_slice(&dict_offset.to_be_bytes());
        out.extend_from_slice(&dict_size.to_be_bytes());
        out.extend_from_slice(&blocks_offset.to_be_bytes());

        // Block table.
        let mut blk_offset: u32 = 0;
        for (i, block) in blocks.iter().enumerate() {
            let first_key = block[0].0.as_bytes();
            let mut fc = [0u8; DBLK_FIRST_CODE_SIZE];
            let n = std::cmp::min(first_key.len(), DBLK_FIRST_CODE_SIZE);
            fc[..n].copy_from_slice(&first_key[..n]);
            out.extend_from_slice(&fc);
            out.extend_from_slice(&blk_offset.to_be_bytes());
            let csize = raw_payloads[i].len() as u32;
            out.extend_from_slice(&csize.to_be_bytes());
            let entry_count = block.len() as u16;
            out.extend_from_slice(&entry_count.to_be_bytes());
            out.extend_from_slice(&[0u8, 0u8]); // reserved
            blk_offset += csize;
        }

        // Block payloads.
        for raw in raw_payloads {
            out.extend_from_slice(&raw);
        }

        out
    }
}

/// D:PACK binary reader.
///
/// Reads the raw-block variant produced by `DPackEncoder`. Use the same
/// instance for `decode` (full corpus reconstruction) and `lookup` (single
/// key resolution without scanning the whole corpus).
#[derive(Debug, Default, Clone)]
pub struct DPackDecoder;

impl DPackDecoder {
    /// Construct a decoder.
    pub fn new() -> Self {
        DPackDecoder
    }

    /// Decode a D:PACK binary back to its `key\tvalue\n` corpus.
    ///
    /// Returns an error if the magic is wrong or the binary uses zstd
    /// blocks that the Rust SDK does not yet decompress.
    pub fn decode(&self, packed: &[u8]) -> Result<Vec<u8>, String> {
        let hdr = parse_header(packed)?;
        if hdr.flags & DBLK_FLAG_RAW == 0 {
            return Err(
                "DBLK binary is not raw-block; Rust SDK requires the raw-block flag bit"
                    .to_string(),
            );
        }
        let mut out: Vec<u8> = Vec::new();
        for i in 0..hdr.block_count as usize {
            let block = read_raw_block(packed, &hdr, i)?;
            if !out.is_empty() {
                out.push(b'\n');
            }
            out.extend_from_slice(&block);
        }
        Ok(out)
    }

    /// Look up a single key without decoding the entire binary.
    ///
    /// Performs a binary search on the block index, then a single-block
    /// linear scan. Returns `Some(value)` when found, `None` when the key
    /// is not present (or when the binary is malformed in a recoverable
    /// way — see error path on decode).
    pub fn lookup(&self, packed: &[u8], key: &str) -> Option<String> {
        let hdr = parse_header(packed).ok()?;
        if hdr.flags & DBLK_FLAG_RAW == 0 {
            return None;
        }
        let block_idx = find_block(packed, &hdr, key);
        let block = read_raw_block(packed, &hdr, block_idx).ok()?;
        if let Some(v) = scan_block(&block, key) {
            return Some(v);
        }
        // Truncation fallback: if the 32-byte first_code overshot during the
        // binary search (key longer than 32 bytes whose suffix sorts low),
        // check the previous block.
        if block_idx > 0 {
            let prev = read_raw_block(packed, &hdr, block_idx - 1).ok()?;
            if let Some(v) = scan_block(&prev, key) {
                return Some(v);
            }
        }
        None
    }
}

#[derive(Debug, Clone, Copy)]
struct DblkHeader {
    flags: u16,
    block_count: u32,
    blocks_offset: u32,
}

fn parse_header(data: &[u8]) -> Result<DblkHeader, String> {
    if data.len() < DBLK_HEADER_SIZE {
        return Err(format!(
            "DBLK binary too short: {} bytes (need >= {})",
            data.len(),
            DBLK_HEADER_SIZE
        ));
    }
    let magic = u32::from_be_bytes([data[0], data[1], data[2], data[3]]);
    if magic != DBLK_MAGIC {
        return Err(format!("not a DBLK binary (magic 0x{:08x})", magic));
    }
    Ok(DblkHeader {
        flags: u16::from_be_bytes([data[6], data[7]]),
        block_count: u32::from_be_bytes([data[8], data[9], data[10], data[11]]),
        blocks_offset: u32::from_be_bytes([data[20], data[21], data[22], data[23]]),
    })
}

fn parse_corpus(corpus: &[u8]) -> Vec<(String, String)> {
    let text = match std::str::from_utf8(corpus) {
        Ok(s) => s,
        Err(_) => return Vec::new(),
    };
    let mut entries: Vec<(String, String)> = Vec::new();
    for line in text.split('\n') {
        if line.is_empty() {
            continue;
        }
        if let Some(tab) = line.find('\t') {
            let k = line[..tab].to_string();
            let v = line[tab + 1..].to_string();
            entries.push((k, v));
        }
    }
    entries
}

fn read_raw_block(data: &[u8], hdr: &DblkHeader, block_idx: usize) -> Result<Vec<u8>, String> {
    let entry_off = DBLK_HEADER_SIZE + block_idx * DBLK_BTABLE_ENTRY_SIZE;
    if entry_off + DBLK_BTABLE_ENTRY_SIZE > data.len() {
        return Err("block table entry out of range".to_string());
    }
    let off_field = entry_off + DBLK_FIRST_CODE_SIZE;
    let blk_offset =
        u32::from_be_bytes([data[off_field], data[off_field + 1], data[off_field + 2], data[off_field + 3]]);
    let blk_size = u32::from_be_bytes([
        data[off_field + 4],
        data[off_field + 5],
        data[off_field + 6],
        data[off_field + 7],
    ]);
    let start = hdr.blocks_offset as usize + blk_offset as usize;
    let end = start + blk_size as usize;
    if end > data.len() {
        return Err("block payload out of range".to_string());
    }
    Ok(data[start..end].to_vec())
}

fn find_block(data: &[u8], hdr: &DblkHeader, key: &str) -> usize {
    let key_bytes = key.as_bytes();
    let mut lo: i64 = 0;
    let mut hi: i64 = hdr.block_count as i64 - 1;
    let mut result: usize = 0;
    while lo <= hi {
        let mid = ((lo + hi) / 2) as usize;
        let off = DBLK_HEADER_SIZE + mid * DBLK_BTABLE_ENTRY_SIZE;
        let mut fc_len = DBLK_FIRST_CODE_SIZE;
        while fc_len > 0 && data[off + fc_len - 1] == 0 {
            fc_len -= 1;
        }
        let fc = &data[off..off + fc_len];
        if fc <= key_bytes {
            result = mid;
            lo = mid as i64 + 1;
        } else {
            hi = mid as i64 - 1;
        }
    }
    result
}

fn scan_block(block: &[u8], key: &str) -> Option<String> {
    let text = std::str::from_utf8(block).ok()?;
    for line in text.split('\n') {
        if let Some(tab) = line.find('\t') {
            if &line[..tab] == key {
                return Some(line[tab + 1..].to_string());
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_corpus() -> &'static [u8] {
        b"H:HR\theart_rate\nH:ICD\tICD-10_diagnosis_code_accessor\nH:TEMP\tbody_temperature"
    }

    #[test]
    fn encode_decode_roundtrip() {
        let enc = DPackEncoder::new();
        let dec = DPackDecoder::new();
        let packed = enc.encode(sample_corpus());
        // Magic check.
        assert_eq!(&packed[0..4], b"DBLK");
        let raw = dec.decode(&packed).expect("decode");
        assert_eq!(raw, sample_corpus().to_vec());
    }

    #[test]
    fn lookup_finds_existing_key() {
        let enc = DPackEncoder::new();
        let dec = DPackDecoder::new();
        let packed = enc.encode(sample_corpus());
        assert_eq!(dec.lookup(&packed, "H:HR"), Some("heart_rate".to_string()));
        assert_eq!(
            dec.lookup(&packed, "H:TEMP"),
            Some("body_temperature".to_string()),
        );
    }

    #[test]
    fn lookup_returns_none_for_missing_key() {
        let enc = DPackEncoder::new();
        let dec = DPackDecoder::new();
        let packed = enc.encode(sample_corpus());
        assert_eq!(dec.lookup(&packed, "H:DOES_NOT_EXIST"), None);
    }

    #[test]
    fn lookup_across_multiple_blocks() {
        // Force several blocks via small block_target.
        let enc = DPackEncoder::with_block_target(20);
        let dec = DPackDecoder::new();
        let packed = enc.encode(sample_corpus());
        let hdr = parse_header(&packed).unwrap();
        assert!(hdr.block_count > 1, "expected multiple blocks");
        assert_eq!(dec.lookup(&packed, "H:HR"), Some("heart_rate".to_string()));
        assert_eq!(
            dec.lookup(&packed, "H:ICD"),
            Some("ICD-10_diagnosis_code_accessor".to_string()),
        );
        assert_eq!(
            dec.lookup(&packed, "H:TEMP"),
            Some("body_temperature".to_string()),
        );
    }

    #[test]
    fn decode_rejects_non_raw_binary() {
        // Hand-craft a tiny DBLK with flags=0 (no raw bit) — decode should reject.
        let mut buf: Vec<u8> = Vec::new();
        buf.extend_from_slice(&DBLK_MAGIC.to_be_bytes());
        buf.extend_from_slice(&DBLK_VERSION.to_be_bytes());
        buf.extend_from_slice(&0u16.to_be_bytes()); // flags = 0
        buf.extend_from_slice(&0u32.to_be_bytes()); // block_count
        buf.extend_from_slice(&(DBLK_HEADER_SIZE as u32).to_be_bytes());
        buf.extend_from_slice(&0u32.to_be_bytes()); // dict_size
        buf.extend_from_slice(&(DBLK_HEADER_SIZE as u32).to_be_bytes()); // blocks_offset
        let dec = DPackDecoder::new();
        assert!(dec.decode(&buf).is_err());
    }
}
