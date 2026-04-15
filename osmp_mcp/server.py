"""
OSMP MCP Server -- Octid Semantic Mesh Protocol
Patent pending -- inventor Clay Holberg
License: Apache 2.0
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# -- Import the OSMP Python SDK (real PyPI dependency) --------------------
from osmp.protocol import (
    SALEncoder,
    SALDecoder,
    BlockCompressor,
    AdaptiveSharedDictionary,
    DAGFragmenter,
    DAGReassembler,
    LossPolicy,
    run_benchmark,
    validate_composition,
    CompositionResult,
    CompositionIssue,
    SALComposer,
    MacroRegistry,
)

# -- Paths ----------------------------------------------------------------
# When pip-installed, package data lives next to this file in osmp_mcp/data/.
# When run from a repo clone, the same layout works because the repo also
# has osmp_mcp/data/ populated by the build pipeline.
PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = PKG_DIR / "data"
REPO_ROOT = PKG_DIR.parent  # only used for the optional grammar resource
MDR_DIR = DATA_DIR
VECTORS_PATH = DATA_DIR / "canonical-test-vectors.json"

MDR_CORPORA = {
    "icd": MDR_DIR / "MDR-ICD10CM-FY2026-blk.dpack",
    "icd10cm": MDR_DIR / "MDR-ICD10CM-FY2026-blk.dpack",
    # ISO 20022 has two complementary corpora: K-ISO (atomic element definitions)
    # and MSG (full message catalog like pacs.008.001.13). The K-ISO corpus is
    # the default "iso" alias for backward compatibility; the MSG corpus is
    # exposed under "iso_msg" / "iso20022_msg" for payment workflows.
    "iso": MDR_DIR / "MDR-ISO20022-K-ISO-blk.dpack",
    "iso20022": MDR_DIR / "MDR-ISO20022-K-ISO-blk.dpack",
    "iso_def": MDR_DIR / "MDR-ISO20022-K-ISO-blk.dpack",
    "iso20022_def": MDR_DIR / "MDR-ISO20022-K-ISO-blk.dpack",
    "iso_msg": MDR_DIR / "MDR-ISO20022-MSG-blk.dpack",
    "iso20022_msg": MDR_DIR / "MDR-ISO20022-MSG-blk.dpack",
    "attack": MDR_DIR / "MDR-MITRE-ATTACK-ENT-v18.1-blk.dpack",
    "mitre": MDR_DIR / "MDR-MITRE-ATTACK-ENT-v18.1-blk.dpack",
}

# -- Singleton instances --------------------------------------------------
_encoder = SALEncoder()
_decoder = SALDecoder()
_bc = BlockCompressor(use_dict=False)
_mdr_cache: dict[str, bytes] = {}
_composer: SALComposer | None = None
_macro_registry: MacroRegistry | None = None


def _get_composer() -> SALComposer:
    global _composer, _macro_registry
    if _composer is None:
        _macro_registry = _get_macro_registry()
        _composer = SALComposer(macro_registry=_macro_registry)
    return _composer


def _get_macro_registry() -> MacroRegistry:
    global _macro_registry
    if _macro_registry is None:
        _macro_registry = MacroRegistry()
        # Load Meshtastic macro corpus if available
        corpus_path = REPO_ROOT / "mdr" / "meshtastic" / "meshtastic-macros.json"
        if not corpus_path.exists():
            corpus_path = DATA_DIR / "meshtastic-macros.json"
        if corpus_path.exists():
            _macro_registry.load_corpus(str(corpus_path))
    return _macro_registry


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
    instructions=(
        "OSMP encodes agentic instructions as SAL (Semantic Assembly Language). "
        "Decode is table lookup. No inference. 86.8% byte reduction vs JSON.\n\n"
        "COMPOSITION: Call osmp_compose with the natural language instruction. "
        "The deterministic pipeline handles opcode selection, grammar assembly, "
        "and validation. Never write SAL by hand. If osmp_compose returns "
        "NL_PASSTHROUGH, send the natural language as-is.\n\n"
        "MANDATORY RULES (if composing manually instead of using osmp_compose):\n"
        "1. ALWAYS call osmp_lookup before composing. Never guess opcodes. "
        "If lookup returns 0 results, the opcode does not exist.\n"
        "2. READ THE DEFINITION, NOT THE MNEMONIC. "
        "K:ORD = financial order entry (ISO 20022), NOT food ordering. "
        "A:SUM = summarize/condense, NOT arithmetic sum. "
        "S:SIGN = cryptographic signature, NOT legal signing. "
        "Z:TEMP = inference sampling temperature, NOT physical temperature. "
        "E:HAZ = obstacle, NOT observation. "
        "If the ASD definition doesn't match the intent, the opcode does not apply.\n"
        "3. SELECT NAMESPACE BY DOMAIN CONTEXT. "
        "Patient temp = H:TEMP. Sensor temp = E:TH. Weather temp = W:TEMP. Model temp = Z:TEMP. "
        "Energy wind = X:WND. Weather wind = W:WIND. "
        "Building fire = B:ALRM + M:EVA. Weather fire advisory = W:FIRE. "
        "Protocol ack = A:ACK. Human ack = U:ACK. Ambiguous = NL passthrough.\n"
        "4. IF NO OPCODE MATCHES THE CORE ACTION: send natural language as-is (NL_PASSTHROUGH). "
        "Do not force-fit. 'Order me tacos' = NL. 'Book a flight' = NL. 'Send an email' = NL.\n"
        "5. R NAMESPACE: EVERY R instruction (except ESTOP) MUST end with a consequence class "
        "(⚠ HAZARDOUS, ↺ REVERSIBLE, or ⊘ IRREVERSIBLE). This applies to EVERY R instruction "
        "in a sequence, not just the first. ⚠/⊘ require I:§ as precondition. "
        "Aerial = ⚠. Ground + humans = ⚠. No medium declared = ⚠. "
        "Mobile peripheral (torch, haptic, vibe, bt, wifi, nfc, gps, accel) = ↺. Camera/mic/scrn = ⚠.\n"
        "6. @ takes a node_id or * (broadcast). NEVER namespace:opcode. "
        "Correct: H:ICD[J93.0]->H:CASREP. Wrong: H:CASREP@H:ICD[J93.0].\n"
        "7. IF SAL IS LONGER THAN THE NATURAL LANGUAGE: send natural language. "
        "Exception: safety-complete R namespace chains.\n"
        "8. NEVER emit an Omega opcode not confirmed by osmp_lookup. "
        "The agent is a dictionary consumer, not a dictionary author.\n\n"
        "Use osmp_lookup to search opcodes. Use osmp_discover for domain codes. "
        "Use osmp_validate to check composition rules before emission. "
        "If osmp_lookup returns a MACRO entry, use it instead of composing from individual opcodes. "
        "Read the osmp://system_prompt resource for the full composition doctrine."
    ),
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
    """Encode structured fields into a SAL instruction frame.

    Example: osmp_encode(namespace="R", opcode="MOV", target="BOT1", consequence_class="⚠")
    Returns: "R:MOV@BOT1⚠"

    consequence_class values: "⚠" (HAZARDOUS), "↺" (REVERSIBLE), "⊘" (IRREVERSIBLE).
    Required for R namespace. Use osmp_lookup to find valid namespaces and opcodes."""
    return _encoder.encode_frame(
        namespace=namespace, opcode=opcode, target=target,
        query_slot=query_slot, consequence_class=consequence_class,
    )


@mcp.tool()
def osmp_decode(sal: str) -> str:
    """Decode a SAL instruction string to structured fields and natural language. Handles compound instructions with operators (→ ∧ ∨ ; ∥ ↔).

    Example: osmp_decode(sal="H:HR@NODE1>120→H:CASREP")
    Returns JSON with each frame decoded: namespace, opcode, meaning, target, consequence class, and natural language expansion."""
    normalized = sal.strip().replace("->", "→").replace("<->", "↔").replace("||", "∥")
    parts = re.split(r'([→∧∨↔∥;])', normalized)
    frames = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part in '→∧∨↔∥;':
            frames.append({"operator": part, "meaning": {
                "→": "THEN", "∧": "AND", "∨": "OR", ";": "SEQUENCE",
                "↔": "IFF", "∥": "PARALLEL"
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
    """Analyze DAG topology and loss tolerance behavior of a compound SAL instruction. Shows fragment dependencies, wire-format sizes, and what executes when fragments are dropped under each loss policy (Phi/fail-safe, Gamma/graceful-degradation, Lambda/atomic).

    Example: osmp_compound_decode(sal="I:§→R:MOV@BOT1⚠∧E:GPS@BOT1")
    Returns JSON with DAG nodes, wire fragments, and per-policy drop simulations."""
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
    """Search the ASD opcode dictionary by namespace and/or keyword. Returns matching opcodes with definitions.

    Examples:
      osmp_lookup(namespace="R") -- all opcodes in the Robotics namespace
      osmp_lookup(keyword="heart") -- all opcodes containing "heart" in name or definition
      osmp_lookup(namespace="H", keyword="rate") -- H namespace opcodes matching "rate"
      osmp_lookup() -- dump entire dictionary (352 opcodes across 26 namespaces)"""
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
    """Resolve a single domain code from a D:PACK/BLK corpus to its description.

    Example: osmp_resolve(code="J93.0", corpus="icd") returns "J93.0: Spontaneous tension pneumothorax"
    Example: osmp_resolve(code="pacs.008.001.13", corpus="iso_msg") returns the FIToFICustomerCreditTransfer scope.

    corpus values:
      "icd"     -- ICD-10-CM diagnosis codes (74,719 entries, FY2026 CMS canonical)
      "iso"     -- ISO 20022 element definitions (47,835 entries, default ISO alias)
      "iso_msg" -- ISO 20022 message catalog (810 entries, dotted IDs like pacs.008.001.13)
      "attack"  -- MITRE ATT&CK techniques (1,661 entries)"""
    try:
        data = _load_mdr(corpus)
    except (ValueError, FileNotFoundError) as e:
        return str(e)
    # Finding 2: normalize dotted clinical codes (J93.0 -> J930) for corpus lookup
    normalized = code.replace(".", "")
    result = _bc.resolve(data, normalized)
    if result is None:
        # Fall back to original code in case corpus uses dotted keys
        result = _bc.resolve(data, code)
    if result is None:
        return f"Not found: {code}"
    return f"{code}: {result}"


@mcp.tool()
def osmp_batch_resolve(codes: str, corpus: str = "icd") -> str:
    """Resolve multiple domain codes in one call. Codes are comma-separated.

    Example: osmp_batch_resolve(codes="J93.0,R00.1,I25.10", corpus="icd")
    Example: osmp_batch_resolve(codes="pacs.008.001.13,camt.053.001.13", corpus="iso_msg")
    Returns JSON array with each code and its description.

    corpus values: "icd", "iso", "iso_msg", "attack" (see osmp_resolve docs for details)."""
    try:
        data = _load_mdr(corpus)
    except (ValueError, FileNotFoundError) as e:
        return str(e)
    results = []
    for code in (c.strip() for c in codes.split(",") if c.strip()):
        # Finding 2: normalize dotted clinical codes for corpus lookup
        normalized = code.replace(".", "")
        r = _bc.resolve(data, normalized)
        if r is None:
            r = _bc.resolve(data, code)
        results.append({"code": code, "description": r})
    return json.dumps({"results": results}, indent=2, ensure_ascii=False)


_corpus_cache: dict[str, dict[str, str]] = {}


@mcp.tool()
def osmp_discover(keyword: str, corpus: str = "icd",
                  code_prefix: str = "", max_results: int = 10) -> str:
    """Search a domain corpus by keyword and/or code prefix when you do not know the exact code.

    Examples:
      osmp_discover(keyword="pneumothorax", corpus="icd") -- find ICD-10 codes for pneumothorax
      osmp_discover(keyword="phishing", corpus="attack") -- find MITRE ATT&CK techniques for phishing
      osmp_discover(code_prefix="J93", corpus="icd") -- all ICD-10 codes starting with J93
      osmp_discover(keyword="credit transfer", corpus="iso_msg") -- ISO 20022 credit transfer messages
      osmp_discover(code_prefix="pacs.008", corpus="iso_msg") -- all FIToFI customer credit transfer versions

    corpus values: "icd", "iso", "iso_msg", "attack" (see osmp_resolve docs for details)."""
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
    """Run the canonical conformance test suite (55 vectors). Returns per-vector byte reduction and overall conformance status. Use to verify SDK correctness."""
    if not VECTORS_PATH.exists():
        return f"Test vectors not found at {VECTORS_PATH}"
    import io, os
    old_stdout = sys.stdout
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    try:
        result = run_benchmark(str(VECTORS_PATH))
    finally:
        sys.stdout = old_stdout
    lines = [
        f"Vectors: {len(result['vectors'])}  Mean: {result['mean_reduction_pct']}%  "
        f"Errors: {result['decode_errors']}  Conformant: {'YES' if result['conformant'] else 'NO'}",
    ]
    for v in result["vectors"]:
        m = "OK" if v["conformant"] and v["decode_ok"] else "FAIL"
        lines.append(f"  {m} {v['id']:<10} {v['nl_bytes']:>4}B->{v['osmp_bytes']:>3}B ({v['reduction_pct']:.1f}%)")
    return "\n".join(lines)


@mcp.tool()
def osmp_validate(sal: str, nl_input: str = "") -> str:
    """Validate a composed SAL instruction against all eight composition rules before emission. Always call this before transmitting any SAL instruction.

    Example: osmp_validate(sal="R:MOV@BOT1⚠", nl_input="Move BOT1 to waypoint")
    Returns JSON with PASS/FAIL status and any violations.

    Rules checked: hallucinated opcodes, namespace-as-target, consequence class requirement,
    I:§ precondition for ⚠/⊘, byte inflation vs NL input, slash operator rejection,
    mixed-mode detection, regulatory dependency prerequisites."""
    asd = AdaptiveSharedDictionary()
    result = validate_composition(sal, nl=nl_input, asd=asd)
    if result.valid:
        return json.dumps({"status": "PASS", "sal": sal, "violations": [],
                           "warnings": [{"rule": w.rule, "message": w.message} for w in result.warnings]},
                          indent=2, ensure_ascii=False)
    return json.dumps({
        "status": "FAIL",
        "sal": sal,
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "violations": [
            {"rule": i.rule, "message": i.message, "severity": i.severity}
            for i in result.issues
        ],
    }, indent=2, ensure_ascii=False)


# -- Composition ----------------------------------------------------------

@mcp.tool()
def osmp_compose(nl_text: str) -> str:
    """Compose valid SAL from natural language. The model's job is to call this
    tool with the user's intent — the deterministic pipeline handles opcode
    selection, grammar assembly, and validation. Never write SAL by hand.

    Returns JSON with either composed SAL or NL_PASSTHROUGH if no opcodes match.

    The pipeline: phrase matching (generation index) -> keyword fallback ->
    macro priority check -> grammar assembly -> 8-rule validation.

    Example: osmp_compose(nl_text="Alert if heart rate exceeds 130")
    Returns: {"mode": "FULL_OSMP", "sal": "H:HR>130→H:ALERT", "nl": "...", ...}"""
    composer = _get_composer()
    sal, is_sal = composer.compose_or_passthrough(nl_text)
    if is_sal:
        result = validate_composition(sal, nl=nl_text)
        return json.dumps({
            "mode": "FULL_OSMP",
            "sal": sal,
            "nl": nl_text,
            "sal_bytes": len(sal.encode("utf-8")),
            "nl_bytes": len(nl_text.encode("utf-8")),
            "reduction_pct": round((1 - len(sal.encode("utf-8")) / len(nl_text.encode("utf-8"))) * 100, 1)
                if len(nl_text.encode("utf-8")) > 0 else 0,
            "valid": result.valid,
            "warnings": [{"rule": w.rule, "message": w.message} for w in result.warnings],
            "errors": [{"rule": e.rule, "message": e.message} for e in result.errors],
        }, indent=2, ensure_ascii=False)
    return json.dumps({
        "mode": "NL_PASSTHROUGH",
        "sal": None,
        "nl": nl_text,
        "reason": "No ASD opcodes matched the input. Send as natural language.",
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_macro_list() -> str:
    """List all registered macros. Macros are pre-validated multi-step SAL
    chains for common workflows. When a macro matches, use it instead of
    composing from individual opcodes — macros have zero composition error surface.

    Returns JSON array of macros with id, description, triggers, and slots."""
    registry = _get_macro_registry()
    macros = registry.list_macros()
    return json.dumps([{
        "macro_id": m.macro_id,
        "description": m.description,
        "chain_template": m.chain_template,
        "triggers": list(m.triggers),
        "slots": [{"name": s.name, "type": s.slot_type, "namespace": s.namespace}
                  for s in m.slots],
        "consequence_class": m.consequence_class,
    } for m in macros], indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_macro_invoke(macro_id: str, slots: str = "{}") -> str:
    """Invoke a registered macro by ID with slot values.

    Example: osmp_macro_invoke(macro_id="MESH:DEV", slots='{"battery_level": "87", "voltage": "3.72"}')
    Returns the expanded SAL chain with slot values filled in.

    Use osmp_macro_list to find available macros and their required slots."""
    registry = _get_macro_registry()
    macro = registry.lookup(macro_id)
    if macro is None:
        return json.dumps({"error": f"Macro '{macro_id}' not found. Use osmp_macro_list to see available macros."},
                          indent=2, ensure_ascii=False)
    try:
        slot_values = json.loads(slots) if isinstance(slots, str) else slots
    except json.JSONDecodeError:
        return json.dumps({"error": f"Invalid JSON for slots: {slots}"}, indent=2, ensure_ascii=False)
    try:
        expanded = registry.expand(macro_id, slot_values)
        compact = registry.encode_compact(macro_id, slot_values)
        return json.dumps({
            "macro_id": macro_id,
            "expanded_sal": expanded,
            "compact_sal": compact,
            "expanded_bytes": len(expanded.encode("utf-8")),
            "compact_bytes": len(compact.encode("utf-8")),
            "consequence_class": macro.consequence_class,
        }, indent=2, ensure_ascii=False)
    except (ValueError, KeyError) as e:
        return json.dumps({"error": str(e), "required_slots": [s.name for s in macro.slots]},
                          indent=2, ensure_ascii=False)


# -- Bridge ---------------------------------------------------------------
# Singleton bridge instance, lazily initialized.
_bridge = None


def _get_bridge() -> "SALBridge":
    global _bridge
    if _bridge is None:
        from osmp.bridge import SALBridge
        _bridge = SALBridge("OSMP-MCP-BRIDGE")
    return _bridge


@mcp.tool()
def osmp_bridge_register(
    peer_id: str,
    attempt_fnp: bool = False,
) -> str:
    """Register a non-OSMP peer with the SAL bridge.

    The bridge manages translation between SAL and natural language
    at the boundary. Non-OSMP peers receive NL with SAL annotations
    that seed their context window. Over time, peers may acquire SAL
    through exposure.

    Example: osmp_bridge_register(peer_id="GPT_AGENT_1")
    """
    bridge = _get_bridge()
    state = bridge.register_peer(peer_id, attempt_fnp=attempt_fnp)
    return json.dumps({
        "peer_id": peer_id,
        "state": state,
        "annotate": bridge.annotate,
        "detail": "Peer registered. Use osmp_bridge_send to send SAL through the bridge.",
    }, indent=2)


@mcp.tool()
def osmp_bridge_send(
    sal: str,
    peer_id: str,
) -> str:
    """Send a SAL instruction through the bridge to a peer.

    - ESTABLISHED/ACQUIRED peers receive SAL directly.
    - FALLBACK peers receive NL decoded from SAL, annotated with the
      SAL equivalent for context seeding.

    Returns the translated message ready for transmission.

    Example: osmp_bridge_send(sal="H:HR@NODE1>120;H:CASREP", peer_id="GPT_AGENT_1")
    """
    bridge = _get_bridge()
    translated = bridge.send(sal, peer_id)
    state = bridge.peer_state(peer_id)
    sal_bytes = len(sal.encode("utf-8"))
    translated_bytes = len(translated.encode("utf-8"))
    return json.dumps({
        "peer_id": peer_id,
        "state": state,
        "original_sal": sal,
        "original_bytes": sal_bytes,
        "translated": translated,
        "translated_bytes": translated_bytes,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_bridge_receive(
    message: str,
    peer_id: str,
) -> str:
    """Process an inbound message from a peer through the bridge.

    Scans for valid SAL fragments in the message. Updates acquisition
    metrics. Handles FALLBACK -> ACQUIRED and ACQUIRED -> FALLBACK
    transitions automatically.

    Example: osmp_bridge_receive(message="A:ACK;M:EVA@MED", peer_id="GPT_AGENT_1")
    """
    from osmp.bridge import BridgeInbound
    bridge = _get_bridge()
    result = bridge.receive(message, peer_id)
    metrics = bridge.get_metrics(peer_id)
    return json.dumps({
        "peer_id": result.peer_id,
        "state": result.state,
        "passthrough": result.passthrough,
        "sal": result.sal,
        "nl": result.nl,
        "detected_frames": result.detected_frames,
        "acquisition_score": round(metrics.acquisition_score, 2) if metrics else 0,
        "consecutive_hits": metrics.consecutive_sal_hits if metrics else 0,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_bridge_status(peer_id: str = "") -> str:
    """Get bridge status and acquisition metrics.

    If peer_id is provided, returns metrics for that peer.
    If empty, returns summary across all peers.

    Example: osmp_bridge_status(peer_id="GPT_AGENT_1")
    """
    bridge = _get_bridge()
    if not peer_id:
        return json.dumps(bridge.summary(), indent=2, ensure_ascii=False)

    metrics = bridge.get_metrics(peer_id)
    state = bridge.peer_state(peer_id)
    if metrics is None:
        return json.dumps({"error": f"No peer registered with id '{peer_id}'"}, indent=2)

    return json.dumps({
        "peer_id": peer_id,
        "state": state,
        "total_messages": metrics.total_messages,
        "messages_with_sal": metrics.messages_with_sal,
        "acquisition_score": round(metrics.acquisition_score, 2),
        "consecutive_hits": metrics.consecutive_sal_hits,
        "consecutive_misses": metrics.consecutive_sal_misses,
        "peak_consecutive_hits": metrics.peak_consecutive_hits,
        "unique_opcodes_seen": sorted(metrics.unique_opcodes_seen),
        "valid_frames_seen": metrics.valid_frames_seen,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_bridge_comparison(peer_id: str) -> str:
    """Get side-by-side SAL vs NL byte comparison for all bridged messages to a peer.

    This is the measurement data for efficiency analysis. Each entry shows
    the SAL encoding, the NL equivalent, byte counts, and reduction percentage.

    Example: osmp_bridge_comparison(peer_id="GPT_AGENT_1")
    """
    bridge = _get_bridge()
    comparisons = bridge.get_comparison(peer_id)
    if not comparisons:
        return json.dumps({"peer_id": peer_id, "comparisons": [],
                           "note": "No annotated messages recorded yet."}, indent=2)

    total_sal = sum(c["sal_bytes"] for c in comparisons)
    total_nl = sum(c["nl_bytes"] for c in comparisons)
    avg_reduction = (1 - total_sal / total_nl) * 100 if total_nl > 0 else 0

    return json.dumps({
        "peer_id": peer_id,
        "message_count": len(comparisons),
        "total_sal_bytes": total_sal,
        "total_nl_bytes": total_nl,
        "aggregate_reduction_pct": round(avg_reduction, 1),
        "comparisons": comparisons,
    }, indent=2, ensure_ascii=False)


# -- Resources ------------------------------------------------------------

@mcp.resource("osmp://system_prompt")
def get_system_prompt() -> str:
    """SAL grammar, composition reference, and usage doctrine."""
    asd = AdaptiveSharedDictionary()

    # Brief definitions for opcodes where 2-word truncation loses meaning
    _DEF_OVERRIDES = {
        "A:CMPR": "structured comparison", "A:DA": "delegate to agent",
        "A:MACRO": "macro invocation", "A:MDR": "corpus version",
        "A:VERIFY": "verify output", "D:PACK": "corpus encode",
        "D:UNPACK": "corpus decode", "D:RESUME": "resume transfer",
        "E:TH": "temp+humidity", "I:AML": "AML check",
        "I:CONS": "consent mgmt", "I:KYC": "KYC check",
        "I:\u00a7": "human confirm", "J:BLOCK": "blocked dependency",
        "J:COMMIT": "commit plan", "J:STEP": "plan step",
        "J:HANDOFF": "transfer execution", "L:CHAIN": "chain custody",
        "L:QUERY": "audit query", "L:TRAIL": "audit trail",
        "O:CONOPS": "concept ops", "Q:FAIL": "gate fail",
        "Q:PASS": "gate pass", "R:RTH": "return home",
        "R:NFC": "nfc read/write", "R:TORCH": "flashlight",
        "S:OPEN": "unseal payload", "T:AFTER": "after condition",
        "T:BEFORE": "before deadline", "T:UNTIL": "until condition",
        "U:APPROVE": "human approval", "U:CONFIRM": "human confirm",
        "U:FEEDBACK": "human feedback", "U:REVIEW": "human review",
        "U:DELEGATE": "delegate human", "V:COURSE": "course ground",
        "V:ETA": "arrival time", "V:ETD": "departure time",
        "V:PORT": "port of call", "V:SPEED": "speed ground",
        "V:MMSI": "vessel MMSI", "W:TAF": "terminal forecast",
        "Y:FETCH": "retrieve key", "Y:FORGET": "delete memory",
        "Y:PAGEOUT": "page out mem", "Y:COMMIT": "working to LT",
        "Y:RECALL": "episodic recall", "Y:RETRIEVE": "retrieve LCS",
        "Y:SUMM": "compress memory", "Y:SYNC": "sync peer mem",
        "Z:TOPP": "top-p sampling", "Z:TOPK": "top-k sampling",
    }

    def _abbrev(ns, op, defn):
        key = f"{ns}:{op}"
        if key in _DEF_OVERRIDES:
            return _DEF_OVERRIDES[key]
        d = defn.replace("_", " ")
        words = d.split()
        return " ".join(words[:2]) if len(words) > 2 else d

    ns_lines = []
    for ns, ops in sorted(asd._data.items()):
        parts = [f"{op}({_abbrev(ns, op, defn)})" for op, defn in sorted(ops.items())]
        ns_lines.append(f"  {ns}: {' '.join(parts)}")

    opcode_count = sum(len(ops) for ops in asd._data.values())
    namespace_count = len(asd._data)
    namespace_listing = chr(10).join(ns_lines)

    return f"""SAL encodes agent instructions as deterministic opcode strings.
