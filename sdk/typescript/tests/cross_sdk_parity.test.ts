/**
 * Cross-SDK Parity Test (TypeScript reader)
 * =========================================
 *
 * Reads tests/parity/parity_vectors.json (generated from Python via
 * tests/parity/gen_parity_vectors.py) and asserts that this SDK's composer
 * produces byte-identical SAL for every vector.
 *
 * Python is the reference SDK. Any mismatch is a parity bug here.
 *
 * Patent pending | License: Apache 2.0
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { SALComposer, MacroRegistry } from "../src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..", "..");
const VECTORS_PATH = resolve(REPO_ROOT, "tests", "parity", "parity_vectors.json");
const CORPUS_PATH = resolve(REPO_ROOT, "mdr", "meshtastic", "meshtastic-macros.json");

interface ParityVector {
  category: string;
  nl: string;
  sal: string | null;
}

interface ParityFile {
  spec_version: string;
  reference_sdk: string;
  macro_corpus: string;
  macros_loaded: number;
  vectors: ParityVector[];
}

const parityFile: ParityFile = JSON.parse(readFileSync(VECTORS_PATH, "utf-8"));
const corpus = JSON.parse(readFileSync(CORPUS_PATH, "utf-8"));

function makeComposer(): SALComposer {
  const reg = new MacroRegistry();
  reg.loadCorpus(corpus);
  return new SALComposer(undefined, reg);
}

describe(`Cross-SDK parity (${parityFile.spec_version}, ref=${parityFile.reference_sdk})`, () => {
  it("loads the same macro corpus as the reference SDK", () => {
    const reg = new MacroRegistry();
    const count = reg.loadCorpus(corpus);
    expect(count).toBe(parityFile.macros_loaded);
  });

  for (const v of parityFile.vectors) {
    it(`[${v.category}] "${v.nl}" → ${v.sal === null ? "PASSTHROUGH" : v.sal}`, () => {
      const composer = makeComposer();
      const got = composer.compose(v.nl);
      // Python emits None on passthrough; JSON serializes that as null;
      // TS composer returns `null`. They must agree.
      expect(got).toBe(v.sal);
    });
  }
});
