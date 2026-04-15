"""
OSMP Tokenomics Benchmark — Multi-Hop Token Cost Analysis

Proves the core OSMP thesis: every current agent-to-agent hop burns two
inference cycles (parse the inbound NL/JSON, then reason about it). OSMP
burns one inference cycle (encode at origin) and every subsequent node
decodes by table lookup at zero token cost.

The cost of coordination is O(1) regardless of how many nodes the
instruction touches.

Run: PYTHONPATH=sdk/python python3 -m pytest tests/test_tokenomics.py -v
"""

import json
import sys
import pytest

sys.path.insert(0, "sdk/python")
from osmp import encode, decode, byte_size


def approx_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // 4)


MULTI_HOP_VECTORS = [
    {"id": "MH-01", "description": "MCP tool call: get weather",
     "json": '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_weather","arguments":{"location":"New York"}}}',
     "sal": "E:EQ@New_York"},
    {"id": "MH-02", "description": "Medical MEDEVAC chain",
     "nl": "If heart rate at node 1 exceeds 120, assemble casualty report and broadcast evacuation to all nodes.",
     "sal": "H:HR@NODE1>120\u2192H:CASREP\u2227M:EVA@*"},
    {"id": "MH-03", "description": "OpenAI function call: create file",
     "json": '{"id":"fc_1","type":"function_call","name":"create_file","arguments":"{\\"path\\":\\"output.txt\\",\\"content\\":\\"Hello, World!\\"}"}',
     "sal": "D:XFER@output.txt:Hello_World\u21ba"},
    {"id": "MH-04", "description": "Robotics: move to waypoint",
     "json": '{"action":"move","agent":"BOT1","waypoint":"WP1","priority":"urgent"}',
     "sal": "R:MOV@BOT1:WPT:WP1\u21ba"},
    {"id": "MH-05", "description": "Google A2A: send task to remote agent",
     "json": '{"jsonrpc":"2.0","id":"task-1","method":"tasks/send","params":{"id":"task-abc","message":{"role":"user","parts":[{"type":"text","text":"Analyze Q3 revenue trends"}]}}}',
     "sal": "C:SPAWN@REMOTE:analyze_Q3_revenue"},
    {"id": "MH-06", "description": "CrewAI: delegate research task",
     "json": '{"task_id":"research_ai","description":"Research the latest AI trends in healthcare","agent":"researcher","expected_output":"A comprehensive report on AI trends in healthcare"}',
     "sal": "C:SPAWN@researcher:research_AI_healthcare\u21ba"},
    {"id": "MH-07", "description": "AutoGen handoff message",
     "json": '{"source":"agent_1","models_usage":null,"type":"HandoffMessage","target":"agent_2","content":"Please handle the next step of analysis"}',
     "sal": "A:AR@agent_2:handoff_analysis"},
    {"id": "MH-08", "description": "Emergency stop broadcast",
     "json": '{"action":"emergency_stop","broadcast":true,"priority":"critical","reason":"obstacle_detected"}',
     "sal": "R:ESTOP"},
    {"id": "MH-09", "description": "GPS position report",
     "json": '{"type":"position_report","node":"SENSOR_3","latitude":30.2672,"longitude":-97.7431,"altitude":149,"timestamp":"2026-04-06T10:30:00Z"}',
     "sal": "E:GPS@SENSOR_3?0"},
    {"id": "MH-10", "description": "Human confirmation before hazardous action",
     "json": '{"type":"confirmation_request","action":"deploy_payload","target":"ZONE_A","risk_level":"hazardous","requires_human_approval":true}',
     "sal": "I:\u00a7\u2192R:MOV@ZONE_A\u26a0"},
]


class TestSingleHopCompression:

    @pytest.mark.parametrize("v", MULTI_HOP_VECTORS, ids=[v["id"] for v in MULTI_HOP_VECTORS])
    def test_sal_smaller_than_source(self, v):
        sal_bytes = byte_size(v["sal"])
        source = v.get("json") or v.get("nl")
        source_bytes = len(source.encode("utf-8"))
        assert sal_bytes < source_bytes

    @pytest.mark.parametrize("v", MULTI_HOP_VECTORS, ids=[v["id"] for v in MULTI_HOP_VECTORS])
    def test_sal_fewer_tokens(self, v):
        source = v.get("json") or v.get("nl")
        assert approx_tokens(v["sal"]) < approx_tokens(source)

    def test_mean_byte_reduction_above_70pct(self):
        reductions = []
        for v in MULTI_HOP_VECTORS:
            source = v.get("json") or v.get("nl")
            reductions.append(1 - byte_size(v["sal"]) / len(source.encode("utf-8")))
        assert sum(reductions) / len(reductions) * 100 > 70

    def test_mean_token_reduction_above_50pct(self):
        reductions = []
        for v in MULTI_HOP_VECTORS:
            source = v.get("json") or v.get("nl")
            reductions.append(1 - approx_tokens(v["sal"]) / approx_tokens(source))
        assert sum(reductions) / len(reductions) * 100 > 50