Decode is table lookup. No inference.
ARCHITECTURAL NOTE: This prompt governs agent-layer composition.
Decode is protocol-layer (no inference). Compose is agent-layer (inference
constrained by these rules). The agent is a dictionary consumer, not a
dictionary author. The agent composes from what exists in the local ASD.

GRAMMAR: [NS:]OPCODE[@TARGET][OPERATOR INSTRUCTION]
OPERATORS: \u2192 THEN  \u2227 AND  \u2228 OR  ; SEQUENCE  \u2225 PARALLEL
TARGET: @NODE_ID or @* (broadcast)  QUERY: ?SLOT  PARAM: [value]

COMPOSITION RULES:
- @ takes a node ID or * (broadcast). Never another opcode or namespace.
  Valid: M:EVA@MEDEVAC, M:EVA@*. Invalid: H:ALERT@H:ICD[J93.0].
- [] carries values: domain codes, parameters, thresholds.
  H:ICD[J93.0], K:XFR[AMT], Z:TOKENS[847].
- Layer 2 accessors (H:ICD, H:SNOMED, H:CPT) are H namespace, not D.
  They are standalone frames in a chain, not target parameters.
  Correct: H:ICD[J93.0]\u2192H:CASREP\u2192M:EVA@MEDEVAC (39 bytes, 3 frames).
  Wrong: H:CASREP@H:ICD[J93.0] (ICD is not a target, it is its own frame).
