"""Tests for Gemini/Claude thought and reasoning content extraction."""

import json
import pytest
from agw.protocol.mapper import gemini_response_to_openai, oai_messages_to_gemini
from agw.protocol.streamer import parse_and_transform_sse_stream


def test_thinking_response_no_type_error():
    """Verify boolean thought field does not crash with TypeError and separates reasoning."""
    payload = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "Thinking step by step...", "thought": True},
                        {"text": "Final answer here."},
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 15,
        },
    }

    oai_resp = gemini_response_to_openai(payload, "gemini-3.5-flash")
    msg = oai_resp["choices"][0]["message"]

    assert msg["content"] == "Final answer here."
    assert msg["reasoning_content"] == "Thinking step by step..."
    assert oai_resp["choices"][0]["finish_reason"] == "stop"


def test_assistant_reasoning_history_and_part_ordering():
    """Verify assistant reasoning is retained and text precedes tool calls."""
    messages = [
        {"role": "user", "content": "What is the weather in Tokyo?"},
        {
            "role": "assistant",
            "reasoning_content": "I should call get_weather for Tokyo.",
            "content": "Checking the weather for Tokyo now.",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "Tokyo"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "name": "get_weather",
            "content": '{"temperature": "18C"}',
        },
        {"role": "user", "content": "Thanks! How about tomorrow?"},
    ]

    import asyncio
    contents, _ = asyncio.run(oai_messages_to_gemini(messages))

    assert len(contents) == 4
    # Turn 0: User
    assert contents[0]["role"] == "user"

    # Turn 1: Model (assistant)
    model_turn = contents[1]
    assert model_turn["role"] == "model"
    parts = model_turn["parts"]
    assert len(parts) == 3
    # 1. Thought part
    assert parts[0].get("thought") is True
    assert parts[0]["text"] == "I should call get_weather for Tokyo."
    # 2. Text part (must precede functionCall)
    assert parts[1]["text"] == "Checking the weather for Tokyo now."
    # 3. Function call
    assert "functionCall" in parts[2]
    assert parts[2]["functionCall"]["name"] == "get_weather"

    # Turn 2: Tool result (isolated in its own user turn)
    tool_turn = contents[2]
    assert tool_turn["role"] == "user"
    assert "functionResponse" in tool_turn["parts"][0]

    # Turn 3: Subsequent user message (must NOT be merged with functionResponse)
    subsequent_user = contents[3]
    assert subsequent_user["role"] == "user"
    assert subsequent_user["parts"][0]["text"] == "Thanks! How about tomorrow?"


@pytest.mark.asyncio
async def test_streaming_thought_and_tool_call_finish_reason():
    """Verify streaming handles thought chunks and keeps finish_reason: tool_calls."""
    async def sample_upstream():
        # Event 1: thought part with boolean flag
        e1 = {
            "candidates": [
                {"content": {"parts": [{"text": "Deep thinking...", "thought": True}]}}
            ]
        }
        # Event 2: tool call
        e2 = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "calc",
                                    "args": {"expr": "2+2"},
                                }
                            }
                        ]
                    }
                }
            ]
        }
        # Event 3: STOP finish reason
        e3 = {
            "candidates": [
                {
                    "content": {"parts": []},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 10,
                "totalTokenCount": 15,
            },
        }
        yield 200, f"data: {json.dumps(e1)}"
        yield 200, f"data: {json.dumps(e2)}"
        yield 200, f"data: {json.dumps(e3)}"
        yield 200, "data: [DONE]"

    chunks = []
    async for chunk in parse_and_transform_sse_stream(sample_upstream(), "gemini-3.5-flash"):
        chunks.append(chunk)

    parsed_chunks = [
        json.loads(c[6:].strip()) for c in chunks if c.startswith("data: ") and c.strip() != "data: [DONE]"
    ]

    # Check reasoning chunk
    thought_chunks = [
        c for c in parsed_chunks if "reasoning_content" in c["choices"][0]["delta"]
    ]
    assert len(thought_chunks) == 1
    assert thought_chunks[0]["choices"][0]["delta"]["reasoning_content"] == "Deep thinking..."

    # Check tool call intermediate chunk (finish_reason MUST be null/None)
    tc_chunks = [
        c for c in parsed_chunks if "tool_calls" in c["choices"][0]["delta"]
    ]
    assert len(tc_chunks) == 1
    assert tc_chunks[0]["choices"][0]["finish_reason"] is None
    assert tc_chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "calc"

    # Check final chunk (finish_reason MUST be tool_calls)
    final_chunk = parsed_chunks[-1]
    assert final_chunk["choices"][0]["finish_reason"] == "tool_calls"
    assert final_chunk["usage"]["total_tokens"] == 15
