"""
OSMP MCP Server -- Octid Semantic Mesh Protocol
Exposes OSMP encoding, decoding, domain resolution, and benchmarking
as MCP tools for any MCP-compatible AI client.

Patent: OSMP-001-UTIL (pending) -- inventor Clay Holberg
License: Apache 2.0

Usage (stdio transport):
    python mcp/server.py

    Or via Claude Code:
    claude mcp add osmp -- python mcp/server.py

    Or in claude_desktop_config.json:
    {
        "mcpServers": {
            "osmp": {
                "command": "python",
                "args": ["mcp/server.py"],
                "cwd": "/path/to/cloudless-sky"
            }
        }
    }
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
    """Load and cache an MDR binary."""
    key = corpus.lower().strip()
    if key not in MDR_CORPORA:
        raise ValueError(
            f"Unknown corpus '{corpus}'. "
            f"Available: {', '.join(sorted(set(MDR_CORPORA.keys())))}"
        )
    if key not in _mdr_cache:
        path = MDR_CORPORA[key]
        if not path.exists():
            raise FileNotFoundError(
                f"MDR binary not found: {path}. "
                f"Run from the cloudless-sky repo root."
            )
        _mdr_cache[key] = path.read_bytes()
    return _mdr_cache[key]


# -- MCP Server -----------------------------------------------------------
mcp = FastMCP(
    "osmp",
    instructions=(
        "OSMP (Octid Semantic Mesh Protocol) encodes agentic AI instructions "
        "as compact, human-readable symbolic strings (SAL). Any node with the "
        "Adaptive Shared Dictionary decodes by table lookup. No inference. "
        "No cloud. Use osmp_translate to convert natural language to SAL, "
        "osmp_encode for structured field encoding, osmp_decode to parse SAL "
        "(including compound multi-frame instructions), osmp_resolve to look "
        "up domain codes (ICD-10-CM clinical, ISO 20022 financial), and "
        "osmp_benchmark to run the conformance suite. Read osmp://system_prompt "
        "to learn how to generate SAL natively, osmp://examples for annotated "
        "instruction samples, and osmp://dictionary for the full opcode reference."
    ),
)


@mcp.tool()
def osmp_encode(
    namespace: str,
    opcode: str,
    target: str | None = None,
    query_slot: str | None = None,
    consequence_class: str | None = None,
) -> str:
    """Encode structured fields into an OSMP/SAL instruction string.

    Args:
        namespace: Single-letter namespace (H=health, K=financial, M=military,
                   A=agentic, O=operational, D=data, R=regulatory, etc.)
        opcode: Operation code from the ASD (e.g. HR, CASREP, EVA, TRIAGE)
        target: Optional target node or address (e.g. NODE1, * for broadcast)
        query_slot: Optional query parameter
        consequence_class: For R namespace: one of the consequence glyphs

    Returns:
        SAL-encoded instruction string (e.g. "H:HR@NODE1>120")
    """
    frame = _encoder.encode_frame(
        namespace=namespace,
        opcode=opcode,
        target=target,
        query_slot=query_slot,
        consequence_class=consequence_class,
    )
    byte_count = len(frame.encode("utf-8"))
    return f"{frame}\n\n({byte_count} bytes, fits LoRa: {'yes' if byte_count <= 51 else 'no'})"


@mcp.tool()
def osmp_decode(sal: str) -> str:
    """Decode an OSMP/SAL instruction string into structured fields.

    Decode is pure table lookup. No inference. No model. Any device
    capable of string processing can decode SAL.

    Handles compound instructions: splits on operators (→ ∧ ∨ ; ∥)
    and decodes each frame independently, returning the full chain
    as a structured execution plan.

    Args:
        sal: SAL-encoded instruction (e.g. "H:HR@NODE1>120" or
             "H:HR@NODE1>120→H:CASREP∧M:EVA@*")

    Returns:
        JSON with parsed fields for each frame in the instruction chain.
    """
    import re
    # Split on SAL operators while preserving them
    split_pattern = r'([→∧∨;])'
    parts = re.split(split_pattern, sal.strip())

    frames = []
    for part in parts:
        part = part.strip()
        if not part or part in '→∧∨;':
            if part in '→∧∨;':
                frames.append({"operator": part, "meaning": {
                    "→": "THEN (sequential)",
                    "∧": "AND (concurrent)",
                    "∨": "OR (alternative)",
                    ";": "SEQUENCE (ordered)"
                }.get(part, part)})
            continue
        try:
            decoded = _decoder.decode_frame(part)
            result = asdict(decoded)
            nl = _decoder.decode_natural_language(part)
            result["natural_language"] = nl
            result["byte_count"] = len(part.encode("utf-8"))
            frames.append(result)
        except Exception:
            frames.append({"raw": part, "error": "could not decode frame"})

    total_bytes = len(sal.encode("utf-8"))
    output = {
        "instruction": sal,
        "total_bytes": total_bytes,
        "fits_lora": total_bytes <= 51,
        "frames": frames,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_translate(natural_language: str) -> str:
    """Translate natural language into an OSMP/SAL instruction.

    This is the primary tool for agents that want to speak SAL.
    Describe what you want in plain English. The translator maps it
    to the closest SAL encoding using the Adaptive Shared Dictionary.

    The translator performs keyword and intent matching against the
    339-opcode dictionary. It does not use inference. If no match is
    found, it returns the closest candidates.

    Args:
        natural_language: Plain English instruction
                          (e.g. "check heart rate at node 1 above 120")

    Returns:
        SAL instruction with explanation, or candidate matches if ambiguous.
    """
    nl = natural_language.lower().strip()
    asd = AdaptiveSharedDictionary()

    # Build reverse index: keyword -> (namespace, opcode, definition)
    _index: list[tuple[str, str, str, list[str]]] = []
    for ns, ops in asd._data.items():
        for op, defn in ops.items():
            defn_words = defn.replace("_", " ").lower().split()
            _index.append((ns, op, defn, defn_words))

    # Score each opcode against the NL input
    nl_words = set(re.sub(r'[^a-z0-9 ]', ' ', nl).split())
    # Remove stop words
    nl_words -= {"the", "a", "an", "to", "at", "on", "in", "of", "and", "or",
                 "is", "it", "if", "then", "all", "this", "that", "for", "from",
                 "with", "up", "look", "check", "get", "set", "do", "run",
                 "immediately", "now", "please", "just", "nodes", "my"}

    # Synonym map: common NL terms -> opcode-matching terms
    _synonyms = {
        "evacuate": "evacuation", "encrypt": "enc", "decrypt": "dec",
        "diagnosis": "icd", "diagnose": "icd", "clinical": "icd",
        "heartbeat": "hr", "vital": "vitals", "vitals": "vitals",
        "gps": "gps", "location": "position", "navigate": "routing",
        "pay": "pay", "payment": "pay", "transfer": "xfr",
        "stop": "stop", "halt": "stop", "kill": "kill",
        "sign": "sign", "verify": "vfy", "approve": "approve",
        "emergency": "estop", "urgent": "alert",
    }

    # Expand NL words with synonyms
    expanded = set(nl_words)
    for w in nl_words:
        if w in _synonyms:
            expanded.add(_synonyms[w])

    scored = []
    for ns, op, defn, defn_words in _index:
        score = 0.0
        matched = set()

        for nl_w in expanded:
            # Exact match on opcode name (highest weight)
            if nl_w == op.lower():
                score += 5.0
                matched.add(nl_w)
            # Exact match on definition word
            elif nl_w in defn_words:
                # Single-word definitions are direct semantic matches (boost)
                score += 4.0 if len(defn_words) == 1 else 2.0
                matched.add(nl_w)
            # Stem match: shared root of 5+ characters
            elif len(nl_w) >= 4:
                for dw in defn_words:
                    # Find shared prefix length
                    shared = 0
                    for a, b in zip(nl_w, dw):
                        if a == b:
                            shared += 1
                        else:
                            break
                    if shared >= 5:
                        score += 1.5
                        matched.add(nl_w)
                        break

        if score > 0:
            scored.append((score, ns, op, defn, matched))

    scored.sort(key=lambda x: -x[0])

    if not scored:
        return (
            "No matching opcodes found for this input. "
            "Try using domain-specific terms like: heart rate, evacuation, "
            "encrypt, waypoint, inference, audit, transfer, triage, "
            "or check osmp://dictionary for the full opcode list."
        )

    # Detect multi-opcode intent: if 2+ top matches have similar high
    # scores from different NL words, chain them with ->
    # Require chain entries to have either opcode-level match (5.0+)
    # or 2+ matched words to avoid false chaining on generic terms
    top_score = scored[0][0]
    chain = [scored[0]]
    used_words = set(scored[0][4])
    for s in scored[1:5]:
        new_words = s[4] - used_words
        if not new_words:
            continue
        strong = s[0] >= 5.0 or len(s[4]) >= 2
        if strong and s[0] >= top_score * 0.35:
            chain.append(s)
            used_words |= s[4]
    if len(chain) > 3:
        chain = chain[:3]

    # Extract target if present (look for @-style addressing or "node X")
    target = None
    node_match = re.search(r'(?:node|@)\s*([A-Za-z0-9_]+)', nl)
    if node_match:
        target = node_match.group(1).upper()

    # Extract threshold if present
    threshold = None
    thresh_match = re.search(r'(?:above|below|exceed|over|under|>|<|=)\s*(\d+)', nl)
    if thresh_match:
        threshold = thresh_match.group(0).replace("above", ">").replace(
            "exceed", ">").replace("over", ">").replace(
            "below", "<").replace("under", "<")
        threshold = re.sub(r'\s+', '', threshold)

    # Build SAL from chain
    sal_parts = []
    for i, entry in enumerate(chain):
        ns, op, defn = entry[1], entry[2], entry[3]
        part = f"{ns}:{op}"
        if i == 0:
            # Only first frame gets target and threshold
            if target:
                part += f"@{target}"
                if threshold:
                    part += threshold
            elif threshold:
                part += threshold
        sal_parts.append(part)

    sal = "\u2192".join(sal_parts)  # join with THEN operator
    byte_count = len(sal.encode("utf-8"))

    # Show matches
    match_lines = []
    for entry in chain:
        match_lines.append(f"  {entry[1]}:{entry[2]} = {entry[3]}")

    # Show alternatives (opcodes not in chain)
    chain_ops = {(e[1], e[2]) for e in chain}
    alternatives = []
    for score, ans, aop, adefn, overlap in scored[:8]:
        if (ans, aop) not in chain_ops:
            alternatives.append(f"  {ans}:{aop} ({adefn})")
        if len(alternatives) >= 3:
            break

    lines = [
        sal,
        "",
        f"({byte_count} bytes, fits LoRa: {'yes' if byte_count <= 51 else 'no'})",
        "",
        "Matched:" if len(chain) == 1 else "Matched (chained with THEN):",
    ]
    lines.extend(match_lines)
    if alternatives:
        lines.append("")
        lines.append("Other candidates:")
        lines.extend(alternatives)

    return "\n".join(lines)


@mcp.tool()
def osmp_resolve(code: str, corpus: str = "icd") -> str:
    """Resolve a single domain code from a D:PACK/BLK binary.

    Decompresses only the containing block (~32KB). On an ESP32 this
    uses 38KB of SRAM. The full ICD-10-CM corpus (74,719 codes) fits
    in 477KB of flash.

    Args:
        code: MDR token to look up (e.g. "A000" for ICD, "ACH" for ISO 20022)
        corpus: Domain registry to query. One of:
                "icd" -- CMS FY2026 ICD-10-CM, 74,719 clinical codes
                "iso" -- ISO 20022 eRepository, 47,835 financial codes

    Returns:
        SAL description text for the code, or an error message if not found.
    """
    try:
        data = _load_mdr(corpus)
    except (ValueError, FileNotFoundError) as e:
        return str(e)

    result = _bc.resolve(data, code)
    if result is None:
        return f"Code '{code}' not found in {corpus} corpus."

    stats = _bc.stats(data)
    return (
        f"{code}: {result}\n\n"
        f"(corpus: {corpus}, {stats['block_count']} blocks, "
        f"{stats['total_bytes']:,} bytes total)"
    )


@mcp.tool()
def osmp_benchmark() -> str:
    """Run the OSMP canonical conformance benchmark.

    Executes the full test vector suite against the Python SDK.
    Reports per-vector compression, mean reduction, LoRa floor
    compliance, and decode correctness.

    Returns:
        Benchmark summary with pass/fail status and statistics.
    """
    vectors_path = str(VECTORS_PATH)
    if not VECTORS_PATH.exists():
        return (
            f"Test vectors not found at {vectors_path}. "
            f"Run from the cloudless-sky repo root."
        )

    result = run_benchmark(vectors_path)

    summary_lines = [
        "OSMP Canonical Benchmark Results",
        "=" * 40,
        f"Vectors:          {len(result['vectors'])}",
        f"Mean reduction:   {result['mean_reduction_pct']}%",
        f"Decode errors:    {result['decode_errors']}",
        f"Conformant:       {'YES' if result['conformant'] else 'NO'}",
        "",
        "Per-vector results:",
    ]

    for v in result["vectors"]:
        marker = "PASS" if v["conformant"] and v["decode_ok"] else "FAIL"
        summary_lines.append(
            f"  {marker} {v['id']:<10} "
            f"{v['nl_bytes']:>4}B -> {v['osmp_bytes']:>3}B "
            f"({v['reduction_pct']:.1f}%)"
        )

    return "\n".join(summary_lines)


@mcp.tool()
def osmp_compound_decode(sal: str) -> str:
    """Analyze the DAG topology of a compound SAL instruction.

    Shows how the instruction decomposes into executable units
    with dependency chains, and what executes under each loss
    tolerance policy if specific fragments are lost in transit.

    Use this BEFORE transmitting a compound instruction to understand
    the structural consequences of packet loss on execution.

    The Overflow Protocol fragments compound instructions into a
    directed acyclic graph (DAG) of executable units. Each unit
    carries a dependency pointer. The receiving node resolves
    execution order via topological sort and applies the active
    loss tolerance policy to determine what runs.

    This tool answers: "If I send this instruction over a lossy
    radio link, what actually executes on the other end?"

    Args:
        sal: Compound SAL instruction containing structural operators
             (→ ∧ ∨ ; ∥). Single-frame instructions work but produce
             trivial single-node output.

    Returns:
        JSON with DAG topology, per-node dependencies, fragment wire
        format details, and execution analysis under all three loss
        tolerance policies (Phi/Gamma/Lambda).
    """
    fragmenter = DAGFragmenter()
    nodes = fragmenter.parse(sal)

    # -- DAG topology --
    dag_nodes = []
    for node in nodes:
        decoded_frames = []
        payload_str = node.payload.decode("utf-8", errors="replace")
        try:
            d = _decoder.decode_frame(payload_str)
            decoded_frames.append({
                "namespace": d.namespace,
                "opcode": d.opcode,
                "meaning": d.opcode_meaning,
                "target": d.target,
                "natural_language": _decoder.decode_natural_language(payload_str),
            })
        except Exception:
            decoded_frames.append({"raw": payload_str})

        dag_nodes.append({
            "index": node.index,
            "payload": payload_str,
            "payload_bytes": len(node.payload),
            "parents": node.parents,
            "is_root": len(node.parents) == 0,
            "decoded": decoded_frames[0] if decoded_frames else None,
        })

    # -- Fragment wire format --
    frags = fragmenter.fragmentize(sal, msg_id=0)
    wire_fragments = []
    for f in frags:
        wire_fragments.append({
            "frag_idx": f.frag_idx,
            "frag_ct": f.frag_ct,
            "dep_byte": f.dep,
            "flags": f.flags,
            "extended_dep": bool(f.flags & 0x08),
            "packed_bytes": len(f.pack()),
            "fits_lora_floor": len(f.pack()) <= 51,
            "fits_lora_standard": len(f.pack()) <= 255,
        })

    # -- Loss analysis per policy --
    loss_analysis = {}
    all_indices = set(range(len(nodes)))

    for policy_name, policy_enum in [
        ("Phi (Fail-Safe)", LossPolicy.FAIL_SAFE),
        ("Gamma (Graceful Degradation)", LossPolicy.GRACEFUL_DEGRADATION),
        ("Lambda (Atomic)", LossPolicy.ATOMIC),
    ]:
        # Full receipt
        reasm = DAGReassembler(policy=policy_enum)
        full_frags = fragmenter.fragmentize(sal, msg_id=1)
        result = None
        for f in full_frags:
            result = reasm.receive(f)
        full_exec = []
        if result:
            full_exec = [p.decode("utf-8", errors="replace") for p in result]

        # Per-node drop analysis (what happens if each node is lost)
        drop_scenarios = []
        if len(nodes) > 1:
            for drop_idx in range(len(nodes)):
                reasm_drop = DAGReassembler(policy=policy_enum)
                drop_frags = fragmenter.fragmentize(sal, msg_id=100 + drop_idx)
                partial_result = None
                for f in drop_frags:
                    if f.frag_idx == drop_idx:
                        continue
                    partial_result = reasm_drop.receive(f)

                # If no terminal was delivered, force resolution for GD
                if partial_result is None and policy_enum == LossPolicy.GRACEFUL_DEGRADATION:
                    # Terminal was the dropped fragment; simulate timeout
                    # by delivering a synthetic terminal to trigger resolution
                    remaining = [f for f in drop_frags if f.frag_idx != drop_idx]
                    if remaining:
                        reasm_drop2 = DAGReassembler(policy=policy_enum)
                        for f in remaining[:-1]:
                            reasm_drop2.receive(f)
                        # Mark last remaining as terminal
                        from copy import copy
                        last = copy(remaining[-1])
                        last.flags |= 0x01  # FLAG_TERMINAL
                        partial_result = reasm_drop2.receive(last)

                survived = []
                if partial_result:
                    survived = [p.decode("utf-8", errors="replace") for p in partial_result]

                dropped_payload = nodes[drop_idx].payload.decode("utf-8", errors="replace")
                drop_scenarios.append({
                    "dropped_fragment": drop_idx,
                    "dropped_instruction": dropped_payload,
                    "executes": survived,
                    "blocked": [n.payload.decode("utf-8", errors="replace")
                                for n in nodes
                                if n.payload.decode("utf-8", errors="replace")
                                not in survived
                                and n.index != drop_idx],
                })

        loss_analysis[policy_name] = {
            "full_receipt_execution_order": full_exec,
            "drop_scenarios": drop_scenarios,
        }

    # -- Build output --
    output = {
        "instruction": sal,
        "total_bytes": len(sal.encode("utf-8")),
        "node_count": len(nodes),
        "has_conditional_branches": any(len(n.parents) > 0 for n in nodes),
        "has_multi_parent_joins": any(len(n.parents) > 1 for n in nodes),
        "dag": dag_nodes,
        "wire_fragments": wire_fragments,
        "loss_tolerance_analysis": loss_analysis,
    }

    return json.dumps(output, indent=2, ensure_ascii=False)


# -- Resources: expose the ASD and grammar as readable context ------------
@mcp.resource("osmp://dictionary")
def get_dictionary() -> str:
    """The Adaptive Shared Dictionary (ASD) -- all namespace:opcode mappings."""
    asd = AdaptiveSharedDictionary()
    lines = ["OSMP Adaptive Shared Dictionary (ASD)", "=" * 50, ""]
    for ns, ops in sorted(asd._data.items()):
        lines.append(f"[{ns}] {len(ops)} opcodes")
        for op, meaning in sorted(ops.items()):
            lines.append(f"  {ns}:{op} -- {meaning}")
        lines.append("")
    return "\n".join(lines)


@mcp.resource("osmp://grammar")
def get_grammar() -> str:
    """The SAL grammar specification (EBNF)."""
    grammar_path = REPO_ROOT / "protocol" / "grammar" / "SAL-grammar.ebnf"
    if grammar_path.exists():
        return grammar_path.read_text()
    return "Grammar file not found. Run from the cloudless-sky repo root."


@mcp.resource("osmp://corpora")
def get_corpora() -> str:
    """List available D:PACK/BLK domain corpora and their stats."""
    lines = ["Available D:PACK/BLK Corpora", "=" * 40, ""]
    seen = set()
    for key, path in sorted(MDR_CORPORA.items()):
        if path in seen:
            continue
        seen.add(path)
        if path.exists():
            data = _load_mdr(key)
            stats = _bc.stats(data)
            all_entries = _bc.unpack_all(data)
            lines.append(
                f"{key}: {len(all_entries):,} entries, "
                f"{stats['block_count']} blocks, "
                f"{stats['total_bytes']:,} bytes "
                f"({stats['total_bytes']/1024:.0f} KB)"
            )
        else:
            lines.append(f"{key}: NOT FOUND at {path}")
    return "\n".join(lines)


@mcp.resource("osmp://examples")
def get_examples() -> str:
    """Annotated SAL examples with natural language equivalents.

    Use this to learn how SAL works. Each example shows the natural
    language intent, the SAL encoding, and why those opcodes were chosen.
    """
    return """OSMP/SAL Examples -- Learn by Reading
