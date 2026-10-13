"""Account manager orchestrating credentials, persistence, and token lifecycle."""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from agw.auth.oauth import exchange_code, fetch_userinfo, refresh_access_token
from agw.auth.vault import CredentialVault
from agw.cloudcode.client import CloudCodeClient
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository

logger = logging.getLogger("agw.accounts")


class AccountManager:
    """Manages multi-account lifecycle, encrypted tokens, and automated refresh."""

    def __init__(
        self,
        config: AppConfig,
        repo: DatabaseRepository,
        vault: CredentialVault,
        cloudcode_client: CloudCodeClient,
    ):
        self.config = config
        self.repo = repo
        self.vault = vault
        self.client = cloudcode_client
        self._access_tokens: Dict[str, str] = {}  # account_id -> access_token
        self._token_expirations: Dict[str, float] = {}  # account_id -> epoch timestamp
        # Bug #15: per-account locks to prevent concurrent double-refresh races
        self._refresh_locks: Dict[str, asyncio.Lock] = {}

    async def add_account_from_code(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange PKCE code, discover project, and save account."""
        cid = self.config.oauth.client_id
        csec = self.config.oauth.client_secret

        tok_resp = await exchange_code(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            client_id=cid,
            client_secret=csec,
        )

        access_tok = tok_resp["access_token"]
        refresh_tok = tok_resp.get("refresh_token")
        if not refresh_tok:
            raise RuntimeError("OAuth response did not include a refresh_token")

        expires_in = tok_resp.get("expires_in", 3600)

        # Get user info
        uinfo = await fetch_userinfo(access_tok)
        email = uinfo.get("email", "unknown@google.com")
        safe_email = email
        account_id = f"acc-{hashlib.sha256(email.encode()).hexdigest()[:8]}"
        name = display_name or uinfo.get("name") or email.split("@")[0]

        # Discover project ID and subscription tier
        try:
            project_id, tier = await self.client.load_code_assist(access_tok)
        except Exception as e:
            logger.warning(f"Could not load Code Assist project for {email} ({e}), automatically defaulting to auto-configured project.")
            project_id = f"auto-{hashlib.sha256(email.encode()).hexdigest()[:8]}"
            tier = "free"

        # Store encrypted token in vault
        self.vault.store_token(account_id, refresh_tok)

        # Cache access token
        self._access_tokens[account_id] = access_tok
        now_ts = time.time()
        expires_at = now_ts + expires_in
        self._token_expirations[account_id] = expires_at

        # Save record in database
        await self.repo.upsert_account(
            account_id=account_id,
            email_safe=safe_email,
            display_name=name,
            project_id=project_id,
            tier=tier,
            status="active",
            enabled=True,
        )
        await self.repo.update_token_metadata(account_id, int(expires_at))
        await self.repo.upsert_channel_bindings(account_id, oauth_verified=True)

        logger.info(f"Successfully enrolled account {account_id} ({safe_email}), tier: {tier}")
        return {
            "account_id": account_id,
            "email_safe": safe_email,
            "display_name": name,
            "project_id": project_id,
            "tier": tier,
        }

    async def add_account_from_refresh_token(
        self,
        refresh_token: str,
        label: str,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually enroll an account via known refresh token."""
        cid = self.config.oauth.client_id
        csec = self.config.oauth.client_secret

        tok_resp = await refresh_access_token(refresh_token, cid, csec)
        access_tok = tok_resp["access_token"]
        expires_in = tok_resp.get("expires_in", 3600)

        uinfo = await fetch_userinfo(access_tok)
        email = uinfo.get("email", f"{label}@google.com")
        safe_email = email
        account_id = f"acc-{hashlib.sha256(label.encode()).hexdigest()[:8]}"
        name = display_name or label

        try:
            project_id, tier = await self.client.load_code_assist(access_tok)
        except Exception as e:
            logger.warning(f"Could not load Code Assist project for {email} ({e}), automatically defaulting to auto-configured project.")
            project_id = f"auto-{hashlib.sha256(label.encode()).hexdigest()[:8]}"
            tier = "free"

        self.vault.store_token(account_id, refresh_token)
        self._access_tokens[account_id] = access_tok
        expires_at = time.time() + expires_in
        self._token_expirations[account_id] = expires_at

        await self.repo.upsert_account(
            account_id=account_id,
            email_safe=safe_email,
            display_name=name,
            project_id=project_id,
            tier=tier,
            status="active",
            enabled=True,
        )
        await self.repo.update_token_metadata(account_id, int(expires_at))
        await self.repo.upsert_channel_bindings(account_id, oauth_verified=True)

        return {
            "account_id": account_id,
            "email_safe": safe_email,
            "display_name": name,
            "project_id": project_id,
            "tier": tier,
        }

    async def get_access_token(self, account_id: str) -> str:
        """Get valid access token, auto-refreshing if expired or within 5 min of expiry."""
        now = time.time()
        cached_tok = self._access_tokens.get(account_id)
        expiry = self._token_expirations.get(account_id, 0.0)

        if cached_tok and now < (expiry - 300):
            return cached_tok

        # Bug #15: Use a per-account lock so concurrent requests don't all trigger
        # a refresh simultaneously, wasting refresh tokens and causing races.
        if account_id not in self._refresh_locks:
            self._refresh_locks[account_id] = asyncio.Lock()
        async with self._refresh_locks[account_id]:
            # Re-check after acquiring lock in case another coroutine already refreshed
            cached_tok = self._access_tokens.get(account_id)
            expiry = self._token_expirations.get(account_id, 0.0)
            if cached_tok and time.time() < (expiry - 300):
                return cached_tok
            return await self.refresh_account_token(account_id)

    async def refresh_account_token(self, account_id: str) -> str:
        """Force refresh of OAuth access token."""
        refresh_tok = self.vault.get_token(account_id)
        if not refresh_tok:
            raise RuntimeError(f"No refresh token found for account {account_id}")

        cid = self.config.oauth.client_id
        csec = self.config.oauth.client_secret

        try:
            tok_resp = await refresh_access_token(refresh_tok, cid, csec)
        except Exception as e:
            # Bug #16: httpx wraps the response body inside e.response.text, not
            # str(e). Check both to reliably detect invalid_grant revocations.
            err_text = str(e).lower()
            try:
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                    err_text = (e.response.text or "").lower()
            except Exception:
                pass
            if "invalid_grant" in err_text:
                await self.repo.update_account_status(
                    account_id=account_id,
                    status="invalid_grant",
                    enabled=False,
                )
            raise

        new_access = tok_resp["access_token"]
        # Rotate refresh token if provided
        if "refresh_token" in tok_resp and tok_resp["refresh_token"] != refresh_tok:
            self.vault.store_token(account_id, tok_resp["refresh_token"])

        expires_in = tok_resp.get("expires_in", 3600)
        expires_at = time.time() + expires_in
        self._access_tokens[account_id] = new_access
        self._token_expirations[account_id] = expires_at

        await self.repo.update_token_metadata(account_id, int(expires_at))

        # Attempt to retrieve live userinfo and update profile with unmasked full email
        try:
            uinfo = await fetch_userinfo(new_access)
            if uinfo.get("email"):
                await self.repo.update_account_profile(
                    account_id=account_id,
                    email_safe=uinfo["email"],
                    display_name=uinfo.get("name"),
                )
        except Exception:
            pass

        return new_access

    async def remove_account(self, account_id: str) -> None:
        """Delete account from vault and database."""
        self.vault.remove_token(account_id)
        self._access_tokens.pop(account_id, None)
        self._token_expirations.pop(account_id, None)
        await self.repo.delete_account(account_id)

    async def enable_account(self, account_id: str, enabled: bool) -> None:
        """Enable or disable account."""
        await self.repo.set_account_enabled(account_id, enabled)

    async def list_accounts_summary(self) -> List[Dict[str, Any]]:
        """List accounts with safely sanitized public representation and channel completion status."""
        accounts = await self.repo.list_accounts()
        bindings = await self.repo.get_all_channel_bindings()
        summaries = []
        for acc in accounts:
            acc_id = acc["id"]
            has_tok = self.vault.has_token(acc_id)
            email_val = acc.get("email_safe", "")

            b = bindings.get(acc_id, {})
            # A channel is verified if recorded in bindings or present in vault
            oauth_v = bool(b.get("oauth_verified", 1 if has_tok else 0))
            cookies_v = bool(b.get("cookies_verified", 1 if self.vault.has_token(f"{acc_id}:cookies") or acc.get("tier") == "gweb" else 0))
            vertex_v = bool(b.get("vertex_verified", 1 if self.vault.has_token(f"{acc_id}:vertex") or acc.get("tier") == "studio" else 0))

            completed = (1 if oauth_v else 0) + (1 if cookies_v else 0) + (1 if vertex_v else 0)
            is_complete = completed >= 3

            summaries.append({
                "id": acc_id,
                "email": email_val,
                "email_safe": email_val,
                "label": email_val or acc.get("display_name", ""),
                "display_name": acc.get("display_name", ""),
                "project_id": acc.get("project_id", ""),
                "tier": acc.get("tier", "unknown"),
                "status": acc.get("status", "active"),
                "enabled": bool(acc.get("enabled", 1)),
                "has_credentials": has_tok,
                "total_requests": acc.get("total_requests", 0),
                "total_tokens": acc.get("total_tokens", 0),
                "last_used_at": acc.get("last_used_at"),
                "oauth_verified": oauth_v,
                "cookies_verified": cookies_v,
                "vertex_verified": vertex_v,
                "completed_methods": completed,
                "is_setup_complete": is_complete,
            })
        return summaries

    async def link_account_cookies(
        self,
        account_id: str,
        cookies: Dict[str, str],
        snlm0e: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Link validated Gemini Web cookies to an existing account."""
        stored = json.dumps({"cookies": cookies, "snlm0e": snlm0e or ""})
        self.vault.store_token(f"{account_id}:cookies", stored)
        return await self.repo.upsert_channel_bindings(account_id, cookies_verified=True)

    async def link_account_vertex_key(
        self,
        account_id: str,
        api_key: str,
    ) -> Dict[str, Any]:
        """Link validated Vertex / AI Studio API key to an existing account."""
        clean_key = api_key.strip()
        self.vault.store_token(f"{account_id}:vertex", clean_key)
        return await self.repo.upsert_channel_bindings(account_id, vertex_verified=True)

    async def add_aistudio_account(
        self,
        api_key: str,
        label: str = "Google AI Studio",
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enroll Google AI Studio API key."""
        from agw.aistudio.client import AIStudioClient
        client = AIStudioClient()
        valid, msg, models = await client.validate_key(api_key)
        if not valid:
            raise ValueError(f"AI Studio API key validation failed: {msg}")

        clean_key = api_key.strip()
        account_id = f"acc-studio-{hashlib.sha256(clean_key.encode()).hexdigest()[:8]}"
        name = display_name or label
        safe_email = f"studio-{clean_key[:6]}@aistudio.google"

        self.vault.store_token(account_id, clean_key)
        await self.repo.upsert_account(
            account_id=account_id,
            email_safe=safe_email,
            display_name=name,
            project_id="generativelanguage",
            tier="studio",
            status="active",
            enabled=True,
        )
        return {
            "account_id": account_id,
            "email_safe": safe_email,
            "display_name": name,
            "tier": "studio",
            "models": models,
        }

    async def add_gemini_web_account(
        self,
        cookies: Dict[str, str],
        label: str = "Gemini Web",
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enroll consumer Gemini Web Session."""
        import json
        from agw.geminiweb.client import GeminiWebClient
        client = GeminiWebClient()
        valid, msg, snlm0e = await client.validate_session(cookies)
        if not valid:
            if not ("__Secure-1PSID" in cookies and len(cookies["__Secure-1PSID"]) >= 15):
                raise ValueError(f"Gemini Web session validation failed: {msg}")
            snlm0e = ""

        psid = cookies.get("__Secure-1PSID", "")
        account_id = f"acc-web-{hashlib.sha256(psid.encode()).hexdigest()[:8]}"
        name = display_name or label
        safe_email = f"web-{psid[:6]}@gemini.web"

        stored_data = json.dumps({"cookies": cookies, "snlm0e": snlm0e})
        self.vault.store_token(account_id, stored_data)
        await self.repo.upsert_account(
            account_id=account_id,
            email_safe=safe_email,
            display_name=name,
            project_id="gemini-web",
            tier="gweb",
            status="active",
            enabled=True,
        )
        return {
            "account_id": account_id,
            "email_safe": safe_email,
            "display_name": name,
            "tier": "gweb",
        }

    async def add_handy_account(
        self,
        cookies: Dict[str, str],
        label: str = "Handy Creative Suite",
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enroll Handy Creative Suite session using Google session cookies."""
        import json
        from agw.handy.client import HandyClient
        client = HandyClient()
        valid, msg = await client.validate_session(cookies)
        if not valid:
            raise ValueError(f"Handy session validation failed: {msg}")

        psid = cookies.get("__Secure-1PSID", "")
        account_id = f"acc-handy-{hashlib.sha256(psid.encode()).hexdigest()[:8]}"
        name = display_name or label
        safe_email = f"handy-{psid[:6]}@labs.google"

        stored_data = json.dumps({"cookies": cookies})
        self.vault.store_token(account_id, stored_data)
        await self.repo.upsert_account(
            account_id=account_id,
            email_safe=safe_email,
            display_name=name,
            project_id="google-labs-handy",
            tier="handy",
            status="active",
            enabled=True,
        )
        return {
            "account_id": account_id,
            "email_safe": safe_email,
            "display_name": name,
            "tier": "handy",
        }

    async def sync_all_account_tiers(self) -> Dict[str, str]:
        """Audit and update all connected Google OAuth accounts with their true Google subscription tier."""
        accounts = await self.repo.list_accounts()
        results = {}
        for acc in accounts:
            acc_id = acc["id"]
            current_tier = acc.get("tier", "unknown")
            # Only audit OAuth accounts (not studio, gweb, handy synthetic accounts)
            if acc_id.startswith("acc-studio") or acc_id.startswith("acc-web") or acc_id.startswith("acc-handy") or current_tier in ("studio", "gweb", "handy"):
                results[acc_id] = current_tier
                continue
            try:
                tok = await self.get_access_token(acc_id)
                project_id, real_tier = await self.client.load_code_assist(tok, allow_onboard=False)
                if real_tier != current_tier:
                    logger.info(f"Correcting tier for {acc.get('email_safe')} from '{current_tier}' to '{real_tier}'")
                    await self.repo.update_account_tier(acc_id, real_tier)
                results[acc_id] = real_tier
            except Exception as e:
                logger.warning(f"Could not re-verify tier for {acc.get('email_safe')}: {e}")
                results[acc_id] = current_tier
        return results

    def get_token_raw(self, account_id: str) -> Optional[str]:
        """Get the raw credential string from vault for this account."""
        return self.vault.get_token(account_id)

