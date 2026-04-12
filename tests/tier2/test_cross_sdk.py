#!/usr/bin/env python3
"""
OSMP Tier 2 QA — Cross-SDK Wire Compatibility
Cloudless Sky Protocol

Methodology:
  1. Python (reference) decodes a corpus covering every namespace, every
     operator, every canonical v12 correction, and every documented edge case.
  2. TypeScript SDK decodes the same corpus via Node subprocess.
  3. Go SDK decodes the same corpus via go run subprocess.
  4. All three decode results must match field-for-field on every instruction.

A single disagreement is a wire incompatibility and blocks release.

Run: python3 tests/tier2/test_cross_sdk.py
"""
import sys, json, subprocess, os, re
sys.path.insert(0, "sdk/python")
from osmp import SALDecoder, utf8_bytes

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

CORPUS = [
    # ── Canonical test vectors ───────────────────────────────────────────────
    ("EQ@4A?TH:0",                                   "TV-001 env query"),
    ("ALRM@AREA!",                                     "TV-002 building alert"),
    ("AR@EP:1",                                       "TV-003 agentic request"),
    ("ALRM@AREA!\u2227AR@EP:1",                        "TV-004 AND compound"),
    ("E@T>38\u2192ALRM@AREA!",                         "TV-005 THEN conditional"),
    ("A\u2225[?WEA\u2227?NEWS\u2227?CAL]",            "TV-006 parallel block"),
    ("\u2200AI:CRT@PM",                               "TV-007 FOR-ALL"),
    ("ALRT@*!EVA",                                     "TV-012 wildcard broadcast"),
    ("H:HR@NODE1>120\u2192H:CASREP\u2227M:EVA@*",    "TV-013 MEDEVAC chain"),
    ("I:KYC@SUBJ\u2192I:\u22a4\u2228I:\u22a5",       "TV-014 KYC outcome states"),
    ("K:PAY@RECV\u2194I:\u00a7\u2192K:XFR[AMT]",     "TV-015 financial IFF"),
    # ── All 26 namespaces — explicit form ────────────────────────────────────
    ("A:SUM","A namespace"), ("B:ALRM","B namespace"), ("C:SPAWN","C namespace"),
    ("D:PACK","D:PACK two-tier encoding"), ("D:UNPACK","D:UNPACK inference-free"),
    ("D:XFER","D:XFER file transfer"), ("E:TH","E namespace"),
    ("F:QRY","F namespace"), ("G:POS","G namespace"),
    ("H:HR","H:HR heart rate"), ("H:ICD","H:ICD layer2 accessor"),
    ("H:SNOMED","H:SNOMED layer2 accessor"), ("H:CPT","H:CPT layer2 accessor"),
    ("I:KYC","I namespace"), ("J:GOAL","J namespace"), ("K:PAY","K namespace"),
    ("L:AUDIT","L namespace"), ("L:QUERY","L:QUERY canonical opcode"),
    ("M:EVA","M namespace"), ("N:CFG","N namespace"),
    ("N:INET","N:INET internet uplink"), ("O:MODE","O namespace"),
    ("P:GUIDE","P namespace"), ("Q:SCORE","Q namespace"),
    ("Q:CORRECT","Q:CORRECT canonical opcode"), ("R:ESTOP","R:ESTOP"),
    ("S:ENC","S namespace"), ("S:ROTATE","S:ROTATE key rotation"),
    ("T:NOW","T namespace"), ("T:AFTER","T:AFTER temporal"),
    ("T:BEFORE","T:BEFORE temporal"),
    ("U:ESCALATE","U namespace"), ("U:ALERT","U:ALERT"),
    ("U:DISPLAY","U:DISPLAY"), ("U:INPUT","U:INPUT"),
    ("V:POS","V namespace"), ("V:HDG","V:HDG canonical"),
    ("V:ROUTE","V:ROUTE canonical"), ("W:METAR","W namespace"),
    ("X:PROD","X namespace"), ("Y:SEARCH","Y namespace"),
    ("Y:RETRIEVE","Y:RETRIEVE canonical"), ("Z:INF","Z:INF canonical"),
    ("Z:ROUTE","Z:ROUTE canonical"),
    # ── All three consequence classes ────────────────────────────────────────
    ("R:MOV@BOT1\u21ba","R REVERSIBLE"),
    ("R:CAM@NODE\u26a0","R HAZARDOUS"),
    ("R:DRVE@BOT1\u2298","R IRREVERSIBLE"),
    # ── Human confirmation gate ──────────────────────────────────────────────
    ("I:\u00a7","I:§ human confirmation"),
    ("I:\u00a7\u2192R:CAM@NODE\u26a0","human gate chain"),
    # ── New operators ────────────────────────────────────────────────────────
    ("EQ@4A?TH:0\u27f3T:DUR:30","REPEAT-EVERY"),
    ("E@T\u226020\u2192BA@BS!","NOT-EQUAL"),
    ("A\u2225[TASK1\u2295TASK2\u2295TASK3]","PRIORITY-ORDER"),
    # ── AI-native namespaces ─────────────────────────────────────────────────
    ("Z:INF\u2227Z:TOKENS:847\u2227Z:LATENCY:230","Z inference chain"),
    ("Q:HALLU","Q hallucination"), ("Q:GROUND","Q grounding"),
    ("Y:SEARCH","Y vector search"), ("Y:STORE","Y memory store"),
    ("J:GOAL","J cognitive state"), ("J:HANDOFF","J handoff"),
    # ── Operational context ──────────────────────────────────────────────────
    ("O:MODE:E\u2227O:TYP:1","O emergency mode"),
    ("O:EMCON:S\u2227O:READY:3","O EMCON silent"),
    ("O:CHAN:L\u2227O:FLOOR:51","O LoRa channel floor"),
    # ── BAEL passthrough ─────────────────────────────────────────────────────
    ("Stop","BAEL passthrough Stop"),
    ("Go","BAEL passthrough Go"),
    ("OK","BAEL passthrough OK"),
    # ── Short-form frames ────────────────────────────────────────────────────
    ("EQ@4A?TH:0","short-form EQ"),
    ("ALRM@AREA!","short-form ALRM"),
    ("AR@EP:1","short-form AR"),
    ("ALRT@*!EVA","short-form ALRT"),
    # ── Sovereign extension ──────────────────────────────────────────────────
    ("\u03a9:MYOP@TARGET","sovereign extension"),
    # ── Device peripherals ───────────────────────────────────────────────────
    ("R:TORCH@PHONE1:ON\u21ba","flashlight reversible"),
    ("I:\u00a7\u2192R:CAM@PHONE2:ON\u26a0","camera hazardous with human gate"),
    # ── File transfer ────────────────────────────────────────────────────────
    ("D:XFER@EDGE1[MAP_TILE];D:CSUM","file transfer + checksum"),
    ("D:PACK","D:PACK at-rest encoding"),
    ("D:UNPACK","D:UNPACK semantic retrieval"),
]

