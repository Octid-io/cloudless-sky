/**
 * Brigade Cross-SDK Parity Test (TypeScript reader)
 * ==================================================
 *
 * Reads tests/parity/brigade_parity_vectors.json (generated from Python via
 * tests/parity/gen_brigade_parity.py) and asserts that this SDK's brigade
 * Orchestrator produces byte-identical SAL + matching mode/reason_code for
 * every vector.
 *
 * Python brigade is the reference SDK. Any mismatch is a parity bug here.
 *
 * Patent pending | License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { Orchestrator } from "../src/brigade/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..", "..");
const VECTORS_PATH = resolve(REPO_ROOT, "tests", "parity", "brigade_parity_vectors.json");

interface BrigadeVector {
  category: string;
  nl: string;
  sal: string | null;
  mode: "sal" | "bridge" | "passthrough" | "refused";
  reason_code: string | null;
}

interface BrigadeParityFile {
  spec_version: string;
  reference_sdk: string;
  vectors: BrigadeVector[];
}

const parityFile: BrigadeParityFile = JSON.parse(readFileSync(VECTORS_PATH, "utf-8"));

describe(`Brigade cross-SDK parity (${parityFile.spec_version}, ref=${parityFile.reference_sdk})`, () => {
  it("reads the parity vector file", () => {
    expect(parityFile.vectors.length).toBeGreaterThan(0);
  });

  for (const v of parityFile.vectors) {
    it(`[${v.category}] ${JSON.stringify(v.nl)} → ${v.sal === null ? "passthrough/refused" : v.sal}`, () => {
      const orch = new Orchestrator();
      const got = orch.composeWithHint(v.nl);
      expect(got.sal).toBe(v.sal);
      expect(got.mode).toBe(v.mode);
      expect(got.reason_code ?? null).toBe(v.reason_code);
    });
  }
});
