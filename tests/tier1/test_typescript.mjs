/**
 * OSMP Tier 1 Tests — TypeScript SDK
 * Mirrors Python suite. Validates canonical dictionary v12 opcodes.
 * Run: node --test tests/tier1/test_typescript.mjs
 */
import { strict as assert } from "assert";
import { test, describe } from "node:test";
import { readFileSync } from "fs";
import {
  AdaptiveSharedDictionary, OSMPEncoder, OSMPDecoder,
  BAELEncoder, BAELMode, OverflowProtocol, LossPolicy,
  packFragment, unpackFragment, isTerminal,
  utf8Bytes, ASD_BASIS, ASD_FLOOR_VERSION,
  GLYPH_OPERATORS, CONSEQUENCE_CLASSES, OUTCOME_STATES,
  FLAG_NL_PASSTHROUGH, FRAGMENT_HEADER_BYTES, LORA_FLOOR_BYTES,
  DictUpdateMode,
} from "../../sdk/typescript/dist/index.js";

// Unicode helpers
const CC = { REV:"\u21ba", HAZ:"\u26a0", IRR:"\u2298" };
const OP = { AND:"\u2227", THEN:"\u2192", IFF:"\u2194", PAR:"\u2225", SEC:"\u00a7" };

// ── SECTION 1: CANONICAL OPCODE VERIFICATION ─────────────────────────────────
describe("Canonical Opcodes from Dictionary v12", () => {
  const cases = [
    ["Z","INF","invoke_inference"],
    ["V","HDG","heading"],
    ["V","ROUTE","routing_instruction"],
    ["D","PACK","two_tier_corpus_encoding_for_at_rest_storage"],
    ["D","UNPACK","inference_free_semantic_retrieval_from_encoded_corpus"],
    ["H","ICD","ICD-10_diagnosis_code_accessor"],
    ["H","SNOMED","SNOMED_CT_concept_identifier_accessor"],
    ["H","CPT","CPT_procedure_code_accessor"],
    ["N","INET","internet_uplink_capability_query"],
    ["A","CMPR","structured_comparison_returning_result"],
    ["C","ALLOC","resource_allocation"],
    ["C","FREE","release_resource"],
    ["S","ROTATE","key_rotation"],
    ["T","AFTER","execute_after_condition"],
    ["T","BEFORE","execute_before_deadline"],
    ["U","ALERT","urgent_operator_alert"],
    ["U","DISPLAY","display_information_to_operator"],
    ["U","INPUT","request_operator_input"],
    ["Y","RETRIEVE","retrieve_from_LCS"],
    ["Z","ROUTE","route_to_model_with_specified_capability"],
    ["L","QUERY","audit_trail_query"],
    ["Q","CORRECT","correction_directive"],
    ["H","HR","heart_rate"],
    ["R","ESTOP","emergency_stop"],
    ["I","\u00a7","human_operator_confirmation"],
  ];
  for (const [ns,op,expected] of cases) {
    test(`${ns}:${op} = ${expected}`, () => {
      assert.equal(new AdaptiveSharedDictionary().lookup(ns,op), expected);
    });
  }

  test("Z:INFER absent — canonical is Z:INF", () =>
    assert.equal(new AdaptiveSharedDictionary().lookup("Z","INFER"), null));
  test("V:HDNG absent — canonical is V:HDG", () =>
    assert.equal(new AdaptiveSharedDictionary().lookup("V","HDNG"), null));
  test("V:ROUT absent — canonical is V:ROUTE", () =>
    assert.equal(new AdaptiveSharedDictionary().lookup("V","ROUT"), null));
  test("total opcodes ≥ 339", () => {
    const total = Object.values(ASD_BASIS).reduce((s,v)=>s+Object.keys(v).length,0);
    assert.ok(total >= 339, `got ${total}`);
  });
  test("all 26 namespaces present", () => {
    for (const c of "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
      assert.ok(c in ASD_BASIS, `missing ${c}`);
  });
});

// ── SECTION 2: DECODER ────────────────────────────────────────────────────────
describe("Decoder — All Namespaces", () => {
  const cases = [
    ["A:SUM","A","SUM"], ["B:BA","B","BA"], ["C:SPAWN","C","SPAWN"],
    ["D:PACK","D","PACK"], ["D:UNPACK","D","UNPACK"], ["D:XFER","D","XFER"],
    ["E:TH","E","TH"], ["F:Q","F","Q"], ["G:POS","G","POS"],
    ["H:HR","H","HR"], ["H:ICD","H","ICD"], ["H:SNOMED","H","SNOMED"],
    ["I:KYC","I","KYC"], ["J:GOAL","J","GOAL"], ["K:PAY","K","PAY"],
    ["L:AUDIT","L","AUDIT"], ["M:EVA","M","EVA"], ["N:CFG","N","CFG"],
    ["N:INET","N","INET"], ["O:MODE","O","MODE"], ["P:GUIDE","P","GUIDE"],
    ["Q:SCORE","Q","SCORE"], ["R:ESTOP","R","ESTOP"], ["S:ENC","S","ENC"],
    ["S:ROTATE","S","ROTATE"], ["T:NOW","T","NOW"], ["T:AFTER","T","AFTER"],
    ["T:BEFORE","T","BEFORE"], ["U:ESCALATE","U","ESCALATE"],
    ["U:ALERT","U","ALERT"], ["U:DISPLAY","U","DISPLAY"],
    ["V:POS","V","POS"], ["V:HDG","V","HDG"], ["V:ROUTE","V","ROUTE"],
    ["W:METAR","W","METAR"], ["X:GEN","X","GEN"], ["Y:SEARCH","Y","SEARCH"],
    ["Y:RETRIEVE","Y","RETRIEVE"], ["Z:INF","Z","INF"], ["Z:ROUTE","Z","ROUTE"],
  ];
  for (const [encoded,ns,op] of cases) {
    test(`${encoded}`, () => {
      const r = new OSMPDecoder().decodeFrame(encoded);
      assert.equal(r.namespace, ns, `ns`);
      assert.equal(r.opcode, op, `op`);
    });
  }
});

describe("Decoder — Core Behaviors", () => {
  test("MEDEVAC chain — target includes threshold", () => {
    const r = new OSMPDecoder().decodeFrame(`H:HR@NODE1>120${OP.THEN}H:CASREP${OP.AND}M:EVA@*`);
    assert.equal(r.namespace,"H"); assert.equal(r.opcode,"HR"); assert.equal(r.target,"NODE1>120");
  });
  test("short-form EQ", () => {
    const r = new OSMPDecoder().decodeFrame("EQ@4A?TH:0");
    assert.equal(r.namespace,"E"); assert.equal(r.opcode,"EQ"); assert.equal(r.target,"4A");
  });
  test("short-form BA", () => {
    const r = new OSMPDecoder().decodeFrame("BA@BS!");
    assert.equal(r.namespace,"B"); assert.equal(r.opcode,"BA");
  });
  test("consequence class REVERSIBLE", () => {
    const r = new OSMPDecoder().decodeFrame(`R:TORCH@PHONE1:ON${CC.REV}`);
    assert.equal(r.consequenceClass, CC.REV); assert.equal(r.consequenceClassName,"REVERSIBLE");
  });
  test("consequence class HAZARDOUS", () => {
    const r = new OSMPDecoder().decodeFrame(`R:CAM@NODE${CC.HAZ}`);
    assert.equal(r.consequenceClassName,"HAZARDOUS");
  });
  test("consequence class IRREVERSIBLE", () => {
    const r = new OSMPDecoder().decodeFrame(`R:DRVE@BOT1${CC.IRR}`);
    assert.equal(r.consequenceClassName,"IRREVERSIBLE");
  });
  test("human confirmation opcode I:§", () => {
    const r = new OSMPDecoder().decodeFrame(`I:${OP.SEC}`);
    assert.equal(r.opcode,OP.SEC); assert.equal(r.opcodeMeaning,"human_operator_confirmation");
  });
  test("D:PACK meaning", () => {
    const r = new OSMPDecoder().decodeFrame("D:PACK");
    assert.ok(r.opcodeMeaning?.includes("at_rest") || r.opcodeMeaning?.includes("corpus"));
  });
  test("D:UNPACK meaning", () => {
    const r = new OSMPDecoder().decodeFrame("D:UNPACK");
    assert.ok(r.opcodeMeaning?.includes("inference_free"));
  });
  test("operational context", () => {
    const r = new OSMPDecoder().decodeFrame(`O:MODE:E${OP.AND}O:TYPE:1`);
    assert.equal(r.namespace,"O"); assert.equal(r.opcode,"MODE");
  });
  test("BAEL passthrough raw preserved", () =>
    assert.equal(new OSMPDecoder().decodeFrame("Stop").raw,"Stop"));
  test("raw preserved", () =>
    assert.equal(new OSMPDecoder().decodeFrame("H:HR@NODE1").raw,"H:HR@NODE1"));
});

// ── SECTION 3: ENCODER ────────────────────────────────────────────────────────
describe("Encoder", () => {
  test("basic frame", () => assert.equal(new OSMPEncoder().encodeFrame("H","HR"),"H:HR"));
  test("with target", () => assert.equal(new OSMPEncoder().encodeFrame("H","HR","NODE1"),"H:HR@NODE1"));
  test("R without cc throws", () => assert.throws(()=>new OSMPEncoder().encodeFrame("R","MOV","B"),/consequence/i));
  test("R reversible", () => {
    const r = new OSMPEncoder().encodeFrame("R","TORCH","P1",undefined,undefined,CC.REV);
    assert.ok(r.endsWith(CC.REV));
  });
  test("sequence", () => assert.equal(new OSMPEncoder().encodeSequence(["A:SUM","A:ACK"]),"A:SUM;A:ACK"));
  test("broadcast", () => assert.equal(new OSMPEncoder().encodeBroadcast("M","EVA"),"M:EVA@*"));
});

// ── SECTION 4: ASD DELTA ─────────────────────────────────────────────────────
describe("ASD Delta (CRDT)", () => {
  test("additive does not overwrite", () => {
    const a = new AdaptiveSharedDictionary();
    a.applyDelta("H","HR","WRONG",DictUpdateMode.ADDITIVE,"v2");
    assert.equal(a.lookup("H","HR"),"heart_rate");
  });
  test("replace overwrites", () => {
    const a = new AdaptiveSharedDictionary();
    a.applyDelta("H","HR","new",DictUpdateMode.REPLACE,"v2");
    assert.equal(a.lookup("H","HR"),"new");
  });
  test("deprecate tombstones", () => {
    const a = new AdaptiveSharedDictionary();
    a.applyDelta("H","HR","",DictUpdateMode.DEPRECATE,"v2");
    assert.equal(a.lookup("H","HR"),null);
  });
  test("fingerprint stable", () => {
    const a = new AdaptiveSharedDictionary();
    assert.equal(a.fingerprint(), a.fingerprint());
  });
  test("fingerprint changes after delta", () => {
    const a = new AdaptiveSharedDictionary(); const fp = a.fingerprint();
    a.applyDelta("\u03a9","X","def",DictUpdateMode.ADDITIVE,"v2");
    assert.notEqual(a.fingerprint(), fp);
  });
});

// ── SECTION 5: OVERFLOW PROTOCOL ─────────────────────────────────────────────
describe("Overflow Protocol", () => {
  test("tier1 single fragment", () => {
    assert.equal(new OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION).fragment(Buffer.from("H:HR")).length,1);
  });
  test("tier1 round-trip", () => {
    const op = new OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION);
    const p = Buffer.from("H:HR@NODE1");
    assert.deepEqual(Buffer.from(op.receive(op.fragment(p)[0])), p);
  });
  test("tier2 multi-fragment", () => {
    assert.ok(new OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION).fragment(Buffer.alloc(300)).length > 1);
  });
  test("tier2 full reassembly", () => {
    const op = new OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION);
    const p = Buffer.alloc(500,0x58);
    let r=null; for(const f of op.fragment(p)) r=op.receive(f);
    assert.deepEqual(Buffer.from(r), p);
  });
  test("LoRa floor: fragments ≤ 51 bytes", () => {
    const op = new OverflowProtocol(LORA_FLOOR_BYTES,LossPolicy.GRACEFUL_DEGRADATION);
    const p = Buffer.from(`H:HR@NODE1>120${OP.THEN}H:CASREP${OP.AND}M:EVA@*`.repeat(2));
    const frags = op.fragment(p); assert.ok(frags.length > 1);
    for (const f of frags) assert.ok(packFragment(f).length <= LORA_FLOOR_BYTES);
  });
  test("ESTOP fires under ATOMIC", () => {
    const op = new OverflowProtocol(255,LossPolicy.ATOMIC);
    assert.ok(op.receive(op.fragment(Buffer.from("R:ESTOP"))[0]) !== null);
  });
  test("ESTOP fires on non-terminal fragment", () => {
    const op = new OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION);
    const frag={msgId:1,fragIdx:0,fragCt:3,flags:0,dep:0,payload:Buffer.from("R:ESTOP@BOT1")};
    assert.ok(op.receive(frag) !== null);
  });
  test("atomic null on partial", () => {
    const op = new OverflowProtocol(255,LossPolicy.ATOMIC);
    const frags = op.fragment(Buffer.alloc(300));
    if(frags.length>1) assert.equal(op.receive(frags[0]),null);
  });
  test("pack/unpack round-trip", () => {
    const op = new OverflowProtocol(255,LossPolicy.GRACEFUL_DEGRADATION);
    const f = op.fragment(Buffer.from("R:ESTOP@*"))[0];
    const u = unpackFragment(packFragment(f));
    assert.equal(u.msgId,f.msgId);
    assert.deepEqual(Buffer.from(u.payload),Buffer.from(f.payload));
  });
});

