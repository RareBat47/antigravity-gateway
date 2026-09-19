"""Async HTTP client for Google Cloud Code Assist upstream APIs."""

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
    RPC_STREAM_GENERATE_CONTENT,
)


class CloudCodeClient:
    """Handles communication with Cloud Code Assist API with endpoint fallbacks."""

    def __init__(self, endpoints: Optional[List[str]] = None, timeout: float = 60.0):
        self.endpoints = endpoints or list(CLOUDCODE_ENDPOINTS)
        self.timeout = timeout

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        headers = dict(ANTIGRAVITY_HEADERS)
        headers["Authorization"] = f"Bearer {access_token}"
        return headers

    async def load_code_assist(self, access_token: str) -> Tuple[str, str]:
        """
        Discover project ID and subscription tier via loadCodeAssist.
        Returns (project_id, tier).
        """
        headers = self._build_headers(access_token)
        body = {"metadata": CLIENT_METADATA, "mode": 1}

        # Try endpoints prod first for project discovery
        discovery_endpoints = list(reversed(self.endpoints))
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
                    else:
                        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except Exception as e:
                    last_err = str(e)

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
                    # For non-network 4xx errors (e.g. rate limit, bad request), don't blindly re-hit next endpoint
                    if resp.status_code in (400, 401, 403, 429):
                        return resp.status_code, parsed, raw_text
                except Exception as e:
                    last_err_tuple = (503, {}, str(e))

        return last_err_tuple

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
                # If network fail, try next endpoint
                pass

        yield 503, json.dumps({"error": "Failed to establish stream with upstream"})
