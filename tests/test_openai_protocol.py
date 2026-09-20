"""Tests for OpenAI protocol mapping and conversions."""

import pytest
from agw.protocol.mapper import gemini_response_to_openai, oai_messages_to_gemini
from agw.protocol.tools import oai_tools_to_gemini


@pytest.mark.asyncio
async def test_oai_messages_to_gemini_conversion():
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Hello, world!"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Write a python function."},
    ]

    contents, system_inst = await oai_messages_to_gemini(messages)

    assert system_inst is not None
    assert system_inst["parts"][0]["text"] == "You are a helpful coding assistant."
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "Hello, world!"
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["text"] == "Hi there!"


def test_oai_tools_conversion():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather in location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    gemini_tools = oai_tools_to_gemini(tools)
    assert len(gemini_tools) == 1
    decls = gemini_tools[0]["functionDeclarations"]
    assert len(decls) == 1
    assert decls[0]["name"] == "get_weather"
    assert "location" in decls[0]["parameters"]["properties"]


def test_gemini_response_to_openai():
    payload = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"text": "Testing output message."}],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 20,
            "candidatesTokenCount": 5,
        },
    }

    oai_resp = gemini_response_to_openai(payload, "gemini-3.5-flash")
    assert oai_resp["object"] == "chat.completion"
    assert oai_resp["choices"][0]["message"]["content"] == "Testing output message."
    assert oai_resp["choices"][0]["finish_reason"] == "stop"
    assert oai_resp["usage"]["total_tokens"] == 25


@pytest.mark.asyncio
async def test_oai_tool_call_thought_signature():
    """Verify functionCall parts get thought_signature and thoughtSignature."""
    messages = [
        {"role": "user", "content": "What is the weather?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_weather_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": "{\"location\": \"Berlin\"}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_weather_1",
            "content": "{\"temp\": 20}",
        },
    ]

    contents, _ = await oai_messages_to_gemini(messages)
    assert len(contents) == 3
    # Model turn with functionCall
    model_turn = contents[1]
    assert model_turn["role"] == "model"
    part = model_turn["parts"][0]
    assert "functionCall" in part
    assert part["functionCall"]["name"] == "get_weather"
    assert part["thoughtSignature"] == "skip_thought_signature_validator"
    assert part["thought_signature"] == "skip_thought_signature_validator"


def test_extract_gemini_tool_calls_preserves_signature():
    """Verify extract_gemini_tool_calls captures thought_signature from Gemini parts."""
    from agw.protocol.tools import extract_gemini_tool_calls

    parts = [
        {
            "functionCall": {
                "name": "calculate",
                "args": {"expr": "2+2"},
            },
            "thoughtSignature": "real_encrypted_signature_xyz",
        }
    ]

    calls = extract_gemini_tool_calls(parts)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "calculate"
    assert calls[0]["thought_signature"] == "real_encrypted_signature_xyz"
    assert calls[0]["thoughtSignature"] == "real_encrypted_signature_xyz"
    assert calls[0]["extra_content"]["thought_signature"] == "real_encrypted_signature_xyz"
    assert calls[0]["extra_content"]["google"]["thought_signature"] == "real_encrypted_signature_xyz"


@pytest.mark.asyncio
async def test_oai_tool_call_recovers_sig_from_extra_content():
    """Verify Hermes-style extra_content is unpacked into Gemini thoughtSignature."""
    messages = [
        {"role": "user", "content": "Run command"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_terminal_1",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{\"command\": \"ls\"}"},
                    "extra_content": {
                        "google": {
                            "thought_signature": "hermes_crypto_sig_456",
                        }
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_terminal_1", "content": "file1.txt"},
    ]
    contents, _ = await oai_messages_to_gemini(messages)
    part = contents[1]["parts"][0]
    assert part["thoughtSignature"] == "hermes_crypto_sig_456"
    assert part["functionCall"]["thoughtSignature"] == "hermes_crypto_sig_456"


@pytest.mark.asyncio
async def test_oai_tool_call_recovers_sig_from_cache():
    """Verify tool call without extra_content or sig recovers it from cache by ID."""
    from agw.protocol.signature_cache import thought_signature_cache
    thought_signature_cache.store(
        call_id="call_terminal_0",
        signature="cached_sig_789",
        fn_name="terminal",
        args={"command": "dir"},
    )

    # Client stripped signature and stripped index from call_terminal_0 -> call_terminal
    messages = [
        {"role": "user", "content": "Run dir"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_terminal",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{\"command\": \"dir\"}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_terminal", "content": "volume C:"},
    ]
    contents, _ = await oai_messages_to_gemini(messages)
    part = contents[1]["parts"][0]
    assert part["thoughtSignature"] == "cached_sig_789"
    assert part["functionCall"]["thoughtSignature"] == "cached_sig_789"

