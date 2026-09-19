"""Administrative endpoints for managing accounts, health, and quotas."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agw.accounts.manager import AccountManager
from agw.api.middleware import get_admin_key_auth
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository
from agw.quota.monitor import QuotaMonitor
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker

logger = logging.getLogger("agw.admin")


class AddAccountRequest(BaseModel):
    refresh_token: str
    label: str
    display_name: Optional[str] = None


def create_admin_router(
    config: AppConfig,
    repo: DatabaseRepository,
    account_mgr: AccountManager,
    quota_monitor: QuotaMonitor,
    cooldown_mgr: CooldownManager,
    health_tracker: AccountHealthTracker,
    dashboard_html_content: str,
) -> APIRouter:
    verify_admin = get_admin_key_auth(config)
    router = APIRouter(prefix="/admin", tags=["Admin API"])

    @router.get("/dashboard", response_class=HTMLResponse)
    async def get_dashboard():
        """Serve embedded web dashboard UI."""
        return HTMLResponse(content=dashboard_html_content)

    @router.get("/accounts", dependencies=[Depends(verify_admin)])
    async def list_accounts():
        """List all accounts with status and statistics."""
        return await account_mgr.list_accounts_summary()

    @router.get("/accounts/{account_id}", dependencies=[Depends(verify_admin)])
    async def get_account(account_id: str):
        """Get single account details."""
        acc = await repo.get_account(account_id)
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        quotas = await repo.get_latest_quota(account_id)
        cooldown = await repo.get_active_cooldown(account_id, "all") or await repo.get_active_cooldown(account_id, "gemini")
        return {
            "account": acc,
            "quotas": quotas,
            "active_cooldown": cooldown,
            "health_score": health_tracker.get_health_score(account_id),
            "avg_latency_ms": health_tracker.get_avg_latency(account_id),
        }

    @router.post("/accounts", dependencies=[Depends(verify_admin)])
    async def add_account(req: AddAccountRequest):
        """Add account manually using an OAuth refresh token."""
        try:
            info = await account_mgr.add_account_from_refresh_token(
                refresh_token=req.refresh_token,
                label=req.label,
                display_name=req.display_name,
            )
            # Trigger immediate quota refresh
            await quota_monitor.refresh_account(info["account_id"])
            return {"status": "success", "account": info}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/accounts/{account_id}", dependencies=[Depends(verify_admin)])
    async def delete_account(account_id: str):
        """Delete account from registry and vault."""
        await account_mgr.remove_account(account_id)
        return {"status": "success", "deleted": account_id}

    @router.post("/accounts/{account_id}/enable", dependencies=[Depends(verify_admin)])
    async def enable_account(account_id: str):
        """Enable account."""
        await account_mgr.enable_account(account_id, True)
        return {"status": "success", "account_id": account_id, "enabled": True}

    @router.post("/accounts/{account_id}/disable", dependencies=[Depends(verify_admin)])
    async def disable_account(account_id: str):
        """Disable account."""
        await account_mgr.enable_account(account_id, False)
        return {"status": "success", "account_id": account_id, "enabled": False}

    @router.post("/accounts/{account_id}/refresh", dependencies=[Depends(verify_admin)])
    async def refresh_account_token(account_id: str):
        """Force immediate OAuth access token refresh."""
        try:
            await account_mgr.refresh_account_token(account_id)
            return {"status": "success", "refreshed": account_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/accounts/{account_id}/quota", dependencies=[Depends(verify_admin)])
    async def get_account_quota(account_id: str):
        """Get latest quota snapshot and optionally poll upstream."""
        snapshot = await quota_monitor.refresh_account(account_id)
        if not snapshot:
            quotas = await repo.get_latest_quota(account_id)
            return {"account_id": account_id, "quotas": quotas}
        return snapshot

    @router.get("/cooldowns", dependencies=[Depends(verify_admin)])
    async def list_cooldowns():
        """List all active cooldowns across all accounts."""
        return await repo.list_all_active_cooldowns()

    @router.post("/accounts/{account_id}/cooldown/clear", dependencies=[Depends(verify_admin)])
    async def clear_cooldown(account_id: str):
        """Clear active cooldown for an account."""
        await cooldown_mgr.clear(account_id)
        return {"status": "success", "cleared": account_id}

    @router.get("/health", dependencies=[Depends(verify_admin)])
    async def admin_health():
        """Comprehensive system and account health report."""
        accounts = await repo.list_accounts()
        cooldowns = await repo.list_all_active_cooldowns()
        
        acc_health = []
        for acc in accounts:
            aid = acc["id"]
            acc_health.append({
                "account_id": aid,
                "display_name": acc.get("display_name"),
                "status": acc.get("status"),
                "enabled": bool(acc.get("enabled", 1)),
                "health_score": health_tracker.get_health_score(aid),
                "avg_latency_ms": health_tracker.get_avg_latency(aid),
                "total_requests": acc.get("total_requests", 0),
            })

        return {
            "status": "healthy",
            "active_accounts": len([a for a in accounts if a.get("enabled", 1)]),
            "total_accounts": len(accounts),
            "active_cooldowns_count": len(cooldowns),
            "accounts": acc_health,
        }

    @router.get("/usage", dependencies=[Depends(verify_admin)])
    async def admin_usage():
        """Aggregate usage analytics."""
        return await repo.get_usage_summary()

    return router
