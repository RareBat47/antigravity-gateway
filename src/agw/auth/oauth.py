"""Google OAuth2 PKCE and token exchange workflows."""

import base64
import hashlib
import secrets
from typing import Any, Dict, Optional, Tuple
import httpx

from agw.constants import (
    OAUTH_AUTH_URL,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
    USERINFO_URL,
)


def generate_pkce() -> Tuple[str, str]:
    """Generate high-entropy code_verifier and S256 code_challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_auth_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scopes: Optional[list] = None,
) -> str:
    """Construct Google OAuth2 authorization URL with PKCE."""
    scope_str = " ".join(scopes or OAUTH_SCOPES)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope_str,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    from urllib.parse import urlencode
    query_str = urlencode(params)
    return f"{OAUTH_AUTH_URL}?{query_str}"


async def exchange_code(
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> Dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(OAUTH_TOKEN_URL, data=data)
        if resp.status_code != 200:
            err_body = resp.text
            raise RuntimeError(f"OAuth code exchange failed ({resp.status_code}): {err_body}")
        return resp.json()


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> Dict[str, Any]:
    """Exchange refresh token for a fresh access token."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(OAUTH_TOKEN_URL, data=data)
        if resp.status_code != 200:
            err_body = resp.text
            raise RuntimeError(f"OAuth refresh failed ({resp.status_code}): {err_body}")
        return resp.json()


async def fetch_userinfo(access_token: str) -> Dict[str, Any]:
    """Fetch user profile metadata (email, name) with access token."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(USERINFO_URL, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        return {}
