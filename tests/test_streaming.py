"""Tests for SSE streaming chunk transformation."""

import json
import pytest
from agw.protocol.streamer import parse_and_transform_sse_stream


@pytest.mark.asyncio
async def test_streaming_sse_transformation():
    async def sample_upstream():
        yield 200, 'data: {"candidates": [{"content": {"parts": [{"text": "First "}]}}]}'
        yield 200, 'data: {"candidates": [{"content": {"parts": [{"text": "second."}]}, "finishReason": "STOP"}]}'
        yield 200, 'data: [DONE]'

    chunks = []
    async for chunk in parse_and_transform_sse_stream(sample_upstream(), "gemini-3.5-flash"):
        chunks.append(chunk)

    assert len(chunks) >= 3
    # Check first role chunk
    first_data = json.loads(chunks[0].replace("data: ", "").strip())
    assert first_data["choices"][0]["delta"]["role"] == "assistant"

    # Check content deltas
    content_pieces = []
    for c in chunks:
        line = c.strip()
        if line.startswith("data: ") and line != "data: [DONE]":
            d = json.loads(line[6:])
            delta = d["choices"][0]["delta"]
            if "content" in delta and delta["content"]:
                content_pieces.append(delta["content"])

    assert "".join(content_pieces) == "First second."
    assert chunks[-1].strip() == "data: [DONE]"
