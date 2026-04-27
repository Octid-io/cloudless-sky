# BRIDGE_FIX_RELEASE.md — ASCII arrow `->` as SAL frame operator

**Status:** DRAFT. Not committed, not pushed, not published.
**Drafted:** 2026-04-24
**Author:** hardware-thread scientist, per 2026-04-24 work-stack Item 9.
**Decision owner:** Clay (pro-se maintainer).

---

## Summary

The SAL frame-boundary operator was Unicode-only (`→ ∧ ∨ ↔ ∥ ;`) prior to this fix. Any SAL string using the ASCII `->` shorthand was parsed as a single frame, not split into constituent frames. The fix adds `->` as a first-class alternate for `→` (THEN) across the frame splitter, validator filters, macro-chain validator filters, and NL-annotation decoder. Behavior under Unicode operators is unchanged.

## Scope of change

Two files in `sdk/python/`:

- `osmp/protocol.py` — five coordinated edits:
  - Line 1787: `_FRAME_SPLIT_RE` pattern adds `->` alternate.
  - Line 2046: `validate_composition` filter whitelist adds `"->"`.
  - Line 2908: `MacroRegistry.register` chain-validation filter adds `"->"`.
  - Line 3052: `MacroRegistry` consequence-class-inheritance filter adds `"->"`.
  - Line 3215: `SALDecoder._OPERATOR_NL` dict adds `"->": " then "` NL mapping.
- `src/osmp.py` (legacy single-file distribution) — two coordinated edits:
  - Line 1610: `_FRAME_SPLIT_RE` pattern adds `->` alternate.
  - Line 1862: `validate_composition` filter whitelist adds `"->"`.

The remaining three edits of the modular package are no-ops on the legacy surface because `MacroRegistry`, `_OPERATOR_NL` are not exported by `osmp.py`. See `LEGACY_PARITY_AUDIT.md` in the RTP-012 directory for the full parity picture.

## Test coverage

`tests/test_bridge_fix.py` — four tests, all passing as of 2026-04-24:

- T1: NL annotation round-trip — ASCII and Unicode arrows produce byte-identical NL output including the word "then".
- T2: Validator parity — ASCII and Unicode arrows fire the same issue sets (same rules, severities, frame identifiers).
- T3: Macro chain with ASCII arrow — a MacroTemplate whose chain_template uses `->` validates successfully when the referenced opcodes exist in the ASD.
- T4: Unicode corpus regression — 10 Unicode-arrow SAL frames decode to byte-identical golden strings captured at fix time; catches any regression in Unicode handling introduced by the ASCII-arrow addition.

Previous "T1–T4 passed on a laptop unit-test battery" claim from the 2026-04-24 morning session wrap was unverifiable — that test file did not exist in the tree. The current `tests/test_bridge_fix.py` was written from scratch 2026-04-24 afternoon against the documented bridge-fix lines, and is the authoritative test surface going forward.

## On-device evidence

RTP-012 raw outputs on phone show `_FRAME_SPLIT_RE.split("H:HR>130->U:ALERT")` producing `["H:HR>130", "->", "U:ALERT"]` correctly across the matrix runs. On-device `sha256sum sdk/python/osmp/protocol.py` matches laptop post-fix hash (captured in per-cell JSONL header field `protocol_py_sha256`).

## Proposed commit message

```
bridge: add ASCII arrow `->` as SAL frame operator

Prior to this change, the SAL frame-boundary operator was Unicode-only.
`H:HR>130->U:ALERT` was parsed as a single frame rather than split into
[H:HR>130, U:ALERT] with an implied THEN operator. This affected
validate_composition, MacroRegistry validation, and SALDecoder NL
annotation.

This change adds `->` as a first-class alternate for `→` across the five
coordinated locations in sdk/python/osmp/protocol.py and the two
equivalent locations in the legacy sdk/python/src/osmp.py. Unicode
behavior is unchanged.

Tests: tests/test_bridge_fix.py (T1–T4, 4 passed).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## Proposed changelog entry

```
### Fixed
- Bridge: ASCII arrow `->` is now treated as a SAL frame-boundary operator
  equivalent to Unicode `→`. Previously, any SAL string using the ASCII
  shorthand was parsed as a single frame, causing validator false negatives
  and NL-annotation failures on protocol-aware prompts.
```

## Version bump recommendation

Per the established RTP-012-B release cadence, bridge fix is a **patch bump**: `osmp-2.3.2 → osmp-2.3.3`. The public API is unchanged; only the operator set recognized by the parser is broader. No downstream breakage. Update `pyproject.toml` and the `osmp/__init__.py` version constant; `server.json` intentionally trails the package version per project convention (memory: `server.json` versioning).

## Not doing

- No commit created.
- No push to remote.
- No PR opened.
- No publish to PyPI.

Per project memory (`feedback_ip_no_autocommit.md`), research-adjacent code stays local until Clay explicitly approves. Per `feedback_release_vs_internal_versioning.md`, public releases loop Clay in; this doc is the loop-in.

## Clay's decision

Three paths:

1. **Ship now.** Commit + push + tag v2.3.3 + publish to PyPI. Small risk surface; tests pass; evidence chain is clean.
2. **Ship after RTP-012-B closes.** Wait until the matrix completes and the acquisition verdict lands. If the verdict depends on the bridge fix being in the on-device substrate (it does — `osmp_patched` carries the fix), shipping it separately is orthogonal and does not change the science.
3. **Defer.** Ship at the next release window alongside whatever else lands.

My CTO-adjacent read: ship after RTP-012-B closes. The matrix is the validation event for this fix; waiting lets the changelog entry cite "verified in RTP-012-B acquisition run."
