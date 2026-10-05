"""Bi-directional mapper between Anthropic Messages API and OpenAI/Gateway internal formats."""

import json
import secrets
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple


def anthropic_to_openai_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Anthropic /v1/messages request body to OpenAI-compatible format."""
    oai_messages: List[Dict[str, Any]] = []

    # 1. System prompt extraction
    system = body.get("system")
    if system:
        if isinstance(system, list):
            sys_text = "\n\n".join(b.get("text", "") for b in system if isinstance(b, dict) and b.get("type") == "text")
        else:
            sys_text = str(system)
        if sys_text.strip():
            oai_messages.append({"role": "system", "content": sys_text.strip()})

    # 2. Messages translation
    for msg in body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            oai_messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_accumulator: List[str] = []
            tool_calls: List[Dict[str, Any]] = []

            for block in content:
                if not isinstance(block, dict):
                    continue
                b_type = block.get("type")
                if b_type == "text":
                    text_accumulator.append(block.get("text", ""))
                elif b_type == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", f"toolu_{secrets.token_hex(8)}"),
                        "type": "function",
                        "function": {
                            "name": block.get("name", "unknown_tool"),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    })
                elif b_type == "tool_result":
                    tool_res_content = block.get("content", "")
                    if isinstance(tool_res_content, list):
                        tool_res_content = "".join(
                            sub.get("text", "") for sub in tool_res_content if isinstance(sub, dict) and sub.get("type") == "text"
                        )
                    oai_messages.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": str(tool_res_content),
                    })
                elif b_type == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        media_type = source.get("media_type", "image/png")
                        data_b64 = source.get("data", "")
                        oai_messages.append({
                            "role": role,
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{media_type};base64,{data_b64}"},
                                }
                            ],
                        })

            if text_accumulator or tool_calls:
                combined_text = "\n".join(text_accumulator).strip()
                entry: Dict[str, Any] = {"role": role, "content": combined_text}
                if tool_calls:
                    entry["tool_calls"] = tool_calls
                oai_messages.append(entry)

    oai_req: Dict[str, Any] = {
        "model": body.get("model", "claude-sonnet-5-5-medium"),
        "messages": oai_messages,
        "stream": bool(body.get("stream", False)),
    }

    if "max_tokens" in body:
        oai_req["max_tokens"] = body["max_tokens"]
    if "temperature" in body:
        oai_req["temperature"] = body["temperature"]
    if "top_p" in body:
        oai_req["top_p"] = body["top_p"]

    # 3. Tools translation
    tools = body.get("tools")
    if tools and isinstance(tools, list):
        oai_tools = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            })
        if oai_tools:
            oai_req["tools"] = oai_tools

    # Thinking configuration passthrough
    if "thinking" in body:
        oai_req["thinking"] = body["thinking"]

    return oai_req


def openai_to_anthropic_response(oai_resp: Dict[str, Any], requested_model: str) -> Dict[str, Any]:
    """Convert OpenAI chat completion response to Anthropic Message object."""
    msg_id = f"msg_{secrets.token_hex(12)}"
    choices = oai_resp.get("choices", [])
    content_blocks: List[Dict[str, Any]] = []
    stop_reason = "end_turn"

    if choices:
        choice = choices[0]
        delta_or_msg = choice.get("message", {})
        text_content = delta_or_msg.get("content")
        if text_content:
            content_blocks.append({"type": "text", "text": str(text_content)})

        # Tool calls translation
        tool_calls = delta_or_msg.get("tool_calls", [])
        if tool_calls:
            stop_reason = "tool_use"
            for tc in tool_calls:
                fn = tc.get("function", {})
                args = fn.get("arguments", "{}")
                try:
                    parsed_args = json.loads(args) if isinstance(args, str) else args
                except Exception:
                    parsed_args = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", f"toolu_{secrets.token_hex(8)}"),
                    "name": fn.get("name", "unknown_tool"),
                    "input": parsed_args,
                })

        oai_finish = choice.get("finish_reason")
        if oai_finish == "length":
            stop_reason = "max_tokens"
        elif oai_finish == "tool_calls":
            stop_reason = "tool_use"

    usage = oai_resp.get("usage", {})
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "model": requested_model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


async def parse_and_transform_anthropic_sse_stream(
    upstream_stream: AsyncIterator[Tuple[int, str]],
    model_id: str,
    request_id: Optional[str] = None,
    usage_out: Optional[List[Dict[str, int]]] = None,
) -> AsyncIterator[str]:
    """Parse upstream CloudCode SSE and yield Anthropic-formatted SSE events."""
    msg_id = request_id or f"msg_{secrets.token_hex(12)}"
    block_index = 0
    text_block_opened = False
    total_output_tokens = 0
    input_tokens = 0
    stop_reason = "end_turn"

    # 1. message_start
    start_event = {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model_id,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 1},
        },
    }
    yield f"event: message_start\ndata: {json.dumps(start_event)}\n\n"

    try:
        async for status_code, line in upstream_stream:
            if status_code != 200:
                continue

            line_str = line.strip()
            if not line_str or line_str.startswith(":") or not line_str.startswith("data:"):
                continue

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
                input_tokens = meta.get("promptTokenCount", 0)
                total_output_tokens = meta.get("candidatesTokenCount", 0)

            candidates = inner.get("candidates", [])
            if not candidates:
                continue

            cand = candidates[0]
            finish_reason = cand.get("finishReason")
            if finish_reason == "MAX_TOKENS":
                stop_reason = "max_tokens"
            elif finish_reason == "STOP":
                stop_reason = "end_turn"

            parts = cand.get("content", {}).get("parts", [])
            for p in parts:
                # Text delta
                if "text" in p and p["text"]:
                    if not text_block_opened:
                        start_block = {
                            "type": "content_block_start",
                            "index": block_index,
                            "content_block": {"type": "text", "text": ""},
                        }
                        yield f"event: content_block_start\ndata: {json.dumps(start_block)}\n\n"
                        text_block_opened = True

                    delta_event = {
                        "type": "content_block_delta",
                        "index": block_index,
                        "delta": {"type": "text_delta", "text": p["text"]},
                    }
                    yield f"event: content_block_delta\ndata: {json.dumps(delta_event)}\n\n"

                # Tool call delta
                if "functionCall" in p:
                    stop_reason = "tool_use"
                    if text_block_opened:
                        yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': block_index})}\n\n"
                        block_index += 1
                        text_block_opened = False

                    fn = p["functionCall"]
                    call_id = f"toolu_{secrets.token_hex(8)}"
                    tool_start = {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": {
                            "type": "tool_use",
                            "id": call_id,
                            "name": fn.get("name", "tool"),
                            "input": {},
                        },
                    }
                    yield f"event: content_block_start\ndata: {json.dumps(tool_start)}\n\n"

                    args = fn.get("args", {})
                    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                    tool_delta = {
                        "type": "content_block_delta",
                        "index": block_index,
                        "delta": {"type": "input_json_delta", "partial_json": args_str},
                    }
                    yield f"event: content_block_delta\ndata: {json.dumps(tool_delta)}\n\n"

                    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': block_index})}\n\n"
                    block_index += 1

    except Exception:
        pass

    if text_block_opened:
        yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': block_index})}\n\n"

    # message_delta with final stop reason and usage
    msg_delta = {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": max(1, total_output_tokens)},
    }
    yield f"event: message_delta\ndata: {json.dumps(msg_delta)}\n\n"

    # message_stop
    yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"

    if usage_out is not None:
        usage_out.append({
            "prompt_tokens": input_tokens,
            "completion_tokens": total_output_tokens,
            "total_tokens": input_tokens + total_output_tokens,
        })