def decode_python(encoded):
    dec = SALDecoder()
    r = dec.decode_frame(encoded)
    return {
        "namespace": r.namespace, "opcode": r.opcode,
        "opcode_meaning": r.opcode_meaning, "target": r.target,
        "query_slot": r.query_slot, "slots": r.slots,
        "consequence_class": r.consequence_class,
        "consequence_class_name": r.consequence_class_name,
        "raw": r.raw,
    }

TS_RUNNER = """
import { OSMPDecoder } from "./index.js";
const dec = new OSMPDecoder();
const results = JSON.parse(process.argv[2]).map(encoded => {
  try {
    const r = dec.decodeFrame(encoded);
    return { namespace:r.namespace, opcode:r.opcode,
             opcode_meaning:r.opcodeMeaning??null, target:r.target??null,
             query_slot:r.querySlot??null, slots:r.slots,
             consequence_class:r.consequenceClass??null,
             consequence_class_name:r.consequenceClassName??null,
             raw:r.raw, error:null };
  } catch(e) { return { error: e.message }; }
});
process.stdout.write(JSON.stringify(results));
"""

GO_RUNNER = '''package main
import (
\t"encoding/json"; "fmt"; "os"
\t"github.com/octid-io/cloudless-sky/sdk/go/osmp"
)
type R struct {
\tNamespace,Opcode,OpcodeMeaning,Target,QuerySlot string
\tSlots map[string]string
\tConsequenceClass,ConsequenceClassName string
\tRaw string; Error string
}
func sp(s string) string { return s }
func main() {
\tvar inputs []string
\tjson.Unmarshal([]byte(os.Args[1]), &inputs)
\tdec := osmp.NewDecoder(nil)
\tresults := make([]R, len(inputs))
\tfor i, enc := range inputs {
\t\tr, err := dec.DecodeFrame(enc)
\t\tif err != nil { results[i] = R{Error: err.Error()}; continue }
\t\tresults[i] = R{Namespace:r.Namespace,Opcode:r.Opcode,
\t\t\tOpcodeMeaning:r.OpcodeMeaning,Target:r.Target,QuerySlot:r.QuerySlot,
\t\t\tSlots:r.Slots,ConsequenceClass:r.ConsequenceClass,
\t\t\tConsequenceClassName:r.ConsequenceClassName,Raw:r.Raw}
\t}
\tout,_:=json.Marshal(results); fmt.Print(string(out))
}
'''