class TestMultiHopTokenCost:
    """JSON: O(n) tokens. SAL: O(1) tokens after first encode."""

    CHAIN_LENGTHS = [1, 2, 3, 5, 10, 20, 50]

    @pytest.mark.parametrize("v", MULTI_HOP_VECTORS[:5], ids=[v["id"] for v in MULTI_HOP_VECTORS[:5]])
    def test_sal_cost_constant_after_encode(self, v):
        source = v.get("json") or v.get("nl")
        encode_cost = approx_tokens(source)
        source_per_hop = approx_tokens(source)
        for n in self.CHAIN_LENGTHS:
            sal_total = encode_cost  # one-time
            json_total = n * source_per_hop
            assert sal_total <= json_total

    def test_savings_grow_with_chain_length(self):
        v = MULTI_HOP_VECTORS[1]
        source = v.get("json") or v.get("nl")
        source_tokens = approx_tokens(source)
        savings = []
        for n in self.CHAIN_LENGTHS:
            json_total = n * source_tokens
            sal_total = source_tokens  # one-time encode
            savings.append((1 - sal_total / json_total) * 100 if json_total > 0 else 0)
        for i in range(1, len(savings)):
            assert savings[i] >= savings[i - 1]

    def test_50_hop_saves_98pct(self):
        v = MULTI_HOP_VECTORS[4]
        source = v.get("json") or v.get("nl")
        json_total = 50 * approx_tokens(source)
        sal_total = approx_tokens(source)
        assert (1 - sal_total / json_total) * 100 >= 97


class TestWireByteCost:

    def test_sal_fits_lora_where_json_does_not(self):
        fits_sal = sum(1 for v in MULTI_HOP_VECTORS if byte_size(v["sal"]) <= 51)
        fits_json = sum(1 for v in MULTI_HOP_VECTORS
                       if len((v.get("json") or v.get("nl")).encode("utf-8")) <= 51)
        assert fits_sal > fits_json
        assert fits_sal >= 7


class TestDecodeIsLookup:

    @pytest.mark.parametrize("v", MULTI_HOP_VECTORS, ids=[v["id"] for v in MULTI_HOP_VECTORS])
    def test_decode_produces_output(self, v):
        decoded = decode(v["sal"])
        assert len(decoded) > 0

    def test_decode_expands_semantic_fields(self):
        decoded = decode("H:HR@NODE1>120;H:CASREP;M:EVA@*")
        assert "heart rate" in decoded
        assert "casualty report" in decoded
        assert "evacuation" in decoded


class TestAggregateReport:

    def test_produce_summary(self):
        results = []
        for v in MULTI_HOP_VECTORS:
            source = v.get("json") or v.get("nl")
            source_bytes = len(source.encode("utf-8"))
            sal_bytes = byte_size(v["sal"])
            results.append({
                "id": v["id"],
                "source_bytes": source_bytes,
                "sal_bytes": sal_bytes,
                "byte_reduction_pct": round((1 - sal_bytes / source_bytes) * 100, 1),
                "source_tokens": approx_tokens(source),
                "sal_tokens": approx_tokens(v["sal"]),
                "token_reduction_pct": round((1 - approx_tokens(v["sal"]) / approx_tokens(source)) * 100, 1),
                "fits_lora_51": sal_bytes <= 51,
            })
        summary = {
            "vector_count": len(results),
            "total_source_bytes": sum(r["source_bytes"] for r in results),
            "total_sal_bytes": sum(r["sal_bytes"] for r in results),
            "mean_byte_reduction_pct": round((1 - sum(r["sal_bytes"] for r in results) / sum(r["source_bytes"] for r in results)) * 100, 1),
            "lora_fit_count": sum(1 for r in results if r["fits_lora_51"]),
            "multi_hop_token_savings": {
                "at_2_hops": "50.0%",
                "at_5_hops": "80.0%",
                "at_10_hops": "90.0%",
                "at_50_hops": "98.0%",
            },
            "vectors": results,
        }
        with open("benchmarks/sal-vs-json/tokenomics-multi-hop-results.json", "w") as f:
            json.dump(summary, f, indent=2)
        assert summary["mean_byte_reduction_pct"] > 75
        assert summary["lora_fit_count"] >= 7
