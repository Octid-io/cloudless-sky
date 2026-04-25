# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/).

---

## [v2.3.4] — 2026-04-24

Cross-SDK parity restoration. The TypeScript and Go composers had been frozen at the April 16 snapshot — missing the macro registry, chain-split, and tighter phrase-matching that already landed in Python's 2.3.3. This patch closes the drift in both downstream SDKs so the protocol's behavior is byte-identical across all three. The protocol itself did not change; this is the work that should have shipped inside 2.3.3.

**Package versions shipped with this release:**
- `osmp` (Python / PyPI): **no change — stays at 2.3.3** (source identical; the 2.3.3 release already shipped macros + chain-split)
- `osmp-protocol` (npm): 2.3.3 → **2.3.4** (catches up to Python 2.3.3: `MacroTemplate`, `MacroRegistry`, `SlotDefinition` now exported; optional `macroRegistry` constructor parameter on `SALComposer`)
- Go module: tag **v2.3.4** (catches up to Python 2.3.3: `MacroTemplate`, `MacroRegistry`, `SlotDefinition`, `NewMacroRegistry`, `NewComposerWithMacros`, `SetMacroRegistry`; no `go.mod` edit, pre-v2 import path)
- `osmp-mcp` (PyPI): no change required (depends on `osmp[dpack]>=2.3.0`; nothing to update on the wrapper)

### Added

- **TypeScript SDK — Registered Macro Architecture (port from Python).** `sdk/typescript/src/macro.ts` (~365 lines) ports `SlotDefinition`, `MacroTemplate`, and `MacroRegistry` 1:1 from `sdk/python/osmp/protocol.py` (lines 2841-3098). Includes register/lookup, opcode-existence validation against the ASD, slot-placeholder ↔ definition validation, expand, encodeCompact, encodeExpanded, encodeWithAnnotation, inheritedConsequenceClass (with severity-ordered inheritance from R-namespace frames), listMacros, and loadCorpus.
- **TypeScript SDK — chain-split + macro priority in `SALComposer`.** Mirrors Python's `compose` flow at protocol.py lines 2553-2576: optional registry parameter on the constructor, `_tryChainSplit` private method, macro priority check at the top of `_composeImpl`. Macros take precedence over individual opcode composition when any trigger substring is present in the NL.
- **Go SDK — Registered Macro Architecture (port from Python).** `sdk/go/osmp/macro.go` (~360 lines). Same API surface as the Python and TS macro modules, idiomatic Go (capitalized exported names, error returns, map[string]any slot values).
- **Go SDK — chain-split + macro priority in `Composer`.** New `NewComposerWithMacros` constructor + `SetMacroRegistry` / `MacroRegistry` accessors. Same flow semantics as TS and Python.
- **Cross-SDK parity vectors.** `tests/parity/parity_vectors.json` (24 vectors) generated from the Python composer with the Meshtastic macro corpus attached. `sdk/typescript/tests/cross_sdk_parity.test.ts` and `sdk/go/osmp/cross_sdk_parity_test.go` read the same JSON and assert byte-identical SAL output. Vectors cover the four site chips, six macro-priority triggers, four chain-split inputs, five single-segment compositions, and five passthrough cases. All 24 pass in all three SDKs.

### Fixed

- **Go SDK — non-deterministic composer iteration.** `Composer.buildKeywordIndex`, `buildPhraseIndex`, and `LookupByKeyword` previously walked `ASDFloorBasis` via `range map`, which Go intentionally randomizes. Different `Composer` instances would build different keyword indices and produce different SAL for the same NL input. Iteration is now sorted (alphabetical by namespace, then by opcode), making Go reproducible across runs and aligned with Python's insertion order for the parity vector set.

### Cross-SDK parity contract

Every input in `tests/parity/parity_vectors.json` produces byte-identical SAL across Python, TypeScript, and Go composers. Adding a feature or trigger that diverges any SDK's output is a parity contract violation and must either (a) update all three SDKs or (b) annotate the vector as a known divergence.

### Tests

- Python: 27/27 macro tests pass (`tests/tier1/test_macros.py`); existing test suites unchanged.
- TypeScript: 158/158 pass — 36 new macro tests (`sdk/typescript/tests/macro.test.ts`) + 25 cross-SDK parity tests (`sdk/typescript/tests/cross_sdk_parity.test.ts`) + 97 pre-existing.
- Go: full module suite passes — 27 new macro tests + 25 cross-SDK parity tests added (`sdk/go/osmp/macro_test.go`, `sdk/go/osmp/cross_sdk_parity_test.go`).

### Background

