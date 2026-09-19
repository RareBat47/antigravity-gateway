"""SSE parser and streaming delta chunk transformer."""

import json
import time
from typing import Any, AsyncIterator, Dict, Optional, Tuple


async def parse_and_transform_sse_stream(
    upstream_stream: AsyncIterator[Tuple[int, str]],
    model_id: str,
    request_id: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    Parse upstream SSE stream and yield OpenAI-formatted SSE chunks.
    Format: 'data: {...}\n\n'
    """
    req_id = request_id or f"chatcmpl-{int(time.time()*1000)}"
    created = int(time.time())

    # Send initial role chunk
    first_chunk = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(first_chunk)}\n\n"

    buffer = ""
    finish_reason_seen = None
    has_tool_calls = False
    last_usage: Optional[Dict[str, int]] = None

    async for status_code, line in upstream_stream:
        if status_code != 200:
            err_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_id,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": f"\n[Upstream Error: {line}]"},
                        "finish_reason": "error",
                    }
                ],
            }
            yield f"data: {json.dumps(err_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return

        line_str = line.strip()
        if not line_str or line_str.startswith(":"):
            continue

        if line_str.startswith("data:"):
            payload_str = line_str[5:].strip()
            if payload_str == "[DONE]":
                break

            try:
                data = json.loads(payload_str)
            except Exception:
                continue

            inner = data.get("response") if isinstance(data.get("response"), dict) else data

            if "usageMetadata" in inner:
                meta = inner["usageMetadata"]
                last_usage = {
                    "prompt_tokens": meta.get("promptTokenCount", 0),
                    "completion_tokens": meta.get("candidatesTokenCount", 0),
                    "total_tokens": meta.get("totalTokenCount", 0),
                }

            candidates = inner.get("candidates", [])
            if not candidates:
                continue

            cand = candidates[0]
            finish_reason = cand.get("finishReason")
            if finish_reason:
                finish_reason_seen = "stop" if finish_reason == "STOP" else ("length" if finish_reason == "MAX_TOKENS" else finish_reason.lower())

            parts = cand.get("content", {}).get("parts", [])
            for p in parts:
                is_thought = bool(p.get("thought"))
                # Reasoning / Thought delta
                if is_thought:
                    t_val = p.get("thought")
                    thought_str = t_val if isinstance(t_val, str) else p.get("text", "")
                    if thought_str:
                        chunk = {
                            "id": req_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_id,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"reasoning_content": str(thought_str)},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                # Text delta (only if not a thought)
                elif "text" in p and p["text"]:
                    chunk = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": p["text"]},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Tool call delta
                if "functionCall" in p:
                    has_tool_calls = True
                    fn = p["functionCall"]
                    args = fn.get("args", {})
                    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                    chunk = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": f"call_{fn.get('name', 'fn')}",
                                            "type": "function",
                                            "function": {
                                                "name": fn.get("name"),
                                                "arguments": args_str,
                                            },
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

    # Final chunk with finish reason
    effective_finish = "tool_calls" if has_tool_calls else (finish_reason_seen or "stop")
    final_chunk: Dict[str, Any] = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": effective_finish,
            }
        ],
    }
    if last_usage:
        final_chunk["usage"] = last_usage

    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"