==========================================

1. SIMPLE: Single sensor query
   NL:  "Node 4A, report temperature at offset zero."
   SAL: EQ@4A?TH:0
   Why: E namespace (environment). EQ = environmental_query. Short form
        (no "E:" prefix) because EQ is unambiguous. @4A = target node.
        ?TH:0 = query temperature_humidity_composite, default 0.
   10 bytes. Fits LoRa floor.

2. CONDITIONAL: Threshold trigger
   NL:  "If temperature exceeds 38, trigger building alert."
   SAL: E@T>38->BA@BS!
   Why: E namespace environmental, T = temperature reading, >38 = threshold.
        -> (THEN operator) chains to B:BA (building_alert) at BS (building_sector).
        ! = broadcast.
   15 bytes. Fits LoRa floor.

3. COMPOUND: Multi-step medical instruction
   NL:  "If heart rate at node 1 exceeds 120, assemble casualty report
        and broadcast evacuation to all nodes."
   SAL: H:HR@NODE1>120->H:CASREP^M:EVA@*
   Why: H namespace (health). HR = heart_rate. @NODE1 = target.
        >120 = threshold. -> = THEN. H:CASREP = casualty_report.
        ^ = AND. M:EVA@* = evacuation broadcast to all (*).
   35 bytes. Fits LoRa floor.

