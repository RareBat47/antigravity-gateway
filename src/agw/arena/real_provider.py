import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from curl_cffi.requests import AsyncSession

from agw.arena.provider import ArenaProvider

logger = logging.getLogger("agw.arena.real")

LMARENA_AUTH_COOKIE = "arena-auth-prod-v1"


def reconstruct_arena_cookie(raw_cookie: str) -> str:
    """
    Reconstruct Arena's single arena-auth-prod-v1 auth cookie from:
    1. Raw base64 token (adds arena-auth-prod-v1= prefix)
    2. Supabase SSR chunks (.0, .1, etc.) in string or JSON format
    3. Full Cookie header string (preserves cf_clearance, etc.)
    Adapted from OmniRoute (PR #6280) and LMArenaBridge (auth.py).
    """
    if not raw_cookie or not str(raw_cookie).strip():
        return ""

    raw_str = str(raw_cookie).strip()

    # Try parsing as JSON dictionary first (e.g. {"arena-auth-prod-v1.0": "..."})
    pairs: Dict[str, str] = {}
    ordered_keys: List[str] = []

    if raw_str.startswith("{") and raw_str.endswith("}"):
        try:
            data = json.loads(raw_str)
            if isinstance(data, dict):
                # Handle cookie array like [{"name": "...", "value": "..."}]
                if "cookies" in data and isinstance(data["cookies"], list):
                    for item in data["cookies"]:
                        if isinstance(item, dict) and "name" in item and "value" in item:
                            k, v = str(item["name"]).strip(), str(item["value"]).strip()
                            pairs[k] = v
                            ordered_keys.append(k)
                else:
                    for k, v in data.items():
                        k_s, v_s = str(k).strip(), str(v).strip()
                        pairs[k_s] = v_s
                        ordered_keys.append(k_s)
        except Exception:
            pass

    # If not parsed from JSON, parse as semicolon or newline delimited string
    if not pairs:
        # If it's a bare token starting with base64- or eyJ (raw cookie value copied without name)
        if raw_str.startswith("base64-") or (raw_str.startswith("eyJ") and "." in raw_str):
            return f"{LMARENA_AUTH_COOKIE}={raw_str}"

        # Split on semicolon or newline
        normalized_parts = re.split(r"[;\n]+", raw_str)
        for part in normalized_parts:
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and v:
                    pairs[k] = v
                    ordered_keys.append(k)

    if not pairs:
        return raw_str

    # If arena-auth-prod-v1 is already present and non-empty, use it directly
    if pairs.get(LMARENA_AUTH_COOKIE):
        joined = pairs[LMARENA_AUTH_COOKIE]
        chunk_prefix = f"{LMARENA_AUTH_COOKIE}."
        preserved = [f"{k}={v}" for k in ordered_keys if k != LMARENA_AUTH_COOKIE and not k.startswith(chunk_prefix)]
        return f"{LMARENA_AUTH_COOKIE}={joined}; " + "; ".join(preserved) if preserved else f"{LMARENA_AUTH_COOKIE}={joined}"

    # Collect chunks (.0, .1, etc.)
    chunk_prefix = f"{LMARENA_AUTH_COOKIE}."
    chunks: Dict[int, str] = {}
    for k, v in pairs.items():
        if k.startswith(chunk_prefix):
            idx_str = k[len(chunk_prefix):]
            if idx_str.isdigit():
                chunks[int(idx_str)] = v

    if not chunks:
        # No chunks found, format all pairs as cookie header
        return "; ".join(f"{k}={v}" for k, v in pairs.items())

    # Join chunks in ascending order (0, 1, 2, ...)
    joined_parts: List[str] = []
    i = 0
    while i in chunks:
        joined_parts.append(chunks[i])
        i += 1

    joined = "".join(joined_parts)
    if not joined:
        return raw_str

    # Reconstruct cookie string: put joined cookie first, keep other cookies (like cf_clearance)
    preserved = [f"{k}={v}" for k in ordered_keys if k != LMARENA_AUTH_COOKIE and not k.startswith(chunk_prefix)]
    return f"{LMARENA_AUTH_COOKIE}={joined}; " + "; ".join(preserved) if preserved else f"{LMARENA_AUTH_COOKIE}={joined}"


