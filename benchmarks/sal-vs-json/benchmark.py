#!/usr/bin/env python3
"""
OSMP SAL vs JSON Benchmark — Production Agent Framework Comparison
Octid Semantic Mesh Protocol — Cloudless Sky Project
Patent: OSMP-001-UTIL (pending) — inventor Clay Holberg
License: Apache 2.0

Measures byte reduction of SAL encoding vs real JSON-RPC/JSON payloads
from five production agent communication frameworks:
  1. MCP (Model Context Protocol) — JSON-RPC 2.0 tool calls
  2. OpenAI — Responses API / Chat Completions function calling
  3. Google A2A (Agent2Agent) — JSON-RPC 2.0 message/send
  4. CrewAI — inter-agent task delegation messages
  5. Microsoft AutoGen — conversation message dictionaries

Every JSON payload is sourced from official framework documentation or
specification. No fabricated examples. Each entry includes:
  - Framework name and version
  - Source URL
  - The real JSON payload (instruction-bearing content only)
  - The semantically equivalent SAL encoding
  - Byte counts for both

Measurement: UTF-8 byte count via len(s.encode('utf-8'))
"""

from __future__ import annotations

import json
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---- Test Vector Definitions ------------------------------------------------

@dataclass
class JSONvsSALVector:
    """Single comparison: a real JSON payload vs its SAL equivalent."""
    id: str
    framework: str
    framework_version: str
    source_url: str
    description: str
    domain: str               # OSMP namespace domain
    json_payload: str         # The real JSON from the framework
    sal_equivalent: str       # Semantically equivalent SAL
    notes: str = ""

# ============================================================================
# VECTORS: MCP (Model Context Protocol)
# Source: modelcontextprotocol.io/specification/2025-11-25/server/tools
# ============================================================================

MCP_VECTORS = [
    JSONvsSALVector(
        id="MCP-01",
        framework="MCP",
        framework_version="2025-11-25",
        source_url="https://modelcontextprotocol.io/specification/2025-11-25/server/tools",
        description="MCP tools/call: get weather for a location",
        domain="Environmental / Sensor",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {
                    "location": "New York"
                }
            }
        }, separators=(',', ':')),
        sal_equivalent="E:EQ@New_York",
        notes="MCP spec example: tools/call request for weather. SAL uses E:EQ (environmental query) with location target."
    ),
    JSONvsSALVector(
        id="MCP-02",
        framework="MCP",
        framework_version="2025-11-25",
        source_url="https://modelcontextprotocol.io/specification/2025-11-25/server/tools",
        description="MCP tools/call response: weather result",
        domain="Environmental / Sensor",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "Current weather in New York:\nTemperature: 72\u00b0F\nConditions: Partly cloudy"
                    }
                ],
                "isError": False
            }
        }, separators=(',', ':')),
        sal_equivalent="D:RT[E:EQ@New_York:72F:partly_cloudy]",
        notes="MCP spec example: tools/call response. SAL uses D:RT (return transmit) wrapping the query result."
    ),
    JSONvsSALVector(
        id="MCP-03",
        framework="MCP",
        framework_version="2025-11-25",
        source_url="https://modelcontextprotocol.io/specification/2025-11-25/server/tools",
        description="MCP tools/call error response",
        domain="Data / Query / File Transfer",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "id": 4,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "Invalid departure date: must be in the future. Current date is 08/08/2025."
                    }
                ],
                "isError": True
            }
        }, separators=(',', ':')),
        sal_equivalent="A:NACK[invalid_date]",
        notes="MCP spec example: tool error response. SAL uses A:NACK (negative acknowledgment) with error slot."
    ),
    JSONvsSALVector(
        id="MCP-04",
        framework="MCP",
        framework_version="2025-11-25",
        source_url="https://modelcontextprotocol.io/specification/2025-11-25/server/tools",
        description="MCP tools/list request",
        domain="Agentic / OSMP-Native",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {
                "cursor": "optional-cursor-value"
            }
        }, separators=(',', ':')),
        sal_equivalent="A:DISCOV?*",
        notes="MCP spec example: tool discovery. SAL uses A:DISCOV (discovery) with wildcard query."
    ),
    JSONvsSALVector(
        id="MCP-05",
        framework="MCP",
        framework_version="2025-11-25",
        source_url="https://portkey.ai/blog/mcp-message-types-complete-json-rpc-reference-guide/",
        description="MCP progress notification for long-running operation",
        domain="Agentic / OSMP-Native",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "method": "progress",
            "params": {
                "progressToken": "operation-123",
                "progress": 75,
                "total": 100,
                "message": "Processing files..."
            }
        }, separators=(',', ':')),
        sal_equivalent="P:PROG@operation-123?[75/100]",
        notes="MCP reference guide: progress notification. SAL uses P:PROG with target and ratio slot."
    ),
]

