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

## Key Results

| Format | Total Bytes (29 vectors) | Reduction vs JSON |
|--------|------------------------|-------------------|
| JSON (minified) | 6,896 | baseline |
| MessagePack | 5,848 | 15.2% |
| Protocol Buffers | 3,081 | 55.3% |
| SAL | 928 | 86.5% |

Token reduction (GPT-4 cl100k_base): 75.6% (1,809 JSON tokens vs 441 SAL tokens).

See the [full analysis](../docs/SAL-efficiency-analysis.md) for methodology, prosecution, and limitations.
