# ADR-004: Dictionary Basis Manifest for SAIL Intern Table Determinism

## Context

ADR-001 established that the canonical semantic dictionary CSV is the single source of truth for the ASD basis set, with the SDKs as derivations of that pin. At the time ADR-001 was written, the Python SDK was a single flat file, there was no SAIL binary wire mode, there was no MDR corpus distribution, and the only thing that needed pinning was one CSV.

The architecture has grown past that scope. SAIL (spec §3.6) introduces a binary wire mode that depends on an intern table — a mapping of integer indices to strings that both ends of a session must agree on for round-trip to work. The intern table is currently constructed at codec initialization time from two inputs: the base dictionary CSV (Phase 1) and zero or more MDR corpus CSVs passed as `mdr_paths` (Phase 2). Phase 1 is deterministic across nodes that load the same base dictionary. Phase 2 is not — it parameterizes the intern table on which MDR corpora are loaded at codec construction time, with no mechanism to coordinate loadouts across nodes.

Finding 41 in `docs/audit/findings-41-48-research.md` logs the resulting architectural risk: two nodes with different MDR loadouts build different intern tables, which silently break SAIL round-trip because the bytes on the wire pass AEAD verification but decode to the wrong strings. The finding was held pending this ADR.

Empirical state at time of writing: Phase 2 is not observable on any MDR currently in the repository. The parser keys on a literal `SECTION B` marker that is absent from `mdr/iso20022/*.csv`, and the other MDR corpora (`icd10cm`, `mitre-attack`) ship as `.dpack` binaries with no CSV at all. A no-MDR codec and a with-MDR codec produce byte-identical 240-entry intern tables today, and cross-codec SAIL round-trip succeeds on every test vector. The vulnerability is latent, not live. It activates the instant a future MDR corpus ships with parseable content and enough stringable entries to clear the intern cost filter.

The architectural question is whether to retreat from runtime corpus extension or to complete it by extending ADR-001's pinning principle from a single canonical CSV to an ordered set of content-addressed corpora.

## Decision

Extend ADR-001. The pin is no longer a single CSV — it is an ordered set of content-addressed dictionary corpora, collectively called the **Dictionary Basis**. The SAIL intern table is a pure function of the basis.

A Dictionary Basis is an ordered list of `(corpus_id, corpus_hash)` pairs, where:

- `corpus_id` is a stable human-readable identifier assigned at corpus build time (e.g. `"asd-v14"`, `"mdr-icd10cm-fy2026"`, `"mdr-iso20022-2025-04"`, `"mdr-mitre-attack-ent-v18.1"`).
- `corpus_hash` is SHA-256 computed over the corpus file bytes verbatim, with no canonicalization transform. The file on disk is the single source of truth; any corpus that wants a canonical form provides one at build time. This matches the ADR-001 principle that derivations cannot diverge from the pin.
- Order is significant. Intern table indices are assigned in the order the basis iterates, so any two nodes that iterate the same ordered basis produce byte-identical intern tables by construction.

Corpus hashes are computed at load time by the SDK from the corpus file bytes. The existing DBLK header format is not changed. Old corpora load in new SDKs with no modification. New corpora load in old SDKs with no modification. The hash is a property of the bytes either side already has, not a property that must be transmitted or stored in the corpus header.

The **Basis Fingerprint** is the first 8 bytes of SHA-256 computed over the canonical serialization of the ordered basis list (each entry as `corpus_id || corpus_hash`). Two nodes with equal basis fingerprints have byte-identical intern tables. Two nodes with unequal basis fingerprints do not, and must not attempt to exchange SAIL payloads with each other.

The FNP handshake is extended to exchange basis fingerprints alongside the existing ASD fingerprint. A session establishes in SAIL-capable mode only if both ends advertise equal basis fingerprints. Sessions with unequal basis fingerprints establish in SAL-only mode and fall through to the existing SALBridge boundary translation architecture (spec §9.7) for cross-basis traffic. This is a capability grading, not a failure mode: two nodes with different bases can always communicate in SAL, they simply cannot unlock SAIL with each other.