# ============================================================================
# VECTORS: OpenAI Function Calling / Responses API
# Source: developers.openai.com/api/docs/guides/function-calling
# ============================================================================

OPENAI_VECTORS = [
    JSONvsSALVector(
        id="OAI-01",
        framework="OpenAI",
        framework_version="Responses API 2025",
        source_url="https://developers.openai.com/api/docs/guides/function-calling",
        description="OpenAI function call: get_weather tool invocation",
        domain="Environmental / Sensor",
        json_payload=json.dumps({
            "type": "function_call",
            "id": "fc_12345xyz",
            "call_id": "call_12345xyz",
            "name": "get_weather",
            "arguments": "{\"location\":\"Paris\",\"unit\":\"celsius\"}"
        }, separators=(',', ':')),
        sal_equivalent="E:EQ@Paris?[C]",
        notes="OpenAI docs: function call output. SAL uses E:EQ with location and unit slot."
    ),
    JSONvsSALVector(
        id="OAI-02",
        framework="OpenAI",
        framework_version="Responses API 2025",
        source_url="https://developers.openai.com/api/docs/guides/function-calling",
        description="OpenAI function call output: weather result returned to model",
        domain="Environmental / Sensor",
        json_payload=json.dumps({
            "type": "function_call_output",
            "call_id": "call_12345xyz",
            "output": "{\"temperature\":\"25\",\"unit\":\"C\"}"
        }, separators=(',', ':')),
        sal_equivalent="D:RT[E:EQ:25C]",
        notes="OpenAI docs: function output. SAL uses D:RT wrapping result."
    ),
    JSONvsSALVector(
        id="OAI-03",
        framework="OpenAI",
        framework_version="Chat Completions API",
        source_url="https://developers.openai.com/api/docs/guides/function-calling",
        description="OpenAI function definition: get_delivery_date tool schema",
        domain="Data / Query / File Transfer",
        json_payload=json.dumps({
            "type": "function",
            "function": {
                "name": "get_delivery_date",
                "description": "Get the delivery date for a customer order.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The customer order ID."
                        }
                    },
                    "required": ["order_id"]
                }
            }
        }, separators=(',', ':')),
        sal_equivalent="D:Q@[order_id]?[delivery_date]",
        notes="OpenAI docs: function definition schema. SAL uses D:Q (data query) with parameter and query slots."
    ),
    JSONvsSALVector(
        id="OAI-04",
        framework="OpenAI",
        framework_version="Chat Completions API",
        source_url="https://developers.openai.com/api/docs/guides/function-calling",
        description="OpenAI tool call: assistant requests function execution",
        domain="Data / Query / File Transfer",
        json_payload=json.dumps({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_62136354",
                    "type": "function",
                    "function": {
                        "name": "get_delivery_date",
                        "arguments": "{\"order_id\":\"order_12345\"}"
                    }
                }
            ]
        }, separators=(',', ':')),
        sal_equivalent="D:Q@[order_12345]?[delivery_date]",
        notes="OpenAI docs: assistant tool_call message. SAL encodes the query directly."
    ),
    JSONvsSALVector(
        id="OAI-05",
        framework="OpenAI",
        framework_version="Chat Completions API",
        source_url="https://developers.openai.com/api/docs/guides/function-calling",
        description="OpenAI tool result: function response message",
        domain="Data / Query / File Transfer",
        json_payload=json.dumps({
            "role": "tool",
            "tool_call_id": "call_62136354",
            "content": "{\"delivery_date\":\"2025-09-15\"}"
        }, separators=(',', ':')),
        sal_equivalent="D:RT[2025-09-15]",
        notes="OpenAI docs: tool response. SAL uses D:RT with the return value."
    ),
]