def parse_arena_sse_line(line: str) -> Optional[Dict[str, Any]]:
    trimmed = line.strip()
    payload = trimmed[6:].strip() if trimmed.startswith("data: ") else trimmed
    if not payload:
        return None

    m = re.match(r"^[ab]([023dfge]):(.*)$", payload)
    if m:
        code = m.group(1)
        raw_val = m.group(2)
    else:
        sep = payload.find(":")
        if sep < 0:
            return None
        code = payload[:sep]
        raw_val = payload[sep + 1:]

    try:
        val = json.loads(raw_val)
    except Exception:
        val = raw_val

    if code == "0":
        text = val if isinstance(val, str) else (val.get("text", "") if isinstance(val, dict) else str(val))
        return {"type": "text", "content": text}
    elif code == "g":
        thinking = val if isinstance(val, str) else (val.get("thinking", "") if isinstance(val, dict) else str(val))
        return {"type": "thinking", "content": thinking}
    elif code == "d":
        if isinstance(val, dict) and val.get("finishReason") == "error":
            return {"type": "error", "content": "Arena stream finished with an error"}
        return {"type": "done"}
    elif code in ("3", "e"):
        err = val if isinstance(val, str) else (val.get("message", "") if isinstance(val, dict) else str(val))
        return {"type": "error", "content": err}
    elif code == "2":
        return {"type": "heartbeat"}

    return None


