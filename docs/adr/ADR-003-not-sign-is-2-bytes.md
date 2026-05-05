# ADR-003: NOT SIGN ¬ (U+00AC) is 2 UTF-8 Bytes

## Context

¬ (U+00AC NOT SIGN) is one of the OSMP grammar terminals. Its UTF-8 byte count matters for: packet budget calculations at the LoRa floor (51 bytes), compression ratio measurements, and any implementation that counts bytes per glyph for encoding decisions.

Earlier documentation listed ¬ in the 3-byte glyph column. This was incorrect. U+00AC has a code point value of 172 decimal, which is in the range U+0080–U+07FF and therefore encodes as 2 UTF-8 bytes: `0xC2 0xAC`.

## Decision

¬ is a 2-byte glyph. It is grouped with the other 2-byte protocol grammar terminals: § (U+00A7), τ (U+03C4), Δ (U+0394).

This is verifiable in any UTF-8 implementation:

```python
len("¬".encode("utf-8")) == 2
```

```javascript
Buffer.byteLength("¬", "utf8") === 2
```

```go
len([]byte("¬")) == 2
```

```rust
"¬".len() == 2
```

## Consequences

Any prior implementation that budgeted 3 bytes per ¬ in packet size calculations was overly conservative by 1 byte per occurrence. The corrected accounting allows slightly more instruction content in a given LoRa packet than previously calculated. The contributor takeaway: when computing on-wire byte counts for protocol grammar terminals, derive byte length from UTF-8 encoding semantics, not from a hardcoded glyph-byte table.