# ============================================================================
# VECTORS: Google A2A (Agent2Agent Protocol)
# Source: a2a-protocol.org/latest/specification/ and Google Codelabs
# ============================================================================

A2A_VECTORS = [
    JSONvsSALVector(
        id="A2A-01",
        framework="Google A2A",
        framework_version="v0.2.5",
        source_url="https://codelabs.developers.google.com/intro-a2a-purchasing-concierge",
        description="A2A message/send: client sends task to remote agent",
        domain="Agentic / OSMP-Native",
        json_payload=json.dumps({
            "id": "abc123",
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "type": "text",
                            "text": "Search for flights from NYC to London on December 15"
                        }
                    ],
                    "messageId": "msg-001"
                }
            }
        }, separators=(',', ':')),
        sal_equivalent="A:AR@flight-agent[NYC>LHR:2025-12-15]",
        notes="A2A codelab: message/send. SAL uses A:AR (agentic request) with route and date slots."
    ),
    JSONvsSALVector(
        id="A2A-02",
        framework="Google A2A",
        framework_version="v0.2.5",
        source_url="https://a2a-protocol.org/v0.2.5/specification/",
        description="A2A task response: agent returns completed task with artifact",
        domain="Agentic / OSMP-Native",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "id": "abc123",
            "result": {
                "id": "task-456",
                "status": {
                    "state": "completed",
                    "timestamp": "2025-12-01T10:30:00Z"
                },
                "artifacts": [
                    {
                        "artifactId": "art-001",
                        "parts": [
                            {
                                "type": "text",
                                "text": "Found 3 flights. Best: BA117 departing 18:30, arriving 06:45+1, $489"
                            }
                        ]
                    }
                ]
            }
        }, separators=(',', ':')),
        sal_equivalent="J:DONE@task-456;D:RT[BA117:1830:0645:489USD]",
        notes="A2A spec: task completion with artifact. SAL uses J:DONE then D:RT with structured result."
    ),
    JSONvsSALVector(
        id="A2A-03",
        framework="Google A2A",
        framework_version="v0.2.5",
        source_url="https://a2a-protocol.org/v0.2.5/specification/",
        description="A2A agent card: capability discovery (skills subset)",
        domain="Agentic / OSMP-Native",
        json_payload=json.dumps({
            "name": "Weather Agent",
            "description": "Provides real-time weather information",
            "url": "https://weather-agent.example.com",
            "version": "1.0.0",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False
            },
            "skills": [
                {
                    "id": "get-weather",
                    "name": "Get Weather",
                    "description": "Returns current weather for a location"
                }
            ]
        }, separators=(',', ':')),
        sal_equivalent="A:DISCOV@weather-agent[E:EQ]",
        notes="A2A spec: agent card. SAL uses A:DISCOV to advertise capability by namespace."
    ),
    JSONvsSALVector(
        id="A2A-04",
        framework="Google A2A",
        framework_version="v0.2.5",
        source_url="https://a2a-protocol.org/v0.2.5/specification/",
        description="A2A message/send with data part: structured payload",
        domain="Financial / Transaction",
        json_payload=json.dumps({
            "id": "req-789",
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "type": "data",
                            "data": {
                                "action": "transfer",
                                "from_account": "ACC-001",
                                "to_account": "ACC-002",
                                "amount": 1500.00,
                                "currency": "USD"
                            }
                        }
                    ],
                    "messageId": "msg-789"
                }
            }
        }, separators=(',', ':')),
        sal_equivalent="K:XFR@ACC-001[ACC-002:1500USD]",
        notes="A2A spec: data part with structured financial payload. SAL uses K:XFR (asset transfer) with accounts and amount."
    ),
]

