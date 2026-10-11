"""Tests for local_trust loopback authentication bypass."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository
from agw.main import create_app


@pytest.mark.asyncio
async def test_local_trust_allows_loopback(temp_dir):
    import os
    from cryptography.fernet import Fernet

    cfg = AppConfig()
    cfg.storage.database_path = os.path.join(temp_dir, "test_lt.db")
    cfg.storage.vault_key_path = os.path.join(temp_dir, "test_lt.key")
    cfg.storage.quota_state_path = os.path.join(temp_dir, "test_lt.json")
    cfg.storage.status_report_path = os.path.join(temp_dir, "test_lt.md")
    cfg.security.encryption_key = Fernet.generate_key().decode()
    cfg.security.local_trust = True

    repo = DatabaseRepository(db_path=cfg.storage.database_path)
    await repo.init_db()

    app = create_app(cfg)
    transport = ASGITransport(app=app, client=("127.0.0.1", 54321))

    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8999") as client:
        # 1. /v1/models with no header
        res1 = await client.get("/v1/models")
        assert res1.status_code == 200
        assert "data" in res1.json()

        # 2. /v1/models with generic sk- key
        res2 = await client.get("/v1/models", headers={"Authorization": "Bearer sk-any-arbitrary-key"})
        assert res2.status_code == 200

        # 3. /admin/accounts with no header
        res3 = await client.get("/admin/accounts")
        assert res3.status_code == 200