// ── SECTION 6: BAEL ───────────────────────────────────────────────────────────
describe("BAEL", () => {
  test("NL passthrough when shorter", () => {
    const r = BAELEncoder.selectMode("Stop","R:ESTOP@*");
    assert.equal(r.mode,BAELMode.NL_PASSTHROUGH); assert.equal(r.payload,"Stop");
  });
  test("FULL_OSMP when shorter", () => {
    const r = BAELEncoder.selectMode("If heart rate exceeds 120, assemble report.","H:HR@NODE1>120"+OP.THEN+"H:CASREP");
    assert.equal(r.mode,BAELMode.FULL_OSMP);
  });
  test("never expands beyond NL", () => {
    for(const [nl,osmp] of [["Go","A:DA@X"],["Stop","R:ESTOP@*"],["OK","A:ACK"]]) {
      const r = BAELEncoder.selectMode(nl,osmp);
      assert.ok(utf8Bytes(r.payload)<=utf8Bytes(nl));
    }
  });
  test("\u00ac NOT SIGN is 2 bytes", () => assert.equal(utf8Bytes("\u00ac"),2));
  test("3-byte glyphs", () => {
    for(const g of [OP.AND,OP.THEN,OP.IFF,OP.PAR,"\u2200","\u2203","\u26a0","\u21ba","\u2298"])
      assert.equal(utf8Bytes(g),3,`U+${g.codePointAt(0).toString(16).toUpperCase()}`);
  });
  test("1-byte ASCII glyphs", () => {
    for(const g of ["@",">","~","*",":",";","?"])
      assert.equal(utf8Bytes(g),1,g);
  });
});

