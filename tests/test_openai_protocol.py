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
