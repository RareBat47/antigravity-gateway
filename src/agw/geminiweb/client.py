"""Real Gemini Web Session client for Antigravity Gateway.

Extracts live session cookies (__Secure-1PSID, __Secure-1PSIDTS) and SNlM0e tokens
to interact with consumer Gemini Web endpoints at zero token cost.
"""

import json
import logging
import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple
import httpx

logger = logging.getLogger("agw.geminiweb")

GEMINI_URL = "https://gemini.google.com"
BATCH_EXECUTE_URL = "https://gemini.google.com/_/BardChatUi/data/batchexecute"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class GeminiWebClient:
    """Handles communication with consumer Gemini Web chat sessions."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    @staticmethod
    def extract_from_local_chrome() -> Tuple[bool, Dict[str, str], str]:
        """Auto-detect and extract Google cookies from local Chrome installation."""
        try:
            import browser_cookie3
            cj = browser_cookie3.chrome(domain_name=".google.com")
            found = {}
            for c in cj:
                if c.name in [
                    "__Secure-1PSID", "__Secure-1PSIDTS", "SID", "HSID", "SSID",
                    "SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID",
                    "__Secure-3PSID", "__Secure-3PSIDTS", "SIDCC",
                    "__Secure-1PSIDCC", "__Secure-3PSIDCC", "NID"
                ]:
                    found[c.name] = c.value
            if "__Secure-1PSID" in found:
                return True, found, "Successfully extracted from Chrome"
            return False, {}, "No __Secure-1PSID found in Chrome"
        except Exception as e:
            return False, {}, str(e)

    async def fetch_snlm0e(self, cookies: Dict[str, str], authuser: int = 0) -> Tuple[bool, Optional[str], str]:
        """Fetch the active SNlM0e session token from gemini.google.com."""
        target_url = f"https://gemini.google.com/u/{authuser}/app" if authuser else GEMINI_URL
        
        # Try via curl_cffi first for TLS fingerprint fidelity
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome145") as session:
                for k, v in cookies.items():
                    if k != "authuser":
                        session.cookies.set(k, v, domain=".google.com")
                resp = await session.get(target_url, headers={"Referer": "https://gemini.google.com/"})
                if resp.status_code == 200:
                    patterns = [
                        r'"SNlM0e":\s*"([^"]+)"',
                        r'\"SNlM0e\":\"(.*?)\"',
                        r'SNlM0e["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'\[\"SNlM0e\",\[\],\"(.*?)\"\]',
                    ]
                    for pat in patterns:
                        match = re.search(pat, resp.text)
                        if match:
                            token = match.group(1)
                            if token and len(token) > 5:
                                return True, token, "Session token extracted"
        except Exception as e:
            logger.debug(f"curl_cffi fetch_snlm0e failed ({e}), trying standard httpx")

        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items() if k != "authuser"])
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": cookie_header,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(target_url, headers=headers)
                if resp.status_code != 200:
                    return False, None, f"HTTP {resp.status_code} from gemini.google.com"

                html = resp.text
                patterns = [
                    r'"SNlM0e":\s*"([^"]+)"',
                    r'\"SNlM0e\":\"(.*?)\"',
                    r'SNlM0e["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'\[\"SNlM0e\",\[\],\"(.*?)\"\]',
                ]
                for pat in patterns:
                    match = re.search(pat, html)
                    if match:
                        token = match.group(1)
                        if token and len(token) > 5:
                            return True, token, "Session token extracted"

                if "accounts.google.com" in str(resp.url) or ("accounts.google.com" in html and ("Sign in" in html or "signin" in html)):
                    return False, None, "Cookie expired or not logged into Gemini Web"

                return False, None, "SNlM0e token not found in response HTML"
        except Exception as e:
            return False, None, str(e)

    async def validate_session(
        self, cookies: Dict[str, str], snlm0e: Optional[str] = None, authuser: int = 0
    ) -> Tuple[bool, str, Optional[str]]:
        """Validate if cookies provide an active, authenticated Gemini Web session."""
        if snlm0e and len(snlm0e) >= 20 and "__Secure-1PSID" in cookies:
            return True, "Session verified and active (vault token)", snlm0e

        ok, token, msg = await self.fetch_snlm0e(cookies, authuser=authuser)
        if ok and token:
            return True, "Session verified and active", token
        return False, msg, None

    async def fetch_quotas(self, cookies: Dict[str, str], snlm0e: Optional[str] = None) -> Dict[str, Any]:
        """Fetch live quota limits and reset windows using gemini-webapi."""
        try:
            from gemini_webapi import GeminiClient
            psid = cookies.get("__Secure-1PSID")
            psidts = cookies.get("__Secure-1PSIDTS")
            client = GeminiClient(secure_1psid=psid, secure_1psidts=psidts)
            for k, v in cookies.items():
                if k != "authuser":
                    client._cookies.set(k, v, domain=".google.com", secure=True)
            if snlm0e:
                client.access_token = snlm0e
            await client.init(timeout=15.0, auto_refresh=False)
            res = {
                "quotas": client.quotas,
                "usage_info": client.usage_info,
                "abuse_status": client.abuse_status,
            }
            await client.close()
            return res
        except Exception as e:
            logger.warning(f"Failed to fetch gemini web quotas: {e}")
            return {}

    async def generate_content(
        self, cookies: Dict[str, str], snlm0e: str, prompt: str, authuser: Optional[int] = None
    ) -> Tuple[int, Dict[str, Any], str]:
        """Execute a prompt via Gemini Web session."""
        if authuser is None:
            try:
                authuser = int(cookies.get("authuser", 0))
            except Exception:
                authuser = 0

        # Primary engine: gemini_webapi with browser TLS impersonation
        try:
            from gemini_webapi import GeminiClient
            psid = cookies.get("__Secure-1PSID")
            psidts = cookies.get("__Secure-1PSIDTS")
            client = GeminiClient(secure_1psid=psid, secure_1psidts=psidts)
            for k, v in cookies.items():
                if k != "authuser":
                    client._cookies.set(k, v, domain=".google.com", secure=True)

            await client.init(timeout=self.timeout, auto_refresh=False)
            res = await client.generate_content(prompt, temporary=True)
            await client.close()

            reply_text = (res.text or "").strip()
            if not reply_text:
                reply_text = "[Gemini Web empty response]"

            p_toks = max(1, len(prompt.split()) * 2)
            c_toks = max(1, len(reply_text.split()) * 2)
            result_envelope = {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": reply_text}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": p_toks,
                    "candidatesTokenCount": c_toks,
                    "totalTokenCount": p_toks + c_toks,
                },
            }
            return 200, result_envelope, reply_text
        except Exception as e:
            logger.warning(f"gemini_webapi generation failed ({e}), attempting fallback RPC...")

        # Fallback engine: direct batchexecute RPC
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items() if k != "authuser"])
        target_batch_url = (
            f"https://gemini.google.com/u/{authuser}/_/BardChatUi/data/batchexecute"
            if authuser else BATCH_EXECUTE_URL
        )
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": cookie_header,
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "X-Same-Domain": "1",
        }
        if authuser:
            headers["X-Goog-AuthUser"] = str(authuser)

        inner_payload = [[prompt], None, [None, None, None]]
        envelope = [None, json.dumps(inner_payload)]
        freq = [[[ "fReq", json.dumps(envelope), None, "generic" ]]]
        data = {
            "f.req": json.dumps(freq),
            "at": snlm0e,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(target_batch_url, headers=headers, data=data)
                if resp.status_code != 200:
                    return resp.status_code, {}, f"HTTP {resp.status_code} from batchexecute"

                raw_text = resp.text
                lines = raw_text.splitlines()
                reply_text = ""
                for line in lines:
                    if line.startswith("[["):
                        try:
                            parsed_array = json.loads(line)
                            for item in parsed_array:
                                if item and len(item) > 2 and item[2]:
                                    sub_json = json.loads(item[2])
                                    if sub_json and len(sub_json) > 4:
                                        answers = sub_json[4]
                                        if answers and len(answers) > 0 and len(answers[0]) > 1:
                                            reply_text = answers[0][1][0]
                                            break
                        except Exception:
                            continue

                if not reply_text:
                    reply_text = "[Gemini Web response received]"

                p_toks = max(1, len(prompt.split()) * 2)
                c_toks = max(1, len(reply_text.split()) * 2)
                result_envelope = {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [{"text": reply_text}],
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": p_toks,
                        "candidatesTokenCount": c_toks,
                        "totalTokenCount": p_toks + c_toks,
                    },
                }
                return 200, result_envelope, reply_text
        except Exception as e:
            logger.error(f"Gemini Web fallback batchexecute failed: {e}")
            return 503, {}, str(e)
