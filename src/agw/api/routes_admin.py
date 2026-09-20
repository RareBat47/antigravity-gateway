"""Administrative endpoints for managing accounts, health, and quotas."""

import logging
import secrets
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agw.accounts.manager import AccountManager
from agw.api.middleware import get_admin_key_auth
from agw.auth.oauth import build_auth_url, generate_pkce
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
        from agw.dashboard import get_dashboard_html
        return HTMLResponse(
            content=get_dashboard_html(),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @router.get("/accounts", dependencies=[Depends(verify_admin)])
    async def list_accounts():
        """List all accounts with status, live quota, and window usage statistics."""
        summaries = await account_mgr.list_accounts_summary()
        for s in summaries:
            aid = s["id"]
            s["health_score"] = round(health_tracker.get_health_score(aid), 1)
            s["active_cooldowns"] = await repo.get_account_cooldowns(aid)
            quotas = await repo.get_latest_quota(aid)
            s["quotas"] = quotas

            # Enrich from quota_monitor in-memory snapshot if present, else from DB
            snap = getattr(quota_monitor, "_latest_snapshots", {}).get(aid)
            if snap:
                s["gemini_fraction"] = snap.gemini_average_fraction
                s["claude_fraction"] = snap.claude_average_fraction
                s["gemini_pct"] = int(round(snap.gemini_average_fraction * 100)) if snap.gemini_average_fraction is not None else None
                s["claude_pct"] = int(round(snap.claude_average_fraction * 100)) if snap.claude_average_fraction is not None else None

                g_resets = [m.reset_time for m in snap.models.values() if m.model_family == "gemini" and m.reset_time]
                c_resets = [m.reset_time for m in snap.models.values() if m.model_family == "claude" and m.reset_time]
                s["gemini_reset_time"] = sorted(g_resets)[0] if g_resets else None
                s["claude_reset_time"] = sorted(c_resets)[0] if c_resets else None

                s["model_quotas"] = {
                    mid: {
                        "model_id": m.model_id,
                        "model_family": m.model_family,
                        "remaining_fraction": m.remaining_fraction,
                        "percentage": m.percentage,
                        "reset_time": m.reset_time,
                    }
                    for mid, m in snap.models.items()
                }
            else:
                gemini_q = [q for q in quotas if q.get("model_family") == "gemini" and q.get("remaining_fraction") is not None]
                claude_q = [q for q in quotas if q.get("model_family") == "claude" and q.get("remaining_fraction") is not None]

                g_avg = sum(q["remaining_fraction"] for q in gemini_q) / len(gemini_q) if gemini_q else None
                c_avg = sum(q["remaining_fraction"] for q in claude_q) / len(claude_q) if claude_q else None
                s["gemini_fraction"] = g_avg
                s["claude_fraction"] = c_avg
                s["gemini_pct"] = int(round(g_avg * 100)) if g_avg is not None else None
                s["claude_pct"] = int(round(c_avg * 100)) if c_avg is not None else None

                g_resets = [q["reset_time"] for q in gemini_q if q.get("reset_time")]
                c_resets = [q["reset_time"] for q in claude_q if q.get("reset_time")]
                s["gemini_reset_time"] = sorted(g_resets)[0] if g_resets else None
                s["claude_reset_time"] = sorted(c_resets)[0] if c_resets else None

                s["model_quotas"] = {
                    q["model_id"]: {
                        "model_id": q["model_id"],
                        "model_family": q.get("model_family"),
                        "remaining_fraction": q.get("remaining_fraction"),
                        "percentage": int(round(q["remaining_fraction"] * 100)) if q.get("remaining_fraction") is not None else None,
                        "reset_time": q.get("reset_time"),
                    }
                    for q in quotas
                }

            s["window_5h"] = await repo.get_account_window_usage(aid, hours=5)
            s["window_7d"] = await repo.get_account_window_usage(aid, days=7)
        return summaries

    @router.get("/accounts/{account_id}", dependencies=[Depends(verify_admin)])
    async def get_account(account_id: str):
        """Get single account details."""
        acc = await repo.get_account(account_id)
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        quotas = await repo.get_latest_quota(account_id)
        active_cooldowns = await repo.get_account_cooldowns(account_id)
        cooldown = active_cooldowns[0] if active_cooldowns else None
        window_5h = await repo.get_account_window_usage(account_id, hours=5)
        window_7d = await repo.get_account_window_usage(account_id, days=7)
        return {
            "account": acc,
            "quotas": quotas,
            "active_cooldown": cooldown,
            "active_cooldowns": active_cooldowns,
            "health_score": health_tracker.get_health_score(account_id),
            "avg_latency_ms": health_tracker.get_avg_latency(account_id),
            "window_5h": window_5h,
            "window_7d": window_7d,
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
        """Force immediate OAuth access token and quota refresh."""
        try:
            await account_mgr.refresh_account_token(account_id)
            await quota_monitor.refresh_account(account_id)
            return {"status": "success", "refreshed": account_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/accounts/{account_id}/reauth", dependencies=[Depends(verify_admin)])
    async def reauth_account(account_id: str, request: Request):
        """Trigger reauthorization flow for an account."""
        acc = await repo.get_account(account_id)
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")

        await cooldown_mgr.clear(account_id)
        state = secrets.token_urlsafe(16)
        verifier, challenge = generate_pkce()
        base_url = config.server.public_base_url or str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/auth/callback"

        auth_url = build_auth_url(
            client_id=config.oauth.client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
        )

        return {
            "status": "pending_reauth",
            "account_id": account_id,
            "auth_url": auth_url,
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        }

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

    @router.get("/api-keys", dependencies=[Depends(verify_admin)])
    async def list_api_keys():
        """List configured API keys and their role permissions."""
        keys = []
        if config.security.gateway_api_key:
            keys.append({
                "key": config.security.gateway_api_key,
                "name": "master-default",
                "description": "Master Gateway Key (Unrestricted)",
                "allowed_families": ["all"],
                "allowed_models": [],
            })
        for k in config.security.api_keys:
            keys.append(k.model_dump())
        return keys

    return router
