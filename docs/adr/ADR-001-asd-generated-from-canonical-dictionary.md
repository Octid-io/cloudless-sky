# ADR-001: ASD Basis Set Generated from Canonical Dictionary

## Context

The first build of this repo used `osmp.py` as the source of truth for the ASD basis set and propagated it to TypeScript and Go SDKs. `osmp.py` had drifted from the canonical semantic dictionary v12 — wrong opcode names (`Z:INFER` instead of `Z:INF`, `V:HDNG` instead of `V:HDG`, `V:ROUT` instead of `V:ROUTE`) and 20 missing opcodes including `D:PACK`, `D:UNPACK`, the H Layer 2 accessors, and several T, U, C, S, Y, Z, Q, L, N opcodes. The test suite validated the code against itself, not against the IP.

## Decision

The canonical semantic dictionary v12 (`protocol/OSMP-semantic-dictionary-v12.csv`) is the single source of truth. `sdk/python/osmp/protocol.py` is built from the dictionary. `sdk/typescript/src/glyphs.ts` is generated from the Python `ASD_BASIS`. `sdk/go/osmp/glyphs.go` is generated from the Python `ASD_BASIS`. No SDK file defines opcodes independently.

The generation command is: `python3 tools/gen_asd.py` (produces `glyphs.ts` and `glyphs.go` from the Python `ASD_BASIS`, which was itself written from the dictionary).

> **Layout note (post-migration):** This ADR was authored when the Python SDK was a single flat file at `sdk/python/src/osmp.py`. The package was subsequently reorganized to `sdk/python/osmp/` with `protocol.py`, `wire.py`, `bridge.py`, etc. The normative source-of-truth relationship is unchanged: the dictionary CSV is the pin, the SDKs are derivations.

## Analog

Nix derivation pinning: a version-locked dependency graph resolved at build time. The dictionary is the pin. The SDKs are derivations. Derivations cannot diverge from the pin without regeneration.

## Consequences

**Easier:** Any opcode correction made in the dictionary flows to all three SDKs by regenerating the glyphs files. ASD drift between SDKs is structurally impossible — they all source from the same generated table.

**Required discipline:** New opcode additions must start in the dictionary, then propagate. Adding an opcode directly to an SDK file creates drift and will be overwritten on the next generation run.

**Test enforcement:** The test suite includes negative assertions — `Z:INFER`, `V:HDNG`, `V:ROUT` are explicitly tested to return null — confirming the wrong names from the prior build cannot silently re-enter.
