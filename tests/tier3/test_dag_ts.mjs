/**
 * OSMP Tier 3 Tests — TypeScript DAG Decomposition
 * Runs against compiled dist/ output.
 */
import { DAGFragmenter, DAGReassembler } from "../../sdk/typescript/dist/dag.js";
import { unpackFragment, packFragment } from "../../sdk/typescript/dist/overflow.js";
import { LossPolicy, FLAG_EXTENDED_DEP, FLAG_TERMINAL } from "../../sdk/typescript/dist/types.js";

const enc = new TextEncoder();
const dec = new TextDecoder();
let pass = 0, fail = 0;

function assert(cond, msg) {
  if (!cond) { console.error(`  FAIL: ${msg}`); fail++; }
  else { pass++; }
}

// ── Parse tests ──────────────────────────────────────────────────────────────

console.log("TestDAGParseSequence");
{
  const df = new DAGFragmenter();
  const nodes = df.parse("A;B;C");
  assert(nodes.length === 3, "expected 3 nodes");
  assert(nodes[0].parents.length === 0, "node 0 root");
  assert(nodes[1].parents[0] === 0, "node 1 deps 0");
  assert(nodes[2].parents[0] === 1, "node 2 deps 1");
}

console.log("TestDAGParseFork");
{
  const df = new DAGFragmenter();
  const nodes = df.parse("A;B∧C");
  assert(nodes.length === 3, "expected 3 nodes");
  assert(nodes[1].parents[0] === 0, "B deps A");
  assert(nodes[2].parents[0] === 0, "C deps A");
}

console.log("TestDAGParseDiamond");
{
  const df = new DAGFragmenter();
  const nodes = df.parse("A;B∧C;D");
  assert(nodes.length === 4, "expected 4");
  assert(nodes[3].parents.length === 2, "D has 2 parents");
  assert(nodes[3].parents.includes(1) && nodes[3].parents.includes(2), "D deps B,C");
}

// ── Fragmentize tests ────────────────────────────────────────────────────────

console.log("TestDAGFragmentizeDiamondExtDep");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B∧C;D", 1);
  const d = frags[3];
  assert(!!(d.flags & FLAG_EXTENDED_DEP), "extended dep flag");
  const dv = new DataView(d.payload.buffer, d.payload.byteOffset, 4);
  const bitmap = dv.getUint32(0, false);
  assert(!!(bitmap & (1 << 1)), "bit 1 set");
  assert(!!(bitmap & (1 << 2)), "bit 2 set");
  assert(dec.decode(d.payload.slice(4)) === "D", "payload after bitmap");
}

console.log("TestDAGFragmentizeSelfRefRoot");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B", 1);
  assert(frags[0].dep === 0, "root self-ref at idx 0");
  assert(frags[1].dep === 0, "frag 1 deps frag 0");
}

console.log("TestDAGTerminalOnLast");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B;C", 1);
  assert(!(frags[0].flags & FLAG_TERMINAL), "frag 0 not terminal");
  assert(!(frags[1].flags & FLAG_TERMINAL), "frag 1 not terminal");
  assert(!!(frags[2].flags & FLAG_TERMINAL), "frag 2 terminal");
}

// ── Pack/Unpack round trip ───────────────────────────────────────────────────

console.log("TestDAGPackUnpackRoundTrip");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B∧C;D", 1);
  for (const f of frags) {
    const packed = packFragment(f);
    const u = unpackFragment(packed);
    assert(u.msgId === f.msgId, `msgId frag ${f.fragIdx}`);
    assert(u.fragIdx === f.fragIdx, `fragIdx frag ${f.fragIdx}`);
    assert(u.flags === f.flags, `flags frag ${f.fragIdx}`);
    assert(u.dep === f.dep, `dep frag ${f.fragIdx}`);
    const orig = Array.from(f.payload);
    const unpk = Array.from(u.payload);
    assert(JSON.stringify(orig) === JSON.stringify(unpk), `payload frag ${f.fragIdx}`);
  }
}

// ── Reassembler tests ────────────────────────────────────────────────────────

console.log("TestDAGReassemblerChain");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B;C", 1);
  const dr = new DAGReassembler(LossPolicy.GRACEFUL_DEGRADATION);
  let result = null;
  for (const f of frags) result = dr.receive(f);
  assert(result && result.length === 3, "3 payloads");
  assert(dec.decode(result[0]) === "A", "first A");
  assert(dec.decode(result[1]) === "B", "second B");
  assert(dec.decode(result[2]) === "C", "third C");
}

console.log("TestDAGReassemblerDiamond");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B∧C;D", 1);
  const dr = new DAGReassembler(LossPolicy.GRACEFUL_DEGRADATION);
  let result = null;
  for (const f of frags) result = dr.receive(f);
  assert(result && result.length === 4, "4 payloads");
  assert(dec.decode(result[0]) === "A", "first A");
  assert(dec.decode(result[3]) === "D", "last D");
}

console.log("TestDAGGracefulDegradationMissingRoot");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B∧C", 1);
  const dr = new DAGReassembler(LossPolicy.GRACEFUL_DEGRADATION);
  dr.receive(frags[1]); // B
  const result = dr.receive(frags[2]); // C terminal, A missing
  assert(result && result.length === 0, "no root -> empty");
}

console.log("TestDAGGracefulDegradationMissingMiddle");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B;C", 1);
  const dr = new DAGReassembler(LossPolicy.GRACEFUL_DEGRADATION);
  dr.receive(frags[0]); // A
  const result = dr.receive(frags[2]); // C terminal, B missing
  assert(result && result.length === 1, "only A");
  assert(dec.decode(result[0]) === "A", "is A");
}

console.log("TestDAGAtomicPartialNull");
{
  const df = new DAGFragmenter();
  const frags = df.fragmentize("A;B;C", 1);
  const dr = new DAGReassembler(LossPolicy.ATOMIC);
  dr.receive(frags[0]);
  const result = dr.receive(frags[2]); // skip B
  assert(result === null, "atomic returns null on partial");
}

console.log("TestDAGEstopImmediate");
{
  const dr = new DAGReassembler(LossPolicy.ATOMIC);
  const f = { msgId: 1, fragIdx: 2, fragCt: 5, flags: 0, dep: 1,
              payload: enc.encode("R:ESTOP@BOT1") };
  const result = dr.receive(f);
  assert(result && result.length === 1, "ESTOP fires immediately");
  assert(dec.decode(result[0]).includes("R:ESTOP"), "payload has ESTOP");
}

// ── Summary ──────────────────────────────────────────────────────────────────

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
