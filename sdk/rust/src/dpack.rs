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
//! Cross-SDK: the Rust decoder reads both the raw-block variant
//! (flags bit 1 set) and the zstd-compressed variant produced by the
//! Python / Go / TypeScript SDKs (flags bit 1 clear). zstd decompression
//! uses the pure-Rust `ruzstd` crate, so the SDK has no C-toolchain build
//! dependency. Trained-dictionary corpora (flags bit 0 set, dict_size > 0)
//! are decoded by the other three SDKs only — the shipped MDR corpora
//! (ICD-10-CM, ISO 20022, MITRE ATT&CK) do not use trained dictionaries.
//! The Rust encoder writes the raw-block variant.
//!
//! License: Apache-2.0

const DBLK_MAGIC: u32 = 0x4442_4c4b; // "DBLK"
const DBLK_VERSION: u16 = 1;
const DBLK_HEADER_SIZE: usize = 24;
const DBLK_BTABLE_ENTRY_SIZE: usize = 44;
const DBLK_FIRST_CODE_SIZE: usize = 32;
const DBLK_DEFAULT_BLOCK_TARGET: usize = 32 * 1024;
const DBLK_FLAG_DICT: u16 = 0x0001;
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
    /// Returns an error if the magic is wrong, the binary uses a trained
    /// zstd dictionary (not yet supported by the Rust SDK), or zstd
    /// decompression fails.
    pub fn decode(&self, packed: &[u8]) -> Result<Vec<u8>, String> {
        let hdr = parse_header(packed)?;
        if hdr.flags & DBLK_FLAG_DICT != 0 {
            return Err(
                "DBLK uses trained dictionary; Rust SDK does not yet support this variant"
                    .to_string(),
            );
        }
        let mut out: Vec<u8> = Vec::new();
        for i in 0..hdr.block_count as usize {
            let block = read_block(packed, &hdr, i)?;
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
        if hdr.flags & DBLK_FLAG_DICT != 0 {
            return None;
        }
        let block_idx = find_block(packed, &hdr, key);
        let block = read_block(packed, &hdr, block_idx).ok()?;
        if let Some(v) = scan_block(&block, key) {
            return Some(v);
        }
        // Truncation fallback: if the 32-byte first_code overshot during the
        // binary search (key longer than 32 bytes whose suffix sorts low),
        // check the previous block.
        if block_idx > 0 {
            let prev = read_block(packed, &hdr, block_idx - 1).ok()?;
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

/// Read the raw on-disk bytes for a block (whether those bytes are an
/// uncompressed corpus payload or a zstd-compressed payload depends on
/// `hdr.flags`). Use `read_block` to get the decompressed corpus bytes.
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

/// Read a block and return its decompressed corpus payload bytes. Routes to
/// `read_raw_block` when `flags & DBLK_FLAG_RAW != 0`, otherwise decompresses
/// the block via the pure-Rust `ruzstd` decoder.
fn read_block(data: &[u8], hdr: &DblkHeader, block_idx: usize) -> Result<Vec<u8>, String> {
    let bytes = read_raw_block(data, hdr, block_idx)?;
    if hdr.flags & DBLK_FLAG_RAW != 0 {
        Ok(bytes)
    } else {
        decompress_zstd(&bytes)
    }
}

fn decompress_zstd(compressed: &[u8]) -> Result<Vec<u8>, String> {
    use std::io::{Cursor, Read};
    let cursor = Cursor::new(compressed);
    let mut decoder = ruzstd::StreamingDecoder::new(cursor)
        .map_err(|e| format!("zstd decoder init: {e}"))?;
    let mut out: Vec<u8> = Vec::new();
    decoder
        .read_to_end(&mut out)
        .map_err(|e| format!("zstd decode: {e}"))?;
    Ok(out)
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
    fn decode_shipped_mitre_attack_corpus() {
        // The shipped MDR corpus is zstd-compressed (flags = 0x0000). This
        // test exercises the ruzstd decompression path end-to-end on a real
        // wire artifact.
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../mdr/mitre-attack/MDR-MITRE-ATTACK-ENT-v18.1-blk.dpack");
        let bytes = match std::fs::read(&path) {
            Ok(b) => b,
            Err(_) => return, // skip when running against a partial workspace
        };
        let dec = DPackDecoder::new();
        let corpus = dec.decode(&bytes).expect("decode shipped MITRE corpus");
        assert!(corpus.len() > 1000, "decoded corpus should be substantial");
        let text = std::str::from_utf8(&corpus).expect("corpus is UTF-8");
        assert!(
            text.contains('\t'),
            "corpus should have tab-separated key/value entries",
        );
    }

    #[test]
    fn lookup_against_shipped_mitre_corpus() {
        // Round-trip a single-key lookup against the shipped compressed
        // corpus. Verifies the zstd path through `read_block` plus the
        // binary-search lookup path together.
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../mdr/mitre-attack/MDR-MITRE-ATTACK-ENT-v18.1-blk.dpack");
        let bytes = match std::fs::read(&path) {
            Ok(b) => b,
            Err(_) => return,
        };
        let dec = DPackDecoder::new();
        let corpus = dec.decode(&bytes).expect("decode shipped MITRE corpus");
        let text = std::str::from_utf8(&corpus).expect("UTF-8");
        // Find the first real key in the corpus and verify lookup returns
        // the same value as we'd extract from the bulk decode.
        let first_line = text.lines().next().expect("at least one entry");
        let (key, value) = first_line
            .split_once('\t')
            .expect("first line has tab separator");
        assert_eq!(
            dec.lookup(&bytes, key),
            Some(value.to_string()),
            "lookup() and decode() must agree on the first key",
        );
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
    fn decode_rejects_trained_dictionary_binary() {
        // Hand-craft a tiny DBLK with the trained-dict flag set — Rust SDK
        // does not yet support trained-dictionary decompression and must
        // reject rather than silently produce wrong output.
        let mut buf: Vec<u8> = Vec::new();
        buf.extend_from_slice(&DBLK_MAGIC.to_be_bytes());
        buf.extend_from_slice(&DBLK_VERSION.to_be_bytes());
        buf.extend_from_slice(&DBLK_FLAG_DICT.to_be_bytes()); // flags = 0x0001 (trained dict)
        buf.extend_from_slice(&0u32.to_be_bytes()); // block_count
        buf.extend_from_slice(&(DBLK_HEADER_SIZE as u32).to_be_bytes());
        buf.extend_from_slice(&0u32.to_be_bytes()); // dict_size
        buf.extend_from_slice(&(DBLK_HEADER_SIZE as u32).to_be_bytes()); // blocks_offset
        let dec = DPackDecoder::new();
        assert!(dec.decode(&buf).is_err());
    }
}
