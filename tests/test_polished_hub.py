import pytest
from httpx import ASGITransport, AsyncClient
from agw.main import create_app
from agw.routing.profiles import resolve_profile
from agw.routing.registry import ModelRegistry
from agw.security.identity import LocalIdentityManager, is_default_secret


def test_identity_replaces_default_secrets():
    from agw.config import AppConfig
    cfg = AppConfig()
    result = LocalIdentityManager().ensure_identity(cfg)
    assert result["changed"] is True
    assert not is_default_secret(cfg.security.gateway_api_key)
    assert not is_default_secret(cfg.security.admin_api_key)
    assert cfg.security.gateway_api_key != cfg.security.admin_api_key


def test_profiles_resolve_to_real_models():
    registry = ModelRegistry()
    for name in ("auto", "fast", "balanced", "powerful", "reasoning"):
        upstream, family, tokens = resolve_profile(name, registry)
        assert upstream
        assert family in ("gemini", "claude", "gpt")
        assert tokens > 0


@pytest.mark.asyncio
async def test_setup_status_endpoint(test_config, test_repo):
    app = create_app(test_config)
    transport = ASGITransport(app=app, client=("127.0.0.1", 54321))
    headers = {"Authorization": f"Bearer {test_config.security.admin_api_key}"}
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8999") as client:
        response = await client.get("/setup/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["state"] in {"account_required", "ready", "not_initialized"}


@pytest.mark.asyncio
async def test_profiles_endpoint(test_config, test_repo):
    app = create_app(test_config)
    transport = ASGITransport(app=app, client=("127.0.0.1", 54321))
    headers = {"Authorization": f"Bearer {test_config.security.gateway_api_key}"}
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8999") as client:
        response = await client.get("/v1/routing/profiles", headers=headers)
        assert response.status_code == 200
        assert {item["id"] for item in response.json()["data"]} == {"auto", "fast", "balanced", "powerful", "reasoning"}
