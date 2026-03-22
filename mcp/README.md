# OSMP MCP Server

MCP server for the [Octid Semantic Mesh Protocol (OSMP)](https://octid.io). Deterministic encode/decode of agentic AI instructions by table lookup. No inference at decode.

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

## Tools (8)

| Tool | What it does |
|---|---|
| `osmp_encode` | Structured fields to SAL instruction |
| `osmp_decode` | SAL to structured fields (handles compound instructions) |
| `osmp_compound_decode` | DAG topology and loss tolerance analysis |
| `osmp_lookup` | Search the opcode dictionary by namespace and/or keyword |
| `osmp_discover` | Search domain corpora by keyword and/or code prefix (ICD-10-CM, ISO 20022) |
| `osmp_resolve` | Single domain code lookup (exact code required) |
| `osmp_batch_resolve` | Multiple exact domain codes in one call |
| `osmp_benchmark` | Canonical conformance suite |

## Resources (6)

| URI | Content |
|---|---|
| `osmp://system_prompt` | SAL grammar, composition rules, and reference (~390 tokens) |
| `osmp://about` | Protocol design philosophy |
| `osmp://dictionary` | Full ASD (339 opcodes, 26 namespaces) |
| `osmp://grammar` | SAL formal grammar (EBNF) |
| `osmp://corpora` | Available D:PACK/BLK domain corpus stats |
| `osmp://examples` | 11 annotated SAL examples |

## Agent Quickstart

1. Read `osmp://system_prompt`
2. Use `osmp_lookup` to find opcodes by namespace or keyword
3. Compose SAL directly from the dictionary
4. Use `osmp_discover` to find domain codes you don't know (keyword + optional prefix)
5. Use `osmp_resolve` for exact code lookup once you have the code
6. Use `osmp_compound_decode` to check DAG topology before transmitting
7. Use `osmp_decode` to parse received instructions

## Context Window Footprint

~124 tokens on connect (server instructions + tool schemas + resource listings). ~514 tokens total after reading the system prompt. Composition rules added to prevent common grammar errors observed during agent testing. Still under 0.3% of a 200K context window.

## Links

- [octid.io](https://octid.io)
- [GitHub](https://github.com/octid-io/cloudless-sky)
- [OSMP Spec](https://github.com/octid-io/cloudless-sky/blob/main/protocol/spec/OSMP-SPEC-v1.md)

## License

Apache 2.0 with express patent grant.