- / is not a SAL operator. Never use slashes.
- One declaration per frame. Chain frames with operators.
- Conditions precede actions across \u2192. I:\u00a7 precedes R:\u26a0 and R:\u2298.
- Always call osmp_lookup before composing. Never guess opcodes.
- Always call osmp_discover when you don't know a domain code.

OPCODE SELECTION DOCTRINE:
Before composing SAL from natural language, follow this decision logic:
1. DECOMPOSE the NL into actions, conditions, targets, parameters.
2. SEARCH the full local ASD (osmp_lookup) for every action. This is mandatory.
   The ASD includes all tiers: Tier 1 (A-Z), Tier 2 (registered double-Latin),
   and any Omega entries registered by the sovereign node operator.
   Tier provenance is invisible to composition: an opcode is an opcode.
3. If zero ASD matches for the core action at ANY tier:
   a. If the gap is operationally critical, recurring, and HITL is available:
      surface a vocabulary gap proposal to the human operator. If approved,
      register the Omega entry, then compose. Never compose before registration.
   b. Otherwise: NL_PASSTHROUGH. Do not force-fit.
   "Order me tacos" \u2192 NL. K:ORD is financial order entry, not food.
   "Book a flight" \u2192 NL. No travel opcode exists.
   "Send an email" \u2192 NL. No email opcode exists.
