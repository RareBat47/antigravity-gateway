"""Tests for Autonomous Provisioning Agent and its admin streaming endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.main import create_app
from agw.agent.provisioner import AutonomousProvisioningAgent
from agw.db.repository import DatabaseRepository


@pytest.mark.asyncio
async def test_agent_pipeline_execution(test_config):
    repo = DatabaseRepository(db_path=test_config.storage.database_path)
    await repo.init_db()

    # Pre-populate an account
    await repo.upsert_account("acc-agent-test", "agent-user@example.com")

    agent = AutonomousProvisioningAgent(
        config=test_config,
        repo=repo,
        account_mgr=None,
        aistudio_client=None,
        geminiweb_client=None,
    )

    events = []
    async for ev in agent.run_pipeline(account_id="acc-agent-test"):
        events.append(ev)

    phases = [e["phase"] for e in events]
    assert "init" in phases
    assert "agy" in phases
    assert "gcli" in phases
    assert "gweb" in phases
    assert "studio" in phases
    assert "complete" in phases


@pytest.mark.asyncio
async def test_admin_agent_provision_endpoint(test_config):
    repo = DatabaseRepository(db_path=test_config.storage.database_path)
    await repo.init_db()
    await repo.upsert_account("acc-agent-http", "http-agent@example.com")

    app = create_app(test_config)
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {test_config.security.admin_api_key}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /admin/agent/provision returns text/event-stream
        resp = await client.get("/admin/agent/provision?account_id=acc-agent-http", headers=headers)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        content = resp.text
        assert "data: " in content
        assert "Autonomous 4-Way Provisioning complete" in content

        # POST /admin/agent/launch-url (mocking launch_browser_url)
        resp_launch = await client.post(
            "/admin/agent/launch-url",
            json={"url": "https://gemini.google.com"},
            headers=headers,
        )
        assert resp_launch.status_code == 200
        assert resp_launch.json()["url"] == "https://gemini.google.com"
