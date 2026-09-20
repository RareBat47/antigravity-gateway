"""Async HTTP client for Google Cloud Code Assist upstream APIs."""

import logging

import json
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
import httpx

from agw.constants import (
    ANTIGRAVITY_HEADERS,
    CLIENT_METADATA,
    CLOUDCODE_ENDPOINTS,
    RPC_FETCH_AVAILABLE_MODELS,
    RPC_GENERATE_CONTENT,
    RPC_LOAD_CODE_ASSIST,
    RPC_ONBOARD_USER,
    RPC_STREAM_GENERATE_CONTENT,
)

logger = logging.getLogger("agw.client")


class CloudCodeClient:
    """Handles communication with Cloud Code Assist API with endpoint fallbacks."""

    def __init__(self, endpoints: Optional[List[str]] = None, timeout: float = 120.0):
        self.endpoints = endpoints or list(CLOUDCODE_ENDPOINTS)
        self.timeout = timeout

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        headers = dict(ANTIGRAVITY_HEADERS)
        headers["Authorization"] = f"Bearer {access_token}"
        return headers

    async def onboard_user(self, access_token: str) -> Optional[str]:
        """Attempt to onboard user to Cloud Code Assist if not yet initialized."""
        headers = self._build_headers(access_token)
        body = {"metadata": CLIENT_METADATA}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for endpoint in self.endpoints:
                url = f"{endpoint}/{RPC_ONBOARD_USER}"
                try:
                    resp = await client.post(url, headers=headers, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data.get("cloudaicompanionProject"), str):
                            return data["cloudaicompanionProject"]
                        elif isinstance(data.get("cloudaicompanionProject"), dict):
                            return data["cloudaicompanionProject"].get("id")
                        elif isinstance(data.get("cloudaicompanion_project"), str):
                            return data["cloudaicompanion_project"]
                except Exception:
                    pass
        return None

    async def load_code_assist(self, access_token: str, allow_onboard: bool = True) -> Tuple[str, str]:
        """
        Discover project ID and subscription tier via loadCodeAssist.
        Returns (project_id, tier).
        """
        headers = self._build_headers(access_token)
        body = {"metadata": CLIENT_METADATA, "mode": 1}

        discovery_endpoints = list(self.endpoints)
        last_err = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for endpoint in discovery_endpoints:
                url = f"{endpoint}/{RPC_LOAD_CODE_ASSIST}"
                try:
                    resp = await client.post(url, headers=headers, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        project_id = ""
                        if isinstance(data.get("cloudaicompanionProject"), str):
                            project_id = data["cloudaicompanionProject"]
                        elif isinstance(data.get("cloudaicompanionProject"), dict):
                            project_id = data["cloudaicompanionProject"].get("id", "")
                        elif isinstance(data.get("cloudaicompanion_project"), str):
                            project_id = data["cloudaicompanion_project"]

                        tier = "unknown"
                        if paid_tier := data.get("paidTier"):
                            tid = paid_tier.get("id", "").lower()
                            tier = "ultra" if "ultra" in tid else ("pro" if "pro" in tid else "free")
                        elif current_tier := data.get("currentTier"):
                            cid = current_tier.get("id", "").lower()
                            tier = "pro" if ("standard" in cid or "pro" in cid) else "free"
                        elif allowed_tiers := data.get("allowedTiers"):
                            for t in allowed_tiers:
                                tid = t.get("id", "").lower()
                                if "pro" in tid or "standard" in tid:
                                    tier = "pro"
                                    break

                        if project_id:
                            return project_id, tier

                        # If response succeeded but project is empty, try onboarding
                        if allow_onboard:
                            onboard_proj = await self.onboard_user(access_token)
                            if onboard_proj:
                                return onboard_proj, tier
                    else:
                        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except Exception as e:
                    last_err = str(e)

        if allow_onboard:
            onboard_proj = await self.onboard_user(access_token)
            if onboard_proj:
                return onboard_proj, "unknown"

        raise RuntimeError(f"loadCodeAssist failed across all endpoints: {last_err}")

    async def fetch_available_models(
        self, access_token: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch model metadata and live quotas via fetchAvailableModels."""
        headers = self._build_headers(access_token)
        body = {"project": project_id} if project_id else {}
        last_err = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for endpoint in self.endpoints:
                url = f"{endpoint}/{RPC_FETCH_AVAILABLE_MODELS}"
                try:
                    resp = await client.post(url, headers=headers, json=body)
                    if resp.status_code == 200:
                        return resp.json()
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except Exception as e:
                    last_err = str(e)

        raise RuntimeError(f"fetchAvailableModels failed across all endpoints: {last_err}")

    async def generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any], str]:
        """
        Execute non-streaming generateContent request.
        Returns (status_code, response_json, raw_text).
        """
        headers = self._build_headers(access_token)
        last_err_tuple = (500, {}, "Unknown upstream error")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for endpoint in self.endpoints:
                url = f"{endpoint}/{RPC_GENERATE_CONTENT}"
                try:
                    resp = await client.post(url, headers=headers, json=envelope)
                    raw_text = resp.text
                    try:
                        parsed = resp.json()
                    except Exception:
                        parsed = {}

                    if resp.status_code == 200:
                        return resp.status_code, parsed, raw_text
                    last_err_tuple = (resp.status_code, parsed, raw_text)
                    # For 429, attempt fallback to stream aggregation for streaming-only models like gpt-oss
                    if resp.status_code == 429:
                        try:
                            aggregated = await self._aggregate_stream_response(access_token, envelope)
                            if aggregated:
                                return 200, aggregated, json.dumps(aggregated)
                        except Exception:
                            pass
                        return resp.status_code, parsed, raw_text
                    # For other non-network 4xx errors (e.g. bad request, auth error), don't blindly re-hit next endpoint
                    if resp.status_code in (400, 401, 403):
                        return resp.status_code, parsed, raw_text
                except Exception as e:
                    last_err_tuple = (503, {}, str(e))

        return last_err_tuple

    async def _aggregate_stream_response(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Collect and aggregate SSE stream chunks into a complete response."""
        parts: List[Dict[str, Any]] = []
        finish_reason = "STOP"
        usage_metadata = {}
        model_version = envelope.get("model", "")
        response_id = ""

        try:
            async for status, line in self.stream_generate_content(access_token, envelope):
                if status != 200:
                    return None
                if not line or not line.startswith("data:"):
                    continue
                raw_data = line[5:].strip()
                if raw_data == "[DONE]":
                    break
                try:
                    payload = json.loads(raw_data)
                except Exception:
                    continue

                resp_obj = payload.get("response", payload)
                if "responseId" in resp_obj:
                    response_id = resp_obj["responseId"]
                if "modelVersion" in resp_obj:
                    model_version = resp_obj["modelVersion"]
                if "usageMetadata" in resp_obj:
                    usage_metadata = resp_obj["usageMetadata"]

                candidates = resp_obj.get("candidates", [])
                for cand in candidates:
                    cand_finish = cand.get("finishReason")
                    if cand_finish:
                        finish_reason = cand_finish
                    content = cand.get("content", {})
                    for p in content.get("parts", []):
                        parts.append(p)

            if not parts:
                return None

            return {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": parts,
                        },
                        "finishReason": finish_reason,
                    }
                ],
                "usageMetadata": usage_metadata,
                "modelVersion": model_version,
                "responseId": response_id,
            }
        except Exception:
            return None

    async def stream_generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> AsyncIterator[Tuple[int, str]]:
        """
        Execute streaming streamGenerateContent request with SSE.
        Yields (status_code, line/event).
        """
        headers = self._build_headers(access_token)
        headers["Accept"] = "text/event-stream"

        for endpoint in self.endpoints:
            url = f"{endpoint}/{RPC_STREAM_GENERATE_CONTENT}?alt=sse"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    async with client.stream("POST", url, headers=headers, json=envelope) as resp:
                        if resp.status_code != 200:
                            err_content = await resp.aread()
                            yield resp.status_code, err_content.decode("utf-8", errors="ignore")
                            return

                        async for line in resp.aiter_lines():
                            yield 200, line
                        return
            except Exception as e:
                # Bug #14: Log the network failure and continue to next endpoint.
                # Previously this was a bare `pass`, meaning the caller could not
                # tell if ALL endpoints failed due to network errors.
                logger.warning(f"Network error streaming from {endpoint}: {type(e).__name__}: {e}")
                continue

        yield 503, json.dumps({"error": "Failed to establish stream with upstream"})
