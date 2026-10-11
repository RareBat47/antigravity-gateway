"""Tests for complete-catalog client API profiles."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.config import ApiKeyEntry, load_config
from agw.main import create_app


@pytest.mark.asyncio
async def test_client_profiles_all_expose_complete_catalog():
    cfg = load_config()
    cfg.security.api_keys = [
        ApiKeyEntry(key="agw-hermes-local", name="Hermes Agent", allowed_families=["all"]),
        ApiKeyEntry(key="agw-claude-code-local", name="Claude Code", allowed_families=["all"]),
        ApiKeyEntry(key="agw-opencode-local", name="OpenCode", allowed_families=["all"]),
    ]
    app = create_app(cfg)
    transport = ASGITransport(app=app)
    expected_models = {
        "gemini-3.8-flash-high",
        "gemini-3.1-pro-low",
        "gemini-pro-agent",
        "claude-opus-5.5",
        "claude-sonnet-5.5",
        "gpt-oss-120b-medium",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for key in ("agw-hermes-local", "agw-claude-code-local", "agw-opencode-local"):
            response = await client.get("/v1/models", headers={"Authorization": f"Bearer {key}"})
            assert response.status_code == 200
            assert expected_models.issubset({item["id"] for item in response.json()["data"]})
        bad = await client.get("/v1/models", headers={"Authorization": "Bearer invalid-key-xyz"})
        assert bad.status_code == 401
