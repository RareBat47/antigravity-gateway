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


@pytest.mark.asyncio
async def test_channel_bindings_and_incomplete_status(test_config):
    repo = DatabaseRepository(db_path=test_config.storage.database_path)
    await repo.init_db()
    aid = "acc-wizard-test"
    await repo.upsert_account(aid, "wizard@example.com")

    # Step 1: Initial OAuth binding
    b1 = await repo.upsert_channel_bindings(aid, oauth_verified=True)
    assert b1["oauth_verified"] is True
    assert b1["completed_methods"] == 1
    assert b1["is_setup_complete"] is False

    # Step 2: Cookies binding
    b2 = await repo.upsert_channel_bindings(aid, cookies_verified=True)
    assert b2["cookies_verified"] is True
    assert b2["completed_methods"] == 2
    assert b2["is_setup_complete"] is False

    # Step 3: Vertex binding
    b3 = await repo.upsert_channel_bindings(aid, vertex_verified=True)
    assert b3["vertex_verified"] is True
    assert b3["completed_methods"] == 3
    assert b3["is_setup_complete"] is True
