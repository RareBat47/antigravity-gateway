import pytest
from httpx import ASGITransport, AsyncClient
from agw.main import create_app


@pytest.mark.asyncio
async def test_dashboard_browser_recovers_from_stale_saved_key(test_config, test_repo):
    """A stale localStorage key must not lock the local browser dashboard."""
    app = create_app(test_config)
    transport = ASGITransport(app=app, client=("127.0.0.1", 54321))
    headers = {
        "User-Agent": "Mozilla/5.0 Chrome/128.0",
        "Authorization": "Bearer stale-key-from-old-install",
    }
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8999") as client:
        response = await client.get("/admin/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
