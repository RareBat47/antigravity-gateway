from typing import Optional
import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

from agw.arena.provider import ArenaProvider

logger = logging.getLogger("agw.arena.real")

class RealArenaProvider(ArenaProvider):
    """Real Arena.ai provider with persistent connection pooling and fast failovers."""

    def __init__(self, endpoints: Optional[List[str]] = None, timeout: float = 120.0):
        # Point directly to live Arena endpoints
        self.endpoints = endpoints or ["https://arena.ai/api", "https://lmarena.ai/api"]
        self.timeout = timeout
        # Fast connect timeout (5s) so dead endpoints failover instantly
        self.httpx_timeout = httpx.Timeout(connect=5.0, read=timeout, write=15.0, pool=10.0)
        self.limits = httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=60.0)
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.httpx_timeout, limits=self.limits)
        return self._client

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        try:
            creds = json.loads(access_token)
            cookie_str = creds.get("cookie", access_token)
            authorization = creds.get("authorization", "")
        except json.JSONDecodeError:
            cookie_str = access_token
            authorization = ""

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie_str
        }
        if authorization:
            headers["Authorization"] = authorization
            
        return headers

    async def fetch_available_models(self, access_token: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch model metadata using pooled client."""
        headers = self._build_headers(access_token)
        client = self._get_client()
        for endpoint in self.endpoints:
            url = f"{endpoint}/models"
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.warning(f"Error fetching models from {url}: {e}")
        return {"models": []}

    async def generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any], str]:
        headers = self._build_headers(access_token)
        headers["Content-Type"] = "application/json"
        client = self._get_client()
        
        for endpoint in self.endpoints:
            url = f"{endpoint}/chat/completions"
            try:
                req_env = dict(envelope)
                req_env["stream"] = False
                
                resp = await client.post(url, headers=headers, json=req_env)
                raw_text = resp.text
                try:
                    parsed = resp.json()
                except Exception:
                    parsed = {}

                return resp.status_code, parsed, raw_text
            except Exception as e:
                return 503, {}, str(e)
        return 500, {}, "Unknown error"

    async def stream_generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> AsyncIterator[Tuple[int, str]]:
        headers = self._build_headers(access_token)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "text/event-stream"
        client = self._get_client()

        for endpoint in self.endpoints:
            url = f"{endpoint}/chat/completions"
            try:
                req_env = dict(envelope)
                req_env["stream"] = True
                
                async with client.stream("POST", url, headers=headers, json=req_env) as resp:
                    if resp.status_code != 200:
                        err_content = await resp.aread()
                        yield resp.status_code, err_content.decode("utf-8", errors="ignore")
                        return

                    async for line in resp.aiter_lines():
                        if line:
                            yield 200, f"{line}\n\n"
                    return
            except Exception as e:
                logger.warning(f"Network error streaming from {endpoint}: {type(e).__name__}: {e}")
                continue

        yield 503, json.dumps({"error": "Failed to establish stream with upstream"})
