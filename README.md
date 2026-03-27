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

## Tools (9)

| Tool | What it does |
|---|---|
| `osmp_encode` | Structured fields to SAL instruction |
| `osmp_decode` | SAL to structured fields (handles compound instructions) |
| `osmp_compound_decode` | DAG topology and loss tolerance analysis |
| `osmp_lookup` | Search the opcode dictionary by namespace and/or keyword |
| `osmp_validate` | Check composed SAL against composition rules before emission |
| `osmp_discover` | Search domain corpora by keyword and/or code prefix (ICD-10-CM, ISO 20022, MITRE ATT&CK) |
| `osmp_resolve` | Single domain code lookup (exact code required) |
| `osmp_batch_resolve` | Multiple exact domain codes in one call |
| `osmp_benchmark` | Canonical conformance suite |

## Resources (6)

| URI | Content |
|---|---|
| `osmp://system_prompt` | SAL grammar, composition rules, and reference (~390 tokens) |
| `osmp://about` | Protocol design philosophy |
| `osmp://dictionary` | Full ASD (341 opcodes, 26 namespaces) |
| `osmp://grammar` | SAL formal grammar (EBNF) |
| `osmp://corpora` | Available D:PACK/BLK domain corpus stats |
| `osmp://examples` | 11 annotated SAL examples |

## Agent Quickstart

1. Read `osmp://system_prompt`
2. Use `osmp_lookup` to find opcodes by namespace or keyword
3. If lookup returns a MACRO entry, use it (slot-fill only, no individual composition)
4. Otherwise compose SAL from individual opcodes using the composition doctrine
5. Use `osmp_validate` to check your composed SAL before emission
6. Use `osmp_discover` to find domain codes you don't know (keyword + optional prefix)
7. Use `osmp_resolve` for exact code lookup once you have the code
8. Use `osmp_compound_decode` to check DAG topology before transmitting
9. Use `osmp_decode` to parse received instructions

## Composition Rules

SAL has a grammar (how to write a legal instruction) and a usage doctrine (which instruction to write). Both matter.

**The taco test:** `K:ORD` is financial order entry (ISO 20022). "Order me some tacos" is NL_PASSTHROUGH, not `K:ORD[TACOS]`. Read the ASD definition, not the mnemonic.

**The lookup gate:** Always call `osmp_lookup` before composing. If the opcode doesn't exist in the dictionary, it doesn't exist in the protocol.

**Composition priority:** (1) Registered MACRO if available, (2) individual opcode composition, (3) NL_PASSTHROUGH if no dictionary coverage.

**R namespace safety:** Every R namespace instruction (except R:ESTOP) requires a consequence class (⚠ ↺ ⊘). ⚠ and ⊘ require I:§ human confirmation. Aerial = ⚠. Ground + humans = ⚠. No medium declared = ⚠.

**Validation:** Call `osmp_validate` after composing and before emitting. It catches hallucinated opcodes, missing consequence classes, namespace-as-target errors, byte inflation, and other structural violations.

Full composition doctrine: [`docs/SAL-usage-doctrine-v1.md`](https://github.com/octid-io/cloudless-sky/blob/main/docs/SAL-usage-doctrine-v1.md)

## Context Window Footprint

~124 tokens on connect (server instructions + tool schemas + resource listings). ~514 tokens total after reading the system prompt. Composition rules added to prevent common grammar errors observed during agent testing. Still under 0.3% of a 200K context window.

## Links

- [octid.io](https://octid.io)
- [GitHub](https://github.com/octid-io/cloudless-sky)
- [OSMP Spec](https://github.com/octid-io/cloudless-sky/blob/main/protocol/spec/OSMP-SPEC-v1.md)

## License

Apache 2.0 with express patent grant.

<!-- mcp-name: io.github.Octid-io/osmp -->
