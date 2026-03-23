#!/usr/bin/env python3
"""
Protobuf Wire Format Size Calculator for OSMP Benchmark
Computes exact serialized sizes for Protocol Buffers with compiled schemas.

Protobuf wire format reference:
https://protobuf.dev/programming-guides/encoding/

Wire types:
  0 = varint (int32, int64, uint32, uint64, sint32, sint64, bool, enum)
  2 = length-delimited (string, bytes, embedded messages)

Field tag = (field_number << 3) | wire_type
  field_number 1-15: 1-byte tag
  field_number 16-2047: 2-byte tag

String field: tag(1B) + varint_length(1B for len<128) + utf8_bytes
Int field: tag(1B) + varint_bytes(1-10B)
Bool field: tag(1B) + 1B
Nested message: tag(1B) + varint_length(1B) + content_bytes
"""

import json
import math


def varint_size(value: int) -> int:
    """Compute bytes needed for a varint encoding."""
    if value < 0:
        return 10  # negative varints always 10 bytes
    if value == 0:
        return 1
    return math.ceil(math.log2(max(value, 1) + 1) / 7) if value > 0 else 1


def field_tag_size(field_number: int) -> int:
    """Field tag size: 1 byte for fields 1-15, 2 for 16-2047."""
    if field_number <= 15:
        return 1
    elif field_number <= 2047:
        return 2
    else:
        return 3


def proto_string(field_num: int, value: str) -> int:
    """Byte cost of a string field in protobuf wire format."""
    utf8_len = len(value.encode('utf-8'))
    return field_tag_size(field_num) + varint_size(utf8_len) + utf8_len


def proto_int(field_num: int, value: int) -> int:
    """Byte cost of an int32/int64 varint field."""
    return field_tag_size(field_num) + varint_size(value)


def proto_bool(field_num: int) -> int:
    """Byte cost of a bool field."""
    return field_tag_size(field_num) + 1


def proto_nested(field_num: int, content_size: int) -> int:
    """Byte cost of a nested message field (tag + length + content)."""
    return field_tag_size(field_num) + varint_size(content_size) + content_size


def proto_float(field_num: int) -> int:
    """Byte cost of a float field (always 4 bytes + tag)."""
    return field_tag_size(field_num) + 4


def proto_double(field_num: int) -> int:
    """Byte cost of a double field (always 8 bytes + tag)."""
    return field_tag_size(field_num) + 8


# ============================================================================
# Protobuf schema definitions for each vector
#
# For each JSON payload, we define what a reasonable .proto schema would
# look like, then compute the serialized size of the same semantic content.
#
# Principle: we are generous to protobuf. We assign low field numbers
# (1-15, all 1-byte tags), use the most compact types available, and
# assume a well-designed schema. This is the STRONGEST binary comparator.
# ============================================================================

