/**
 * Cross-SDK ASD Fingerprint Tests (Finding 37)
 * ============================================
 *
 * These tests lock in the cross-SDK ASD fingerprint invariant. If the
 * TypeScript SDK computes a different fingerprint than the Python SDK
 * for the same ASD_BASIS content, FNP handshakes between a Python node
 * and a TypeScript node will fail because the fingerprint check in the
 * FNP_ADV message will report a mismatch.
 *
 * The canonical fingerprint value is hardcoded below. It is computed as:
 *   sha256(json.dumps(ASD_BASIS, sort_keys=True))[:16]
 *
 * Any change to ASD_BASIS (adding or removing an opcode, renaming one,
 * changing a meaning string) invalidates this fingerprint and requires
 * coordinated updates across all three SDKs via tools/gen_asd.py, with
 * the new canonical value being captured in this test AND in the
 * equivalent Python test at tests/test_asd_no_drift.py.
 *
 * Patent pending | License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import { AdaptiveSharedDictionary } from "../src/asd.js";
import { ASD_BASIS } from "../src/glyphs.js";

// --- AUTO-UPDATED by tools/gen_asd.py --- do not edit manually ---
// The canonical ASD fingerprint for dictionary v15 (352 opcodes, 26 namespaces).
// This value MUST match the output of the equivalent Python computation:
//
//   python3 -c "import sys; sys.path.insert(0, 'sdk/python'); \
//     from osmp.protocol import AdaptiveSharedDictionary; \
//     print(AdaptiveSharedDictionary().fingerprint())"
//
// If this test fails, run: python3 tools/gen_asd.py
// That regenerates glyphs AND this constant from the canonical Python source.
const CANONICAL_FINGERPRINT_V15 = "1c125bb41b1838e1";
// --- END AUTO-UPDATED ---

describe("ASD Cross-SDK Fingerprint", () => {
  it("computes the canonical fingerprint", () => {
    const asd = new AdaptiveSharedDictionary();
    expect(asd.fingerprint()).toBe(CANONICAL_FINGERPRINT_V15);
  });

  it("fingerprint is 16 hex characters", () => {
    const asd = new AdaptiveSharedDictionary();
    expect(asd.fingerprint()).toMatch(/^[0-9a-f]{16}$/);
  });

  it("fingerprint is deterministic across instances", () => {
    const a = new AdaptiveSharedDictionary();
    const b = new AdaptiveSharedDictionary();
    expect(a.fingerprint()).toBe(b.fingerprint());
  });

  it("ASD_BASIS contains 26 namespaces", () => {
    expect(Object.keys(ASD_BASIS).length).toBe(26);
  });

  it("ASD_BASIS contains 352 opcodes total", () => {
    let total = 0;
    for (const ops of Object.values(ASD_BASIS)) {
      total += Object.keys(ops).length;
    }
    expect(total).toBe(352);
  });

  it("canonical JSON is deterministic", () => {
    const a = new AdaptiveSharedDictionary();
    const b = new AdaptiveSharedDictionary();
    expect(a.canonicalJSON()).toBe(b.canonicalJSON());
  });

  it("fingerprint marker — Finding 37", () => {
    // Single-line marker that explicitly references the audit finding.
    // If this test fails, cross-SDK FNP handshakes will break.
    const asd = new AdaptiveSharedDictionary();
    expect(asd.fingerprint()).toBe(CANONICAL_FINGERPRINT_V15);
  });
});
