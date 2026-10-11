"""Security middlewares: secret redaction in logs, authentication, and auditing."""

import logging
import re
import time
from typing import Callable, Optional
from fastapi import HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from agw.config import AppConfig

# Patterns that must never appear in logs
SENSITIVE_PATTERNS = [
    (re.compile(r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'("refresh_token":\s*")[^"]+(")', re.IGNORECASE), r'\1[REDACTED]\2'),
    (re.compile(r'("access_token":\s*")[^"]+(")', re.IGNORECASE), r'\1[REDACTED]\2'),
    (re.compile(r'("client_secret":\s*")[^"]+(")', re.IGNORECASE), r'\1[REDACTED]\2'),
    (re.compile(r'(code=[A-Za-z0-9\-._~+/]+)', re.IGNORECASE), r'code=[REDACTED]'),
    (re.compile(r'("code_verifier":\s*")[^"]+(")', re.IGNORECASE), r'\1[REDACTED]\2'),
]


class RedactingLogger(logging.Filter):
    """Logging filter that scrubs sensitive credentials from output."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pat, repl in SENSITIVE_PATTERNS:
            msg = pat.sub(repl, msg)
        record.msg = msg
        record.args = ()
        return True


bearer_scheme = HTTPBearer(auto_error=False)


def is_loopback_client(request: Request) -> bool:
    """Check if request originates from local machine loopback."""
    if not request.client or not request.client.host:
        return True
    host = request.client.host.strip()
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


def get_api_key_auth(config: AppConfig) -> Callable:
    """Dependency for client API key verification (/v1/*) with role/model permissions."""
    async def verify_gateway_key(
        request: Request,
        auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    ) -> str:
        provided = None
        if auth and auth.credentials:
            provided = auth.credentials.strip()
        elif header_key := (request.headers.get("x-api-key") or request.headers.get("api-key")):
            provided = header_key.strip()

        # 1. Check primary master gateway key
        if config.security.gateway_api_key and provided == config.security.gateway_api_key:
            request.state.api_key_info = {
                "key": provided,
                "name": "master-default",
                "allowed_families": ["all"],
                "allowed_models": [],
            }
            return provided

        # 2. Check multi-key pool
        if provided:
            for entry in config.security.api_keys:
                if provided == entry.key:
                    request.state.api_key_info = {
                        "key": entry.key,
                        "name": entry.name,
                        "allowed_families": [f.lower() for f in entry.allowed_families],
                        "allowed_models": entry.allowed_models,
                    }
                    return provided

        # 3. Local trust bypass for loopback requests (OpenCode, Cursor, Aider, Claude Code, etc.)
        if config.security.local_trust and is_loopback_client(request):
            if not provided or provided in ("local", "auto", "default", "dummy", "none") or provided.startswith("sk-") or provided.startswith("agw-"):
                effective_key = provided or "local-trusted"
                request.state.api_key_info = {
                    "key": effective_key,
                    "name": "local-trusted",
                    "allowed_families": ["all"],
                    "allowed_models": [],
                }
                return effective_key

        if not provided:
            raise HTTPException(
                status_code=401,
                detail={"error": {"message": "Invalid or missing Gateway API key", "type": "auth_error"}},
            )

        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "Invalid Gateway API key", "type": "auth_error"}},
        )

    return verify_gateway_key


def get_admin_key_auth(config: AppConfig) -> Callable:
    """Dependency for admin API key verification (/admin/*)."""
    async def verify_admin_key(
        request: Request,
        auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    ) -> str:
        expected = config.security.admin_api_key
        if not expected:
            return "anon"

        provided = None
        if auth and auth.credentials:
            provided = auth.credentials.strip()
        elif header_key := (
            request.headers.get("x-admin-key")
            or request.headers.get("x-api-key")
            or request.headers.get("api-key")
        ):
            provided = header_key.strip()

        if provided and provided == expected:
            return provided

        # Local dashboard bootstrap bypass is narrower than legacy local_trust:
        # only browser requests from loopback may access admin data without copying a key.
        if config.security.dashboard_local_access and is_loopback_client(request):
            user_agent = request.headers.get("user-agent", "").lower()
            if "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent or "edge" in user_agent:
                # Ignore stale browser-held credentials for a loopback dashboard.
                # The browser is already local; normal remote/admin clients still require exact keys.
                return "local-dashboard"

        # Preserve the explicit legacy compatibility switch for automated local clients/tests.
        if config.security.local_trust and is_loopback_client(request):
            if not provided or provided in ("local", "admin", "auto", "default", "dummy"):
                return provided or "local-admin"

        if not provided or provided != expected:
            raise HTTPException(
                status_code=401,
                detail={"error": {"message": "Invalid or missing Admin API key", "type": "admin_auth_error"}},
            )
        return provided

    return verify_admin_key


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Structured audit logger with response time and status codes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000.0

        # Don't log health check spam
        if path != "/health":
            logging.getLogger("agw.audit").info(
                f"method={request.method} path={path} status={response.status_code} "
                f"ip={client_ip} latency_ms={duration_ms:.1f}"
            )
        return response