The April 16 commit (b6da16f) explicitly flagged "Python-only additions (TS/Go ports to follow if needed): chain-split infrastructure, 3+ confidence gate tightening." Macros landed in Python shortly after. The "ports to follow if needed" never got prioritized. The site's encoder demo surfaced the gap when chip phrases like `report battery level` resolved to `A:MACRO[MESH:DEV]` server-side (Python) but passed through client-side (TS). This release closes that drift.

---

## [v2.3.3] — 2026-04-24

Patch release. Bridge-fix: ASCII arrow `->` is now a first-class SAL frame-boundary operator equivalent to Unicode `→`.

**Package versions shipped with this release:**
- `osmp` (Python / PyPI): 2.3.2 → **2.3.3**
- `osmp-protocol` (npm): 2.3.2 → **2.3.3**
- `osmp-mcp` (PyPI): 1.1.0 → **1.1.1** (patch bump — no functional change; re-published so `server.json` can advance per lag-of-one convention)
- MCP Registry entry (`io.github.Octid-io/osmp` in server.json): 1.0.37 → **1.1.0** (lag-of-one convention; previous `packages[0].version` becomes the new registry version)

### Fixed

- **Bridge:** `->` (ASCII) is now treated as a SAL frame-boundary operator equivalent to `→` (Unicode). Previously, any SAL string using the ASCII shorthand (e.g. `H:HR>130->U:ALERT`) was parsed as a single frame rather than split into constituent frames, causing `validate_composition` to false-negative on valid chains, `MacroRegistry.register` to reject ASCII-arrow chain templates, and `SALDecoder.decode_natural_language` to skip the "then" NL mapping. Unicode behavior is unchanged.

Coordinated edits across two files:
- `sdk/python/osmp/protocol.py` — five edits: line 1787 (`_FRAME_SPLIT_RE` adds `->` alternate), line 2046 (`validate_composition` filter whitelist adds `"->"`), line 2908 (`MacroRegistry.register` chain-validation filter adds `"->"`), line 3052 (`MacroRegistry` consequence-class-inheritance filter adds `"->"`), line 3215 (`SALDecoder._OPERATOR_NL` adds `"->": " then "`).
- `sdk/python/src/osmp.py` (legacy single-file distribution) — two edits: line 1610 (frame-split regex), line 1862 (validator filter). Three edits from the modular package have no legacy counterpart because `MacroRegistry` and `_OPERATOR_NL` are not exported from the legacy surface. See `LEGACY_PARITY_AUDIT.md` for the full parity picture.

### Tests

- Added `sdk/python/tests/test_bridge_fix.py` — T1 (NL annotation round-trip ASCII↔Unicode byte-identical, "then" present), T2 (validator parity — same issue set across arrow forms), T3 (macro chain with ASCII arrow validates against ASD), T4 (Unicode corpus regression: 10 golden frames decode byte-identical). 4/4 pass.
- TypeScript suite (existing): 97/97 pass.
- Go suite (existing): `osmp` tests ok.

### Field verification

Verified on-device during RTP-012-B (2026-04-24, Gemma-4-E4B Q4_K_M on RedMagic 10S Pro via llama-server in Termux). Patched-substrate cells used the `->` operator across 9 cells × 15 rounds = 135 opportunities with zero parser defects. Ctrl-substrate cells (pre-fix) produced 0/9 acquisition across all priming conditions — supporting evidence that the pre-fix parser silently gated valid SAL chains.

### Not changed

- No API additions, no breaking changes, no migration required.
- `osmp-mcp` server not re-released; it picks up `osmp==2.3.3` automatically at install time.
- `server.json` unchanged; MCP registry entry trails the package version per project convention.

---

## [v2.1.0] — 2026-04-21

Additive release. No breaking changes. Patent-pending UBOT evaluator integrated across all three SDKs + MCP server.

**Package versions shipped with this release:**
- `osmp` (Python / PyPI): 2.2.5 → **2.3.2**
- `osmp-protocol` (npm): 2.2.5 → **2.3.2**
- `osmp-mcp` (PyPI): 1.0.37 → **1.1.0**
- MCP Registry entry (`io.github.Octid-io/osmp` in server.json): 1.0.36 → 1.0.37 (lag-of-one convention)

*Note: `osmp` and `osmp-protocol` passed through 2.3.0 (patent-docket strip) and 2.3.1 (contact-email strip, `licensing@` → `ack@`) before landing at 2.3.2. 2.3.2 is functionally identical to 2.3.1 across both; fresh installs pull 2.3.2 automatically.*

### Added — EML (Universal Binary Operator Evaluator)