Every node carries a configured expected basis fingerprint. When a session establishes with a peer whose basis fingerprint differs from the expected one, the session opens in SAL-only mode and the node logs a session-degradation event, surfaced through the FNP capability state so operator monitoring can alert on it. Deployments that want hard-fail semantics configure a node policy flag `require_sail: true` that converts degradation events into session refusal at the local node — without forcing that policy on the protocol as a whole.

Phase 2 of the current intern table construction is removed. The `mdr_paths` parameter to `_build_intern_table` is replaced by a `DictionaryBasis` parameter. Corpus extraction rules are defined per corpus type at build time, not at codec construction time — the canonical artifact shipped with each corpus is a pre-extracted stringable set, not a CSV parsed in-process by every codec instance. This moves the extraction logic from runtime to build time, which is where it belongs under ADR-001.

The base ASD CSV remains exactly what ADR-001 defines it to be: the first entry in every basis. A node that loads only the base ASD has a basis of length one, a well-defined basis fingerprint, and a fully functional SAIL wire mode. Loading additional MDR corpora grows the basis in a deterministic order specified by the node operator; that order is part of the basis and is reflected in the basis fingerprint.

## Analog

Nix derivation pinning, extended. ADR-001 pinned one derivation (the CSV). ADR-004 pins an ordered list of derivations (the basis). The derivation graph is still resolved at build time for each corpus individually, but the composition of corpora into a basis is also pinned, and the pin of the composition is the basis fingerprint. A node that advertises a basis fingerprint is asserting the same guarantee ADR-001 asserts for the CSV: this is what I loaded, in this order, with these exact bytes, and any other node asserting the same fingerprint loaded the same thing.

The FNP handshake becomes the runtime witness for the build-time pin. Two nodes with equal fingerprints are provably running equal bases, in the same way two Nix systems with equal store path hashes are provably running equal derivations.

## Utility cost honestly named

This ADR introduces a new failure category that does not exist in SAL-only OSMP today: two nodes that both speak OSMP, both have current dictionaries, and are perfectly capable of understanding each other can no longer use the SAIL binary wire mode together if their corpus load order differs. This is a real cost and it deserves to be named at the point of decision, not discovered downstream.

The mitigations make the cost tolerable in every deployment profile considered:

- **Heterogeneous deployments (two independent organizations sharing only the base ASD).** Sessions establish in SAL-only mode. Traffic flows normally. The bijective SAL round-trip guarantee is unaffected. Wire compression is limited to SAL's own reduction, which at time of writing is approximately 76% token reduction versus the JSON-based industry baseline — a floor already well above any competing agent communication protocol's ceiling. The marginal gain that SAIL provides over SAL on MDR-covered content is lost for this peer pair, but the baseline OSMP value proposition is fully preserved.
- **Homogeneous deployments (one operator, fleet of identical nodes).** Basis fingerprints match by construction because every node loads the same configured basis. SAIL is unlocked for all intra-fleet traffic. The operator monitoring signal catches any node that drifts from the expected basis before the drift produces silent compression regression.
- **Mixed deployments that need hard interop guarantees.** `require_sail: true` converts the graded-capability model into hard-fail locally without forcing the policy on peers. An operator who cannot tolerate SAL-only sessions configures their nodes to refuse them; peers without the policy flag are unaffected.
- **The default case.** A node that loads only the base ASD has a basis of length one and a well-defined basis fingerprint. Two such nodes always match on basis and always unlock SAIL. The graded-capability model introduces no new behavior for the common case.

The honest trade: the marginal compression benefit of SAIL over SAL on MDR-covered instructions is now conditioned on basis agreement, and some peer pairs will not have it. In exchange, the bijection property is cryptographically anchored rather than runtime-hoped-for, the commercial MDR distribution story becomes technically coherent, and the FNP handshake acquires a novel capability negotiation mechanism that the prior art does not teach.

## Consequences

