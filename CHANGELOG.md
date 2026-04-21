# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/).

---

## [v2.1.0] — 2026-04-21

Additive release. No breaking changes. Patent-pending UBOT evaluator integrated across all three SDKs + MCP server.

**Package versions shipped with this release:**
- `osmp` (Python / PyPI): 2.2.5 → **2.3.1**
- `osmp-protocol` (npm): 2.2.5 → **2.3.1**
- `osmp-mcp` (PyPI): 1.0.37 → **1.1.0**
- MCP Registry entry (`io.github.Octid-io/osmp` in server.json): 1.0.36 → 1.0.37 (lag-of-one convention)

*Note: `osmp` and `osmp-protocol` were initially published as 2.3.0. Patch 2.3.1 strips docstring-level patent-docket references from the eml module — functionally identical; fresh installs pull 2.3.1 automatically.*

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
