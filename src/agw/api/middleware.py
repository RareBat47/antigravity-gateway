"""Security middlewares: secret redaction in logs, authentication, and auditing."""

import logging
import re
import time
from typing import Callable
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


def get_api_key_auth(config: AppConfig) -> Callable:
    """Dependency for client API key verification (/v1/*)."""
    async def verify_gateway_key(
        auth: HTTPAuthorizationCredentials = Security(bearer_scheme),
    ) -> str:
        expected = config.security.gateway_api_key
        if not expected:
            return "anon"
        if not auth or auth.credentials != expected:
            raise HTTPException(
                status_code=401,
                detail={"error": {"message": "Invalid or missing Gateway API key", "type": "auth_error"}},
            )
        return auth.credentials

    return verify_gateway_key


def get_admin_key_auth(config: AppConfig) -> Callable:
    """Dependency for admin API key verification (/admin/*)."""
    async def verify_admin_key(
        auth: HTTPAuthorizationCredentials = Security(bearer_scheme),
    ) -> str:
        expected = config.security.admin_api_key
        if not expected:
            return "anon"
        if not auth or auth.credentials != expected:
            raise HTTPException(
                status_code=401,
                detail={"error": {"message": "Invalid or missing Admin API key", "type": "admin_auth_error"}},
            )
        return auth.credentials

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
