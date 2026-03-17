# ADR-002: Go ASD Basis Set as Compiled-In var Map Literal

## Context

The Go SDK targets PicoClaw and constrained hardware where a binary must operate correctly after boot, after extended off-grid operation, and after filesystem unavailability. The ASD floor version must be present regardless of external state.

## Decision

`ASDFloorBasis` in `sdk/go/osmp/glyphs.go` is a `var` initialized from a map literal compiled into the binary. No file I/O. No network access. No runtime dictionary load. `NewASD()` deep-copies it into the live dictionary at construction time.

## Analog

Nix derivation pinning: the floor version is compiled in and does not depend on filesystem state, network state, or synchronization state. Every glyph in the floor version resolves correctly at any node at any time.

## Consequences

**Easier:** Binary deployment. No data files. No installer. The conformance guarantee of the floor version is structural — it cannot be violated by external state.

**Note on Go var vs const:** Go does not support map literals as `const`. The `var` declaration with a map literal is the idiomatic equivalent. The value is initialized once from the binary's data segment at program start.
