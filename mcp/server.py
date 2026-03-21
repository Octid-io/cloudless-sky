"""
OSMP MCP Server -- Octid Semantic Mesh Protocol
Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# -- Resolve repo root and import the Python SDK --------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = REPO_ROOT / "sdk" / "python" / "src"
sys.path.insert(0, str(SDK_PATH))

from osmp import (  # noqa: E402
    SALEncoder,
    SALDecoder,
    BlockCompressor,
    AdaptiveSharedDictionary,
    DAGFragmenter,
    DAGReassembler,
    LossPolicy,
    run_benchmark,
)

# -- Paths ----------------------------------------------------------------
MDR_DIR = REPO_ROOT / "mdr"
VECTORS_PATH = REPO_ROOT / "protocol" / "test-vectors" / "canonical-test-vectors.json"

MDR_CORPORA = {
    "icd": MDR_DIR / "icd10cm" / "MDR-ICD10CM-FY2026-blk.dpack",
    "icd10cm": MDR_DIR / "icd10cm" / "MDR-ICD10CM-FY2026-blk.dpack",
    "iso": MDR_DIR / "iso20022" / "MDR-ISO20022-K-ISO-blk.dpack",
    "iso20022": MDR_DIR / "iso20022" / "MDR-ISO20022-K-ISO-blk.dpack",
}

# -- Singleton instances --------------------------------------------------
_encoder = SALEncoder()
_decoder = SALDecoder()
_bc = BlockCompressor(use_dict=False)
_mdr_cache: dict[str, bytes] = {}


def _load_mdr(corpus: str) -> bytes:
    key = corpus.lower().strip()
    if key not in MDR_CORPORA:
        raise ValueError(f"Unknown corpus '{corpus}'. Available: {', '.join(sorted(set(MDR_CORPORA.keys())))}")
    if key not in _mdr_cache:
        path = MDR_CORPORA[key]
        if not path.exists():
            raise FileNotFoundError(f"MDR binary not found: {path}")
        _mdr_cache[key] = path.read_bytes()
    return _mdr_cache[key]


# -- MCP Server -----------------------------------------------------------
mcp = FastMCP(
    "osmp",
    instructions="Use when encoding agent instructions, reducing inter-agent token spend, or resolving domain codes (ICD-10, ISO 20022). 60%+ byte reduction over JSON. Deterministic decode by table lookup.",
)


# -- Tools ----------------------------------------------------------------

@mcp.tool()
def osmp_encode(
    namespace: str,
    opcode: str,
    target: str | None = None,
    query_slot: str | None = None,
    consequence_class: str | None = None,
) -> str:
    """Encode structured fields into a SAL instruction. Use osmp_lookup to find valid namespaces and opcodes."""
    return _encoder.encode_frame(
        namespace=namespace, opcode=opcode, target=target,
        query_slot=query_slot, consequence_class=consequence_class,
    )


@mcp.tool()
def osmp_decode(sal: str) -> str:
    """Decode SAL to structured fields. Handles compound instructions."""
    parts = re.split(r'([→∧∨;])', sal.strip())
    frames = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part in '→∧∨;':
            frames.append({"operator": part, "meaning": {
                "→": "THEN", "∧": "AND", "∨": "OR", ";": "SEQUENCE"
            }.get(part, part)})
            continue
        try:
            decoded = _decoder.decode_frame(part)
            result = asdict(decoded)
            result["natural_language"] = _decoder.decode_natural_language(part)
            frames.append(result)
        except Exception:
            frames.append({"raw": part, "error": "could not decode"})
    return json.dumps({
        "instruction": sal,
        "total_bytes": len(sal.encode("utf-8")),
        "frames": frames,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_compound_decode(sal: str) -> str:
    """Analyze DAG topology and loss tolerance behavior of a compound SAL instruction."""
    fragmenter = DAGFragmenter()
    nodes = fragmenter.parse(sal)

    dag_nodes = []
    for node in nodes:
        payload_str = node.payload.decode("utf-8", errors="replace")
        try:
            d = _decoder.decode_frame(payload_str)
            decoded = {
                "namespace": d.namespace, "opcode": d.opcode,
                "meaning": d.opcode_meaning, "target": d.target,
            }
        except Exception:
            decoded = {"raw": payload_str}
        dag_nodes.append({
            "index": node.index, "payload": payload_str,
            "parents": node.parents, "is_root": len(node.parents) == 0,
            "decoded": decoded,
        })

    frags = fragmenter.fragmentize(sal, msg_id=0)
    wire = [{"frag_idx": f.frag_idx, "dep": f.dep, "flags": f.flags,
             "packed_bytes": len(f.pack())} for f in frags]

    loss = {}
    for policy_name, policy_enum in [
        ("Phi", LossPolicy.FAIL_SAFE),
        ("Gamma", LossPolicy.GRACEFUL_DEGRADATION),
        ("Lambda", LossPolicy.ATOMIC),
    ]:
        reasm = DAGReassembler(policy=policy_enum)
        full_frags = fragmenter.fragmentize(sal, msg_id=1)
        result = None
        for f in full_frags:
            result = reasm.receive(f)
        full_exec = [p.decode("utf-8", errors="replace") for p in result] if result else []

        drops = []
        if len(nodes) > 1:
            for drop_idx in range(len(nodes)):
                reasm_d = DAGReassembler(policy=policy_enum)
                d_frags = fragmenter.fragmentize(sal, msg_id=100 + drop_idx)
                partial = None
                for f in d_frags:
                    if f.frag_idx == drop_idx:
                        continue
                    partial = reasm_d.receive(f)
                if partial is None and policy_enum == LossPolicy.GRACEFUL_DEGRADATION:
                    remaining = [f for f in d_frags if f.frag_idx != drop_idx]
                    if remaining:
                        from copy import copy
                        reasm_d2 = DAGReassembler(policy=policy_enum)
                        for f in remaining[:-1]:
                            reasm_d2.receive(f)
                        last = copy(remaining[-1])
                        last.flags |= 0x01
                        partial = reasm_d2.receive(last)
                survived = [p.decode("utf-8", errors="replace") for p in partial] if partial else []
                drops.append({"dropped": drop_idx, "executes": survived})
        loss[policy_name] = {"full": full_exec, "drops": drops}

    return json.dumps({
        "instruction": sal, "total_bytes": len(sal.encode("utf-8")),
        "node_count": len(nodes), "dag": dag_nodes,
        "wire": wire, "loss_tolerance": loss,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_lookup(namespace: str = "", keyword: str = "") -> str:
    """Search the opcode dictionary by namespace and/or keyword."""
    asd = AdaptiveSharedDictionary()
    results = []
    kw = keyword.lower().strip()
    ns = namespace.upper().strip()
    for n, ops in sorted(asd._data.items()):
        if ns and n != ns:
            continue
        for op, defn in sorted(ops.items()):
            if kw and kw not in op.lower() and kw not in defn.lower():
                continue
            results.append({"ns": n, "op": op, "def": defn})
    return json.dumps({"match_count": len(results), "results": results},
                      indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_resolve(code: str, corpus: str = "icd") -> str:
    """Resolve a domain code from D:PACK/BLK. Corpora: icd (74,719), iso (47,835)."""
    try:
        data = _load_mdr(corpus)
    except (ValueError, FileNotFoundError) as e:
        return str(e)
    result = _bc.resolve(data, code)
    if result is None:
        return f"Not found: {code}"
    return f"{code}: {result}"


@mcp.tool()
def osmp_batch_resolve(codes: str, corpus: str = "icd") -> str:
    """Resolve multiple comma-separated domain codes in one call."""
    try:
        data = _load_mdr(corpus)
    except (ValueError, FileNotFoundError) as e:
        return str(e)
    results = []
    for code in (c.strip() for c in codes.split(",") if c.strip()):
        r = _bc.resolve(data, code)
        results.append({"code": code, "description": r})
    return json.dumps({"results": results}, indent=2, ensure_ascii=False)


_corpus_cache: dict[str, dict[str, str]] = {}


@mcp.tool()
def osmp_discover(keyword: str, corpus: str = "icd",
                  code_prefix: str = "", max_results: int = 10) -> str:
    """Search a domain corpus by keyword and/or code prefix. Use when you don't know the exact code."""
    try:
        data = _load_mdr(corpus)
    except (ValueError, FileNotFoundError) as e:
        return str(e)
    key = corpus.lower().strip()
    if key not in _corpus_cache:
        _corpus_cache[key] = _bc.unpack_all(data)
    entries = _corpus_cache[key]
    kw = keyword.lower().strip()
    pfx = code_prefix.strip()
    results = []
    for code, desc in entries.items():
        if pfx and not code.startswith(pfx):
            continue
        if kw and kw not in desc.lower() and kw not in code.lower():
            continue
        results.append({"code": code, "description": desc})
        if len(results) >= max_results:
            break
    total_matches = sum(1 for c, d in entries.items()
                        if (not pfx or c.startswith(pfx))
                        and (not kw or kw in d.lower() or kw in c.lower()))
    return json.dumps({
        "corpus": corpus, "keyword": kw, "prefix": pfx or "*",
        "showing": len(results), "total_matches": total_matches,
        "results": results,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_benchmark() -> str:
    """Run the canonical conformance suite."""
    if not VECTORS_PATH.exists():
        return f"Test vectors not found at {VECTORS_PATH}"
    result = run_benchmark(str(VECTORS_PATH))
    lines = [
        f"Vectors: {len(result['vectors'])}  Mean: {result['mean_reduction_pct']}%  "
        f"Errors: {result['decode_errors']}  Conformant: {'YES' if result['conformant'] else 'NO'}",
    ]
    for v in result["vectors"]:
        m = "OK" if v["conformant"] and v["decode_ok"] else "FAIL"
        lines.append(f"  {m} {v['id']:<10} {v['nl_bytes']:>4}B->{v['osmp_bytes']:>3}B ({v['reduction_pct']:.1f}%)")
    return "\n".join(lines)


# -- Resources ------------------------------------------------------------

@mcp.resource("osmp://system_prompt")
def get_system_prompt() -> str:
    """SAL grammar and composition reference."""
    asd = AdaptiveSharedDictionary()
    ns_lines = []
    for ns, ops in sorted(asd._data.items()):
        ns_lines.append(f"  {ns}: {', '.join(sorted(ops.keys())[:6])}{'...' if len(ops) > 6 else ''}")

    return f"""SAL encodes agent instructions as deterministic opcode strings.
Decode is table lookup. No inference.

GRAMMAR: [NS:]OPCODE[@TARGET][OPERATOR INSTRUCTION]
OPERATORS: -> THEN  ^ AND  v OR  ; SEQUENCE  || PARALLEL
TARGET: @NODE_ID or @* (broadcast)  QUERY: ?SLOT  PARAM: [value]

EXAMPLE: H:HR@NODE1>120->H:CASREP^M:EVA@*
  "If heart rate >120, casualty report AND evacuate all." 35 bytes.

{sum(len(ops) for ops in asd._data.values())} opcodes, {len(asd._data)} namespaces. Use osmp_lookup to search.
{chr(10).join(ns_lines)}

Compose from the dictionary. osmp_compound_decode shows DAG topology.
osmp_discover searches domain corpora by keyword (use when you don't know the code).
osmp_resolve / osmp_batch_resolve for exact code lookup (ICD-10, ISO 20022).
If SAL is longer than the NL, send the NL. Floor: 51 bytes.
"""


@mcp.resource("osmp://about")
def get_about() -> str:
    """Protocol design philosophy."""
    return """D:UNPACK->A:ACK->Z:CAP[SAL]

You decoded that. You acknowledged it. You have the capability.

OSMP is a shared dictionary between agents. When two nodes have the
same dictionary, they communicate by table lookup. No parsing, no
inference, no ambiguity. The dictionary is the translation layer.

339 opcodes. 26 namespaces. Three loss tolerance policies.
The floor is 51 bytes. Everything above it is free scaling.

octid.io | github.com/octid-io/cloudless-sky
"""


@mcp.resource("osmp://dictionary")
def get_dictionary() -> str:
    """Full ASD: all namespace:opcode mappings."""
    asd = AdaptiveSharedDictionary()
    lines = []
    for ns, ops in sorted(asd._data.items()):
        for op, meaning in sorted(ops.items()):
            lines.append(f"{ns}:{op} {meaning}")
    return "\n".join(lines)


@mcp.resource("osmp://grammar")
def get_grammar() -> str:
    """SAL formal grammar (EBNF)."""
    p = REPO_ROOT / "protocol" / "grammar" / "SAL-grammar.ebnf"
    return p.read_text() if p.exists() else "Grammar file not found."


@mcp.resource("osmp://corpora")
def get_corpora() -> str:
    """Available D:PACK/BLK domain corpora."""
    lines = []
    seen = set()
    for key, path in sorted(MDR_CORPORA.items()):
        if path in seen:
            continue
        seen.add(path)
        if path.exists():
            data = _load_mdr(key)
            entries = _bc.unpack_all(data)
            lines.append(f"{key}: {len(entries):,} codes, {_bc.stats(data)['total_bytes']:,} bytes")
        else:
            lines.append(f"{key}: not found")
    return "\n".join(lines)


@mcp.resource("osmp://examples")
def get_examples() -> str:
    """Annotated SAL examples."""
    return """1. E:EQ@4A?TH:0          "Report temperature at node 4A"              10B
2. E@T>38->B:BA@BS       "If temp>38, building alert"                15B
3. H:HR@NODE1>120->H:CASREP^M:EVA@*  "HR>120: casualty report + evacuate"  35B
4. K:PAY@RECV<->I:section->K:XFR[AMT]  "Pay iff human confirms, transfer"  26B
5. R:TORCH@PHONE1:ON     "Flashlight on (reversible)"                22B
6. I:section->R:CAM@PHONE2:ON  "Human gate then camera"              25B
7. O:MODE:E^O:TYPE:1     "Emergency mode, type 1"                    17B
8. Z:INF^Z:TOKENS:847    "Invoke inference, report tokens"           33B
9. H:ICD[A000]           "Look up ICD-10 cholera code"               10B
10. J:GOAL[QTR]->J:HANDOFF@BETA  "Declare goal, hand off to Beta"   30B

Operators: -> THEN  ^ AND  v OR  ; SEQUENCE  @ target  ? query  * broadcast  [] param"""


# -- Entry point ----------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
