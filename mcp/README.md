# OSMP MCP Server

MCP server for the [Octid Semantic Mesh Protocol (OSMP)](https://octid.io). Gives any MCP-compatible AI client native OSMP capability: encode, decode, translate, and resolve agentic instructions by table lookup. No inference at decode.

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

## Tools

| Tool | What it does |
|---|---|
| `osmp_translate` | Natural language to SAL instruction. The primary tool for agents learning to speak OSMP. |
| `osmp_encode` | Structured fields to SAL instruction (`H:HR@NODE1>120`) |
| `osmp_decode` | SAL string to structured fields. Handles compound multi-frame instructions. |
| `osmp_compound_decode` | DAG topology analysis of compound instructions. Shows dependency chains, wire format, and what executes under each loss policy if fragments are lost. |
| `osmp_resolve` | Domain code to SAL description from D:PACK/BLK binary (74,719 ICD-10-CM, 47,835 ISO 20022) |
| `osmp_benchmark` | Run the canonical conformance suite |

## Resources

| URI | What it provides |
|---|---|
| `osmp://system_prompt` | Ready-to-use system prompt fragment. Inject into any LLM to enable native SAL generation. |
| `osmp://examples` | 10 annotated SAL examples with NL equivalents and explanations. |
| `osmp://dictionary` | Full Adaptive Shared Dictionary (339 opcodes across 26 namespaces). |
| `osmp://grammar` | SAL formal grammar (EBNF). |
| `osmp://corpora` | Available D:PACK/BLK domain corpus stats. |

## Agent Quickstart

1. Connect the MCP server
2. Read `osmp://system_prompt` and inject it into your context
3. Use `osmp_translate` to convert natural language to SAL
4. Use `osmp_compound_decode` to analyze DAG topology before transmitting compound instructions
5. Use `osmp_decode` to parse SAL instructions you receive
6. Use `osmp_resolve` to look up domain codes (ICD-10, ISO 20022)

## What ships in the package

The 1.7MB package includes the full Python SDK, the Adaptive Shared Dictionary (339 opcodes across 26 namespaces), and two D:PACK/BLK domain corpora (ICD-10-CM and ISO 20022) compressed for edge deployment. No additional downloads required.

## Links

- [octid.io](https://octid.io)
- [GitHub](https://github.com/octid-io/cloudless-sky)
- [OSMP Spec](https://github.com/octid-io/cloudless-sky/blob/main/protocol/spec/OSMP-SPEC-v1.md)

## License

Apache 2.0 with express patent grant.