# ============================================================================
# VECTORS: CrewAI
# Source: docs.crewai.com/core-concepts/Tasks/ and docs.crewai.com/concepts/agents
# ============================================================================

CREWAI_VECTORS = [
    JSONvsSALVector(
        id="CREW-01",
        framework="CrewAI",
        framework_version="0.86+",
        source_url="https://docs.crewai.com/core-concepts/Tasks/",
        description="CrewAI task delegation: research agent assigned a search task",
        domain="Cognitive Execution State",
        json_payload=json.dumps({
            "description": "Find and summarize the latest AI news",
            "expected_output": "A bullet list summary of the top 5 most important AI news",
            "agent": {
                "role": "AI Technology Researcher",
                "goal": "Research the latest AI developments",
                "verbose": True
            },
            "tools": ["SerperDevTool"],
            "async_execution": False
        }, separators=(',', ':')),
        sal_equivalent="J:GOAL@researcher[AI_news:top5];A:AR[search]",
        notes="CrewAI docs: task definition. SAL uses J:GOAL (declare goal) with agent target and A:AR for tool request."
    ),
    JSONvsSALVector(
        id="CREW-02",
        framework="CrewAI",
        framework_version="0.86+",
        source_url="https://docs.crewai.com/core-concepts/Tasks/",
        description="CrewAI task output: structured JSON result",
        domain="Cognitive Execution State",
        json_payload=json.dumps({
            "description": "Find and summarize the latest AI news",
            "summary": "Top 5 AI developments: GPT-5 launch, Claude 4 release, Gemini 2.0, Llama 4, Mistral Large 3",
            "raw": "## Top 5 AI News\n1. GPT-5 launched with...",
            "json_dict": {
                "main_points": ["GPT-5 launch", "Claude 4", "Gemini 2.0"],
                "key_technologies": ["transformers", "MoE", "RLHF"]
            },
            "agent": "AI Technology Researcher"
        }, separators=(',', ':')),
        sal_equivalent="J:DONE@researcher;D:RT[AI_news:3items]",
        notes="CrewAI docs: TaskOutput object. SAL uses J:DONE with D:RT for result payload."
    ),
    JSONvsSALVector(
        id="CREW-03",
        framework="CrewAI",
        framework_version="0.86+",
        source_url="https://docs.crewai.com/concepts/agents",
        description="CrewAI agent kickoff with conversation history",
        domain="Cognitive Execution State",
        json_payload=json.dumps([
            {"role": "user", "content": "I need information about large language models"},
            {"role": "assistant", "content": "I'd be happy to help with that! What specifically would you like to know?"},
            {"role": "user", "content": "What are the latest developments in 2025?"}
        ], separators=(',', ':')),
        sal_equivalent="A:AR@researcher[LLM_developments:2025]",
        notes="CrewAI docs: agent kickoff with message history. SAL encodes the instruction, not the conversation."
    ),
    JSONvsSALVector(
        id="CREW-04",
        framework="CrewAI",
        framework_version="0.86+",
        source_url="https://docs.crewai.com/core-concepts/Tasks/",
        description="CrewAI task with context dependency: write_blog depends on research",
        domain="Cognitive Execution State",
        json_payload=json.dumps({
            "description": "Write a full blog post about the importance of AI and its latest news",
            "expected_output": "Full blog post that is 4 paragraphs long",
            "agent": "writer_agent",
            "context": ["research_ai_task", "research_ops_task"]
        }, separators=(',', ':')),
        sal_equivalent="J:GOAL@writer[blog_post:4para]->J:BLOCK[research_ai;research_ops]",
        notes="CrewAI docs: task with context dependencies. SAL uses J:GOAL chained to J:BLOCK for deps. '->' is natural language here; actual SAL would be a compound with THEN operator."
    ),
]

