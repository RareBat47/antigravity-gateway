"""OpenAI Chat Completions protocol to Gemini contents and response conversion."""

import json
import time
from typing import Any, Dict, List, Optional, Tuple
from agw.protocol.tools import (
    extract_gemini_tool_calls,
    oai_tool_choice_to_gemini,
    oai_tools_to_gemini,
)
from agw.protocol.signature_cache import thought_signature_cache
from agw.protocol.vision import process_image_url


async def oai_messages_to_gemini(
    messages: List[Dict[str, Any]],
    model_id: str = "",
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Convert OpenAI messages list into Gemini contents list and systemInstruction.
    """
    contents: List[Dict[str, Any]] = []
    system_instruction: Optional[Dict[str, Any]] = None
    system_parts: List[Dict[str, Any]] = []

    # Map tool_call_id to function name for tool responses
    call_id_to_name: Dict[str, str] = {}
    for msg in messages:
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                cid = tc.get("id")
                fn_name = tc.get("function", {}).get("name")
                if cid and fn_name:
                    call_id_to_name[cid] = fn_name

    for msg in messages:
        role = msg.get("role", "user")
        raw_content = msg.get("content")

        # 1. System Instruction
        if role in ("system", "developer"):
            text = ""
            if isinstance(raw_content, str):
                text = raw_content
            elif isinstance(raw_content, list):
                text = "\n".join(p.get("text", "") for p in raw_content if isinstance(p, dict))
            if text:
                system_parts.append({"text": text})
            continue

        # 2. Tool Results (role: tool)
        if role == "tool":
            tool_call_id = msg.get("tool_call_id", "")
            fn_name = call_id_to_name.get(tool_call_id, msg.get("name", "function"))
            
            # Response object
            content_val = raw_content
            try:
                if isinstance(raw_content, str):
                    content_val = json.loads(raw_content)
            except Exception:
                pass

            response_obj = content_val if isinstance(content_val, dict) else {"result": content_val}

            part = {
                "functionResponse": {
                    "name": fn_name,
                    "response": response_obj,
                }
            }
            # Only merge if previous turn is a user turn that ONLY contains functionResponse
            if (
                contents
                and contents[-1].get("role") == "user"
                and all("functionResponse" in p for p in contents[-1].get("parts", []))
            ):
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": "user", "parts": [part]})
            continue

        # 3. User & Assistant messages
        gemini_role = "user" if role == "user" else "model"
        parts: List[Dict[str, Any]] = []

        # Include thought/reasoning content if present from assistant
        if role == "assistant":
            thought_text = msg.get("reasoning_content") or msg.get("thought")
            if isinstance(thought_text, str) and thought_text:
                parts.append({"thought": True, "text": thought_text})

        # Process content (str or list of parts) - text goes BEFORE functionCall in Gemini
        if isinstance(raw_content, str) and raw_content:
            parts.append({"text": raw_content})
        elif isinstance(raw_content, list):
            for block in raw_content:
                if not isinstance(block, dict):
                    continue
                b_type = block.get("type", "")
                if b_type == "text" and block.get("text"):
                    parts.append({"text": block["text"]})
                elif b_type == "image_url":
                    img_dict = block.get("image_url", {})
                    url = img_dict.get("url") if isinstance(img_dict, dict) else img_dict
                    img_part = await process_image_url(url)
                    if img_part:
                        parts.append(img_part)

        # Handle tool calls made by assistant (must follow text parts)
        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                args = {}
                try:
                    if isinstance(fn.get("arguments"), str):
                        args = json.loads(fn["arguments"])
                    elif isinstance(fn.get("arguments"), dict):
                        args = fn["arguments"]
                except Exception:
                    args = {"raw": fn.get("arguments")}

                # Resolve thought_signature with multi-layer recovery:
                # 1. Directly from tc (flat)
                sig = tc.get("thought_signature") or tc.get("thoughtSignature")

                # 2. From extra_content on tc (Hermes native format)
                if not sig and "extra_content" in tc:
                    extra = tc["extra_content"]
                    if isinstance(extra, dict):
                        sig = extra.get("thought_signature") or extra.get("thoughtSignature")
                        if not sig and isinstance(extra.get("google"), dict):
                            sig = extra["google"].get("thought_signature") or extra["google"].get("thoughtSignature")

                # 3. From tool_call id / call_id in signature cache
                if not sig:
                    call_id = tc.get("id") or tc.get("call_id")
                    if call_id:
                        sig = thought_signature_cache.get(call_id)

                # 4. From function name + arguments in signature cache
                if not sig:
                    sig = thought_signature_cache.get_by_call(fn.get("name"), fn.get("arguments"))

                # 5. From parent message
                if not sig:
                    sig = msg.get("thought_signature") or msg.get("thoughtSignature")
                    if not sig and "extra_content" in msg:
                        extra = msg["extra_content"]
                        if isinstance(extra, dict):
                            sig = extra.get("thought_signature") or extra.get("thoughtSignature")
                            if not sig and isinstance(extra.get("google"), dict):
                                sig = extra["google"].get("thought_signature") or extra["google"].get("thoughtSignature")

                # 6. Fallback to most recent known signature from cache
                if not sig:
                    sig = thought_signature_cache.get_latest()

                # 7. Ultimate fallback for mock tests / initial calls
                if not sig:
                    sig = "skip_thought_signature_validator"

                fn_call_dict = {
                    "name": fn.get("name"),
                    "args": args,
                }
                parts.append({
                    "functionCall": fn_call_dict,
                    "thoughtSignature": sig,
                    "thought_signature": sig,
                })

        if parts:
            # Enforce alternation: if consecutive turns have same role, combine them unless mixing functionResponse
            can_merge = (
                contents
                and contents[-1].get("role") == gemini_role
                and not any("functionResponse" in p for p in contents[-1].get("parts", []))
            )
            if can_merge:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": gemini_role, "parts": parts})

    if system_parts:
        system_instruction = {"parts": system_parts}

    # Ensure first turn is user
    if contents and contents[0].get("role") != "user":
        contents.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})

    return contents, system_instruction


def build_generation_config(body: Dict[str, Any], max_output_tokens: int) -> Dict[str, Any]:
    """Construct Gemini generationConfig."""
    cfg: Dict[str, Any] = {}
    if "temperature" in body and body["temperature"] is not None:
        cfg["temperature"] = float(body["temperature"])
    if "top_p" in body and body["top_p"] is not None:
        cfg["topP"] = float(body["top_p"])

    # Max tokens
    req_max = body.get("max_tokens") or body.get("max_completion_tokens")
    if req_max:
        cfg["maxOutputTokens"] = min(int(req_max), max_output_tokens)
    else:
        cfg["maxOutputTokens"] = max_output_tokens

    if "stop" in body:
        stop = body["stop"]
        cfg["stopSequences"] = [stop] if isinstance(stop, str) else stop

    return cfg


def gemini_response_to_openai(
    response_payload: Dict[str, Any],
    requested_model: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert Cloud Code / Gemini response payload into OpenAI ChatCompletion."""
    inner = response_payload.get("response") if isinstance(response_payload.get("response"), dict) else response_payload
    candidates = inner.get("candidates", [])
    candidate = candidates[0] if candidates else {}
    content_obj = candidate.get("content", {})
    parts = content_obj.get("parts", [])

    text_pieces = []
    reasoning_pieces = []

    for p in parts:
        is_thought = bool(p.get("thought"))
        if is_thought:
            t_val = p.get("thought")
            thought_str = t_val if isinstance(t_val, str) else p.get("text", "")
            if thought_str:
                reasoning_pieces.append(str(thought_str))
        else:
            if "text" in p and p["text"]:
                text_pieces.append(str(p["text"]))

    tool_calls = extract_gemini_tool_calls(parts)
    if text_pieces:
        content_str = "".join(text_pieces)
    else:
        content_str = None if tool_calls else ""
    reasoning_str = "".join(reasoning_pieces) if reasoning_pieces else None

    finish_reason = "stop"
    if tool_calls:
        finish_reason = "tool_calls"
    elif candidate.get("finishReason") == "MAX_TOKENS":
        finish_reason = "length"

    message: Dict[str, Any] = {
        "role": "assistant",
        "content": content_str,
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
    if reasoning_str:
        message["reasoning_content"] = reasoning_str

    usage_meta = inner.get("usageMetadata", {})
    prompt_tokens = usage_meta.get("promptTokenCount", 0)
    completion_tokens = usage_meta.get("candidatesTokenCount", 0)

    res = {
        "id": request_id or f"chatcmpl-{int(time.time()*1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": requested_model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return res
