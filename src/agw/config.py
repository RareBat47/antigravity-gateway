"""Configuration manager for Antigravity Gateway."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from agw.constants import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_MODELS,
    QUOTA_EXHAUSTED_BACKOFF_TIERS_SECONDS,
)


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8999
    debug: bool = False
    public_base_url: str = ""


class ApiKeyEntry(BaseModel):
    key: str
    name: str = "default"
    description: Optional[str] = None
    allowed_families: List[str] = Field(default_factory=lambda: ["all"])
    allowed_models: List[str] = Field(default_factory=list)


class SecuritySettings(BaseModel):
    gateway_api_key: str = Field(default="agw-hermes-secret-key-change-me")
    admin_api_key: str = Field(default="agw-admin-super-secret-key-change-me")
    encryption_key: Optional[str] = None
    rate_limit_per_minute: int = 120
    cors_origins: List[str] = Field(default_factory=list)
    api_keys: List[ApiKeyEntry] = Field(default_factory=list)


class StorageSettings(BaseModel):
    database_path: str = "data/gateway.db"
    vault_key_path: str = "data/vault.key"
    quota_state_path: str = "data/quota-state.json"
    status_report_path: str = "docs/account-status.md"


class SchedulerWeights(BaseModel):
    health: float = 2.0
    tokens: float = 5.0
    quota: float = 3.0
    lru: float = 0.1


class SchedulerSettings(BaseModel):
    strategy: str = "hybrid"
    weights: SchedulerWeights = Field(default_factory=SchedulerWeights)
    global_quota_threshold: float = 0.05
    max_account_retries: int = 3
    default_cooldown_seconds: int = 60
    cooldown_tiers_seconds: List[int] = Field(
        default_factory=lambda: list(QUOTA_EXHAUSTED_BACKOFF_TIERS_SECONDS)
    )


class QuotaMonitorSettings(BaseModel):
    enabled: bool = True
    interval_seconds: int = 300
    stale_threshold_seconds: int = 600


class OAuthSettings(BaseModel):
    client_id: str = DEFAULT_CLIENT_ID
    client_secret: str = DEFAULT_CLIENT_SECRET


class AppConfig(BaseModel):
    server: ServerSettings = Field(default_factory=ServerSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    quota_monitor: QuotaMonitorSettings = Field(default_factory=QuotaMonitorSettings)
    oauth: OAuthSettings = Field(default_factory=OAuthSettings)
    models: Dict[str, Any] = Field(default_factory=lambda: dict(DEFAULT_MODELS))


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file and environment variables."""
    cfg_data: Dict[str, Any] = {}

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    target_path = config_path or os.environ.get("GATEWAY_CONFIG_PATH")
    if not target_path:
        for candidate in ["config.yaml", "config.yml", "config.example.yaml"]:
            if Path(candidate).is_file():
                target_path = candidate
                break

    if target_path and Path(target_path).is_file():
        with open(target_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                cfg_data = loaded

    # Overlay environment variables
    server_data = cfg_data.get("server", {})
    if host := os.environ.get("GATEWAY_HOST"):
        server_data["host"] = host
    if port := os.environ.get("GATEWAY_PORT"):
        server_data["port"] = int(port)
    if debug := os.environ.get("GATEWAY_DEBUG"):
        server_data["debug"] = debug.lower() in ("true", "1", "yes")
    if public_url := os.environ.get("PUBLIC_BASE_URL"):
        server_data["public_base_url"] = public_url.rstrip("/")
    cfg_data["server"] = server_data

    sec_data = cfg_data.get("security", {})
    if gw_key := os.environ.get("GATEWAY_API_KEY"):
        sec_data["gateway_api_key"] = gw_key
    if admin_key := os.environ.get("ADMIN_API_KEY"):
        sec_data["admin_api_key"] = admin_key
    if enc_key := os.environ.get("GATEWAY_ENCRYPTION_KEY"):
        sec_data["encryption_key"] = enc_key
    cfg_data["security"] = sec_data

    oauth_data = cfg_data.get("oauth", {})
    if cid := os.environ.get("GOOGLE_CLIENT_ID"):
        oauth_data["client_id"] = cid
    elif not oauth_data.get("client_id"):
        oauth_data["client_id"] = DEFAULT_CLIENT_ID

    if csec := os.environ.get("GOOGLE_CLIENT_SECRET"):
        oauth_data["client_secret"] = csec
    elif not oauth_data.get("client_secret"):
        oauth_data["client_secret"] = DEFAULT_CLIENT_SECRET
    cfg_data["oauth"] = oauth_data

    stor_data = cfg_data.get("storage", {})
    if db_p := os.environ.get("DATABASE_PATH"):
        stor_data["database_path"] = db_p
    if qs_p := os.environ.get("QUOTA_STATE_PATH"):
        stor_data["quota_state_path"] = qs_p
    if sr_p := os.environ.get("STATUS_REPORT_PATH"):
        stor_data["status_report_path"] = sr_p
    cfg_data["storage"] = stor_data

    # Ensure storage paths exist
    for key in ["database_path", "vault_key_path", "quota_state_path"]:
        p = Path(stor_data.get(key, "data/temp"))
        p.parent.mkdir(parents=True, exist_ok=True)
    if "status_report_path" in stor_data:
        Path(stor_data["status_report_path"]).parent.mkdir(parents=True, exist_ok=True)

    return AppConfig(**cfg_data)