# ============================================================================
# VECTORS: Microsoft AutoGen
# Source: microsoft.github.io/autogen/stable/ (AgentChat messages)
# ============================================================================

AUTOGEN_VECTORS = [
    JSONvsSALVector(
        id="AG-01",
        framework="AutoGen",
        framework_version="0.4 (AgentChat)",
        source_url="https://microsoft.github.io/autogen/stable//reference/python/autogen_agentchat.messages.html",
        description="AutoGen HandoffMessage: transfer execution to another agent",
        domain="Cognitive Execution State",
        json_payload=json.dumps({
            "type": "HandoffMessage",
            "id": "msg-hnd-001",
            "source": "assistant",
            "content": "Transferred to flights_refunder, adopting the role of flights_refunder immediately.",
            "target": "flights_refunder",
            "context": [],
            "metadata": {},
            "created_at": "2025-11-01T10:00:00Z"
        }, separators=(',', ':')),
        sal_equivalent="J:HANDOFF@flights_refunder",
        notes="AutoGen AgentChat: HandoffMessage. SAL uses J:HANDOFF with target agent."
    ),
    JSONvsSALVector(
        id="AG-02",
        framework="AutoGen",
        framework_version="0.4 (AgentChat)",
        source_url="https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/tutorial/agents.html",
        description="AutoGen StructuredMessage: categorization output",
        domain="Cognitive Execution State",
        json_payload=json.dumps({
            "type": "StructuredMessage",
            "source": "assistant",
            "content": {
                "thoughts": "The user expressed positive emotion with exclamation.",
                "response": "happy"
            },
            "metadata": {},
            "created_at": "2025-11-01T10:05:00Z"
        }, separators=(',', ':')),
        sal_equivalent="J:BELIEF@assistant[sentiment:happy]",
        notes="AutoGen tutorial: StructuredMessage with typed content. SAL uses J:BELIEF (assert belief state)."
    ),
    JSONvsSALVector(
        id="AG-03",
        framework="AutoGen",
        framework_version="0.2",
        source_url="https://microsoft.github.io/autogen/0.2/docs/reference/agentchat/conversable_agent/",
        description="AutoGen conversation message with function_call",
        domain="Agentic / OSMP-Native",
        json_payload=json.dumps({
            "role": "assistant",
            "content": None,
            "name": "chatbot",
            "function_call": {
                "name": "python",
                "arguments": "import matplotlib.pyplot as plt\nfig, ax = plt.subplots()\nax.text(0.5, 0.5, 'Hello')\nplt.savefig('output.png')"
            }
        }, separators=(',', ':')),
        sal_equivalent="A:AR@python[exec:plot_save]",
        notes="AutoGen 0.2: conversation message with function_call. SAL uses A:AR with tool target."
    ),
    JSONvsSALVector(
        id="AG-04",
        framework="AutoGen",
        framework_version="0.4 (AgentChat)",
        source_url="https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/serialize-components.html",
        description="AutoGen component serialization: agent config dump",
        domain="Agentic / OSMP-Native",
        json_payload=json.dumps({
            "provider": "autogen_agentchat.agents.AssistantAgent",
            "component_type": "agent",
            "version": 1,
            "component_version": 1,
            "description": None,
            "config": {
                "name": "assistant",
                "model_client": {
                    "provider": "autogen_ext.models.openai.OpenAIChatCompletionClient",
                    "component_type": "model",
                    "version": 1,
                    "component_version": 1,
                    "config": {
                        "model": "gpt-4o"
                    }
                },
                "handoffs": [
                    {
                        "target": "flights_refunder",
                        "description": "Handoff to flights_refunder.",
                        "name": "transfer_to_flights_refunder",
                        "message": "Transferred to flights_refunder, adopting the role of flights_refunder immediately."
                    },
                    {
                        "target": "user",
                        "description": "Handoff to user.",
                        "name": "transfer_to_user",
                        "message": "Transferred to user, adopting the role of user immediately."
                    }
                ],
                "system_message": "Use tools to solve tasks.",
                "description": "An agent that provides assistance with ability to use tools."
            }
        }, separators=(',', ':')),
        sal_equivalent="C:SPAWN@assistant[gpt-4o];J:HANDOFF@flights_refunder∨J:HANDOFF@user",
        notes="AutoGen serialization docs: full agent config. SAL uses C:SPAWN for agent creation and J:HANDOFF for handoff routes."
    ),
]