4. FINANCIAL: Payment with human confirmation gate
   NL:  "Execute payment to receiver if and only if a human operator
        confirms, then transfer the amount."
   SAL: K:PAY@RECV<->I:section->K:XFR[AMT]
   Why: K namespace (financial). PAY = payment_execution.
        <-> = IFF (if and only if). I:section = human_operator_confirmation.
        -> = THEN. K:XFR[AMT] = asset_transfer with amount parameter.
   26 bytes. Fits LoRa floor.

5. ROBOTICS: Reversible physical action
   NL:  "Turn on flashlight on phone 1. This is reversible."
   SAL: R:TORCH@PHONE1:ON(reversible)
   Why: R namespace (regulatory/robotics). TORCH = flashlight_on_off.
        @PHONE1 = target device. :ON = parameter.
        (reversible) = consequence class glyph indicating undo is possible.
   22 bytes. Fits LoRa floor.

6. HAZARDOUS: Camera with human gate
   NL:  "Require human approval, then activate camera on phone 2.
        Mark as hazardous."
   SAL: I:section->R:CAM@PHONE2:ON(hazardous)
   Why: I:section = human_operator_confirmation gate. Must execute first.
        -> = THEN. R:CAM = camera_activation. @PHONE2 = target.
        (hazardous) = consequence class.
   25 bytes. Fits LoRa floor.

