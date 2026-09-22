"""FastAPI application entrypoint for Antigravity Gateway."""

import contextlib
import logging
import sys
from typing import AsyncIterator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agw.accounts.manager import AccountManager
from agw.api.middleware import AuditLoggingMiddleware, RedactingLogger
from agw.api.routes_admin import create_admin_router
from agw.api.routes_auth import create_auth_router
from agw.api.routes_v1 import create_v1_router
from agw.auth.crypto import TokenEncryption
from agw.auth.vault import CredentialVault
from agw.arena.provider import ArenaProvider
from agw.config import AppConfig, load_config
from agw.dashboard import get_dashboard_html
from agw.db.repository import DatabaseRepository
from agw.quota.monitor import QuotaMonitor
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker
from agw.routing.registry import ModelRegistry
from agw.routing.scheduler import AccountScheduler


def configure_logging(debug: bool = False) -> None:
    """Configure structured logging with secret redaction."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Avoid duplicate handlers
    if not any(isinstance(f, RedactingLogger) for h in root_logger.handlers for f in h.filters):
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(RedactingLogger())
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler.setFormatter(formatter)
        root_logger.handlers = [handler]


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Application factory."""
    cfg = config or load_config()
    configure_logging(cfg.server.debug)

    # Core singletons
    crypto = TokenEncryption(key=cfg.security.encryption_key, key_file_path=cfg.storage.vault_key_path)
    vault = CredentialVault(crypto=crypto)
    repo = DatabaseRepository(db_path=cfg.storage.database_path)
    from agw.arena.factory import get_arena_provider
    client = get_arena_provider(timeout=float(cfg.scheduler.upstream_timeout_seconds), use_mock=cfg.server.debug)
    account_mgr = AccountManager(cfg, repo, vault, client)

    cooldown_mgr = CooldownManager(
        repo=repo,
        default_cooldown_seconds=cfg.scheduler.default_cooldown_seconds,
        tiers=cfg.scheduler.cooldown_tiers_seconds,
    )
    health_tracker = AccountHealthTracker()
    model_registry = ModelRegistry(cfg.models)

    scheduler = AccountScheduler(
        repo=repo,
        cooldown_mgr=cooldown_mgr,
        health_tracker=health_tracker,
        settings=cfg.scheduler,
        vault=vault,
    )

    quota_monitor = QuotaMonitor(
        repo=repo,
        cloudcode_client=client,
        account_manager=account_mgr,
        interval_seconds=cfg.quota_monitor.interval_seconds,
        quota_state_path=cfg.storage.quota_state_path,
        status_report_path=cfg.storage.status_report_path,
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup
        await repo.init_db()
        if cfg.quota_monitor.enabled:
            quota_monitor.start()
        logging.getLogger("agw").info(
            f"Antigravity Gateway running on {cfg.server.host}:{cfg.server.port}"
        )
        yield
        # Shutdown
        await quota_monitor.stop()

    app = FastAPI(
        title="Antigravity Gateway",
        description="Multi-Account OpenAI-compatible Gateway for Hermes Agent",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Middlewares
    app.add_middleware(AuditLoggingMiddleware)
    if cfg.security.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.security.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Health check
    @app.get("/health", tags=["Health"])
    async def health_check():
        summary = await repo.get_usage_summary()
        accounts = await repo.list_accounts()
        return {
            "status": "ok",
            "active_accounts": len([a for a in accounts if a.get("enabled", 1)]),
            "total_accounts": len(accounts),
            "total_requests": summary.get("total_requests", 0),
        }

    # Register Routers
    app.include_router(create_auth_router(cfg, account_mgr))
    app.include_router(
        create_v1_router(
            config=cfg,
            repo=repo,
            account_mgr=account_mgr,
            cloudcode_client=client,
            model_registry=model_registry,
            scheduler=scheduler,
            cooldown_mgr=cooldown_mgr,
            health_tracker=health_tracker,
        )
    )
    app.include_router(
        create_admin_router(
            config=cfg,
            repo=repo,
            account_mgr=account_mgr,
            quota_monitor=quota_monitor,
            cooldown_mgr=cooldown_mgr,
            health_tracker=health_tracker,
            dashboard_html_content=get_dashboard_html(),
            model_registry=model_registry,
        )
    )

    # Root redirect / welcome
    @app.get("/", tags=["Root"])
    async def root():
        return {
            "service": "Antigravity Gateway",
            "version": "1.0.0",
            "docs": "/docs",
            "dashboard": "/admin/dashboard",
            "endpoints": {
                "models": "/v1/models",
                "chat_completions": "/v1/chat/completions",
                "health": "/health",
            },
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    cfg = load_config()
    uvicorn.run(
        "agw.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=cfg.server.debug,
    )
