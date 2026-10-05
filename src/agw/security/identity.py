"""Secure local identity generation and legacy-secret migration."""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any
import yaml

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
        self._persist_if_config_file(config, changed)
        return {
            "changed": changed,
            "gateway_key": masked_key(config.security.gateway_api_key),
            "admin_key": masked_key(config.security.admin_api_key),
        }

    @staticmethod
    def _persist_if_config_file(config: Any, changed: bool) -> None:
        """Persist generated credentials only for the real config file, never test objects."""
        config_path = Path(__import__("os").environ.get("GATEWAY_CONFIG_PATH", "config.yaml"))
        if not changed or not config_path.is_file():
            return
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            security = data.setdefault("security", {})
            security["gateway_api_key"] = config.security.gateway_api_key
            security["admin_api_key"] = config.security.admin_api_key
            config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        except Exception:
            # Startup must remain available; the dashboard can report migration attention.
            return

    def rotate_keys(self, config: Any) -> dict[str, str]:
        config.security.gateway_api_key = generate_secret("agw-local")
        config.security.admin_api_key = generate_secret("agw-admin")
        return {
            "gateway_key": masked_key(config.security.gateway_api_key),
            "admin_key": masked_key(config.security.admin_api_key),
        }