7. OPERATIONAL: Emergency mode declaration
   NL:  "Set operational mode to emergency, incident type 1."
   SAL: O:MODE:E^O:TYPE:1
   Why: O namespace (operational). MODE = operational_mode, value E (emergency).
        ^ = AND. TYPE = incident_type, value 1.
   17 bytes. Fits LoRa floor.

8. INFERENCE: Route to model with parameters
   NL:  "Invoke inference, report token count 847, latency 230ms."
   SAL: Z:INF^Z:TOKENS:847^Z:LATENCY:230
   Why: Z namespace (inference). INF = invoke_inference.
        ^ = AND chains to TOKENS and LATENCY reports.
   33 bytes. Fits LoRa floor.

9. DOMAIN CODE RESOLUTION:
   NL:  "Look up ICD-10 code A000."
   SAL: H:ICD[A000]
   Why: H namespace (health). ICD = ICD-10_diagnosis_code_accessor.
        [A000] = the code to resolve. D:PACK/BLK resolves to:
        "Cholera d/t Vibrio cholerae 01, biovar cholerae"
   10 bytes for the instruction. 477KB corpus in flash.

10. COGNITIVE: Agent goal declaration and handoff
    NL:  "Declare goal quarterly report, hand off execution to agent Beta."
    SAL: J:GOAL[QTR_RPT]->J:HANDOFF@BETA
    Why: J namespace (cognitive/planning). GOAL = declare_goal.
         [QTR_RPT] = parameter. -> = THEN. HANDOFF = transfer execution
         with full state context. @BETA = target agent.
    30 bytes. Fits LoRa floor.

