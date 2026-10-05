"""Secure local identity generation and legacy-secret migration."""
from __future__ import annotations

import secrets
from typing import Any

DEFAULT_MARKERS = (
    "change-me",
    "changeme",
    "your-key",
    "replace-me",
)


def is_default_secret(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return any(marker in lowered for marker in DEFAULT_MARKERS)


def generate_secret(prefix: str) -> str:
    return f"{prefix}-{secrets.token_urlsafe(32)}"


def masked_key(value: str | None) -> str:
    if not value:
        return "not configured"
    return f"{value[:6]}…{value[-4:]}" if len(value) > 12 else "configured"


class LocalIdentityManager:
    """Owns generated local/admin API identities without touching account vault data."""

    def ensure_identity(self, config: Any) -> dict[str, Any]:
        changed = False
        if is_default_secret(config.security.gateway_api_key):
            config.security.gateway_api_key = generate_secret("agw-local")
            changed = True
        if is_default_secret(config.security.admin_api_key):
            config.security.admin_api_key = generate_secret("agw-admin")
            changed = True
        return {
            "changed": changed,
            "gateway_key": masked_key(config.security.gateway_api_key),
            "admin_key": masked_key(config.security.admin_api_key),
        }

    def rotate_keys(self, config: Any) -> dict[str, str]:
        config.security.gateway_api_key = generate_secret("agw-local")
        config.security.admin_api_key = generate_secret("agw-admin")
        return {
            "gateway_key": masked_key(config.security.gateway_api_key),
            "admin_key": masked_key(config.security.admin_api_key),
        }
