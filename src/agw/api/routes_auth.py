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
                <meta charset="UTF-8">
                <title>Authentication Successful — Secured Gateway</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Outfit', 'Segoe UI', Roboto, sans-serif;
                        background: #090d16;
                        color: #f8fafc;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }}
                    .card {{
                        background: #111726;
                        border: 1px solid rgba(56, 189, 248, 0.3);
                        padding: 2.5rem 2rem;
                        border-radius: 16px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.6);
                        text-align: center;
                        max-width: 440px;
                        animation: pop 0.3s ease-out;
                    }}
                    @keyframes pop {{
                        0% {{ opacity: 0; transform: scale(0.95); }}
                        100% {{ opacity: 1; transform: scale(1); }}
                    }}
                    .icon {{
                        width: 54px;
                        height: 54px;
                        border-radius: 50%;
                        background: rgba(16, 185, 129, 0.15);
                        border: 1px solid rgba(16, 185, 129, 0.4);
                        color: #10b981;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 26px;
                        margin-bottom: 1rem;
                    }}
                    h2 {{ color: #38bdf8; margin: 0 0 0.5rem 0; font-size: 1.4rem; }}
                    p {{ color: #94a3b8; line-height: 1.5; font-size: 0.92rem; margin: 0.5rem 0; }}
                    .pill {{
                        background: rgba(56, 189, 248, 0.12);
                        color: #38bdf8;
                        border: 1px solid rgba(56, 189, 248, 0.25);
                        padding: 4px 12px;
                        border-radius: 6px;
                        font-size: 0.82rem;
                        display: inline-block;
                        margin-top: 0.5rem;
                        font-weight: 500;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon">✓</div>
                    <h2>Setup Completed Automatically!</h2>
                    <p>Account <strong>{acc_info['email_safe']}</strong> has been enrolled and configured.</p>
                    <div class="pill">Claude 5 & Gemini 3 Models Activated</div>
                    <p style="margin-top: 1.25rem; font-size: 0.8rem; color: #64748b;">
                        Closing window and returning to dashboard...
                    </p>
                </div>
                <script>
                    const accountData = {{
                        account_id: "{acc_info['account_id']}",
                        email_safe: "{acc_info['email_safe']}",
                        display_name: "{acc_info['display_name']}",
                        tier: "{acc_info['tier']}"
                    }};
                    if (window.opener) {{
                        try {{
                            window.opener.postMessage({{
                                type: 'AGW_OAUTH_SUCCESS',
                                account: accountData
                            }}, '*');
                        }} catch(e) {{}}
                    }}
                    try {{
                        localStorage.setItem('agw_last_oauth_event', JSON.stringify({{
                            timestamp: Date.now(),
                            account: accountData
                        }}));
                    }} catch(e) {{}}
                    setTimeout(() => {{
                        try {{ window.close(); }} catch(e) {{}}
                    }}, 1000);
                </script>
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
