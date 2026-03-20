# OSMP MCP Server

MCP server that gives any MCP-compatible AI client native OSMP capability. The client doesn't need to "know" OSMP. It calls the tools. The protocol spreads through the tool ecosystem rather than through training data or prompt engineering.

## Tools

| Tool | Description |
|---|---|
| `osmp_encode` | Structured fields to SAL instruction string |
| `osmp_decode` | SAL instruction string to structured fields (table lookup, no inference) |
| `osmp_resolve` | Single domain code to SAL description from D:PACK/BLK binary (ICD-10-CM, ISO 20022) |
| `osmp_benchmark` | Run the canonical conformance suite against the Python SDK |

## Resources

| URI | Description |
|---|---|
| `osmp://dictionary` | Full Adaptive Shared Dictionary (all namespace:opcode mappings) |
| `osmp://grammar` | SAL grammar specification (EBNF) |
| `osmp://corpora` | Available D:PACK/BLK domain corpora with stats |

## Setup

Requires Python 3.10+ and the `mcp` package.

```bash
cd cloudless-sky
pip install -r mcp/requirements.txt
```

Dependencies: `mcp[cli]>=1.2.0`, `zstandard>=0.22.0`. Total install is lightweight. The OSMP Python SDK (`sdk/python/src/osmp.py`) is imported directly from the repo; no separate install needed.

## Usage

### Claude Code

```bash
claude mcp add osmp -- python mcp/server.py
```

Run Claude Code from the `cloudless-sky` repo root.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
    "mcpServers": {
        "osmp": {
            "command": "python",
            "args": ["mcp/server.py"],
            "cwd": "/path/to/cloudless-sky"
        }
    }
}
```

### Cursor / Other MCP Clients

Any client supporting stdio transport can connect. The command is `python mcp/server.py` with the working directory set to the repo root.

### MCP Inspector (testing)

```bash
cd cloudless-sky
npx @modelcontextprotocol/inspector python mcp/server.py
```

## How It Propagates

An AI client connected to this MCP server can:

1. **Encode** natural language instructions as SAL (`osmp_encode`)
2. **Decode** SAL instructions received from other agents (`osmp_decode`)
3. **Resolve** domain codes from compressed corpora in flash-sized binaries (`osmp_resolve`)
4. **Verify** protocol conformance against the canonical test vectors (`osmp_benchmark`)

The client doesn't need OSMP in its training data. It doesn't need the grammar in its system prompt. It calls `osmp_encode` with structured fields and gets SAL back. The protocol becomes a tool the agent uses, not a language the agent learns.

## Architecture

```
AI Client (Claude, GPT, Cursor, etc.)
    |
    | MCP stdio
    |
OSMP MCP Server (this file, ~280 lines)
    |
    |-- SALEncoder / SALDecoder (sdk/python/src/osmp.py)
    |-- BlockCompressor.resolve() (D:PACK/BLK random access)
    |-- MDR binaries (mdr/*.dpack, 477KB ICD + 1.2MB ISO)
    |-- Test vectors (protocol/test-vectors/)
    |-- ASD (339 opcodes, compiled into SDK)
```

The server is a thin wrapper. All protocol logic lives in the Python SDK. The MCP layer adds tool definitions, input validation, and human-readable output formatting. No protocol logic is duplicated.