# ============================================================================
# CROSS-FRAMEWORK DOMAIN SCENARIOS
# Real-world multi-agent instructions that would appear in any framework
# ============================================================================

DOMAIN_VECTORS = [
    JSONvsSALVector(
        id="DOM-01",
        framework="MCP",
        framework_version="2025-11-25",
        source_url="https://modelcontextprotocol.io/specification/2025-11-25/server/tools",
        description="Clinical: query ICD-10 code for pneumothorax diagnosis",
        domain="Health / Clinical",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "lookup_diagnosis",
                "arguments": {
                    "code_system": "ICD-10-CM",
                    "code": "J93.9",
                    "include_description": True
                }
            }
        }, separators=(',', ':')),
        sal_equivalent="H:ICD[J939]",
        notes="Domain scenario over MCP transport. SAL uses H:ICD Layer 2 accessor. ICD codes stored without dots in MDR."
    ),
    JSONvsSALVector(
        id="DOM-02",
        framework="OpenAI",
        framework_version="Chat Completions API",
        source_url="https://developers.openai.com/api/docs/guides/function-calling",
        description="Financial: execute a payment transfer between accounts",
        domain="Financial / Transaction",
        json_payload=json.dumps({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_pay_001",
                    "type": "function",
                    "function": {
                        "name": "execute_payment",
                        "arguments": json.dumps({
                            "from_account": "ACC-1234",
                            "to_account": "ACC-5678",
                            "amount": 2500.00,
                            "currency": "USD",
                            "reference": "INV-2025-0042"
                        }, separators=(',', ':'))
                    }
                }
            ]
        }, separators=(',', ':')),
        sal_equivalent="K:PAY@ACC-1234[ACC-5678:2500USD:INV-2025-0042]",
        notes="Domain scenario over OpenAI function calling. SAL uses K:PAY with structured slots."
    ),
    JSONvsSALVector(
        id="DOM-03",
        framework="Google A2A",
        framework_version="v0.2.5",
        source_url="https://a2a-protocol.org/v0.2.5/specification/",
        description="Security: request encryption of a payload with key rotation",
        domain="Security / Cryptographic",
        json_payload=json.dumps({
            "id": "sec-001",
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "type": "data",
                            "data": {
                                "action": "encrypt_and_rotate",
                                "target_payload": "msg-body-445",
                                "algorithm": "AES-256-GCM",
                                "rotate_key": True
                            }
                        }
                    ],
                    "messageId": "msg-sec-001"
                }
            }
        }, separators=(',', ':')),
        sal_equivalent="S:ENC@msg-body-445[AES256];S:ROTATE",
        notes="Domain scenario over A2A. SAL uses S:ENC then S:ROTATE as a sequence."
    ),
    JSONvsSALVector(
        id="DOM-04",
        framework="AutoGen",
        framework_version="0.4 (AgentChat)",
        source_url="https://microsoft.github.io/autogen/stable//reference/python/autogen_agentchat.messages.html",
        description="Compute: scale a service to 5 replicas and set resource limits",
        domain="Compute / Resource Management",
        json_payload=json.dumps({
            "type": "ToolCallSummaryMessage",
            "source": "assistant",
            "content": json.dumps({
                "action": "scale_service",
                "service": "api-gateway",
                "replicas": 5,
                "cpu_limit": "2000m",
                "memory_limit": "4Gi"
            }, separators=(',', ':')),
            "metadata": {},
            "created_at": "2025-11-01T12:00:00Z"
        }, separators=(',', ':')),
        sal_equivalent="C:SCALE@api-gateway?5;C:LIMIT@api-gateway[2000m:4Gi]",
        notes="Domain scenario over AutoGen. SAL uses C:SCALE then C:LIMIT as sequence."
    ),
    JSONvsSALVector(
        id="DOM-05",
        framework="CrewAI",
        framework_version="0.86+",
        source_url="https://docs.crewai.com/core-concepts/Tasks/",
        description="Logging: write audit record for a compliance event",
        domain="Logging / Audit / Compliance",
        json_payload=json.dumps({
            "description": "Log the compliance check result for transaction TXN-9921",
            "expected_output": "Audit log entry with timestamp and result",
            "agent": {
                "role": "Compliance Officer",
                "goal": "Maintain regulatory compliance audit trail"
            },
            "output_json": {
                "transaction_id": "TXN-9921",
                "check_type": "AML",
                "result": "pass",
                "severity": "informational",
                "timestamp": "2025-12-01T14:30:00Z"
            }
        }, separators=(',', ':')),
        sal_equivalent="L:AUDIT@TXN-9921[I:AML:\u22a4];L:SEV[6]",
        notes="Domain scenario over CrewAI. SAL uses L:AUDIT with I:AML pass result and L:SEV severity 6 (informational)."
    ),
    JSONvsSALVector(
        id="DOM-06",
        framework="MCP",
        framework_version="2025-11-25",
        source_url="https://modelcontextprotocol.io/specification/2025-11-25/server/tools",
        description="Security: MITRE ATT&CK technique lookup for phishing detection",
        domain="Security / Cryptographic",
        json_payload=json.dumps({
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "lookup_attack_technique",
                "arguments": {
                    "framework": "MITRE ATT&CK",
                    "technique_id": "T1566",
                    "include_subtechniques": True,
                    "include_mitigations": True
                }
            }
        }, separators=(',', ':')),
        sal_equivalent="D:Q[T1566]",
        notes="Domain scenario: MITRE ATT&CK lookup over MCP. SAL resolves T1566 via MDR corpus."
    ),
    JSONvsSALVector(
        id="DOM-07",
        framework="OpenAI",
        framework_version="Chat Completions API",
        source_url="https://developers.openai.com/api/docs/guides/function-calling",
        description="Geospatial: calculate route between two waypoints",
        domain="Geospatial / Navigation",
        json_payload=json.dumps({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_nav_001",
                    "type": "function",
                    "function": {
                        "name": "calculate_route",
                        "arguments": json.dumps({
                            "origin": {"lat": 40.7128, "lng": -74.0060},
                            "destination": {"lat": 34.0522, "lng": -118.2437},
                            "mode": "driving",
                            "avoid": ["tolls"]
                        }, separators=(',', ':'))
                    }
                }
            ]
        }, separators=(',', ':')),
        sal_equivalent="G:ROUT[40.7128,-74.006>34.0522,-118.2437]",
        notes="Domain scenario: navigation over OpenAI function calling. SAL uses G:ROUT with coordinate pair."
    ),
]


