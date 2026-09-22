from typing import Optional
import asyncio
import json
import uuid
from typing import Any, AsyncIterator, Dict, List, Tuple

from agw.arena.provider import ArenaProvider


def _extract_text_from_content(content: Any) -> str:
    """Safely pull plain text out of a message content (string or OpenAI parts list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif part.get("type") == "image_url":
                # Don't echo the base64 payload - just note its presence
                parts.append(f"[image attached: {part.get('image_url', {}).get('detail', 'low')}]")
        return " ".join(p for p in parts if p).strip()
    return ""


def _has_image_attachments(messages: List[Dict[str, Any]]) -> bool:
    """Detect if any message contains an image_url / base64 image payload."""
    for m in messages or []:
        c = m.get("content")
        if isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
        if isinstance(c, str) and c.startswith("data:image/") and ";base64," in c:
            return True
    return False


def _summarize_text(text: str, limit: int = 80) -> str:
    text = (text or "").strip()
    if not text:
        return "(no text)"
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _build_mock_reply(messages: List[Dict[str, Any]], model: str) -> str:
    """Build a clean, useful mock reply based on the last user message."""
    if not messages:
        return "Ready when you are."

    last_msg = messages[-1] if messages else {}
    last_text = _extract_text_from_content(last_msg.get("content", ""))
    has_image = _has_image_attachments(messages)

    if has_image and not last_text:
        return ("I can see the image you attached. In production, this would be routed "
                "to a vision-capable model (e.g. gpt-5-chat, gemini-3.1-pro-preview) "
                "and would return a description or analysis of the image.")

    if has_image and last_text:
        return (f"Got your message (\"{_summarize_text(last_text)}\") along with an image. "
                "In production this would go to a vision model for combined image + text understanding.")

    if last_text:
        snippet = _summarize_text(last_text, 100)
        return (f"You said: \"{snippet}\".\n\n"
                "I'm a local mock response running in your Arena Gateway. "
                "Real Arena accounts are not yet wired in, but the OpenCode -> "
                "Gateway -> Response pipeline is fully working.")

    return "Hello! How can I help?"


class MockArenaProvider(ArenaProvider):
    """Mock Arena.ai provider for testing without live credentials."""

    async def fetch_available_models(self, access_token: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        if access_token == "EXPIRED":
            raise RuntimeError("Mock token expired")
        return {
            "models": [
                {"id": "mock-gpt-4o", "name": "Mock GPT-4o"},
                {"id": "mock-claude-3-5", "name": "Mock Claude 3.5 Sonnet"},
            ]
        }

    async def generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any], str]:
        if access_token == "EXPIRED":
            return 401, {"error": "Unauthorized"}, "Unauthorized"
        if access_token == "RATE_LIMITED":
            return 429, {"error": "Rate limit exceeded"}, "Rate limit exceeded"
        if access_token == "ERROR":
            return 500, {"error": "Internal Server Error"}, "Internal Server Error"

        model = envelope.get("model", "mock-model")
        messages = envelope.get("messages", [])
        text = _build_mock_reply(messages, model)

        resp = {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(asyncio.get_event_loop().time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": max(1, len(text.split())),
                "total_tokens": 10 + max(1, len(text.split())),
            },
        }
        await asyncio.sleep(0.3)
        return 200, resp, json.dumps(resp)

    async def stream_generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> AsyncIterator[Tuple[int, str]]:
        if access_token == "EXPIRED":
            yield 401, "Unauthorized"
            return
        if access_token == "RATE_LIMITED":
            yield 429, "Rate limit exceeded"
            return
        if access_token == "ERROR":
            yield 500, "Internal Server Error"
            return

        model = envelope.get("model", "mock-model")
        messages = envelope.get("messages", [])
        text = _build_mock_reply(messages, model)

        chat_id = f"chatcmpl-{uuid.uuid4()}"
        created = int(asyncio.get_event_loop().time())

        # First chunk: open the stream with role
        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None,
            }],
        }
        yield 200, f"data: {json.dumps(chunk)}\n\n"

        # Stream the clean reply word-by-word
        words = text.split(" ")
        for w in words:
            chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": w + " "},
                    "finish_reason": None,
                }],
            }
            yield 200, f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.04)

        # Final chunk
        final = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield 200, f"data: {json.dumps(final)}\n\n"
        yield 200, "data: [DONE]\n\n"
