# OSMP SAL vs JSON Benchmark Suite

Encoding efficiency comparison: SAL (Semantic Assembly Language) vs JSON-RPC vs MessagePack vs Protocol Buffers.

Supporting data for [SAL Efficiency Analysis](../docs/SAL-efficiency-analysis.md).

## Quick Start

```bash
pip install tiktoken msgpack protobuf

# 29-vector empirical benchmark (5 frameworks)
python3 benchmark.py

# 1,000-point grammar-level structural sweep
python3 grammar-analysis.py

# Four-way format comparison (JSON / MsgPack / Protobuf / SAL)
python3 protobuf-comparison.py
```

## Scripts

| File | What It Does |
|------|-------------|
| benchmark.py | 29 real JSON payloads from MCP, OpenAI, A2A, CrewAI, AutoGen. Measures byte counts and SAL equivalents. Runs token analysis via tiktoken (cl100k_base). |
| benchmark.proto | Compiled .proto schemas for all 29 vectors. Verified with protoc 3.21.12. |
| grammar-analysis.py | Sweeps composition parameter space (params, chain length, nesting depth). Computes structural overhead ratios. Runs Shannon entropy on structural token corpora. |
| protobuf-comparison.py | Analytical Protocol Buffers wire format calculation. Four-way comparison table. Verifies the 82-byte JSON-RPC envelope. |

## Result Files

| File | Contents |
|------|----------|
| benchmark-results.json | Aggregate stats from 29-vector benchmark |
| sal-vs-json-vectors.json | Full vector metadata with source URLs |
| grammar-analysis-results.json | 1,000-point sweep data |
| four-way-comparison.json | JSON / MsgPack / Protobuf / SAL totals |
| token-analysis-results.json | GPT-4 cl100k_base token counts per vector |
| dpack-comparison.json | Two-tier batch compression and per-vector D:PACK results |

## Key Results

| Format | Total Bytes (29 vectors) | Reduction vs JSON |
|--------|------------------------|-------------------|
| JSON (minified) | 6,896 | baseline |
| MessagePack | 5,848 | 15.2% |
| Protocol Buffers (compiled) | 3,075 | 55.4% |
| SAL | 908 | 86.8% |

Token reduction (GPT-4 cl100k_base): 76.0% (1,809 JSON tokens vs 434 SAL tokens).

Per-vector scoreboard vs compiled protobuf: SAL wins 28 of 29. The single protobuf win (DOM-04: Kubernetes scaling, protobuf 27B vs SAL 32B) is a deliberate design choice preserving human readability on numeric payloads. See [Section 6.3](../docs/SAL-efficiency-analysis.md#63-where-sal-loses) of the whitepaper.

See the [full analysis](../docs/SAL-efficiency-analysis.md) for methodology, prosecution, and limitations.
