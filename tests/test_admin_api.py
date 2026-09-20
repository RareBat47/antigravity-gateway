"""Tests for FastAPI endpoints and admin authentication."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.main import create_app


@pytest.mark.asyncio
async def test_api_auth_and_health(test_config):
    from agw.db.repository import DatabaseRepository
    repo = DatabaseRepository(db_path=test_config.storage.database_path)
    await repo.init_db()

    app = create_app(test_config)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Public health endpoint requires no auth
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

        # Admin endpoint without key must return 401
        admin_resp = await client.get("/admin/accounts")
        assert admin_resp.status_code == 401

        # Admin endpoint with correct key
        headers = {"Authorization": f"Bearer {test_config.security.admin_api_key}"}
        admin_ok = await client.get("/admin/accounts", headers=headers)
        assert admin_ok.status_code == 200
        assert isinstance(admin_ok.json(), list)

        # /v1/models without key must return 401
        v1_unauth = await client.get("/v1/models")
        assert v1_unauth.status_code == 401

        # /v1/models with gateway key
        v1_headers = {"Authorization": f"Bearer {test_config.security.gateway_api_key}"}
        v1_ok = await client.get("/v1/models", headers=v1_headers)
        assert v1_ok.status_code == 200
        assert "data" in v1_ok.json()

        # Create test account and test reauth endpoint
        await repo.upsert_account("acc-reauth-test", "reauth@test.com")
        await repo.record_quota_snapshot(
            account_id="acc-reauth-test",
            model_id="gemini-3.7-flash-medium",
            model_family="gemini",
            remaining_fraction=0.85,
            reset_time="2026-09-20T16:00:00Z",
        )
        
        # Test accounts list enrichment
        admin_accounts = await client.get("/admin/accounts", headers=headers)
        assert admin_accounts.status_code == 200
        accs_data = admin_accounts.json()
        target_acc = [a for a in accs_data if a["id"] == "acc-reauth-test"][0]
        assert target_acc["gemini_pct"] == 85
        assert target_acc["gemini_reset_time"] == "2026-09-20T16:00:00Z"
        assert "window_5h" in target_acc
        assert "window_7d" in target_acc
        assert "model_quotas" in target_acc

        reauth_resp = await client.post("/admin/accounts/acc-reauth-test/reauth", headers=headers)
        assert reauth_resp.status_code == 200
        reauth_data = reauth_resp.json()
        assert reauth_data["status"] == "pending_reauth"
        assert "auth_url" in reauth_data
        assert "code_verifier" in reauth_data