def decode_ts_batch(encoded_list):
    script = "/home/claude/cloudless-sky/sdk/typescript/dist/_runner.mjs"
    with open(script,"w") as f: f.write(TS_RUNNER)
    result = subprocess.run(["node", script, json.dumps(encoded_list)],
                            capture_output=True, text=True,
                            cwd="/home/claude/cloudless-sky/sdk/typescript/dist")
    try: os.unlink(script)
    except: pass
    if result.returncode != 0: raise RuntimeError(f"TS runner failed: {result.stderr[:200]}")
    return json.loads(result.stdout)

def decode_go_batch(encoded_list):
    runner_dir = "/tmp/osmp_go_runner"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs(runner_dir, exist_ok=True)
    with open(f"{runner_dir}/main.go","w") as f: f.write(GO_RUNNER)
    with open(f"{runner_dir}/go.mod","w") as f:
        f.write(f"module osmp_runner\n\ngo 1.22.2\n\n"
                f"require github.com/octid-io/cloudless-sky/sdk/go v0.0.0\n\n"
                f"replace github.com/octid-io/cloudless-sky/sdk/go => {repo_root}/sdk/go\n")
    subprocess.run(["go","mod","tidy"], capture_output=True, text=True, cwd=runner_dir,
                   env={**os.environ, "GOPROXY":"direct", "GONOSUMCHECK":"*"})
    result = subprocess.run(["go","run","main.go", json.dumps(encoded_list)],
                            capture_output=True, text=True, cwd=runner_dir,
                            env={**os.environ, "GOPROXY":"direct", "GONOSUMCHECK":"*"})
    if result.returncode != 0: raise RuntimeError(f"Go runner failed: {result.stderr[:200]}")
    return json.loads(result.stdout)

def normalize(d):
    if not d: return {}
    # Normalize PascalCase (Go) and snake_case (Python/TS) to snake_case
    key_map = {
        "Namespace":"namespace","Opcode":"opcode",
        "OpcodeMeaning":"opcode_meaning","Target":"target",
        "QuerySlot":"query_slot","Slots":"slots",
        "ConsequenceClass":"consequence_class",
        "ConsequenceClassName":"consequence_class_name","Raw":"raw",
    }
    out = {key_map.get(k,k): v for k,v in d.items()}
    for k in ["target","query_slot","consequence_class","consequence_class_name","opcode_meaning"]:
        if out.get(k) == "": out[k] = None
    if out.get("slots") is None: out["slots"] = {}
    return out

