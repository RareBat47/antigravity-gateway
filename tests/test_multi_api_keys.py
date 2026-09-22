"""Unit and integration tests for multi-API key management and model family restrictions."""

import pytest
from httpx import ASGITransport, AsyncClient
from agw.config import load_config
from agw.main import create_app


@pytest.mark.asyncio
async def test_multi_api_key_role_restrictions(test_repo, temp_dir):
    cfg = load_config()
    cfg.storage.database_path = test_repo.db_path
    
    # Override api keys for strict testing
    for ak in cfg.security.api_keys:
        if ak.key == "agw-plan-claude-9x82":
            ak.allowed_families = ["claude"]
            ak.allowed_models = []
        elif ak.key == "agw-code-gemini-3-8d52":
            ak.allowed_families = []
            ak.allowed_models = ["gemini-3.8-flash-high"]
        elif ak.key == "agw-code-hybrid-1-4a29":
            ak.allowed_families = []
            ak.allowed_models = ["gemini-3.1-pro-low"]
        elif ak.key == "agw-code-hybrid-2-6e83":
            ak.allowed_families = []
            ak.allowed_models = ["claude-sonnet-4-6"]
        elif ak.key == "agw-debug-all-9c37":
            ak.allowed_families = []
            ak.allowed_models = ["gpt-oss-120b-medium"]
    
    app = create_app(cfg)
    # The new create_app uses the cfg path, so we're good.
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Planning Key (Claude only)
        plan_headers = {"Authorization": "Bearer agw-plan-claude-9x82"}
        res_models = await client.get("/v1/models", headers=plan_headers)
        assert res_models.status_code == 200
        model_ids = [m["id"] for m in res_models.json()["data"]]
        assert any("claude" in m for m in model_ids)
        assert not any("gemini-2.5-flash" in m for m in model_ids)

        # Disallow Gemini for planning key
        res_fail = await client.post(
            "/v1/chat/completions",
            headers=plan_headers,
            json={"model": "gemini-2.5-flash", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert res_fail.status_code == 403
        assert "not permitted" in res_fail.json()["detail"]["error"]["message"]

        # 2. Test Coding Key (Gemini 3.8 Flash High only)
        code_headers = {"Authorization": "Bearer agw-code-gemini-3-8d52"}
        res_code_models = await client.get("/v1/models", headers=code_headers)
        assert res_code_models.status_code == 200
        code_ids = [m["id"] for m in res_code_models.json()["data"]]
        assert code_ids == ["gemini-3.8-flash-high"]

        res_fail_claude = await client.post(
            "/v1/chat/completions",
            headers=code_headers,
            json={"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert res_fail_claude.status_code == 403

        # 3. Test Pro Key (Gemini 3.1 Pro Low only)
        pro_headers = {"Authorization": "Bearer agw-code-hybrid-1-4a29"}
        res_pro_models = await client.get("/v1/models", headers=pro_headers)
        assert res_pro_models.status_code == 200
        pro_ids = [m["id"] for m in res_pro_models.json()["data"]]
        assert pro_ids == ["gemini-3.1-pro-low"]

        # 4. Test Debugging Key (Claude Sonnet 4.6 only)
        debug_headers = {"Authorization": "Bearer agw-code-hybrid-2-6e83"}
        res_debug_models = await client.get("/v1/models", headers=debug_headers)
        assert res_debug_models.status_code == 200
        debug_ids = [m["id"] for m in res_debug_models.json()["data"]]
        assert debug_ids == ["claude-sonnet-4-6"]

        # 5. Test GPT Key (GPT-OSS 120B only)
        gpt_headers = {"Authorization": "Bearer agw-debug-all-9c37"}
        res_gpt_models = await client.get("/v1/models", headers=gpt_headers)
        assert res_gpt_models.status_code == 200
        gpt_ids = [m["id"] for m in res_gpt_models.json()["data"]]
        assert gpt_ids == ["gpt-oss-120b-medium"]

        # 6. Test Invalid Key
        bad_headers = {"Authorization": "Bearer invalid-key-xyz"}
        res_bad = await client.get("/v1/models", headers=bad_headers)
        assert res_bad.status_code == 401
