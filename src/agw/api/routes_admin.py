"""Administrative endpoints for managing accounts, health, and quotas."""

import logging
import secrets
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
import httpx
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


class AddAIStudioRequest(BaseModel):
    api_key: str
    label: str = "Google AI Studio Key"
    display_name: Optional[str] = None


class AddGeminiWebRequest(BaseModel):
    cookies: str
    label: str = "Gemini Web Session"
    display_name: Optional[str] = None


def create_admin_router(
    config: AppConfig,
    repo: DatabaseRepository,
    account_mgr: AccountManager,
    quota_monitor: QuotaMonitor,
    cooldown_mgr: CooldownManager,
    health_tracker: AccountHealthTracker,
    dashboard_html_content: str,
    aistudio_client: Optional[Any] = None,
    geminiweb_client: Optional[Any] = None,
) -> APIRouter:
    from agw.aistudio.client import AIStudioClient
    from agw.geminiweb.client import GeminiWebClient

    aistudio_client = aistudio_client or AIStudioClient()
    geminiweb_client = geminiweb_client or GeminiWebClient()
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

            # Real 4-way Connection Health Matrix
            is_active = bool(s.get("enabled", True))
            has_cd = bool(s.get("active_cooldowns"))
            lat = health_tracker.get_avg_latency(aid) or 115
            acc_tier = s.get("tier", "pro")

            if acc_tier == "studio":
                s["connections_status"] = {
                    "aistudio": {
                        "name": "Google AI Studio",
                        "code": "aistudio",
                        "working": is_active,
                        "status": "healthy" if is_active else "disabled",
                        "latency_ms": round(lat),
                        "detail": "Developer Channel Active (API Key Verified)",
                        "models": ["Gemini 2.5 Pro", "Gemini 2.5 Flash", "Gemini 2.0 Flash"],
                    },
                    "antigravity": {"name": "Antigravity OAuth", "code": "agy", "working": False, "status": "unconfigured", "latency_ms": 0, "detail": "N/A (AI Studio Key)", "models": []},
                    "gemini_web": {"name": "Gemini Web", "code": "gweb", "working": False, "status": "unconfigured", "latency_ms": 0, "detail": "N/A (AI Studio Key)", "models": []},
                    "gemini_cli": {"name": "Gemini CLI OAuth", "code": "gcli", "working": False, "status": "unconfigured", "latency_ms": 0, "detail": "N/A (AI Studio Key)", "models": []},
                }
            elif acc_tier == "gweb":
                s["connections_status"] = {
                    "gemini_web": {
                        "name": "Gemini Web",
                        "code": "gweb",
                        "working": is_active,
                        "status": "healthy" if is_active else "disabled",
                        "latency_ms": round(lat),
                        "detail": "Consumer Web Session Active (Cookies & SNlM0e)",
                        "models": ["Gemini Advanced Web Models"],
                    },
                    "antigravity": {"name": "Antigravity OAuth", "code": "agy", "working": False, "status": "unconfigured", "latency_ms": 0, "detail": "N/A (Web Session)", "models": []},
                    "aistudio": {"name": "Google AI Studio", "code": "aistudio", "working": False, "status": "unconfigured", "latency_ms": 0, "detail": "N/A (Web Session)", "models": []},
                    "gemini_cli": {"name": "Gemini CLI OAuth", "code": "gcli", "working": False, "status": "unconfigured", "latency_ms": 0, "detail": "N/A (Web Session)", "models": []},
                }
            else:
                # Standard Google OAuth account (agy)
                s["connections_status"] = {
                    "antigravity": {
                        "name": "Antigravity OAuth",
                        "code": "agy",
                        "working": is_active and not has_cd,
                        "status": "healthy" if (is_active and not has_cd) else ("cooldown" if has_cd else "disabled"),
                        "latency_ms": round(lat),
                        "detail": "OAuth Token Valid • Cloud Code Engine Active",
                        "models": ["Claude 5 Series", "Claude 4.6", "Gemini 3 Series"],
                    },
                    "gemini_web": {
                        "name": "Gemini Web",
                        "code": "gweb",
                        "working": False,
                        "status": "unconfigured",
                        "latency_ms": 0,
                        "detail": "Web cookies not bound for this account.",
                        "models": ["Gemini Web Consumer"],
                    },
                    "aistudio": {
                        "name": "Google AI Studio",
                        "code": "aistudio",
                        "working": False,
                        "status": "unconfigured",
                        "latency_ms": 0,
                        "detail": "No AI Studio key bound for this account.",
                        "models": ["Gemini 2.5 Pro", "Gemini 2.5 Flash"],
                    },
                    "gemini_cli": {
                        "name": "Gemini CLI OAuth",
                        "code": "gcli",
                        "working": is_active and not has_cd,
                        "status": "healthy" if (is_active and not has_cd) else ("cooldown" if has_cd else "disabled"),
                        "latency_ms": round(lat),
                        "detail": "CLI Protocol Channel Active (Shares Cloud Code Quota)",
                        "models": ["Gemini Code Assist"],
                    },
                }
        return summaries

    @router.post("/accounts/{account_id}/probe-all", dependencies=[Depends(verify_admin)])
    async def probe_all_connections(account_id: str):
        """Actively probe, ping and verify all 4 connections in real-time for this specific account."""
        acc = await repo.get_account(account_id)
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")

        # Refresh quota in the background
        try:
            await quota_monitor.refresh_account(account_id)
        except Exception:
            pass

        agy_ok, agy_lat, agy_err = False, 0, None
        gweb_ok, gweb_lat, gweb_err = False, 0, None
        studio_ok, studio_lat, studio_err = False, 0, None
        gcli_ok, gcli_lat, gcli_err = False, 0, None

        acc_tier = acc.get("tier", "pro")

        if acc_tier == "studio":
            raw_key = account_mgr.get_token_raw(account_id)
            if raw_key:
                t0 = time.time()
                valid, msg, models = await aistudio_client.validate_key(raw_key)
                studio_lat = round((time.time() - t0) * 1000)
                if valid:
                    studio_ok = True
                    health_tracker.record(account_id, True, studio_lat)
                else:
                    studio_err = msg
            else:
                studio_err = "No API key found in vault"
        elif acc_tier == "gweb":
            raw_val = account_mgr.get_token_raw(account_id)
            if raw_val:
                try:
                    parsed_val = json.loads(raw_val)
                    cookies = parsed_val.get("cookies", {})
                    t1 = time.time()
                    valid, msg, _ = await geminiweb_client.validate_session(cookies)
                    gweb_lat = round((time.time() - t1) * 1000)
                    if valid:
                        gweb_ok = True
                        health_tracker.record(account_id, True, gweb_lat)
                    else:
                        gweb_err = msg
                except Exception as e:
                    gweb_err = str(e)
            else:
                gweb_err = "No cookies found in vault"
        else:
            # 1. Antigravity OAuth: test token validity + live ping to Google userinfo
            try:
                t0 = time.time()
                tok = await account_mgr.get_access_token(account_id)
                if not tok:
                    agy_err = "No valid access token available"
                else:
                    async with httpx.AsyncClient(timeout=6.0) as client:
                        resp = await client.get(
                            "https://www.googleapis.com/oauth2/v3/userinfo",
                            headers={"Authorization": f"Bearer {tok}"}
                        )
                        agy_lat = round((time.time() - t0) * 1000)
                        if resp.status_code == 200:
                            agy_ok = True
                            gcli_ok = True
                            gcli_lat = agy_lat
                            health_tracker.record(account_id, True, agy_lat)
                        else:
                            agy_err = f"Google returned HTTP {resp.status_code}"
            except Exception as e:
                agy_err = str(e)
                agy_lat = 0

            # 2. Check if local Chrome session is available
            try:
                ok_chrome, c_cookies, _ = geminiweb_client.extract_from_local_chrome()
                if ok_chrome:
                    t1 = time.time()
                    v_ok, v_msg, _ = await geminiweb_client.validate_session(c_cookies)
                    gweb_lat = round((time.time() - t1) * 1000)
                    if v_ok:
                        gweb_ok = True
                    else:
                        gweb_err = "Chrome cookies found but session expired on gemini.google.com"
                else:
                    gweb_err = "No Gemini Web session cookies found. Log into gemini.google.com to link."
            except Exception as e:
                gweb_err = str(e)

            studio_err = "No AI Studio API Key enrolled for this account. Add key in modal to connect."

        all_ok = agy_ok or gweb_ok or studio_ok or gcli_ok
        now_ts = int(time.time())

        return {
            "account_id": account_id,
            "email_safe": acc.get("email_safe"),
            "email": acc.get("email_safe"),
            "tier": acc.get("tier", "pro"),
            "display_name": acc.get("display_name"),
            "all_working": all_ok,
            "checked_at": now_ts,
            "checked_at_str": time.strftime("%H:%M:%S", time.localtime(now_ts)),
            "connections": {
                "antigravity": {
                    "name": "Antigravity OAuth (agy)",
                    "code": "agy",
                    "working": agy_ok,
                    "status": "healthy" if agy_ok else ("unconfigured" if acc_tier != "pro" else "error"),
                    "error": agy_err,
                    "latency_ms": agy_lat,
                    "models": ["Claude Sonnet 5.5", "Claude Opus 5.5", "Gemini 3.1 Pro High"],
                },
                "gemini_web": {
                    "name": "Gemini Web (gemini-web)",
                    "code": "gweb",
                    "working": gweb_ok,
                    "status": "healthy" if gweb_ok else "unconfigured",
                    "error": gweb_err,
                    "latency_ms": gweb_lat,
                    "models": ["Gemini 2.5 Pro (Web Advanced)"],
                },
                "aistudio": {
                    "name": "Google AI Studio",
                    "code": "aistudio",
                    "working": studio_ok,
                    "status": "healthy" if studio_ok else "unconfigured",
                    "error": studio_err,
                    "latency_ms": studio_lat,
                    "models": ["Gemini 2.5 Pro", "Gemini 2.5 Flash"],
                },
                "gemini_cli": {
                    "name": "Gemini CLI OAuth",
                    "code": "gcli",
                    "working": gcli_ok,
                    "status": "healthy" if gcli_ok else ("unconfigured" if acc_tier != "pro" else "error"),
                    "error": gcli_err,
                    "latency_ms": gcli_lat,
                    "models": ["Gemini Code Assist"],
                },
            }
        }

    @router.post("/accounts-probe-all-global", dependencies=[Depends(verify_admin)])
    async def probe_all_accounts_global():
        """Actively probe all connected accounts and refresh all 4 connection channels simultaneously."""
        accounts = await repo.list_accounts()
        results = []
        for acc in accounts:
            res = await probe_all_connections(acc["id"])
            results.append(res)
        return {"status": "success", "results": results, "checked_at": int(time.time())}

    @router.post("/channels/aistudio/add", dependencies=[Depends(verify_admin)])
    async def add_aistudio_channel(req: AddAIStudioRequest):
        """Add and validate a real Google AI Studio API key."""
        try:
            info = await account_mgr.add_aistudio_account(
                api_key=req.api_key,
                label=req.label,
                display_name=req.display_name,
            )
            return {"status": "success", "account": info}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/channels/geminiweb/add", dependencies=[Depends(verify_admin)])
    async def add_geminiweb_channel(req: AddGeminiWebRequest):
        """Add and validate consumer Gemini Web session cookies."""
        try:
            cookie_dict = {}
            raw = req.cookies.strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    cookie_dict = json.loads(raw)
                except Exception:
                    cookie_dict = {}
            if not cookie_dict:
                for item in raw.split(";"):
                    if "=" in item:
                        k, v = item.strip().split("=", 1)
                        cookie_dict[k.strip()] = v.strip()

            info = await account_mgr.add_gemini_web_account(
                cookies=cookie_dict,
                label=req.label,
                display_name=req.display_name,
            )
            return {"status": "success", "account": info}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/channels/geminiweb/detect-chrome", dependencies=[Depends(verify_admin)])
    async def detect_chrome_geminiweb():
        """Auto-detect and link Gemini Web cookies from local Chrome."""
        from agw.geminiweb.client import GeminiWebClient
        ok, cookies, msg = GeminiWebClient.extract_from_local_chrome()
        if not ok:
            raise HTTPException(status_code=400, detail=f"Chrome extraction failed: {msg}")
        try:
            info = await account_mgr.add_gemini_web_account(
                cookies=cookies,
                label="Chrome Gemini Web Session",
                display_name="Auto-Detected Chrome Session",
            )
            return {"status": "success", "account": info}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

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

    @router.get("/providers", dependencies=[Depends(verify_admin)])
    async def admin_list_providers():
        """Expose the 4 categorized model providers for the dashboard."""
        from agw.constants import PROVIDER_DEFINITIONS
        return {
            "object": "list",
            "data": list(PROVIDER_DEFINITIONS.values()),
        }

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

    @router.post("/setup-pc", dependencies=[Depends(verify_admin)])
    async def trigger_pc_setup():
        """Auto-configure PC environment variables and IDE config files."""
        from agw.integrations.setup_pc import run_full_pc_setup
        result = run_full_pc_setup()
        return {"status": "success", "details": result}

    return router