A new companion math-evaluation layer based on Odrzywołek (2026, [arXiv:2603.21852](https://arxiv.org/abs/2603.21852)): the single binary operator `eml(x, y) = exp(x) − ln(y)`, together with the constant 1, generates the standard calculator function basis — exp, ln, sin, cos, sqrt, arithmetic, and more — as compact expression trees.

- **`sdk/python/osmp/eml.py`** — Python evaluator: operator, EMLNode tree, 16-entry base corpus, 4-compound arithmetic primitives, three wire formats (paper tree / restricted chain / wide multi-variable chain), SHA-256 corpus fingerprint
- **`sdk/go/osmp/eml/`** — Go evaluator (subpackage): same API surface, same semantics, byte-exact fingerprint
- **`sdk/typescript/src/eml.ts`** — TypeScript evaluator: same API surface, same semantics, byte-exact fingerprint
- **Cross-language byte-exact determinism** verified: `e9a4a71383f14624472fe0602ca5e0ff1959e00b09725a62d584e1361f842c1b`
- **Zero runtime dependencies.** Evaluator uses only standard-library / built-in math + `frexp` / `ldexp`
- **Attribution** to Odrzywołek in every module docstring per [PATENT-NOTICE.md](PATENT-NOTICE.md)

### Added — Fast-mode backend (`fdlibm.{py,go,ts}`)

Sun fdlibm-derived `exp` and `log` implementations. Public-domain-derived constants. 1-ULP accurate across IEEE-754-conformant platforms. Byte-exact across Python, Go, TypeScript. Sufficient for LoRa/BLE/edge-ML, constrained-channel telemetry, drone swarm coordination, and general scientific computation.

### Added — Precision-mode stub (`crlibm.{py,go,ts}`)

Stub file advertising the commercial precision-mode backend:

- `python`: `from osmp.crlibm import exp, log, AVAILABLE, PrecisionModeNotAvailable`
- `go`: `eml.CrlibmExp`, `eml.CrlibmLog`, `eml.CrlibmAvailable`, `eml.ErrPrecisionPackNotInstalled`
- `typescript`: `import { exp, log, AVAILABLE, PrecisionModeNotAvailableError } from "./crlibm"`

Calling `set_precision_mode("precision")` / `SetPrecisionMode(Precision)` without the commercial precision pack installed raises `PrecisionModeNotAvailable` (Python), returns `ErrPrecisionPackNotInstalled` (Go), or throws `PrecisionModeNotAvailableError` (TypeScript).

The commercial precision pack replaces the stub file with a real CRLibm-derived correctly-rounded implementation for regulated-industry applications:

- Medical IEC 62304
- Aerospace DO-178C
- Nuclear IEC 61513
- Audit-grade financial, cryptographic protocol-frame hash inputs
- DoD distribution under DFARS 252.227-7013 / 7014 Restricted Rights

Licensing: `ack@octid.io`.

### Added — MCP tools

Two new tools on the MCP server (`osmp-mcp` 1.1.0), bringing the total from 17 to 19:

- `osmp_eml_evaluate(chain_name, values)` — evaluate a pre-built EML chain at given input value(s). Supports 16 single-variable base entries (exp, ln, identity, etc.) and 4 multi-variable arithmetic compounds (neg_y, x_plus_y, x_times_y, linear_calibration).
- `osmp_eml_corpus_lookup(chain_name)` — list available chains, or inspect the structure (variables, levels, operand pairs) of a named entry.

Precision mode is not exposed via MCP; fast-mode evaluation only.

### Added — Documentation

- `README.md` — new "EML — Mathematics on the Wire" section
- `sdk/python/README.md`, `sdk/go/README.md`, `sdk/typescript/README.md` — per-language EML usage with examples
- `osmp_mcp/README.md` — new Math (2) tool category, updated tool count to 19
- `PATENT-NOTICE.md` — dual-tier distribution (open fast mode + commercial precision mode) documented

### Patent Pending

Patent pending. The underlying operator (Odrzywołek) is not claimed.

---

## [v2.0.0 and earlier]

See the [git log](https://github.com/octid-io/cloudless-sky/commits/main) for earlier version history. Prior GitHub releases:

- **v2.0.0** — OSMP (Semantic Assembly Language) encode / decode / validate, SALComposer, MCP server, three MDR corpora (ICD-10-CM, ISO 20022, MITRE ATT&CK). Package versions at release: osmp 2.2.5, osmp-mcp 1.0.37.
- **v1.0.1** — patch release on v1.0.0.
- **v1.0.0** — initial public release.