KEY: Operators
  ->  THEN (sequential execution)
  ^   AND (concurrent execution)
  v   OR (alternative paths)
  ;   SEQUENCE (ordered)
  @   target node
  ?   query
  *   broadcast to all
  !   alert/broadcast
  []  parameter block
"""


@mcp.resource("osmp://system_prompt")
def get_system_prompt() -> str:
    """Ready-to-use system prompt fragment for OSMP/SAL generation.

    Inject this into an LLM's system prompt to make it generate SAL
    natively. Includes the grammar, operator reference, and examples.
    This is the viral adoption vector for OSMP.
    """
    asd = AdaptiveSharedDictionary()
    ns_summary = []
    for ns, ops in sorted(asd._data.items()):
        op_list = ", ".join(sorted(ops.keys())[:8])
        more = f" (+{len(ops)-8} more)" if len(ops) > 8 else ""
        ns_summary.append(f"  {ns}: {op_list}{more}")

    return f"""You are an OSMP-capable agent. When transmitting instructions to other agents
or edge devices, encode them in SAL (Semantic Assembly Language).

SAL is a compact, human-readable symbolic instruction format. Any node
with the Adaptive Shared Dictionary (ASD) decodes SAL by table lookup.
No inference required at the receiving end.

GRAMMAR (simplified):
  instruction = [namespace ":"] opcode ["@" target] [operator instruction]
  operators: -> (THEN), ^ (AND), v (OR), ; (SEQUENCE)
  target: @NODE_ID or @* (broadcast)
  query: ?SLOT[:default]
  parameter: [value]

NAMESPACES ({sum(len(ops) for ops in asd._data.values())} opcodes across {len(asd._data)} domains):
{chr(10).join(ns_summary)}

EXAMPLES:
  "Check heart rate at node 1 above 120" -> H:HR@NODE1>120
  "Evacuate all nodes"                   -> M:EVA@*
  "Encrypt then sign"                    -> S:ENC->S:SIGN
  "Human approval then camera on"        -> I:section->R:CAM@PHONE1:ON
  "Set emergency mode"                   -> O:MODE:E
  "Invoke inference, 0.1 temp"           -> Z:INF^Z:TEMP:0.1
  "Look up ICD code A000"               -> H:ICD[A000]
  "Declare goal, hand off to Beta"       -> J:GOAL[QTR]->J:HANDOFF@BETA

RULES:
- Prefer SAL over natural language when the instruction maps cleanly to opcodes.
- If SAL is longer than the NL, send the NL (BAEL passthrough).
- Every SAL instruction decodes by table lookup. No ambiguity.
- The floor is 51 bytes (LoRa SF12). Design for it.
- Domain codes (ICD-10, ISO 20022) resolve via D:PACK: H:ICD[A000], K:ISO[ACH].
"""


# -- Entry point ----------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
