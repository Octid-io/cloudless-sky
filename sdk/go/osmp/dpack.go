// Package osmp provides the OSMP protocol implementation.
//
// This file implements D:PACK/BLK resolve: read-only access to DBLK v1
// binaries.  Resolves a single key by decompressing only the containing
// block.
//
// Dependency: github.com/klauspost/compress/zstd (decoder only).
// The compiled binary includes only the decoder path.  The full module
// source is large but Go compiles only imported packages.
//
// Supports both dict-free and dict-compressed DBLK binaries.
// Dict-free binaries (flags bit 0 = 0) require no dictionary setup.
// Dict binaries (flags bit 0 = 1) load the trained dictionary from
// the binary header.
//
// DBLK v1 format: see OSMP-SPEC-v1.0.2.md section 10.4.1
package osmp

import (
	"bytes"
	"encoding/binary"
	"errors"
	"strings"

	"github.com/klauspost/compress/zstd"
)

// DBLK format constants
const (
	dblkMagic          = 0x44424c4b // "DBLK"
	dblkHeaderSize     = 24
	dblkFirstCodeSize  = 32
	dblkBtableEntrySize = 44
	maxDecompressSize  = 40960 // 32KB target + 8KB headroom
)

// DblkStats holds structural statistics for a DBLK binary.
type DblkStats struct {
	TotalBytes     int
	HeaderBytes    int
	BtableBytes    int
	DictBytes      int
	BlockDataBytes int
	BlockCount     int
}

type dblkHeader struct {
	version      uint16
	flags        uint16
	blockCount   uint32
	dictOffset   uint32
	dictSize     uint32
	blocksOffset uint32
}

func parseDblkHeader(data []byte) (dblkHeader, error) {
	if len(data) < dblkHeaderSize {
		return dblkHeader{}, errors.New("data too short for DBLK header")
	}
	magic := binary.BigEndian.Uint32(data[0:4])
	if magic != dblkMagic {
		return dblkHeader{}, errors.New("not a DBLK binary (bad magic)")
	}
	return dblkHeader{
		version:      binary.BigEndian.Uint16(data[4:6]),
		flags:        binary.BigEndian.Uint16(data[6:8]),
		blockCount:   binary.BigEndian.Uint32(data[8:12]),
		dictOffset:   binary.BigEndian.Uint32(data[12:16]),
		dictSize:     binary.BigEndian.Uint32(data[16:20]),
		blocksOffset: binary.BigEndian.Uint32(data[20:24]),
	}, nil
}

func findDblkBlock(data []byte, hdr dblkHeader, code string) int {
	codeBytes := []byte(code)
	lo, hi, result := 0, int(hdr.blockCount)-1, 0
	for lo <= hi {
		mid := (lo + hi) / 2
		off := dblkHeaderSize + mid*dblkBtableEntrySize

		// extract first_code, strip null padding
		fc := data[off : off+dblkFirstCodeSize]
		fcLen := dblkFirstCodeSize
		for fcLen > 0 && fc[fcLen-1] == 0 {
			fcLen--
		}
		fc = fc[:fcLen]

		if bytes.Compare(fc, codeBytes) <= 0 {
			result = mid
			lo = mid + 1
		} else {
			hi = mid - 1
		}
	}
	return result
}

func decompressDblkBlock(data []byte, hdr dblkHeader, blockIdx int, decoder *zstd.Decoder) ([]byte, error) {
	entryOff := dblkHeaderSize + blockIdx*dblkBtableEntrySize
	blkOffset := binary.BigEndian.Uint32(data[entryOff+dblkFirstCodeSize : entryOff+dblkFirstCodeSize+4])
	blkCsize := binary.BigEndian.Uint32(data[entryOff+dblkFirstCodeSize+4 : entryOff+dblkFirstCodeSize+8])

	start := int(hdr.blocksOffset) + int(blkOffset)
	compressed := data[start : start+int(blkCsize)]

	buf := make([]byte, 0, maxDecompressSize)
	return decoder.DecodeAll(compressed, buf)
}

func searchDblkBlock(decompressed []byte, code string) (string, bool) {
	text := string(decompressed)
	for _, line := range strings.Split(text, "\n") {
		idx := strings.Index(line, "\t")
		if idx > 0 && line[:idx] == code {
			return line[idx+1:], true
		}
	}
	return "", false
}

// ResolveBlk resolves a single key from a DBLK binary.
//
// Decompresses only the block containing the target key.
// When the 32-byte first_code truncation causes the binary search
// to overshoot, the previous block is checked as a fallback.
//
// Returns the SAL description text and nil error, or empty string
// and nil if the key is not found.  Returns an error only for
// structural problems (bad magic, decompression failure).
func ResolveBlk(data []byte, code string) (string, error) {
	hdr, err := parseDblkHeader(data)
	if err != nil {
		return "", err
	}

	// Build decoder with or without dictionary
	var opts []zstd.DOption
	if hdr.flags&1 != 0 && hdr.dictSize > 0 {
		dictBytes := data[hdr.dictOffset : hdr.dictOffset+hdr.dictSize]
		opts = append(opts, zstd.WithDecoderDicts(dictBytes))
	}
	decoder, err := zstd.NewReader(nil, opts...)
	if err != nil {
		return "", err
	}
	defer decoder.Close()

	blkIdx := findDblkBlock(data, hdr, code)

	raw, err := decompressDblkBlock(data, hdr, blkIdx, decoder)
	if err != nil {
		return "", err
	}
	if result, ok := searchDblkBlock(raw, code); ok {
		return result, nil
	}

	// Truncation fallback: try previous block
	if blkIdx > 0 {
		raw, err = decompressDblkBlock(data, hdr, blkIdx-1, decoder)
		if err != nil {
			return "", err
		}
		if result, ok := searchDblkBlock(raw, code); ok {
			return result, nil
		}
	}

	return "", nil
}

// BlkStats returns structural statistics for a DBLK binary.
func BlkStats(data []byte) (*DblkStats, error) {
	hdr, err := parseDblkHeader(data)
	if err != nil {
		return nil, err
	}
	btable := int(hdr.blockCount) * dblkBtableEntrySize
	return &DblkStats{
		TotalBytes:     len(data),
		HeaderBytes:    dblkHeaderSize,
		BtableBytes:    btable,
		DictBytes:      int(hdr.dictSize),
		BlockDataBytes: len(data) - int(hdr.blocksOffset),
		BlockCount:     int(hdr.blockCount),
	}, nil
}