def compute_proto_sizes():
    """Compute protobuf wire format sizes for all 29 test vectors."""

    results = []

    # === MCP VECTORS ===

    # MCP-01: tools/call get_weather(location="New York")
    # Proto schema: message ToolCall { string method=1; string name=2; string location=3; }
    # No jsonrpc version, no id -- those are transport framing protobuf wouldn't carry
    # BUT to be fair, we include method and tool name as protobuf would need routing info
    inner = proto_string(3, "New York")  # location
    tool = proto_string(1, "tools/call") + proto_string(2, "get_weather") + inner
    results.append(("MCP-01", tool, "tools/call + get_weather + location"))

    # MCP-02: tools/call response with weather text
    # Proto: message ToolResult { string text=1; bool is_error=2; }
    text = "Current weather in New York:\nTemperature: 72\u00b0F\nConditions: Partly cloudy"
    r = proto_string(1, text) + proto_bool(2)
    results.append(("MCP-02", r, "text result + is_error"))

    # MCP-03: tools/call error response
    text = "Invalid departure date: must be in the future. Current date is 08/08/2025."
    r = proto_string(1, text) + proto_bool(2)
    results.append(("MCP-03", r, "error text + is_error=true"))

    # MCP-04: tools/list request with cursor
    # Proto: message ListRequest { string method=1; string cursor=2; }
    r = proto_string(1, "tools/list") + proto_string(2, "optional-cursor-value")
    results.append(("MCP-04", r, "method + cursor"))

    # MCP-05: progress notification
    # Proto: message Progress { string token=1; int32 progress=2; int32 total=3; string message=4; }
    r = (proto_string(1, "operation-123") +
         proto_int(2, 75) + proto_int(3, 100) +
         proto_string(4, "Processing files..."))
    results.append(("MCP-05", r, "token + progress + total + message"))

    # === OPENAI VECTORS ===

    # OAI-01: function call get_weather
    # Proto: message FuncCall { string name=1; string location=2; string unit=3; }
    r = proto_string(1, "get_weather") + proto_string(2, "Paris") + proto_string(3, "celsius")
    results.append(("OAI-01", r, "name + location + unit"))

    # OAI-02: function output
    # Proto: message FuncOutput { string call_id=1; int32 temperature=2; string unit=3; }
    r = proto_string(1, "call_12345xyz") + proto_int(2, 25) + proto_string(3, "C")
    results.append(("OAI-02", r, "call_id + temperature + unit"))

    # OAI-03: function definition (schema)
    # Proto: message FuncDef { string name=1; string description=2; string param_name=3; string param_type=4; string param_desc=5; bool required=6; }
    r = (proto_string(1, "get_delivery_date") +
         proto_string(2, "Get the delivery date for a customer order.") +
         proto_string(3, "order_id") + proto_string(4, "string") +
         proto_string(5, "The customer order ID.") + proto_bool(6))
    results.append(("OAI-03", r, "func definition with schema"))

    # OAI-04: tool call with order_id
    # Proto: message ToolCall { string call_id=1; string name=2; string order_id=3; }
    r = (proto_string(1, "call_62136354") +
         proto_string(2, "get_delivery_date") +
         proto_string(3, "order_12345"))
    results.append(("OAI-04", r, "call_id + name + order_id"))

    # OAI-05: tool result
    # Proto: message ToolResult { string call_id=1; string delivery_date=2; }
    r = proto_string(1, "call_62136354") + proto_string(2, "2025-09-15")
    results.append(("OAI-05", r, "call_id + delivery_date"))

    # === A2A VECTORS ===

    # A2A-01: message/send with text
    # Proto: message A2AMessage { string method=1; string role=2; string text=3; string msg_id=4; }
    r = (proto_string(1, "message/send") + proto_string(2, "user") +
         proto_string(3, "Search for flights from NYC to London on December 15") +
         proto_string(4, "msg-001"))
    results.append(("A2A-01", r, "method + role + text + msg_id"))

    # A2A-02: task response with artifact
    # Proto: message TaskResponse { string task_id=1; string state=2; string timestamp=3; string artifact_id=4; string artifact_text=5; }
    r = (proto_string(1, "task-456") + proto_string(2, "completed") +
         proto_string(3, "2025-12-01T10:30:00Z") + proto_string(4, "art-001") +
         proto_string(5, "Found 3 flights. Best: BA117 departing 18:30, arriving 06:45+1, $489"))
    results.append(("A2A-02", r, "task response with artifact"))

    # A2A-03: agent card
    # Proto: message AgentCard { string name=1; string description=2; string url=3; string version=4; bool streaming=5; bool push=6; string skill_id=7; string skill_name=8; string skill_desc=9; }
    r = (proto_string(1, "Weather Agent") +
         proto_string(2, "Provides real-time weather information") +
         proto_string(3, "https://weather-agent.example.com") +
         proto_string(4, "1.0.0") + proto_bool(5) + proto_bool(6) +
         proto_string(7, "get-weather") + proto_string(8, "Get Weather") +
         proto_string(9, "Returns current weather for a location"))
    results.append(("A2A-03", r, "agent card with capabilities"))

    # A2A-04: financial transfer data part
    # Proto: message Transfer { string action=1; string from=2; string to=3; double amount=4; string currency=5; }
    r = (proto_string(1, "transfer") + proto_string(2, "ACC-001") +
         proto_string(3, "ACC-002") + proto_double(4) + proto_string(5, "USD"))
    results.append(("A2A-04", r, "transfer action with accounts"))

    # === CREWAI VECTORS ===

    # CREW-01: task delegation
    # Proto: message Task { string description=1; string expected_output=2; string agent_role=3; string agent_goal=4; string tool=5; bool async=6; }
    r = (proto_string(1, "Find and summarize the latest AI news") +
         proto_string(2, "A bullet list summary of the top 5 most important AI news") +
         proto_string(3, "AI Technology Researcher") +
         proto_string(4, "Research the latest AI developments") +
         proto_string(5, "SerperDevTool") + proto_bool(6))
    results.append(("CREW-01", r, "task with agent and tool"))

    # CREW-02: task output
    # Proto: message TaskOutput { string description=1; string summary=2; string raw=3; repeated string main_points=4; repeated string technologies=5; string agent=6; }
    r = (proto_string(1, "Find and summarize the latest AI news") +
         proto_string(2, "Top 5 AI developments: GPT-5 launch, Claude 4 release, Gemini 2.0, Llama 4, Mistral Large 3") +
         proto_string(3, "## Top 5 AI News\n1. GPT-5 launched with...") +
         proto_string(4, "GPT-5 launch") + proto_string(5, "Claude 4") + proto_string(6, "Gemini 2.0") +
         proto_string(7, "transformers") + proto_string(8, "MoE") + proto_string(9, "RLHF") +
         proto_string(10, "AI Technology Researcher"))
    results.append(("CREW-02", r, "task output with structured data"))

    # CREW-03: conversation history (3 messages)
    # Proto: message Message { string role=1; string content=2; }
    # repeated Message messages = 1
    msg1 = proto_string(1, "user") + proto_string(2, "I need information about large language models")
    msg2 = proto_string(1, "assistant") + proto_string(2, "I'd be happy to help with that! What specifically would you like to know?")
    msg3 = proto_string(1, "user") + proto_string(2, "What are the latest developments in 2025?")
    r = proto_nested(1, msg1) + proto_nested(1, msg2) + proto_nested(1, msg3)
    results.append(("CREW-03", r, "3-message conversation history"))

    # CREW-04: task with context deps
    # Proto: message Task { string description=1; string expected_output=2; string agent=3; repeated string context=4; }
    r = (proto_string(1, "Write a full blog post about the importance of AI and its latest news") +
         proto_string(2, "Full blog post that is 4 paragraphs long") +
         proto_string(3, "writer_agent") +
         proto_string(4, "research_ai_task") + proto_string(5, "research_ops_task"))
    results.append(("CREW-04", r, "task with context dependencies"))

    # === AUTOGEN VECTORS ===

    # AG-01: HandoffMessage
    # Proto: message Handoff { string id=1; string source=2; string content=3; string target=4; string created_at=5; }
    r = (proto_string(1, "msg-hnd-001") + proto_string(2, "assistant") +
         proto_string(3, "Transferred to flights_refunder, adopting the role of flights_refunder immediately.") +
         proto_string(4, "flights_refunder") +
         proto_string(5, "2025-11-01T10:00:00Z"))
    results.append(("AG-01", r, "handoff message"))

    # AG-02: StructuredMessage
    # Proto: message Structured { string source=1; string thoughts=2; string response=3; string created_at=4; }
    r = (proto_string(1, "assistant") +
         proto_string(2, "The user expressed positive emotion with exclamation.") +
         proto_string(3, "happy") +
         proto_string(4, "2025-11-01T10:05:00Z"))
    results.append(("AG-02", r, "structured categorization"))

    # AG-03: function_call message
    # Proto: message FuncCallMsg { string name=1; string arguments=2; }
    code = "import matplotlib.pyplot as plt\nfig, ax = plt.subplots()\nax.text(0.5, 0.5, 'Hello')\nplt.savefig('output.png')"
    r = proto_string(1, "python") + proto_string(2, code)
    results.append(("AG-03", r, "function call with code"))

    # AG-04: component serialization (agent config)
    # Proto: message AgentConfig { string provider=1; string type=2; int32 version=3; string name=4; string model_provider=5; string model=6; repeated Handoff handoffs=7; string system_msg=8; string description=9; }
    handoff1_inner = (proto_string(1, "flights_refunder") +
                      proto_string(2, "Handoff to flights_refunder.") +
                      proto_string(3, "transfer_to_flights_refunder") +
                      proto_string(4, "Transferred to flights_refunder, adopting the role of flights_refunder immediately."))
    handoff2_inner = (proto_string(1, "user") +
                      proto_string(2, "Handoff to user.") +
                      proto_string(3, "transfer_to_user") +
                      proto_string(4, "Transferred to user, adopting the role of user immediately."))
    r = (proto_string(1, "autogen_agentchat.agents.AssistantAgent") +
         proto_string(2, "agent") + proto_int(3, 1) +
         proto_string(4, "assistant") +
         proto_string(5, "autogen_ext.models.openai.OpenAIChatCompletionClient") +
         proto_string(6, "gpt-4o") +
         proto_nested(7, handoff1_inner) + proto_nested(7, handoff2_inner) +
         proto_string(8, "Use tools to solve tasks.") +
         proto_string(9, "An agent that provides assistance with ability to use tools."))
    results.append(("AG-04", r, "full agent config serialization"))

    # === DOMAIN VECTORS ===

    # DOM-01: ICD-10 lookup
    # Proto: message CodeLookup { string method=1; string tool=2; string system=3; string code=4; bool include_desc=5; }
    r = (proto_string(1, "tools/call") + proto_string(2, "lookup_diagnosis") +
         proto_string(3, "ICD-10-CM") + proto_string(4, "J93.9") + proto_bool(5))
    results.append(("DOM-01", r, "ICD-10 code lookup"))

    # DOM-02: payment transfer
    # Proto: message Payment { string call_id=1; string name=2; string from=3; string to=4; double amount=5; string currency=6; string ref=7; }
    r = (proto_string(1, "call_pay_001") + proto_string(2, "execute_payment") +
         proto_string(3, "ACC-1234") + proto_string(4, "ACC-5678") +
         proto_double(5) + proto_string(6, "USD") + proto_string(7, "INV-2025-0042"))
    results.append(("DOM-02", r, "payment execution"))

    # DOM-03: encrypt + rotate
    # Proto: message CryptoOp { string method=1; string target=2; string algorithm=3; bool rotate=4; }
    r = (proto_string(1, "message/send") +
         proto_string(2, "msg-body-445") + proto_string(3, "AES-256-GCM") + proto_bool(4))
    results.append(("DOM-03", r, "encrypt and rotate"))

    # DOM-04: scale + limit
    # Proto: message ScaleOp { string service=1; int32 replicas=2; string cpu=3; string memory=4; }
    r = (proto_string(1, "api-gateway") + proto_int(2, 5) +
         proto_string(3, "2000m") + proto_string(4, "4Gi"))
    results.append(("DOM-04", r, "scale and resource limit"))

    # DOM-05: audit log
    # Proto: message AuditLog { string description=1; string agent_role=2; string agent_goal=3; string txn_id=4; string check=5; string result=6; string severity=7; string timestamp=8; }
    r = (proto_string(1, "Log the compliance check result for transaction TXN-9921") +
         proto_string(2, "Compliance Officer") +
         proto_string(3, "Maintain regulatory compliance audit trail") +
         proto_string(4, "TXN-9921") + proto_string(5, "AML") +
         proto_string(6, "pass") + proto_string(7, "informational") +
         proto_string(8, "2025-12-01T14:30:00Z"))
    results.append(("DOM-05", r, "compliance audit log"))

    # DOM-06: ATT&CK lookup
    # Proto: message AttackLookup { string method=1; string tool=2; string framework=3; string technique=4; bool subtechniques=5; bool mitigations=6; }
    r = (proto_string(1, "tools/call") + proto_string(2, "lookup_attack_technique") +
         proto_string(3, "MITRE ATT&CK") + proto_string(4, "T1566") +
         proto_bool(5) + proto_bool(6))
    results.append(("DOM-06", r, "ATT&CK technique lookup"))

    # DOM-07: route calculation
    # Proto: message RouteCalc { string call_id=1; string name=2; double orig_lat=3; double orig_lng=4; double dest_lat=5; double dest_lng=6; string mode=7; string avoid=8; }
    r = (proto_string(1, "call_nav_001") + proto_string(2, "calculate_route") +
         proto_double(3) + proto_double(4) +  # origin lat/lng
         proto_double(5) + proto_double(6) +  # dest lat/lng
         proto_string(7, "driving") + proto_string(8, "tolls"))
    results.append(("DOM-07", r, "route calculation"))

    return results


