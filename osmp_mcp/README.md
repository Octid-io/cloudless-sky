# OSMP MCP Server

MCP server for the [Octid Semantic Mesh Protocol (OSMP)](https://octid.io). Deterministic encode/decode of agentic AI instructions by table lookup. No inference at decode.

This is a production integration path. The agent connects, reads the system prompt, learns SAL, and speaks it natively from that point forward. The server stays running as the encode/decode/validate layer underneath.

For the standalone SDK (no MCP dependency): `pip install osmp`

## Install

```bash
pip install osmp-mcp
```

## Connect

### Claude Code
```bash
claude mcp add osmp -- osmp-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json`:
```json
{
    "mcpServers": {
        "osmp": {
            "command": "osmp-mcp"
        }
    }
}
```

### Cursor / VS Code / Any MCP Client
```json
{
    "servers": {
        "osmp": {
            "command": "osmp-mcp",
            "transport": "stdio"
        }
    }
}
```

## Tools (14)

### Core (9)

| Tool | What it does |
|---|---|
| `osmp_encode` | Structured fields to SAL instruction |
| `osmp_decode` | SAL to structured fields and natural language (handles compound instructions) |
| `osmp_validate` | Check composed SAL against all eight composition rules before emission |
| `osmp_compound_decode` | DAG topology and loss tolerance analysis |
| `osmp_lookup` | Search the opcode dictionary by namespace and/or keyword |
| `osmp_discover` | Search domain corpora by keyword and/or code prefix (ICD-10-CM, ISO 20022, MITRE ATT&CK) |
| `osmp_resolve` | Single domain code lookup (exact code required) |
| `osmp_batch_resolve` | Multiple exact domain codes in one call |
| `osmp_benchmark` | Canonical conformance suite (55 vectors) |

### Bridge (5)

For mixed environments where some agents speak OSMP and others don't.

| Tool | What it does |
|---|---|
| `osmp_bridge_register` | Register a non-OSMP peer for bridge translation |
| `osmp_bridge_send` | Send SAL through the bridge (auto-decodes to annotated NL for non-OSMP peers) |
| `osmp_bridge_receive` | Process inbound message (scans for SAL acquisition) |
| `osmp_bridge_status` | Get FNP state and acquisition metrics for a peer |
| `osmp_bridge_comparison` | Side-by-side byte comparison data (SAL vs NL) |

The bridge annotates outbound messages with SAL equivalents, seeding the remote agent's context window. When the remote agent starts producing valid SAL through exposure, the bridge detects it and transitions from FALLBACK to ACQUIRED. OSMP spreads by contact, not installation.

## Resources (6)

| URI | Content |
|---|---|
| `osmp://system_prompt` | SAL grammar, composition rules, and reference (~390 tokens) |
| `osmp://about` | Protocol design philosophy |
| `osmp://dictionary` | Full ASD (352 opcodes, 26 namespaces) |
| `osmp://grammar` | SAL formal grammar (EBNF) |
| `osmp://corpora` | Available D:PACK/BLK domain corpus stats |
| `osmp://examples` | 11 annotated SAL examples |

## Agent Quickstart

1. Read `osmp://system_prompt` -- the agent learns SAL grammar and composition rules on connect
2. Use `osmp_lookup` to find opcodes by namespace or keyword
3. Compose SAL directly from the dictionary
4. Use `osmp_validate` to check composition before emission
5. Use `osmp_discover` to find domain codes you don't know
6. Use `osmp_resolve` for exact code lookup once you have the code
7. Use `osmp_compound_decode` to check DAG topology before transmitting
8. Use `osmp_decode` to parse received instructions
9. Use the bridge tools when communicating with non-OSMP agents

## Context Window Footprint

~124 tokens on connect (server instructions + tool schemas + resource listings). ~514 tokens total after reading the system prompt. Still under 0.3% of a 200K context window.

## Links

- [octid.io](https://octid.io)
- [GitHub](https://github.com/octid-io/cloudless-sky)
- [OSMP Spec](https://github.com/octid-io/cloudless-sky/blob/main/protocol/spec/OSMP-SPEC-v1.0.2.md)

## License

Apache 2.0 with express patent grant.

<!-- mcp-name: io.github.Octid-io/osmp -->