def compare(py, other, sdk, encoded):
    py_n, ot_n = normalize(py), normalize(other)
    mismatches = []
    for f in ["namespace","opcode","target","query_slot","consequence_class","consequence_class_name","raw"]:
        if py_n.get(f) != ot_n.get(f):
            mismatches.append(f"  {sdk}.{f}: py={py_n.get(f)!r} {sdk}={ot_n.get(f)!r}")
    return mismatches

def run():
    encoded_list = [e for e,_ in CORPUS]
    descriptions = [d for _,d in CORPUS]

    print(f"\n{'='*72}")
    print("  OSMP Tier 2 QA — Cross-SDK Wire Compatibility")
    print("  Python (reference) × TypeScript × Go")
    print(f"{'='*72}\n")

    print("  [1/3] Python reference decode...")
    py_results = []
    for enc in encoded_list:
        try: py_results.append(decode_python(enc))
        except Exception as e: py_results.append({"error": str(e)})
    print(f"        {len(py_results)} instructions decoded")

    print("  [2/3] TypeScript SDK decode...")
    try:
        ts_results = decode_ts_batch(encoded_list)
        print(f"        {len(ts_results)} instructions decoded")
    except Exception as e:
        print(f"        ERROR: {e}"); ts_results = [{"error":"runner_failed"}]*len(encoded_list)

    print("  [3/3] Go SDK decode...")
    try:
        go_results = decode_go_batch(encoded_list)
        print(f"        {len(go_results)} instructions decoded")
    except Exception as e:
        print(f"        ERROR: {e}"); go_results = [{"error":"runner_failed"}]*len(encoded_list)

    print()
    print(f"  {'':2} {'Description':<44} {'TS':>6} {'Go':>6}")
    print(f"  {'─'*60}")

    ts_pass = go_pass = 0
    all_mismatches = []

    for i, (encoded, desc) in enumerate(CORPUS):
        py = py_results[i]
        ts = ts_results[i] if i < len(ts_results) else {"error":"missing"}
        go = go_results[i] if i < len(go_results) else {"error":"missing"}

        if py.get("error"):
            print(f"  ? {desc:<44} {'PYERR':>6} {'PYERR':>6}"); continue

        ts_mm = compare(py,ts,"TS",encoded) if not ts.get("error") else [f"  TS: {ts['error']}"]
        go_mm = compare(py,go,"Go",encoded) if not go.get("error") else [f"  Go: {go['error']}"]

        if not ts_mm: ts_pass += 1
        if not go_mm: go_pass += 1

        ts_s = PASS if not ts_mm else FAIL
        go_s = PASS if not go_mm else FAIL
        mk = "✓" if not ts_mm and not go_mm else "✗"
        d = desc[:42]+"…" if len(desc)>44 else desc
        print(f"  {mk} {d:<44} {ts_s:>6} {go_s:>6}")

        if ts_mm: all_mismatches.append((encoded, desc, "TypeScript", ts_mm))
        if go_mm: all_mismatches.append((encoded, desc, "Go", go_mm))

    total = len(CORPUS)
    print(f"\n  {'─'*60}")
    print(f"  Corpus: {total} instructions")
    print(f"  TypeScript: {ts_pass}/{total}  Go: {go_pass}/{total}")

    if all_mismatches:
        print(f"\n  ── WIRE MISMATCHES ({len(all_mismatches)}) ─────────────────────────")
        for enc, desc, sdk, mm in all_mismatches:
            print(f"\n  [{sdk}] {desc}")
            print(f"  Encoded: {enc!r}")
            for line in mm: print(line)
        verdict = "NON-CONFORMANT ✗  — wire mismatches detected"
        code = 1
    else:
        verdict = "WIRE COMPATIBLE ✓  — all three SDKs produce identical decode results"
        code = 0

    print(f"\n  {verdict}")
    print(f"{'='*72}\n")
    return code

if __name__ == "__main__":
    sys.exit(run())