**Easier:** SAIL round-trip is deterministic by construction for any peers sharing a basis fingerprint. The bijection property promised by spec §3.6 is anchored to a cryptographic equality check rather than an out-of-band assumption. Commercial MDR distribution has a coherent story: loading a paid MDR changes the basis fingerprint, peers loading the same MDR automatically light up SAIL wire compression for that corpus's content, and the wire efficiency gain is a direct function of basis composition.

**Required discipline:** Corpus build tooling computes the corpus hash at build time and publishes it alongside the corpus artifact for operator convenience, but the hash is not required in-band — SDKs compute it from file bytes at load time if not provided. Node operators treat the basis as a structural configuration, not an ad-hoc parameter — adding or reordering corpora changes the basis fingerprint, which grades SAIL interop with prior peers until both sides converge on a new basis.

**Structural failure mode eliminated:** Silent SAIL misdecode across mismatched loadouts is impossible. Two nodes with different bases fail the FNP capability check and establish in SAL-only mode. They cannot exchange SAIL bytes and therefore cannot silently misdecode them. The AEAD envelope in spec §8.6 continues to authenticate the bytes on the wire; the basis fingerprint check authenticates the semantic interpretation of those bytes before the session opens.

**Wire cost:** FNP ADV and ACK each grow by 8 bytes when the advertising node has loaded any corpus beyond the base ASD, signaled by a flag bit in `msg_type`. Base-ASD-only nodes pay zero additional bytes and interoperate with other base-ASD-only nodes exactly as before. The per-envelope cost of SAIL is unchanged; basis agreement is session state established once at handshake, not per-message state.

**Old-meets-new compatibility:** The DBLK header format is unchanged. Old corpora load in new SDKs unchanged. New corpora load in old SDKs unchanged. The JTD clarity principle holds in both directions: if old and new can clearly do the job, no update is required, and trickle-charge updates flow through normal channels at operator discretion. Corpus hashes are computed from file bytes either side already has, not stored in the corpus header.

**Spec changes:** §3.6 rewrites the bijection language to tie the mapping to basis fingerprint equality. §9.1 and §9.2 add the optional `basis_fingerprint` field gated by a flag bit in `msg_type`. §9.3 extends the canonical-serialization and fingerprint-computation rules to cover bases. §9.5 state machine gains a capability grading between SAIL-capable and SAL-only ESTABLISHED states. A new §9.8 formalizes the Dictionary Basis Manifest.

**SDK changes:** All three SDKs add a `DictionaryBasis` type, move intern table construction onto it, refactor FNP ADV/ACK serialization for the new optional field, update the FNP state machine for capability grading, and add the `require_sail` node policy flag. The `mdr_paths` parameter to codec constructors is removed in the same release as dictionary v15 and the training-convergence sibling opcode work, so downstream users see a single coordinated upgrade rather than two sequential breaking changes. Release notes describe the new architecture forward-looking; they do not volunteer commentary on the prior Phase 2 implementation state.

**Test enforcement:** A new cross-SDK test verifies that Python, TypeScript, and Go compute identical basis fingerprints for the same ordered corpus list, that identical bases produce byte-identical intern tables, that different bases produce different fingerprints, and that FNP correctly grades sessions based on fingerprint agreement. This is the test Finding 41 identified as missing.

**Not changed:** The base ASD CSV remains the source of truth under ADR-001. The Go compiled-in floor under ADR-002 remains the default basis of length one. SAL encoding and decoding are unaffected — this ADR is entirely about SAIL. SALBridge, SEC envelope, regulatory dependency grammar, macro architecture, and all composition rules are unaffected.

**Future optimization (not shipping with this ADR):** The DBLK header's existing `flags` field reserves a bit for an optional cached corpus hash at a fixed header offset. When enabled by a future build tool, the SDK skips the compute-at-load pass and reads the cached hash directly. Pure optimization, backward compatible in both directions, not coupled to the ADR-004 rollout. Tracked for a later sprint when corpus load time on constrained hardware becomes measurable.
