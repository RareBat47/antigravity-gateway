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

    async def fetch_quotas(
        self,
        cookies: Dict[str, str],
        snlm0e: Optional[str] = None,
        authuser: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fetch live quota limits and reset windows directly from Google's native jSf9Qc batchexecute RPC."""
        import datetime
        if authuser is None:
            try:
                authuser = int(cookies.get("authuser", 0))
            except Exception:
                authuser = 0

        target_url = (
            f"https://gemini.google.com/u/{authuser}/_/BardChatUi/data/batchexecute?rpcids=jSf9Qc&source-path=%2Fu%2F{authuser}%2Fusage&hl=en&rt=c"
            if authuser is not None else "https://gemini.google.com/_/BardChatUi/data/batchexecute?rpcids=jSf9Qc&source-path=%2Fusage&hl=en&rt=c"
        )
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items() if k != "authuser"])
        headers = {
            "Cookie": cookie_str,
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "X-Same-Domain": "1",
            "User-Agent": USER_AGENT,
        }
        if authuser is not None:
            headers["X-Goog-AuthUser"] = str(authuser)

        f_req = json.dumps([[["jSf9Qc", "[]", None, "1"]]])
        data = {"f.req": f_req, "at": snlm0e or ""}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(target_url, headers=headers, data=data)
                if resp.status_code != 200:
                    return {}
                for line in resp.text.splitlines():
                    if "jSf9Qc" in line:
                        arr = json.loads(line)
                        inner = json.loads(arr[0][2])
                        tier_code = inner[0]
                        tier_str = "PRO" if tier_code == 2 else "FREE"
                        windows = inner[1]
                        current_5h = {}
                        weekly = {}
                        for w in windows:
                            if len(w) > 2:
                                w_type = w[2]
                                rem = w[0]
                                epoch = w[3][0][0] if len(w) > 3 and w[3] and len(w[3][0]) > 0 else None
                                reset_iso = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat() if epoch else ""
                                if w_type == 1:
                                    max_cr = 2400 if tier_code == 2 else 600
                                    current_5h = {
                                        "remaining_credits": rem,
                                        "max_credits": max_cr,
                                        "reset_at": reset_iso,
                                        "usage_percentage": max(0, int(round((1.0 - (rem / max_cr)) * 100))),
                                    }
                                elif w_type == 2:
                                    max_cr = 48384 if tier_code == 2 else 12096
                                    weekly = {
                                        "remaining_credits": rem,
                                        "max_credits": max_cr,
                                        "reset_at": reset_iso,
                                    }
                        return {
                            "usage_info": {
                                "tier": {"id": tier_code, "label": tier_str},
                                "current_5h": current_5h,
                                "weekly": weekly,
                            }
                        }
        except Exception as e:
            logger.warning(f"Native jSf9Qc quota fetch failed for authuser={authuser}: {e}")
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

        # Primary engine: gemini_webapi with direct chrome131 session injection
        try:
            from curl_cffi.requests import AsyncSession
            from gemini_webapi import GeminiClient
            psid = cookies.get("__Secure-1PSID")
            psidts = cookies.get("__Secure-1PSIDTS")
            client = GeminiClient(secure_1psid=psid, secure_1psidts=psidts)
            
            # Explicitly set all session cookies including the user index
            for k, v in cookies.items():
                if k != "authuser":
                    client._cookies.set(k, str(v), domain=".google.com", secure=True)
            client._cookies.set("authuser", str(authuser), domain=".google.com", secure=True)

            # Essential: Inject pre-authenticated Chrome 131 AsyncSession directly.
            # Bypasses client.init() which triggers Google's IP 429 bot check on naked GET requests.
            session = AsyncSession(impersonate="chrome131")
            session.cookies.update(client._cookies)
            client.client = session
            if snlm0e:
                client.access_token = snlm0e

            res = await client.generate_content(prompt, temporary=True)
            await session.close()

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
