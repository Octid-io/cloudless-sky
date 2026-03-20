/**
 * D:PACK/BLK Tier 1 unit tests — TypeScript
 *
 * 14 hardcoded test codes (7 ICD-10-CM, 7 ISO 20022).
 * Verifies resolveBlk against exact or prefix-matched SAL descriptions
 * from dict-free DBLK binaries.
 *
 * Run:
 *   npm install fzstd
 *   node --loader ts-node/esm tests/tier1/test_dpack.ts
 *   # or: npx tsx tests/tier1/test_dpack.ts
 *   # or: compile and run with tsc
 *
 * Binary paths assume execution from repo root (cloudless-sky/).
 */

import { readFileSync } from "fs";
import { resolveBlk } from "../../sdk/typescript/src/dpack.js";

interface TestCase {
  code: string;
  expected: string;
  prefix: boolean;
}

const icdTests: TestCase[] = [
  { code: "A000", expected: "Cholera d/t Vibrio cholerae 01, biovar cholerae", prefix: false },
  { code: "E0AW", expected: "Type 2 diabetes mellitus w/o comps", prefix: false },
  { code: "I00Z", expected: "Essential (primary) hypertension", prefix: false },
  { code: "M2AB", expected: "Radiculopathy, lumbar region", prefix: false },
  { code: "R001", expected: "Bradycardia, unsp", prefix: false },
  { code: "S083", expected: "Laceration without foreign body of scalp, init", prefix: false },
  { code: "Z135", expected: "Dependence on supplemental oxygen", prefix: false },
];

const isoTests: TestCase[] = [
  { code: "AAMVAFormat", expected: "AAMVAFormat: American driver license.", prefix: false },
  { code: "ACH", expected: "ACH: Automated Clearing House.", prefix: true },
  { code: "AccountIdentification4Choice", expected: "AcctID4Choice:", prefix: true },
  { code: "ActiveCurrencyAndAmount", expected: "ActiveCcyAndAmt:", prefix: true },
  { code: "PaymentIdentification7", expected: "PmtID7: Provides further means of referencing a pmt txn.", prefix: false },
  { code: "SupplementaryData1", expected: "SupplementaryData1:", prefix: true },
  { code: "TransactionReferences6", expected: "TxnRefs6: Identifies the underlying txn.", prefix: false },
];

function run(label: string, binaryPath: string, tests: TestCase[]): number {
  const data = new Uint8Array(readFileSync(binaryPath));
  let pass = 0, fail = 0;

  for (const t of tests) {
    const got = resolveBlk(data, t.code);
    if (got === null) {
      console.log(`  FAIL  ${t.code}: got null`);
      fail++;
      continue;
    }
    const ok = t.prefix ? got.startsWith(t.expected) : got === t.expected;
    if (ok) {
      console.log(`  PASS  ${t.code}`);
      pass++;
    } else {
      console.log(`  FAIL  ${t.code}`);
      console.log(`    expected: ${t.expected}`);
      console.log(`    got:      ${got.slice(0, 80)}`);
      fail++;
    }
  }
  console.log(`  ${label}: ${pass}/${pass + fail} passed\n`);
  return fail;
}

console.log("D:PACK/BLK Tier 1 Tests (TypeScript)\n");

// Binary paths: relative from repo root (run with: npx tsx tests/tier1/test_dpack.ts)
// or from tests/tier1/: use ../../mdr/...
const BASE = process.cwd().endsWith("tier1") ? "../../" : "";

const icdFail = run("ICD-10-CM", `${BASE}mdr/icd10cm/MDR-ICD10CM-FY2026-blk.dpack`, icdTests);
const isoFail = run("ISO 20022", `${BASE}mdr/iso20022/MDR-ISO20022-K-ISO-blk.dpack`, isoTests);

if (icdFail + isoFail === 0) {
  console.log("=== ALL 14 TESTS PASSED ===");
} else {
  console.log(`=== ${icdFail + isoFail} TESTS FAILED ===`);
  process.exit(1);
}
