"""End-to-end integration tests for /v1/chat/completions failover and streaming."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.api.routes_v1 import create_v1_router
from agw.config import AppConfig
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker
from agw.routing.registry import ModelRegistry
from agw.routing.scheduler import AccountScheduler
from agw.arena.mock_provider import MockArenaProvider

@pytest.mark.asyncio
async def test_v1_chat_completions_failover(test_repo, test_vault, test_config):
    # Setup 2 accounts
    await test_repo.upsert_account("acc-f1", "f1@google.com", project_id="p1")
    await test_repo.upsert_account("acc-f2", "f2@google.com", project_id="p2")
    test_vault.store_token("acc-f1", "1//tok1")
    test_vault.store_token("acc-f2", "1//tok2")

    cooldown_mgr = CooldownManager(test_repo)
    health_tracker = AccountHealthTracker()
    model_registry = ModelRegistry()
    scheduler = AccountScheduler(
        repo=test_repo,
        cooldown_mgr=cooldown_mgr,
        health_tracker=health_tracker,
        settings=test_config.scheduler,
        vault=test_vault,
    )

    class FlakyArenaProvider(MockArenaProvider):
        async def generate_content(self, access_token, envelope):
            # If project is p1, fail with 429
            # Note: with new architecture, envelope/project logic might be different,
            # but let's assume we can trigger 429 based on access_token
            if access_token == "access_acc-f1":
                return 429, {"error": "RESOURCE_EXHAUSTED"}, "RESOURCE_EXHAUSTED"
            return await super().generate_content(access_token, envelope)

    flaky_client = FlakyArenaProvider()

    class FakeAccountMgr:
        async def get_access_token(self, aid):
            return f"access_{aid}"

    router = create_v1_router(
        config=test_config,
        repo=test_repo,
        account_mgr=FakeAccountMgr(),
        cloudcode_client=flaky_client,
        model_registry=model_registry,
        scheduler=scheduler,
        cooldown_mgr=cooldown_mgr,
        health_tracker=health_tracker,
    )

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {test_config.security.gateway_api_key}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            headers=headers,
            json={
                "model": "gemini-3.5-flash",
                "messages": [{"role": "user", "content": "Test failover"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "Mock reply to: Test failover"
        # Verify account used was acc-f2 (since acc-f1 returned 429 and failed over!)
        assert resp.headers.get("x-agw-account") == "acc-f2"
        # Verify acc-f1 is now on cooldown
        assert await cooldown_mgr.is_cooling_down("acc-f1", "gemini") is True
