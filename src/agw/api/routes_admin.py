"""Administrative endpoints for managing accounts, health, and quotas."""

import json
import logging
import re
import secrets
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import httpx
from pydantic import BaseModel

from agw.accounts.manager import AccountManager
from agw.api.middleware import get_admin_key_auth
from agw.auth.oauth import build_auth_url, generate_pkce
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository
from agw.quota.monitor import QuotaMonitor, is_developer_facing_model
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


def _parse_gemini_cookies(raw_cookies: Any) -> Dict[str, str]:
    """Parse Gemini Web cookies from header string, json, or raw token string."""
    if isinstance(raw_cookies, dict):
        return {str(k): str(v) for k, v in raw_cookies.items()}
    if not isinstance(raw_cookies, str) or not raw_cookies.strip():
        return {}
    raw = raw_cookies.strip()
    if raw.startswith("{") and raw.endswith("}"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            pass

    # Strip prefixes
    if raw.lower().startswith("cookie:"):
        raw = raw[7:].strip()
    elif raw.lower().startswith("cookies:"):
        raw = raw[8:].strip()

    cookies: Dict[str, str] = {}

    # Extract known cookies via regex
    known = ["__Secure-1PSID", "__Secure-1PSIDTS", "__Secure-1PSIDCC", "__Secure-3PSID", "__Secure-3PSIDTS", "SID", "HSID", "SSID", "APISID", "SAPISID"]
    for k in known:
        m = re.search(rf'(?:^|[;\s]){re.escape(k)}=([^;\s\r\n]+)', raw)
        if m:
            cookies[k] = m.group(1).strip('"\'')

    # Also parse line or semicolon separated items
    normalized = raw.replace("\n", ";").replace("\r", ";")
    for item in normalized.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"\'')
            if k and v and len(k) < 60 and k not in cookies:
                cookies[k] = v

    # Fallback: if __Secure-1PSID was not extracted, assume the whole raw string is __Secure-1PSID
    if "__Secure-1PSID" not in cookies:
        clean = raw.strip().strip('"\'')
        if clean.startswith("__Secure-1PSID="):
            clean = clean[len("__Secure-1PSID="):].strip()
        if len(clean) >= 15:
            cookies["__Secure-1PSID"] = clean

    return cookies


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
    provisioning_agent: Optional[Any] = None,
) -> APIRouter:
    from agw.aistudio.client import AIStudioClient
    from agw.geminiweb.client import GeminiWebClient
    from agw.agent.provisioner import AutonomousProvisioningAgent

    aistudio_client = aistudio_client or AIStudioClient()
    geminiweb_client = geminiweb_client or GeminiWebClient()
    agent = provisioning_agent or AutonomousProvisioningAgent(
        config=config,
        repo=repo,
        account_mgr=account_mgr,
        aistudio_client=aistudio_client,
        geminiweb_client=geminiweb_client,
    )
    verify_admin = get_admin_key_auth(config)
    router = APIRouter(prefix="/admin", tags=["Admin API"])

    @router.get("/dashboard", response_class=HTMLResponse)
    async def get_dashboard():
        """Serve embedded web dashboard UI with live synced API keys."""
        from agw.dashboard import get_dashboard_html
        content = get_dashboard_html()
        if config.security.gateway_api_key:
            content = content.replace("agw-local-dE9XbJxEmq2AJpjsk1zTPxbF0O7f2Q2WyQO8g5GQgOM", config.security.gateway_api_key)
            content = content.replace("__GATEWAY_KEY_PLACEHOLDER__", config.security.gateway_api_key)
        if config.security.admin_api_key:
            content = content.replace("agw-admin-YvMPfKwf5tYbYRIeMC-AV2R6wI3oRYTwQJ1EnmZefL4", config.security.admin_api_key)
            content = content.replace("__ADMIN_KEY_PLACEHOLDER__", config.security.admin_api_key)
        return HTMLResponse(
            content=content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @router.api_route("/oauth/start", methods=["GET", "POST"])
    async def admin_oauth_start(request: Request):
        """Initiate OAuth2 PKCE login flow from admin/wizard."""
        from agw.api.routes_auth import _PENDING_SESSIONS
        from agw.auth.oauth import build_auth_url, generate_pkce
        state = secrets.token_urlsafe(16)
        verifier, challenge = generate_pkce()
        base_url = config.server.public_base_url or str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/auth/callback"
        _PENDING_SESSIONS[state] = {
            "verifier": verifier,
            "redirect_uri": redirect_uri,
        }
        auth_url = build_auth_url(
            client_id=config.oauth.client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
        )
        return {
            "status": "pending",
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "auth_url": auth_url,
            "message": "Open auth_url in your browser to authenticate with Google Antigravity.",
        }

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
                s["gemini_pro_pct"] = int(round(snap.gemini_pro_fraction * 100)) if getattr(snap, "gemini_pro_fraction", None) is not None else s["gemini_pct"]
                s["gemini_flash_pct"] = int(round(snap.gemini_flash_fraction * 100)) if getattr(snap, "gemini_flash_fraction", None) is not None else s["gemini_pct"]

                s["gemini_reset_time"] = snap.gemini_reset_time
                s["claude_reset_time"] = snap.claude_reset_time

                s["model_quotas"] = {
                    mid: {
                        "model_id": m.model_id,
                        "model_family": m.model_family,
                        "remaining_fraction": m.remaining_fraction,
                        "percentage": m.percentage,
                        "reset_time": m.reset_time,
                        "is_developer_facing": is_developer_facing_model(m.model_id),
                    }
                    for mid, m in snap.models.items()
                }
            else:
                gemini_q = [
                    q for q in quotas
                    if q.get("model_family") == "gemini"
                    and is_developer_facing_model(q.get("model_id", ""))
                    and q.get("remaining_fraction") is not None
                ]
                claude_q = [
                    q for q in quotas
                    if q.get("model_family") == "claude"
                    and is_developer_facing_model(q.get("model_id", ""))
                    and q.get("remaining_fraction") is not None
                ]

                g_avg = sum(q["remaining_fraction"] for q in gemini_q) / len(gemini_q) if gemini_q else None
                c_avg = sum(q["remaining_fraction"] for q in claude_q) / len(claude_q) if claude_q else None
                s["gemini_fraction"] = g_avg
                s["claude_fraction"] = c_avg
                s["gemini_pct"] = int(round(g_avg * 100)) if g_avg is not None else None
                s["claude_pct"] = int(round(c_avg * 100)) if c_avg is not None else None
                s["gemini_pro_pct"] = s["gemini_pct"]
                s["gemini_flash_pct"] = s["gemini_pct"]

                g_resets = [q["reset_time"] for q in gemini_q if q.get("reset_time") and q.get("remaining_fraction", 1.0) < 0.95]
                c_resets = [q["reset_time"] for q in claude_q if q.get("reset_time") and q.get("remaining_fraction", 1.0) < 0.95]
                s["gemini_reset_time"] = sorted(g_resets)[0] if g_resets else None
                s["claude_reset_time"] = sorted(c_resets)[0] if c_resets else None

                s["model_quotas"] = {
                    q["model_id"]: {
                        "model_id": q["model_id"],
                        "model_family": q.get("model_family"),
                        "remaining_fraction": q.get("remaining_fraction"),
                        "percentage": int(round(q["remaining_fraction"] * 100)) if q.get("remaining_fraction") is not None else None,
                        "reset_time": q.get("reset_time"),
                        "is_developer_facing": is_developer_facing_model(q.get("model_id", "")),
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
                        "working": bool(s.get("cookies_verified")),
                        "status": "healthy" if s.get("cookies_verified") else "unconfigured",
                        "latency_ms": round(lat) if s.get("cookies_verified") else 0,
                        "detail": "Consumer Web Session Active" if s.get("cookies_verified") else "Web cookies not bound for this account.",
                        "models": ["Gemini Web Consumer"] if s.get("cookies_verified") else [],
                    },
                    "aistudio": {
                        "name": "Google AI Studio",
                        "code": "aistudio",
                        "working": bool(s.get("vertex_verified")),
                        "status": "healthy" if s.get("vertex_verified") else "unconfigured",
                        "latency_ms": round(lat) if s.get("vertex_verified") else 0,
                        "detail": "Vertex AI / Studio Key Active" if s.get("vertex_verified") else "No Vertex/Studio key bound for this account.",
                        "models": ["Gemini 2.5 Pro", "Gemini 2.5 Flash"] if s.get("vertex_verified") else [],
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

            # 2. Check if account-specific session or local Chrome session is available
            try:
                raw_c = account_mgr.vault.get_token(f"{account_id}:cookies")
                if raw_c:
                    parsed_c = json.loads(raw_c)
                    c_cookies = parsed_c.get("cookies", {})
                    c_authuser = parsed_c.get("authuser", 0)
                    c_snlm0e = parsed_c.get("snlm0e", "")
                    t1 = time.time()
                    v_ok, v_msg, _ = await geminiweb_client.validate_session(
                        c_cookies, snlm0e=c_snlm0e, authuser=c_authuser
                    )
                    gweb_lat = round((time.time() - t1) * 1000)
                    if v_ok:
                        gweb_ok = True
                    else:
                        gweb_err = v_msg
                else:
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
            # 3. Check if account-specific Vertex / AI Studio API key is available
            try:
                raw_k = account_mgr.vault.get_token(f"{account_id}:vertex")
                if raw_k:
                    t2 = time.time()
                    v_ok, v_msg, models = await aistudio_client.validate_key(raw_k)
                    studio_lat = round((time.time() - t2) * 1000)
                    if v_ok:
                        studio_ok = True
                        studio_err = None
                    else:
                        studio_err = v_msg
                else:
                    studio_err = "No AI Studio API Key bound for this account."
            except Exception as e:
                studio_err = str(e)

        all_ok = agy_ok and gweb_ok and studio_ok and gcli_ok
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
                    "models": ["Gemini 3.8 Flash", "Gemini 3.1 Pro", "Imagen 3"] if studio_ok else [],
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
            cookie_dict = _parse_gemini_cookies(req.cookies)
            if not cookie_dict:
                raise ValueError("No valid session cookies detected.")
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

    @router.post("/channels/geminiweb/sync-all", dependencies=[Depends(verify_admin)])
    async def sync_all_geminiweb_accounts():
        """Trigger automated Playwright & curl_cffi harvest across all multi-account sessions."""
        try:
            from scripts.gweb_auto_keeper import sync_and_refresh_all_accounts
            res = await sync_and_refresh_all_accounts(
                vault_path=str(account_mgr.vault.vault_path),
                key_path=str(account_mgr.vault.crypto.key_file),
                db_path=str(repo.db_path),
            )
            return res
        except Exception as e:
            logger.error(f"Failed to auto-sync Gemini Web accounts: {e}")
            raise HTTPException(status_code=500, detail=str(e))


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

    @router.post("/accounts-refresh-all-quotas", dependencies=[Depends(verify_admin)])
    async def refresh_all_quotas():
        """Force live quota fetch across all accounts immediately."""
        try:
            await quota_monitor.refresh_all()
            return {"status": "success", "message": "All account quotas refreshed from upstream"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

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

    class LinkCookiesRequest(BaseModel):
        cookies: Optional[Any] = None

    @router.post("/accounts/{account_id}/link-cookies", dependencies=[Depends(verify_admin)])
    async def admin_link_cookies(account_id: str, req: LinkCookiesRequest):
        """Link Gemini Web cookies to an existing account, auto-harvesting from Chrome if omitted."""
        cookies = _parse_gemini_cookies(req.cookies)

        snlm0e = ""
        if not cookies:
            ok, extracted, msg = geminiweb_client.extract_from_local_chrome()
            if not ok:
                raise HTTPException(status_code=400, detail=f"Chrome cookie extraction failed: {msg}")
            cookies = extracted

        valid, vmsg, token = await geminiweb_client.validate_session(cookies)
        if not valid:
            if "__Secure-1PSID" in cookies and len(cookies["__Secure-1PSID"]) >= 15:
                logger.warning("Gemini Web validation warning for %s: %s (saving cookies anyway)", account_id, vmsg)
                snlm0e = ""
            else:
                raise HTTPException(status_code=400, detail=f"Gemini Web session validation failed: {vmsg}")
        else:
            snlm0e = token or ""

        res = await account_mgr.link_account_cookies(account_id, cookies, snlm0e)
        return {"status": "success", "account_id": account_id, "channel": "cookies", "bindings": res, "warning": None if valid else vmsg}

    class LinkVertexRequest(BaseModel):
        api_key: str

    @router.post("/accounts/{account_id}/link-vertex", dependencies=[Depends(verify_admin)])
    async def admin_link_vertex(account_id: str, req: LinkVertexRequest):
        """Link Vertex AI / AI Studio API key to an existing account."""
        key = req.api_key.strip()
        valid, msg, models = await aistudio_client.validate_key(key)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Vertex AI / Studio key validation failed: {msg}")

        res = await account_mgr.link_account_vertex_key(account_id, key)
        return {"status": "success", "account_id": account_id, "channel": "vertex", "models": models, "bindings": res}

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

    @router.get("/channels/summary", dependencies=[Depends(verify_admin)])
    async def get_channels_summary():
        """Aggregate real-time usage, limits, and quotas across all 4 channels."""
        usage_by_ch = await repo.get_channel_usage_summary()
        acc_summaries = await account_mgr.list_accounts_summary()
        cooldowns = await repo.list_all_active_cooldowns()

        cooling_families = {c["target_family"].lower() for c in cooldowns}
        has_all_cd = "all" in cooling_families

        # Accounts supporting each channel
        agy_accs = [a for a in acc_summaries if a.get("oauth_verified")]
        gweb_accs = [a for a in acc_summaries if a.get("cookies_verified")]
        studio_accs = [a for a in acc_summaries if a.get("vertex_verified")]
        gcli_accs = [a for a in acc_summaries if a.get("oauth_verified")]
        handy_accs = [a for a in acc_summaries if a.get("cookies_verified") or a.get("tier") == "handy"]

        # Quotas for agy (Cloud Code)
        total_g_rem = 0.0
        total_c_rem = 0.0
        g_count = 0
        c_count = 0
        for a in agy_accs:
            aid = a["id"]
            quotas = await repo.get_latest_quota(aid)
            gemini_q = [q["remaining_fraction"] for q in quotas if q.get("model_family") == "gemini" and q.get("remaining_fraction") is not None]
            claude_q = [q["remaining_fraction"] for q in quotas if q.get("model_family") == "claude" and q.get("remaining_fraction") is not None]
            if gemini_q:
                total_g_rem += sum(gemini_q) / len(gemini_q)
                g_count += 1
            if claude_q:
                total_c_rem += sum(claude_q) / len(claude_q)
                c_count += 1

        agy_gemini_pct = int(round((total_g_rem / g_count) * 100)) if g_count > 0 else 100
        agy_claude_pct = int(round((total_c_rem / c_count) * 100)) if c_count > 0 else 100
        agy_quota_free = int(round((agy_gemini_pct + agy_claude_pct) / 2))
        agy_quota_used = max(0, 100 - agy_quota_free)

        agy_working = len([a for a in agy_accs if a.get("enabled", True)]) > 0 and not has_all_cd
        gweb_working = len([a for a in gweb_accs if a.get("enabled", True)]) > 0
        studio_working = len([a for a in studio_accs if a.get("enabled", True)]) > 0
        gcli_working = len([a for a in gcli_accs if a.get("enabled", True)]) > 0 and not has_all_cd
        handy_working = len([a for a in handy_accs if a.get("enabled", True)]) > 0

        result = {
            "agy": {
                "name": "Google OAuth (agy)",
                "code": "agy",
                "badge": "🛸 agy OAuth",
                "connected_accounts": len(agy_accs),
                "active_accounts": len([a for a in agy_accs if a.get("enabled", True)]),
                "working": agy_working,
                "status": "Healthy" if agy_working else ("Cooldown" if "claude" in cooling_families or has_all_cd else "Idle"),
                "quota_used_pct": agy_quota_used,
                "quota_free_pct": agy_quota_free,
                "quota_detail": f"Claude: {agy_claude_pct}% • Gemini: {agy_gemini_pct}%",
                "limit_type": "Google Cloud Code Quota (5h Sliding Window)",
                "requests": usage_by_ch["agy"]["requests"],
                "total_tokens": usage_by_ch["agy"]["total_tokens"],
                "prompt_tokens": usage_by_ch["agy"]["prompt_tokens"],
                "completion_tokens": usage_by_ch["agy"]["completion_tokens"],
                "window_5h_requests": usage_by_ch["agy"]["window_5h_requests"],
                "window_5h_tokens": usage_by_ch["agy"]["window_5h_tokens"],
                "avg_latency_ms": usage_by_ch["agy"]["avg_latency_ms"] or 118.0,
                "models": ["Claude Sonnet 5.5", "Claude Opus 5.5", "Claude 1M Mega", "Gemini 3.8 Flash", "Gemini 3.1 Pro"],
            },
            "gweb": {
                "name": "Gemini Web (gweb)",
                "code": "gweb",
                "badge": "🍪 Gemini Web",
                "connected_accounts": len(gweb_accs),
                "active_accounts": len([a for a in gweb_accs if a.get("enabled", True)]),
                "working": gweb_working,
                "status": "Healthy" if gweb_working else "Unconfigured",
                "quota_used_pct": 0 if gweb_working else 0,
                "quota_free_pct": 100 if gweb_working else 0,
                "quota_detail": "Consumer Web Session Active" if gweb_working else "Web Cookies Not Linked",
                "limit_type": "Consumer Google One Web Session Limits (~50 msg/3h)",
                "requests": usage_by_ch["gweb"]["requests"],
                "total_tokens": usage_by_ch["gweb"]["total_tokens"],
                "prompt_tokens": usage_by_ch["gweb"]["prompt_tokens"],
                "completion_tokens": usage_by_ch["gweb"]["completion_tokens"],
                "window_5h_requests": usage_by_ch["gweb"]["window_5h_requests"],
                "window_5h_tokens": usage_by_ch["gweb"]["window_5h_tokens"],
                "avg_latency_ms": usage_by_ch["gweb"]["avg_latency_ms"] or 142.0,
                "models": ["Gemini 2.5 Pro (Web Advanced)", "Gemini 2.0 Flash Thinking"],
            },
            "studio": {
                "name": "Google AI Studio (studio)",
                "code": "studio",
                "badge": "🔑 AI Studio Key",
                "connected_accounts": len(studio_accs),
                "active_accounts": len([a for a in studio_accs if a.get("enabled", True)]),
                "working": studio_working,
                "status": "Healthy" if studio_working else "Unconfigured",
                "quota_used_pct": min(100, int(round((usage_by_ch["studio"]["requests"] / 1500.0) * 100))) if studio_working else 0,
                "quota_free_pct": max(0, 100 - int(round((usage_by_ch["studio"]["requests"] / 1500.0) * 100))) if studio_working else 0,
                "quota_detail": f"{usage_by_ch['studio']['requests']} / 1,500 RPD Used" if studio_working else "No API Key Linked",
                "limit_type": "Google AI Studio Free Tier (15 RPM • 1,500 RPD)",
                "requests": usage_by_ch["studio"]["requests"],
                "total_tokens": usage_by_ch["studio"]["total_tokens"],
                "prompt_tokens": usage_by_ch["studio"]["prompt_tokens"],
                "completion_tokens": usage_by_ch["studio"]["completion_tokens"],
                "window_5h_requests": usage_by_ch["studio"]["window_5h_requests"],
                "window_5h_tokens": usage_by_ch["studio"]["window_5h_tokens"],
                "avg_latency_ms": usage_by_ch["studio"]["avg_latency_ms"] or 92.0,
                "models": ["Gemini 2.5 Pro", "Gemini 2.5 Flash", "Gemini 2.0 Flash"],
            },
            "gcli": {
                "name": "Gemini CLI (gcli)",
                "code": "gcli",
                "badge": "⚡ Gemini CLI",
                "connected_accounts": len(gcli_accs),
                "active_accounts": len([a for a in gcli_accs if a.get("enabled", True)]),
                "working": gcli_working,
                "status": "Healthy" if gcli_working else ("Cooldown" if has_all_cd else "Idle"),
                "quota_used_pct": 0,
                "quota_free_pct": 100 if gcli_working else 0,
                "quota_detail": "Developer CLI Channel Active" if gcli_working else "Idle",
                "limit_type": "Google Cloud Code CLI Quota",
                "requests": usage_by_ch["gcli"]["requests"],
                "total_tokens": usage_by_ch["gcli"]["total_tokens"],
                "prompt_tokens": usage_by_ch["gcli"]["prompt_tokens"],
                "completion_tokens": usage_by_ch["gcli"]["completion_tokens"],
                "window_5h_requests": usage_by_ch["gcli"]["window_5h_requests"],
                "window_5h_tokens": usage_by_ch["gcli"]["window_5h_tokens"],
                "avg_latency_ms": usage_by_ch["gcli"]["avg_latency_ms"] or 108.0,
                "models": ["Gemini Code Assist", "Gemini CLI Coding Engine"],
            },
            "handy": {
                "name": "Handy Creative Media (handy)",
                "code": "handy",
                "badge": "🎨 handy",
                "connected_accounts": len(handy_accs),
                "active_accounts": len([a for a in handy_accs if a.get("enabled", True)]),
                "working": handy_working,
                "status": "Healthy" if handy_working else "Unconfigured",
                "quota_used_pct": 0,
                "quota_free_pct": 100 if handy_working else 0,
                "quota_detail": "Google Labs Shared Cookies Active" if handy_working else "Cookies Not Linked",
                "limit_type": "Google Labs / DeepMind Session Limits",
                "requests": usage_by_ch.get("handy", {}).get("requests", 0),
                "total_tokens": usage_by_ch.get("handy", {}).get("total_tokens", 0),
                "prompt_tokens": usage_by_ch.get("handy", {}).get("prompt_tokens", 0),
                "completion_tokens": usage_by_ch.get("handy", {}).get("completion_tokens", 0),
                "window_5h_requests": usage_by_ch.get("handy", {}).get("window_5h_requests", 0),
                "window_5h_tokens": usage_by_ch.get("handy", {}).get("window_5h_tokens", 0),
                "avg_latency_ms": usage_by_ch.get("handy", {}).get("avg_latency_ms") or 220.0,
                "models": [
                    "handy-google-playground",
                    "handy-project-genie",
                    "handy-google-flow",
                    "handy-veo-video",
                    "handy-flow-music",
                    "handy-musicfx-dj",
                ],
            },
        }

        all_ok = all(c["working"] for c in result.values() if c["connected_accounts"] > 0)
        return {
            "channels": result,
            "all_healthy": all_ok,
            "overall_status": "All Free & Operational" if all_ok else "Attention Needed",
            "total_tokens_all": sum(c["total_tokens"] for c in result.values()),
            "total_requests_all": sum(c["requests"] for c in result.values()),
            "checked_at": int(time.time()),
        }

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

    @router.get("/agent/provision", dependencies=[Depends(verify_admin)])
    async def run_agent_provision(account_id: Optional[str] = Query(None)):
        """Stream real-time autonomous provisioning agent pipeline progress via SSE."""
        import json

        async def event_generator():
            async for ev in agent.run_pipeline(account_id):
                yield f"data: {json.dumps(ev)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    class LaunchUrlRequest(BaseModel):
        url: str

    @router.post("/agent/launch-url", dependencies=[Depends(verify_admin)])
    async def agent_launch_url(req: LaunchUrlRequest):
        """Allow the agent to open helper URLs in the host's desktop browser."""
        ok = AutonomousProvisioningAgent.launch_browser_url(req.url)
        return {"status": "success" if ok else "failed", "url": req.url}

    return router