if __name__ == "__main__":
    # Load the existing benchmark data
    with open("benchmarks/sal-vs-json/sal-vs-json-vectors.json", encoding="utf-8") as f:
        vectors = json.load(f)["vectors"]

    proto_results = compute_proto_sizes()

    # Build lookup
    vector_map = {v["id"]: v for v in vectors}

    print("=" * 110)
    print("  FOUR-WAY COMPARISON: JSON vs MessagePack vs Protocol Buffers vs SAL")
    print("  Protobuf: compiled schema, optimal field numbering (1-15), wire format sizes")
    print("=" * 110)
    print()
    print(f"  {'ID':<10} {'JSON':>7} {'MsgPack':>8} {'Protobuf':>9} {'SAL':>6} {'PB%json':>8} {'SAL%json':>9} {'SAL%PB':>7}")
    print(f"  {'-'*10} {'-'*7} {'-'*8} {'-'*9} {'-'*6} {'-'*8} {'-'*9} {'-'*7}")

    total_json = total_mp = total_pb = total_sal = 0

    for vid, pb_size, notes in proto_results:
        v = vector_map[vid]
        jb = v["json_bytes"]
        sb = v["sal_bytes"]

        # Get msgpack from token analysis
        import msgpack
        json_obj = json.loads(v["json_payload"])
        mp = len(msgpack.packb(json_obj, use_bin_type=True))

        pb_vs_json = (1 - pb_size / jb) * 100
        sal_vs_json = (1 - sb / jb) * 100
        sal_vs_pb = (1 - sb / pb_size) * 100

        total_json += jb
        total_mp += mp
        total_pb += pb_size
        total_sal += sb

        print(f"  {vid:<10} {jb:>7} {mp:>8} {pb_size:>9} {sb:>6} {pb_vs_json:>7.1f}% {sal_vs_json:>8.1f}% {sal_vs_pb:>6.1f}%")

    print()
    print("-" * 110)
    mp_vs_json = (1 - total_mp / total_json) * 100
    pb_vs_json = (1 - total_pb / total_json) * 100
    sal_vs_json = (1 - total_sal / total_json) * 100
    sal_vs_pb = (1 - total_sal / total_pb) * 100
    sal_vs_mp = (1 - total_sal / total_mp) * 100

    print(f"  TOTALS:")
    print(f"    JSON (minified):          {total_json:>6} bytes")
    print(f"    MessagePack:              {total_mp:>6} bytes  ({mp_vs_json:.1f}% reduction vs JSON)")
    print(f"    Protocol Buffers:         {total_pb:>6} bytes  ({pb_vs_json:.1f}% reduction vs JSON)")
    print(f"    SAL:                      {total_sal:>6} bytes  ({sal_vs_json:.1f}% reduction vs JSON)")
    print()
    print(f"  SAL vs Protocol Buffers:    {sal_vs_pb:.1f}% reduction")
    print(f"  SAL vs MessagePack:         {sal_vs_mp:.1f}% reduction")
    print(f"  Protobuf vs MessagePack:    {(1 - total_pb / total_mp) * 100:.1f}% reduction")
    print("=" * 110)

    # Also verify the 79-byte envelope claim
    print()
    print("ENVELOPE VERIFICATION:")
    envelope = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"","arguments":{}}}'
    print(f'  Exact string: {envelope}')
    print(f'  Byte count: {len(envelope.encode("utf-8"))}')
    print(f'  (Paper claimed 79. Actual is {len(envelope.encode("utf-8"))})')

    # Export
    export = {
        "comparison": "JSON vs MessagePack vs Protocol Buffers vs SAL",
        "protobuf_method": "Analytical wire format calculation, optimal field numbering (1-15)",
        "totals": {
            "json_bytes": total_json,
            "msgpack_bytes": total_mp,
            "protobuf_bytes": total_pb,
            "sal_bytes": total_sal,
        },
        "reductions_vs_json": {
            "msgpack": round(mp_vs_json, 1),
            "protobuf": round(pb_vs_json, 1),
            "sal": round(sal_vs_json, 1),
        },
        "sal_vs_protobuf": round(sal_vs_pb, 1),
    }
    with open("benchmarks/sal-vs-json/four-way-comparison.json", "w") as f:
        json.dump(export, f, indent=2)
    print(f"\n  Exported to: benchmarks/sal-vs-json/four-way-comparison.json")
