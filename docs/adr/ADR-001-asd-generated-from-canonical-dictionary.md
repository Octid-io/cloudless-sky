# ADR-001: ASD Basis Set Generated from Canonical Dictionary

## Context

The OSMP wire format is dictionary-decoded: a (namespace, opcode) tuple resolves to a definition through a shared lookup table called the ASD (Adaptive Shared Dictionary). For the protocol to round-trip correctly across SDKs, every implementation must hold byte-identical opcode tables. The risk to manage is *drift* — an opcode added or renamed in one SDK but not another silently breaks cross-SDK interop, and tests that validate the SDK against its own table will pass while round-trip fails on the wire.

## Decision

The canonical semantic dictionary CSV (`protocol/OSMP-semantic-dictionary-v15.csv`) is the single source of truth. Every SDK derives its ASD basis from this file. No SDK file defines opcodes independently. Adding a new opcode means adding a row to the CSV; the SDKs are derivations of that pin.

## Analog

Nix derivation pinning: a version-locked dependency graph resolved at build time. The dictionary is the pin. The SDKs are derivations. Derivations cannot diverge from the pin without regeneration.

## Consequences

**Easier:** Any opcode correction made in the dictionary flows to all SDKs by regeneration. ASD drift between SDKs is structurally impossible — they all source from the same pinned table.

**Required discipline:** New opcode additions must start in the dictionary, then propagate. Adding an opcode directly to an SDK file creates drift and will be overwritten on the next regeneration.

**Test enforcement:** The cross-SDK fingerprint test (a SHA-256 over the canonical-serialized dictionary, truncated to 16 hex characters) gates that all SDKs hold byte-identical tables. A drift between any SDK and the canonical CSV produces a fingerprint mismatch, which fails the test.
