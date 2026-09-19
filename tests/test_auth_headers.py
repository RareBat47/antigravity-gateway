"""Tests for x-api-key and api-key header authentication."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.main import create_app


@pytest.mark.asyncio
async def test_api_key_via_custom_headers(test_config):
    from agw.db.repository import DatabaseRepository
    repo = DatabaseRepository(db_path=test_config.storage.database_path)
    await repo.init_db()

    app = create_app(test_config)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. x-api-key for /v1/models
        resp1 = await client.get(
            "/v1/models",
            headers={"x-api-key": test_config.security.gateway_api_key},
        )
        assert resp1.status_code == 200

        # 2. api-key for /v1/models
        resp2 = await client.get(
            "/v1/models",
            headers={"api-key": test_config.security.gateway_api_key},
        )
        assert resp2.status_code == 200

        # 3. x-admin-key for /admin/accounts
        resp3 = await client.get(
            "/admin/accounts",
            headers={"x-admin-key": test_config.security.admin_api_key},
        )
        assert resp3.status_code == 200
