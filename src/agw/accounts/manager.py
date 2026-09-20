"""Account manager orchestrating credentials, persistence, and token lifecycle."""

import hashlib
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
        project_id, tier = await self.client.load_code_assist(access_tok)

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

        project_id, tier = await self.client.load_code_assist(access_tok)

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

        # Refresh token
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
            if "invalid_grant" in str(e).lower():
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
        """List accounts with safely sanitized public representation."""
        accounts = await self.repo.list_accounts()
        summaries = []
        for acc in accounts:
            acc_id = acc["id"]
            has_tok = self.vault.has_token(acc_id)
            summaries.append({
                "id": acc_id,
                "email_safe": acc.get("email_safe", ""),
                "display_name": acc.get("display_name", ""),
                "project_id": acc.get("project_id", ""),
                "tier": acc.get("tier", "unknown"),
                "status": acc.get("status", "active"),
                "enabled": bool(acc.get("enabled", 1)),
                "has_credentials": has_tok,
                "total_requests": acc.get("total_requests", 0),
                "total_tokens": acc.get("total_tokens", 0),
                "last_used_at": acc.get("last_used_at"),
            })
        return summaries