// ── SECTION 7: CANONICAL TEST VECTORS ────────────────────────────────────────
describe("Canonical Test Vectors", () => {
  const data = JSON.parse(readFileSync("protocol/test-vectors/canonical-test-vectors.json","utf8"));
  test("all 48 decode without error", () => {
    const dec = new OSMPDecoder(); const errors = [];
    for(const v of data.vectors) {
      try { const r=dec.decodeFrame(v.encoded); if(!r.namespace||!r.opcode) errors.push(v.id); }
      catch(e) { errors.push(`${v.id}:${e.message}`); }
    }
    assert.equal(errors.length,0,"Errors:\n"+errors.join("\n"));
  });
  test("byte counts match spec", () => {
    const errors = [];
    for(const v of data.vectors) {
      if(utf8Bytes(v.natural_language)!==v.nl_bytes) errors.push(`${v.id}:nl`);
      if(utf8Bytes(v.encoded)!==v.osmp_bytes) errors.push(`${v.id}:osmp`);
    }
    assert.equal(errors.length,0,errors.join(","));
  });
  test("mean reduction ≥ 60%", () => {
    const mean = data.vectors.reduce((s,v)=>s+v.reduction_pct,0)/data.vectors.length;
    assert.ok(mean>=data.compression_summary.conformance_threshold_pct,`mean=${mean.toFixed(1)}%`);
  });
  test("zero decode errors (conformance verdict)", () => {
    const dec=new OSMPDecoder(); let e=0;
    for(const v of data.vectors){try{const r=dec.decodeFrame(v.encoded);if(!r.namespace||!r.opcode)e++;}catch{e++;}}
    assert.equal(e,0);
  });
});
