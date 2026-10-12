"""Real Google AI Studio REST and SDK client for Antigravity Gateway."""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("agw.aistudio")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class AIStudioClient:
    """Handles communication with Google AI Studio Generative Language REST APIs."""

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
        self.httpx_timeout = httpx.Timeout(connect=15.0, read=timeout, write=30.0, pool=20.0)

    async def validate_key(self, api_key: str) -> Tuple[bool, str, List[str]]:
        """Validate an AI Studio API key by querying available models."""
        if not api_key or not api_key.strip():
            return False, "API key is empty", []

        url = f"{BASE_URL}/models?key={api_key.strip()}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
                    return True, "Valid", models
                else:
                    try:
                        err_data = resp.json()
                        err_msg = err_data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                    except Exception:
                        err_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
                    return False, err_msg, []
        except Exception as e:
            return False, str(e), []

    def _convert_envelope(self, envelope: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Convert internal CloudCode Assist envelope to AI Studio REST format."""
        raw_model = envelope.get("model", "gemini-2.5-flash")
        # Strip provider prefix if present
        clean_model = raw_model.split("/")[-1]

        # Check standard models or map aliases
        if clean_model in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
            target_model = "gemini-3.8-flash"
        elif clean_model in ("gemini-2.5-pro", "gemini-1.5-pro"):
            target_model = "gemini-3.1-pro-preview"
        elif clean_model.startswith("gemini-") or clean_model.startswith("imagen-"):
            target_model = clean_model
        elif "pro" in clean_model.lower():
            target_model = "gemini-3.1-pro-preview"
        elif "flash" in clean_model.lower():
            target_model = "gemini-3.8-flash"
        else:
            target_model = "gemini-3.8-flash"

        # Check nested request envelope or top-level
        inner = envelope.get("request", envelope) if isinstance(envelope.get("request"), dict) else envelope

        # Extract contents and generation config
        req_body: Dict[str, Any] = {}
        if "contents" in inner:
            req_body["contents"] = inner["contents"]
        elif "prompt" in inner:
            req_body["contents"] = [{"role": "user", "parts": [{"text": str(inner["prompt"])}]}]
        elif "contents" in envelope:
            req_body["contents"] = envelope["contents"]
        else:
            req_body["contents"] = []

        if "generationConfig" in inner:
            req_body["generationConfig"] = inner["generationConfig"]
        elif "generation_config" in inner:
            req_body["generationConfig"] = inner["generation_config"]
        elif "generationConfig" in envelope:
            req_body["generationConfig"] = envelope["generationConfig"]

        if "systemInstruction" in inner:
            req_body["systemInstruction"] = inner["systemInstruction"]
        elif "systemInstruction" in envelope:
            req_body["systemInstruction"] = envelope["systemInstruction"]

        if "tools" in inner and inner["tools"]:
            req_body["tools"] = inner["tools"]
        if "toolConfig" in inner and inner["toolConfig"]:
            req_body["toolConfig"] = inner["toolConfig"]
        if "safetySettings" in inner and inner["safetySettings"]:
            req_body["safetySettings"] = inner["safetySettings"]

        return target_model, req_body

    async def generate_content(
        self, api_key: str, envelope: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any], str]:
        """Execute non-streaming generateContent via Google AI Studio."""
        target_model, body = self._convert_envelope(envelope)
        url = f"{BASE_URL}/models/{target_model}:generateContent?key={api_key.strip()}"

        try:
            async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
                resp = await client.post(url, json=body)
                raw_text = resp.text
                try:
                    parsed = resp.json()
                except Exception:
                    parsed = {}

                # Map candidates into standard CloudCode schema if needed
                return resp.status_code, parsed, raw_text
        except Exception as e:
            logger.error(f"AI Studio generateContent failed: {e}")
            return 503, {}, str(e)

    async def stream_generate_content(
        self, api_key: str, envelope: Dict[str, Any]
    ) -> AsyncIterator[Tuple[int, str]]:
        """Stream SSE generateContent via Google AI Studio."""
        target_model, body = self._convert_envelope(envelope)
        url = f"{BASE_URL}/models/{target_model}:streamGenerateContent?alt=sse&key={api_key.strip()}"

        try:
            async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
                async with client.stream("POST", url, json=body) as stream_resp:
                    if stream_resp.status_code != 200:
                        err_body = await stream_resp.aread()
                        yield stream_resp.status_code, f"data: {err_body.decode('utf-8', errors='ignore')}\n\n"
                        return

                    async for line in stream_resp.aiter_lines():
                        if line:
                            yield 200, f"{line}\n\n"
                    yield 200, "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"AI Studio streamGenerateContent failed: {e}")
            yield 503, f"data: {json.dumps({'error': str(e)})}\n\n"
