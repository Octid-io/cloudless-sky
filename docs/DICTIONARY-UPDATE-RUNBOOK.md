# Dictionary Update Runbook

**How to change opcodes without breaking CI.**

When you add, remove, rename, or change the meaning of opcodes in the
OSMP semantic dictionary, three SDKs (Python, TypeScript, Go) must stay
in lockstep. This runbook documents the exact steps so nothing is left
to guesswork.

---

## What the CI tests actually verify

The cross-SDK test workflow (`.github/workflows/test.yml`) enforces
integrity at three levels:

| Layer | What it checks | Gate job |
|-------|----------------|----------|
| **Source sync** | TS and Go glyph files match what `gen_asd.py` would generate from canonical Python | `asd-drift-gate` |
| **Runtime fingerprint** | TS computes the same ASD fingerprint as Python (FNP handshake contract) | `typescript-tests` |
| **Structural floor** | Each namespace has a sane minimum opcode count (>= 20 for A) | `python-tests` |

If any layer fails, the `cross-sdk-status` job blocks the merge.

---

## Step-by-step: changing opcodes

### 1. Edit the canonical Python source

All opcodes are defined in `sdk/python/osmp/protocol.py` inside `ASD_BASIS`.
This is the single source of truth (ADR-001). Make your changes here and
only here.

```python
# Example: adding a new opcode to the A namespace
ASD_BASIS = {
    "A": {
        ...
        "NEWOP": "description_of_new_opcode",
    },
    ...
}
```

### 2. Update the dictionary CSV (if applicable)

If this is a new dictionary version, add or update the CSV in `protocol/`:

```
protocol/OSMP-semantic-dictionary-v16.csv
```

`gen_asd.py` auto-detects the highest-numbered CSV for version tagging.

### 3. Run gen_asd.py

```bash
python3 tools/gen_asd.py
```

This single command regenerates **all derived files**:

- `sdk/typescript/src/glyphs.ts` -- TS opcode tables
- `sdk/go/osmp/glyphs.go` -- Go opcode tables
- `sdk/typescript/tests/asd_fingerprint.test.ts` -- canonical fingerprint
  constant and total opcode count (between the `AUTO-UPDATED` markers)

### 4. Verify locally

```bash
python3 tools/gen_asd.py --check
```

Expected output:

```
Dictionary version: v15
ASD_BASIS: 26 namespaces, 356 opcodes

Checking TypeScript: sdk/typescript/src/glyphs.ts
  OK (in sync)
Checking TS fingerprint test: sdk/typescript/tests/asd_fingerprint.test.ts
  OK (in sync)
Checking Go: sdk/go/osmp/glyphs.go
  OK (in sync)
```

If any target shows `DRIFT DETECTED`, re-run step 3.

### 5. Commit everything together

Stage all changed files in a single commit. The drift gate will reject
partial updates.

```bash
git add sdk/python/osmp/protocol.py \
        sdk/typescript/src/glyphs.ts \
        sdk/go/osmp/glyphs.go \
        sdk/typescript/tests/asd_fingerprint.test.ts \
        protocol/OSMP-semantic-dictionary-v*.csv
git commit -m "v16 dictionary (N opcodes), update description here"
```

### 6. Push and verify CI

All jobs should pass. If they don't, the failure message tells you
exactly which layer broke.

---

## What you do NOT need to touch

These files handle version changes automatically:

| File | Why it's safe |
|------|---------------|
| `.github/workflows/test.yml` | Installs from pyproject.toml/package.json, not hardcoded versions |
| `tests/tier1/test_adp.py` | Uses a floor assertion (`>= 20`), not an exact opcode count |
| `sdk/python/pyproject.toml` | Declares deps; only touch for package version bumps, not opcode changes |

---

## What gen_asd.py handles automatically

| Derived artifact | Source | Auto-updated? |
|-----------------|--------|---------------|
| `sdk/typescript/src/glyphs.ts` | `protocol.py` ASD_BASIS + glyph tables | Yes |
| `sdk/go/osmp/glyphs.go` | `protocol.py` ASD_BASIS + glyph tables | Yes |
| `asd_fingerprint.test.ts` fingerprint constant | `AdaptiveSharedDictionary().fingerprint()` | Yes |
| `asd_fingerprint.test.ts` opcode count | `sum(len(ops) for ops in ASD_BASIS.values())` | Yes |

---

## Troubleshooting

**CI says "ASD drift gate failed"**
You edited a glyph file by hand or forgot to run `gen_asd.py`.
Fix: `python3 tools/gen_asd.py && git add -u && git commit --amend`

**CI says fingerprint mismatch (TS test)**
The dictionary changed but the test constant is stale. This means
`gen_asd.py` was not run after the opcode change.
Fix: `python3 tools/gen_asd.py` (it now patches the test file too).

**CI says namespace count assertion failed (Python test)**
A namespace dropped below 20 opcodes. This is a structural guard --
either the removal was too aggressive, or there's a bug in protocol.py.

**gen_asd.py --check says "DRIFT DETECTED" but I haven't changed anything**
Someone edited a generated file by hand. Run `python3 tools/gen_asd.py`
to restore it to the canonical state.

---

## Design rationale

The protocol's ethos is zero-decode handoffs: every participant in the
chain -- human, tool, CI -- should be able to act on what it receives
without guessing. This runbook exists so that updating the dictionary is
a mechanical sequence, not a context-dependent puzzle.

The enforcement chain: **CSV -> protocol.py -> gen_asd.py -> all SDKs +
tests**. One command propagates. One command checks. CI blocks drift.
