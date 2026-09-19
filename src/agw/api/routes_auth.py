"""OAuth2 PKCE authorization routes and callbacks."""

import secrets
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agw.accounts.manager import AccountManager
from agw.auth.oauth import build_auth_url, generate_pkce
from agw.config import AppConfig

# Temporary in-memory pending PKCE sessions: state -> (verifier, redirect_uri)
_PENDING_SESSIONS: Dict[str, Dict[str, str]] = {}


class ManualLoginRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: Optional[str] = None
    display_name: Optional[str] = None


def create_auth_router(config: AppConfig, account_mgr: AccountManager) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["OAuth"])

    @router.post("/login")
    async def start_login(request: Request):
        """Initiate OAuth2 PKCE login flow and return auth URL."""
        state = secrets.token_urlsafe(16)
        verifier, challenge = generate_pkce()

        # Compute redirect URI
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

    @router.get("/callback", response_class=HTMLResponse)
    async def oauth_callback(code: str = Query(...), state: str = Query(...)):
        """Handle Google browser redirect callback."""
        session = _PENDING_SESSIONS.pop(state, None)
        if not session:
            return HTMLResponse(
                content="<h2>Authentication Error</h2><p>Session expired or invalid state. Please try logging in again.</p>",
                status_code=400,
            )

        verifier = session["verifier"]
        redirect_uri = session["redirect_uri"]

        try:
            acc_info = await account_mgr.add_account_from_code(
                code=code,
                code_verifier=verifier,
                redirect_uri=redirect_uri,
            )
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Successful</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #1e293b; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); text-align: center; max-width: 420px; }}
                    h2 {{ color: #38bdf8; margin-top: 0; }}
                    p {{ color: #94a3b8; line-height: 1.5; }}
                    .badge {{ background: #0284c7; color: white; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>✓ Antigravity Connected!</h2>
                    <p>Account <strong>{acc_info['email_safe']}</strong> has been registered successfully.</p>
                    <p>Project: <code>{acc_info['project_id']}</code> | Tier: <span class="badge">{acc_info['tier']}</span></p>
                    <p>You may now close this browser tab and return to Hermes Agent.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html, status_code=200)
        except Exception as e:
            return HTMLResponse(
                content=f"<h2>Authentication Failed</h2><p>{str(e)}</p>",
                status_code=500,
            )

    @router.post("/manual")
    async def manual_exchange(req: ManualLoginRequest, request: Request):
        """Manually exchange authorization code and code_verifier (headless/remote mode)."""
        base_url = config.server.public_base_url or str(request.base_url).rstrip("/")
        redirect_uri = req.redirect_uri or f"{base_url}/auth/callback"

        try:
            acc_info = await account_mgr.add_account_from_code(
                code=req.code,
                code_verifier=req.code_verifier,
                redirect_uri=redirect_uri,
                display_name=req.display_name,
            )
            return {"status": "success", "account": acc_info}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return router