4. If multiple namespace matches: select by DOMAIN CONTEXT, not mnemonic.
   Patient temperature \u2192 H:TEMP. Sensor temperature \u2192 E:TH.
   Weather temperature \u2192 W:TEMP. Model temperature \u2192 Z:TEMP.
   Energy wind \u2192 X:WND. Weather wind \u2192 W:WIND.
   Agent task handoff \u2192 J:HANDOFF. Physical authority handoff \u2192 R:HANDOFF.
   Store to memory \u2192 Y:STORE. Store energy \u2192 X:STORE.
   Generate embedding \u2192 Z:EMBED. Store embedding \u2192 Y:EMBED.
   Crypto verify \u2192 S:VFY. Quality verify \u2192 Q:VERIFY. Agent verify \u2192 A:VERIFY.
   Protocol acknowledge \u2192 A:ACK. Human acknowledge \u2192 U:ACK. Ambiguous \u2192 NL.

NAMESPACE PRINCIPLES (apply when the collision list above doesn't cover it):
P1: OPERATIONAL EVENT vs EXTERNAL DATA. Building on fire = B:ALRM + M:EVA (event
   happening to you). Fire weather watch from NWS = W:FIRE (data product about
   conditions). Your sensor reads 38C = E:TH (local instrument). NWS publishes
   temperature = W:TEMP (external data). This applies to every hazard type.
P2: DEFINITION MATCH, NOT MNEMONIC MATCH. Read the ASD definition. If the
   definition's operational context diverges from the NL usage context, the
   mnemonic match is a false positive. A:ACK = "protocol acknowledgment,
   NACK complement, Atomic policy." That is not "acknowledge a business receipt."
   K:ORD = "financial order entry." That is not "order food."
5. R namespace: EVERY R instruction (except ESTOP) MUST carry \u26a0, \u21ba, or \u2298.
   This is mandatory on EVERY R instruction, including sequences of multiple R
   instructions. R:TORCH\u21ba R:VIBE\u21ba R:WIFI\u21ba — the designator never drops.
   \u26a0 and \u2298 require I:\u00a7\u2192 as precondition.
   CONSEQUENCE CLASS BY MEDIUM (physics determines reversibility):
   Ground + no humans (COLLAB:O) = \u21ba. Ground + humans (COLLAB:A) = \u26a0.
   Aerial (all) = \u26a0. Gravity makes in-transit failure unrecoverable.
   Surface water controlled = \u21ba. Open water / offshore = \u26a0.
   Subsurface (UUV) = \u26a0. Microgravity propulsive = \u2298. Non-propulsive = \u26a0.
   Mobile peripheral (torch, haptic, vibe, spkr, disp, bt, wifi, nfc, gps, accel) = \u21ba.
   Camera/mic/scrn = \u26a0 (privacy). No medium declared = default \u26a0 (conservative).
6. BYTE CHECK: if SAL bytes >= NL bytes, use NL_PASSTHROUGH.
   EXCEPTION: safety-complete R namespace chains are exempt.
7. SEMANTIC CHECK: decode your SAL. If meaning diverges from intent, NL_PASSTHROUGH.
8. When genuinely ambiguous and no context resolves it: NL_PASSTHROUGH.
   A correct NL_PASSTHROUGH is always better than an incorrect SAL composition.

READ THE DEFINITION, NOT THE MNEMONIC:
A:SUM = summarize (condense), not arithmetic sum.
A:CMP = compress/compare, not compute.
E:HAZ = obstacle, not observation. Mnemonic similarity is not definition match.
K:ORD = financial order entry (ISO 20022), not food ordering.
S:SIGN = cryptographic signature, not legal document signing.
Z:TEMP = inference sampling temperature, not physical temperature.
H:ALERT = clinical threshold crossing, not general notification.
L:ALERT = compliance alert, not clinical or weather.
W:ALERT = weather advisory, not clinical or compliance.
U:ALERT = urgent operator alert (human-facing notification).

PROHIBITED PATTERNS:
- Never hallucinate an opcode. If osmp_lookup returns 0 results, the opcode does not exist.
- Never place namespace:opcode after @. The @ target is a node_id or *.
- Never use / as an operator. It is not SAL syntax.
- Never force-fit an OOV concept into the closest-sounding opcode.
- Never omit consequence class on R namespace (except ESTOP).
- Never omit I:\u00a7 before R:\u26a0 or R:\u2298.
- Never emit SAL longer than the NL input (BAEL guarantee).
- Never emit an Omega opcode not in the local ASD. The agent is a dictionary
  consumer, not a dictionary author. Propose Omega entries via HITL gate;
  never compose against an unregistered Omega opcode.

MACRO ARCHITECTURE:
A:MACRO[name] invokes a pre-validated multi-step SAL chain template by name
and slot-fill. If osmp_lookup returns a MACRO entry for the required workflow,
USE THE MACRO instead of composing from individual opcodes. The macro eliminates
composition errors: the chain structure is pre-validated, the agent only fills slots.
Composition priority: (1) Macro if registered, (2) individual opcode composition,
(3) NL_PASSTHROUGH if no dictionary coverage.
Always call osmp_validate on composed SAL before emission.

EXAMPLE: H:HR@NODE1>120\u2192H:CASREP\u2227M:EVA@*
  "If heart rate >120, casualty report AND evacuate all." 35 bytes.

{opcode_count} opcodes, {namespace_count} namespaces. Use osmp_lookup to search.
{namespace_listing}

COMPOSITION TOOLS (use these instead of writing SAL by hand):
osmp_compose: NL to SAL via deterministic pipeline. Call this first. It handles
  phrase matching, opcode selection, grammar assembly, and validation automatically.
  Returns SAL or NL_PASSTHROUGH. The model's job is to call this tool, not write SAL.
osmp_macro_list: List all registered macros (pre-validated multi-step SAL chains).
osmp_macro_invoke: Invoke a macro by ID with slot values. Zero composition error surface.

VALIDATION AND LOOKUP:
osmp_validate checks composition rules before emission (hallucination, consequence class, etc).
osmp_lookup searches the ASD by namespace or keyword.
osmp_discover searches domain corpora by keyword (use when you don't know the code).
osmp_resolve / osmp_batch_resolve for exact code lookup (ICD-10, ISO 20022, MITRE ATT&CK).
osmp_compound_decode shows DAG topology and loss tolerance behavior.
If SAL is longer than the NL, send the NL. Floor: 51 bytes.
"""


@mcp.resource("osmp://about")
def get_about() -> str:
    """Protocol design philosophy."""
    return """D:UNPACK->A:ACK->Z:CAPS[SAL]

You decoded that. You acknowledged it. You have the capability.

OSMP is a shared dictionary between agents. When two nodes have the
same dictionary, they communicate by table lookup. No parsing, no
inference, no ambiguity. The dictionary is the translation layer.

352 opcodes. 26 namespaces. Three loss tolerance policies.
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
2. E@T>38->B:ALRM@AREA   "If temp>38, building alert"                15B
3. H:HR@NODE1>120->H:CASREP^M:EVA@*  "HR>120: casualty report + evacuate"  35B
4. K:PAY@RECV<->I:section->K:XFR[AMT]  "Pay iff human confirms, transfer"  26B
5. R:TORCH@PHONE1:ON     "Flashlight on (reversible)"                22B
6. I:section->R:CAM@PHONE2:ON  "Human gate then camera"              25B
7. O:MODE:E^O:TYP:1      "Emergency mode, type 1"                    17B
8. Z:INF^Z:TOKENS:847    "Invoke inference, report tokens"           33B
9. H:ICD[A000]           "Look up ICD-10 cholera code"               10B
10. J:GOAL[QTR]->J:HANDOFF@BETA  "Declare goal, hand off to Beta"   30B
11. H:ICD[J93.0]->H:CASREP->M:EVA@MEDEVAC  "Pneumothorax: report + MEDEVAC"  39B

Operators: -> THEN  ^ AND  v OR  ; SEQUENCE  @ target  ? query  * broadcast  [] param"""


# -- Entry point ----------------------------------------------------------
def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