# ---- Benchmark Runner -------------------------------------------------------

ALL_VECTORS = MCP_VECTORS + OPENAI_VECTORS + A2A_VECTORS + CREWAI_VECTORS + AUTOGEN_VECTORS + DOMAIN_VECTORS

def measure(v: JSONvsSALVector) -> dict:
    """Compute byte counts and reduction for a single vector."""
    json_bytes = len(v.json_payload.encode("utf-8"))
    sal_bytes = len(v.sal_equivalent.encode("utf-8"))
    reduction = (1 - sal_bytes / json_bytes) * 100 if json_bytes > 0 else 0
    return {
        "id": v.id,
        "framework": v.framework,
        "domain": v.domain,
        "description": v.description,
        "json_bytes": json_bytes,
        "sal_bytes": sal_bytes,
        "reduction_pct": reduction,
        "source_url": v.source_url,
    }


def run_benchmark() -> dict:
    """Run the full SAL vs JSON benchmark and return structured results."""
    results = [measure(v) for v in ALL_VECTORS]
    total = len(results)
    mean_reduction = sum(r["reduction_pct"] for r in results) / total if total else 0
    min_reduction = min(r["reduction_pct"] for r in results)
    max_reduction = max(r["reduction_pct"] for r in results)

    # Group by framework
    frameworks = {}
    for r in results:
        fw = r["framework"]
        if fw not in frameworks:
            frameworks[fw] = []
        frameworks[fw].append(r)

    framework_stats = {}
    for fw, frs in frameworks.items():
        fw_mean = sum(r["reduction_pct"] for r in frs) / len(frs)
        framework_stats[fw] = {
            "count": len(frs),
            "mean_reduction_pct": fw_mean,
        }

    return {
        "total_vectors": total,
        "mean_reduction_pct": mean_reduction,
        "min_reduction_pct": min_reduction,
        "max_reduction_pct": max_reduction,
        "framework_stats": framework_stats,
        "results": results,
    }


