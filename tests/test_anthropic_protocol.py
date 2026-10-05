"""Tests for Anthropic /v1/messages protocol compatibility."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.main import create_app
from agw.protocol.anthropic_mapper import anthropic_to_openai_request, openai_to_anthropic_response


def test_anthropic_request_mapping():
    anthropic_payload = {
        "model": "claude-3-5-sonnet-20241022",
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "What is 2+2?"}
        ],
        "max_tokens": 512,
        "temperature": 0.2,
    }

    oai_req = anthropic_to_openai_request(anthropic_payload)
    assert oai_req["model"] == "claude-3-5-sonnet-20241022"
    assert oai_req["max_tokens"] == 512
    assert oai_req["temperature"] == 0.2
    assert len(oai_req["messages"]) == 2
    assert oai_req["messages"][0]["role"] == "system"
    assert oai_req["messages"][0]["content"] == "You are a helpful assistant."
    assert oai_req["messages"][1]["role"] == "user"
    assert oai_req["messages"][1]["content"] == "What is 2+2?"


def test_anthropic_response_mapping():
    oai_resp = {
        "id": "chatcmpl-12345",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Four.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 2,
            "total_tokens": 14,
        },
    }

    anthropic_resp = openai_to_anthropic_response(oai_resp, "claude-3-5-sonnet-20241022")
    assert anthropic_resp["type"] == "message"
    assert anthropic_resp["role"] == "assistant"
    assert anthropic_resp["model"] == "claude-3-5-sonnet-20241022"
    assert len(anthropic_resp["content"]) == 1
    assert anthropic_resp["content"][0]["type"] == "text"
    assert anthropic_resp["content"][0]["text"] == "Four."
    assert anthropic_resp["stop_reason"] == "end_turn"
    assert anthropic_resp["usage"]["input_tokens"] == 12
    assert anthropic_resp["usage"]["output_tokens"] == 2


@pytest.mark.asyncio
async def test_anthropic_messages_endpoint(test_config, test_repo, test_vault, mock_client):
    from agw.api.routes_anthropic import create_anthropic_router
    from agw.routing.cooldown import CooldownManager
    from agw.routing.health import AccountHealthTracker
    from agw.routing.registry import ModelRegistry
    from agw.routing.scheduler import AccountScheduler
    from fastapi import FastAPI

    await test_repo.upsert_account("acc-ant1", "ant1@google.com", project_id="p1")
    test_vault.store_token("acc-ant1", "1//tok1")

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

    class FakeAccountMgr:
        async def get_access_token(self, aid):
            return f"access_{aid}"

    router = create_anthropic_router(
        config=test_config,
        repo=test_repo,
        account_mgr=FakeAccountMgr(),
        cloudcode_client=mock_client,
        model_registry=model_registry,
        scheduler=scheduler,
        cooldown_mgr=cooldown_mgr,
        health_tracker=health_tracker,
    )

    app = FastAPI()
    app.include_router(router)

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {test_config.security.gateway_api_key}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello Claude!"}],
            "max_tokens": 256,
        }

        resp = await client.post("/v1/messages", headers=headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "message"
        assert data["role"] == "assistant"
        assert any(c["type"] == "text" for c in data["content"])
