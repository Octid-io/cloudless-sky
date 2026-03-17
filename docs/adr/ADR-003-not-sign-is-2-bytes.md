# ADR-003: NOT SIGN ¬ (U+00AC) is 2 UTF-8 Bytes

## Context

Prior versions of CONTRIBUTING.md and earlier SDK implementations listed ¬ (U+00AC NOT SIGN) in the 3-byte glyph column. This is incorrect. U+00AC has a code point value of 172 decimal, which is in the range U+0080–U+07FF and therefore encodes as 2 UTF-8 bytes: 0xC2 0xAC.

The distinction matters for: packet budget calculations at LoRa floor (51 bytes), compression ratio measurements, and any implementation that counts bytes per glyph for encoding decisions.

## Decision

¬ is a 2-byte glyph. It is listed in the 2-byte column alongside § (U+00A7), τ (U+03C4), and Δ (U+0394). This is confirmed by `len("¬".encode("utf-8")) == 2` in Python and `Buffer.byteLength("¬","utf8") == 2` in Node.js.

The correction is applied in:
- `CONTRIBUTING.md` — byte count reference table updated
- `tests/tier1/test_python.py` — `test_two_byte_glyphs` includes ¬ and asserts 2 bytes
- `tests/tier1/test_typescript.mjs` — `2-byte glyphs — NOT SIGN is 2 bytes` asserts 2 bytes

## Consequences

Any prior implementation that budgeted 3 bytes per ¬ operator in packet size calculations was overly conservative by 1 byte per occurrence. Correcting this allows slightly more instruction content in a given LoRa packet than previously calculated.