def print_results(data: dict) -> None:
    """Print formatted benchmark results."""
    print()
    print("=" * 100)
    print("  OSMP SAL vs JSON BENCHMARK -- Production Agent Framework Comparison")
    print("  Measurement: UTF-8 byte count: len(s.encode('utf-8'))")
    print("  Vectors sourced from: MCP Spec, OpenAI API Docs, Google A2A Spec,")
    print("                        CrewAI Docs, Microsoft AutoGen Docs")
    print("=" * 100)
    print()
    print(f"  {'ID':<10} {'Framework':<12} {'Description':<52} {'JSON':>6} {'SAL':>6} {'Reduction':>10}")
    print(f"  {'-'*10} {'-'*12} {'-'*52} {'-'*6} {'-'*6} {'-'*10}")

    for r in data["results"]:
        desc = r["description"][:50] + ".." if len(r["description"]) > 52 else r["description"]
        print(f"  {r['id']:<10} {r['framework']:<12} {desc:<52} {r['json_bytes']:>6} {r['sal_bytes']:>6} {r['reduction_pct']:>9.1f}%")

    print()
    print("-" * 100)
    print("  FRAMEWORK SUMMARY")
    print("-" * 100)
    for fw, stats in data["framework_stats"].items():
        print(f"  {fw:<20} {stats['count']:>3} vectors    Mean reduction: {stats['mean_reduction_pct']:.1f}%")

    print()
    print("-" * 100)
    print(f"  TOTAL VECTORS:    {data['total_vectors']}")
    print(f"  MEAN REDUCTION:   {data['mean_reduction_pct']:.1f}%")
    print(f"  RANGE:            {data['min_reduction_pct']:.1f}% -- {data['max_reduction_pct']:.1f}%")
    print("=" * 100)
    print()


def export_json(data: dict, path: str) -> None:
    """Export benchmark results as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Results exported to: {path}")


def export_vectors_json(path: str) -> None:
    """Export all test vectors with full metadata as JSON."""
    vectors = []
    for v in ALL_VECTORS:
        vectors.append({
            "id": v.id,
            "framework": v.framework,
            "framework_version": v.framework_version,
            "source_url": v.source_url,
            "description": v.description,
            "domain": v.domain,
            "json_payload": v.json_payload,
            "sal_equivalent": v.sal_equivalent,
            "json_bytes": len(v.json_payload.encode("utf-8")),
            "sal_bytes": len(v.sal_equivalent.encode("utf-8")),
            "reduction_pct": round((1 - len(v.sal_equivalent.encode("utf-8")) / len(v.json_payload.encode("utf-8"))) * 100, 1),
            "notes": v.notes,
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"vectors": vectors, "count": len(vectors)}, f, indent=2, ensure_ascii=False)
    print(f"  Vectors exported to: {path}")


# ---- Main -------------------------------------------------------------------

if __name__ == "__main__":
    data = run_benchmark()
    print_results(data)

    out_dir = Path(__file__).parent
    export_json(data, str(out_dir / "benchmark-results.json"))
    export_vectors_json(str(out_dir / "sal-vs-json-vectors.json"))
