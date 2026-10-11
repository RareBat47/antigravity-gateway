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
                if c.name in ["__Secure-1PSID", "__Secure-1PSIDTS", "SID", "HSID"]:
                    found[c.name] = c.value
            if "__Secure-1PSID" in found:
                return True, found, "Successfully extracted from Chrome"
            return False, {}, "No __Secure-1PSID found in Chrome"
        except Exception as e:
            return False, {}, str(e)

    async def fetch_snlm0e(self, cookies: Dict[str, str]) -> Tuple[bool, Optional[str], str]:
        """Fetch the active SNlM0e session token from gemini.google.com."""
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": cookie_header,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(GEMINI_URL, headers=headers)
                if resp.status_code != 200:
                    return False, None, f"HTTP {resp.status_code} from gemini.google.com"

                html = resp.text
                match = re.search(r'\"SNlM0e\":\"(.*?)\"', html)
                if match:
                    token = match.group(1)
                    return True, token, "Session token extracted"

                if "accounts.google.com" in html and ("Sign in" in html or "signin" in html):
                    return False, None, "Cookie expired or not logged into Gemini Web"

                return False, None, "SNlM0e token not found in response HTML"
        except Exception as e:
            return False, None, str(e)

    async def validate_session(self, cookies: Dict[str, str]) -> Tuple[bool, str, Optional[str]]:
        """Validate if cookies provide an active, authenticated Gemini Web session."""
        ok, token, msg = await self.fetch_snlm0e(cookies)
        if ok and token:
            return True, "Session verified and active", token
        return False, msg, None

    async def generate_content(
        self, cookies: Dict[str, str], snlm0e: str, prompt: str
    ) -> Tuple[int, Dict[str, Any], str]:
        """Execute a prompt via Gemini Web batchexecute RPC."""
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": cookie_header,
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "X-Same-Domain": "1",
        }

        # Build standard Bard/Gemini batchexecute payload
        inner_payload = [[prompt], None, [None, None, None]]
        envelope = [None, json.dumps(inner_payload)]
        freq = [[[ "fReq", json.dumps(envelope), None, "generic" ]]]
        data = {
            "f.req": json.dumps(freq),
            "at": snlm0e,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(BATCH_EXECUTE_URL, headers=headers, data=data)
                if resp.status_code != 200:
                    return resp.status_code, {}, f"HTTP {resp.status_code} from batchexecute"

                # Parse Google batchexecute response
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
                                        # Candidate answers
                                        answers = sub_json[4]
                                        if answers and len(answers) > 0 and len(answers[0]) > 1:
                                            reply_text = answers[0][1][0]
                                            break
                        except Exception:
                            continue

                if not reply_text:
                    reply_text = "[Gemini Web response received]"

                result_envelope = {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [{"text": reply_text}],
                            },
                            "finishReason": "STOP",
                        }
                    ]
                }
                return 200, result_envelope, reply_text
        except Exception as e:
            logger.error(f"Gemini Web batchexecute failed: {e}")
            return 503, {}, str(e)
