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
        "No cloud. Use osmp_encode to produce SAL, osmp_decode to parse SAL, "
        "osmp_resolve to look up domain codes (ICD-10-CM clinical, ISO 20022 "
        "financial), and osmp_benchmark to run the conformance suite."
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

    Args:
        sal: SAL-encoded instruction (e.g. "H:HR@NODE1>120")

    Returns:
        JSON with parsed fields: namespace, opcode, opcode_meaning,
        target, query_slot, slots, consequence_class, raw
    """
    decoded = _decoder.decode_frame(sal)
    result = asdict(decoded)
    nl = _decoder.decode_natural_language(sal)
    result["natural_language"] = nl
    result["byte_count"] = len(sal.encode("utf-8"))
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def osmp_resolve(code: str, corpus: str = "icd") -> str:
    """Resolve a single domain code from a D:PACK/BLK binary.

    Decompresses only the containing block (~32KB). On an ESP32 this
    uses 38KB of SRAM. The full ICD-10-CM corpus (74,719 codes) fits
    in 477KB of flash.

    Args:
        code: MDR token to look up (e.g. "A000" for ICD, "ACH" for ISO 20022)
        corpus: Which domain registry to query.
                "icd" or "icd10cm" for CMS FY2026 ICD-10-CM (74,719 codes).
                "iso" or "iso20022" for ISO 20022 eRepository (47,835 codes).

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


# -- Resources: expose the ASD and grammar as readable context ------------
@mcp.resource("osmp://dictionary")
def get_dictionary() -> str:
    """The Adaptive Shared Dictionary (ASD) -- all namespace:opcode mappings."""
    asd = AdaptiveSharedDictionary()
    lines = ["OSMP Adaptive Shared Dictionary (ASD)", "=" * 50, ""]
    for ns, ops in sorted(asd.basis.items()):
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


# -- Entry point ----------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
