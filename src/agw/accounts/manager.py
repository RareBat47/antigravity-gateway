"""Account manager orchestrating credentials, persistence, and token lifecycle."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from agw.auth.vault import CredentialVault
from agw.arena.provider import ArenaProvider
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
        cloudcode_client: ArenaProvider,
    ):
        self.config = config
        self.repo = repo
        self.vault = vault
        self.cloudcode_client = cloudcode_client
        self._refresh_locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, account_id: str) -> asyncio.Lock:
        if account_id not in self._refresh_locks:
            self._refresh_locks[account_id] = asyncio.Lock()
        return self._refresh_locks[account_id]

    async def add_account_from_credentials(
        self, display_name: str, credentials_json: str
    ) -> Dict[str, Any]:
        """Add an account using direct credentials (e.g., cookie string or JSON)."""
        credentials_str = credentials_json.strip()
        if credentials_str.startswith("{"):
            try:
                json.loads(credentials_str)
            except Exception:
                raise ValueError("credentials_json is invalid JSON")

        account_id = f"arena-{uuid.uuid4().hex[:8]}"
        email = f"{display_name.lower().replace(' ', '_')}@arena.ai"

        # Encrypt and store credential securely in vault
        self.vault.store_token(account_id, credentials_str)

        # Save to DB
        await self.repo.upsert_account(
            account_id=account_id,
            email_safe=email,
            display_name=display_name,
            project_id="arena_project",
            tier="arena",
            status="active",
            enabled=True,
        )
        logger.info(f"Added new Arena account: {display_name} ({account_id})")
        return {"account_id": account_id, "display_name": display_name, "email": email}

    async def get_access_token(self, account_id: str) -> str:
        """Get the stored credential string."""
        token = self.vault.get_token(account_id)
        if not token:
            raise RuntimeError(f"No credentials found for {account_id}")
        return token

    async def refresh_account_token(self, account_id: str) -> str:
        """Return the current token."""
        return await self.get_access_token(account_id)

    async def remove_account(self, account_id: str) -> None:
        await self.repo.delete_account(account_id)
        self.vault.remove_token(account_id)
        if account_id in self._refresh_locks:
            del self._refresh_locks[account_id]

    async def enable_account(self, account_id: str, enabled: bool) -> None:
        await self.repo.set_account_enabled(account_id, enabled)

    async def list_accounts_summary(self) -> List[Dict[str, Any]]:
        return await self.repo.list_accounts()
