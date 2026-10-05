"""Recalculating onboarding/readiness state."""
from __future__ import annotations

from typing import Any


class SetupStateService:
    def __init__(self, config: Any, repo: Any):
        self.config = config
        self.repo = repo

    async def status(self) -> dict[str, Any]:
        accounts = await self.repo.list_accounts()
        identity_ready = bool(self.config.security.gateway_api_key and self.config.security.admin_api_key)
        active_accounts = [a for a in accounts if a.get("enabled", 1)]
        if not identity_ready:
            state = "not_initialized"
        elif not active_accounts:
            state = "account_required"
        else:
            state = "ready"
        return {
            "state": state,
            "identity_ready": identity_ready,
            "accounts_connected": len(accounts),
            "active_accounts": len(active_accounts),
            "integrations_pending": False,
        }