class RealArenaProvider(ArenaProvider):
    def __init__(self, endpoints: Optional[List[str]] = None, timeout: float = 120.0):
        self.endpoints = ["https://arena.ai"]
        self.timeout = timeout

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        try:
            creds = json.loads(access_token)
            cookie_str = creds.get("cookie", access_token)
        except (json.JSONDecodeError, TypeError):
            cookie_str = access_token

        final_cookie = reconstruct_arena_cookie(str(cookie_str))

        headers = {
            "Accept": "text/event-stream, application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Origin": "https://arena.ai",
            "Referer": "https://arena.ai/direct",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Cookie": final_cookie,
        }
        return headers

    def _build_arena_payload(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        messages = envelope.get("messages", [])
        rendered_parts = []
        for m in messages:
            role = m.get("role", "user")
            c = m.get("content", "")
            if isinstance(c, list):
                text_parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
                content_text = " ".join(text_parts).strip()
            else:
                content_text = str(c).strip()

            if not content_text:
                continue

            if len(messages) == 1 and role == "user":
                rendered_parts.append(content_text)
            else:
                label = "System" if role == "system" else ("Assistant" if role == "assistant" else "User")
                rendered_parts.append(f"{label}: {content_text}")

        full_prompt = "\n\n".join(rendered_parts) if rendered_parts else "Hello"

        raw_model = envelope.get("model", "gpt-4o")
        clean_model = raw_model.replace("arena/", "").strip()

        # Resolve public model name to Arena internal UUID (adapted from g4f / OmniRoute)
        target_model_id = clean_model
        try:
            map_path = Path("arena_model_map.json")
            if map_path.exists():
                with open(map_path, "r", encoding="utf-8") as f:
                    model_map = json.load(f)
                    if clean_model in model_map:
                        target_model_id = model_map[clean_model]
                    else:
                        # Case-insensitive search or partial match
                        for k, v in model_map.items():
                            if k.lower() == clean_model.lower():
                                target_model_id = v
                                break
        except Exception:
            pass

        return {
            "id": str(uuid.uuid4()),
            "mode": "direct-battle",
            "modelAId": target_model_id,
            "userMessageId": str(uuid.uuid4()),
            "modelAMessageId": str(uuid.uuid4()),
            "userMessage": {
                "content": full_prompt,
                "experimental_attachments": [],
                "metadata": {},
            },
            "modality": "chat",
        }

    async def fetch_available_models(self, access_token: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        return {"models": []}

    async def generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any], str]:
        headers = self._build_headers(access_token)
        url = "https://arena.ai/nextjs-api/stream/create-evaluation"
        payload = self._build_arena_payload(envelope)
        model = envelope.get("model", "gpt-4o")

        try:
            async with AsyncSession(impersonate="chrome124") as s:
                resp = await s.post(url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code != 200:
                    return resp.status_code, {"error": resp.text}, resp.text

                full_text = ""
                for line in resp.text.split("\n"):
                    ev = parse_arena_sse_line(line)
                    if ev and ev.get("type") == "text":
                        full_text += ev.get("content", "")

                result = {
                    "id": f"chatcmpl-{uuid.uuid4()}",
                    "object": "chat.completion",
                    "created": int(asyncio.get_event_loop().time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": full_text},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": len(payload["userMessage"]["content"].split()),
                        "completion_tokens": len(full_text.split()),
                        "total_tokens": len(payload["userMessage"]["content"].split()) + len(full_text.split()),
                    },
                }
                return 200, result, json.dumps(result)
        except Exception as e:
            logger.error(f"Error in generate_content: {e}")
            return 503, {"error": str(e)}, str(e)

    async def stream_generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> AsyncIterator[Tuple[int, str]]:
        headers = self._build_headers(access_token)
        url = "https://arena.ai/nextjs-api/stream/create-evaluation"
        payload = self._build_arena_payload(envelope)
        model = envelope.get("model", "gpt-4o")
        chat_id = f"chatcmpl-{uuid.uuid4()}"
        created = int(asyncio.get_event_loop().time())

        try:
            async with AsyncSession(impersonate="chrome124") as s:
                resp = await s.post(url, headers=headers, json=payload, timeout=self.timeout, stream=True)
                if resp.status_code != 200:
                    err_body = resp.text
                    logger.warning(f"Upstream Arena returned error {resp.status_code}: {err_body}")
                    yield resp.status_code, json.dumps({"error": f"Arena error {resp.status_code}: {err_body}"})
                    return

                # Only yield role chunk after upstream confirmed 200 OK
                init_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
                }
                yield 200, f"data: {json.dumps(init_chunk)}\n\n"

                buffer = ""
                has_content = False
                async for chunk in resp.aiter_content():
                    if not chunk:
                        continue
                    buffer += chunk.decode("utf-8", errors="ignore")
                    lines = buffer.split("\n")
                    buffer = lines.pop()

                    for line in lines:
                        ev = parse_arena_sse_line(line)
                        if not ev:
                            continue
                        if ev["type"] == "text" and ev.get("content"):
                            has_content = True
                            c = {
                                "id": chat_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{"index": 0, "delta": {"content": ev["content"]}, "finish_reason": None}],
                            }
                            yield 200, f"data: {json.dumps(c)}\n\n"
                        elif ev["type"] == "done":
                            final_chunk = {
                                "id": chat_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                            }
                            yield 200, f"data: {json.dumps(final_chunk)}\n\n"
                            yield 200, "data: [DONE]\n\n"
                            return
                        elif ev["type"] == "error":
                            err_chunk = {
                                "id": chat_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                                "error": {"message": ev.get("content", "Upstream stream error")},
                            }
                            yield 200, f"data: {json.dumps(err_chunk)}\n\n"
                            yield 200, "data: [DONE]\n\n"
                            return

                final_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield 200, f"data: {json.dumps(final_chunk)}\n\n"
                yield 200, "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Exception during stream: {e}")
            yield 503, json.dumps({"error": str(e)})
