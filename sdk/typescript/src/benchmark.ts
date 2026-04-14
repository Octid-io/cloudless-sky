/**
 * OSMP Conformance Benchmark Runner — TypeScript SDK
 * Patent pending | License: Apache 2.0
 */
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { OSMPDecoder } from "./decoder.js";
import { utf8Bytes } from "./bael.js";
import { BenchmarkReport, VectorResult } from "./types.js";

export function runBenchmark(vectorsPath?: string): BenchmarkReport {
  const resolved = vectorsPath ?? path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../protocol/test-vectors/canonical-test-vectors.json"
  );
  const data = JSON.parse(fs.readFileSync(resolved,"utf8"));
  const dec  = new OSMPDecoder();
  const results: VectorResult[] = [];
  let passed = 0, totalMustPass = 0;
  const threshold = data.compression_summary.conformance_threshold_pct;

  console.log(`\n${"=".repeat(72)}`);
  console.log(`  OSMP BENCHMARK — Cloudless Sky Protocol v${data.version}`);
  console.log(`  Measurement: ${data.measurement_basis}`);
  console.log(`  SDK: TypeScript`);
  console.log("=".repeat(72)+"\n");
  console.log(`  ${"ID".padEnd(10)} ${"NL Bytes".padStart(8)} ${"OSMP Bytes".padStart(10)} ${"Reduction".padStart(10)}  Status`);
  console.log(`  ${"-".repeat(60)}`);

  for (const vec of data.vectors) {
    const nl   = utf8Bytes(vec.natural_language);
    const osmp = utf8Bytes(vec.encoded);
    const red  = Math.round((1-osmp/nl)*1000)/10;
    const conf = red >= threshold;
    let status = conf ? "PASS" : "LOW";
    if (vec.must_pass) { totalMustPass++; if (conf) passed++; }
    let decodeOk = false;
    try { const r=dec.decodeFrame(vec.encoded); decodeOk=!!(r.namespace&&r.opcode); }
    catch { status="FAIL (decode error)"; }
    const mk = (conf&&decodeOk)?"✓":"✗";
    console.log(`  ${mk} ${vec.id.padEnd(8)} ${String(nl).padStart(8)} ${String(osmp).padStart(10)} ${(red.toFixed(1)+"%").padStart(10)}  ${status}`);
    results.push({ id:vec.id, nlBytes:nl, osmpBytes:osmp, reductionPct:red,
                   expectedReductionPct:vec.reduction_pct, conformant:conf,
                   decodeOk, mustPass:vec.must_pass });
  }

  const reds = results.map(r=>r.reductionPct);
  const mean = reds.reduce((a,b)=>a+b,0)/reds.length;
  const minR = Math.min(...reds), maxR = Math.max(...reds);
  const decErr = results.filter(r=>!r.decodeOk).length;
  const conformant = mean >= threshold && decErr === 0;
  const verdict = conformant ? "CONFORMANT ✓" : "NON-CONFORMANT ✗";

  console.log(`\n${"-".repeat(72)}`);
  console.log(`  Vectors:        ${results.length}`);
  console.log(`  Must-pass:      ${totalMustPass}   Passed: ${passed}`);
  console.log(`  Mean reduction: ${mean.toFixed(1)}%`);
  console.log(`  Range:          ${minR.toFixed(1)}% – ${maxR.toFixed(1)}%`);
  console.log(`  Conformance threshold: ${threshold}%`);
  console.log(`  Decode errors:  ${decErr}`);
  console.log(`\n  ${verdict}  (mean ${mean.toFixed(1)}% vs ${threshold}% threshold)`);
  console.log("=".repeat(72)+"\n");

  return { conformant, passed, totalMustPass,
           meanReductionPct:Math.round(mean*10)/10,
           minReductionPct:Math.round(minR*10)/10,
           maxReductionPct:Math.round(maxR*10)/10,
           vectors:results };
}
