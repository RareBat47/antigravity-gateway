"""Tests for SQLite persistence, account models, and cooldown records."""

import pytest


@pytest.mark.asyncio
async def test_account_crud_and_persistence(test_repo, test_config):
    await test_repo.upsert_account(
        account_id="acc-test-1",
        email_safe="tes***@gmail.com",
        display_name="Test Account",
        project_id="mock-project",
        tier="pro",
    )

    acc = await test_repo.get_account("acc-test-1")
    assert acc is not None
    assert acc["email_safe"] == "tes***@gmail.com"
    assert acc["tier"] == "pro"
    assert acc["enabled"] == 1

    # Disable account
    await test_repo.set_account_enabled("acc-test-1", False)
    acc = await test_repo.get_account("acc-test-1")
    assert acc["enabled"] == 0

    # Usage recording
    await test_repo.record_account_usage("acc-test-1", 150, True)
    acc = await test_repo.get_account("acc-test-1")
    assert acc["total_requests"] == 1
    assert acc["total_tokens"] == 150

    # Verify persistence across new repo instance
    from agw.db.repository import DatabaseRepository
    repo2 = DatabaseRepository(db_path=test_config.storage.database_path)
    acc2 = await repo2.get_account("acc-test-1")
    assert acc2 is not None
    assert acc2["total_tokens"] == 150


@pytest.mark.asyncio
async def test_cooldown_storage(test_repo):
    acc_id = "acc-test-cd"
    await test_repo.upsert_account(acc_id, "safe@email.com")

    # Set 60s cooldown for claude
    await test_repo.set_cooldown(acc_id, "claude", 60, "rate_limited")

    # Should be cooling down for claude
    cd_claude = await test_repo.get_active_cooldown(acc_id, "claude")
    assert cd_claude is not None
    assert cd_claude["target_family"] == "claude"

    # Should NOT be cooling down for gemini
    cd_gemini = await test_repo.get_active_cooldown(acc_id, "gemini")
    assert cd_gemini is None

    # Clear cooldown
    await test_repo.clear_cooldown(acc_id, "claude")
    cd_cleared = await test_repo.get_active_cooldown(acc_id, "claude")
    assert cd_cleared is None


@pytest.mark.asyncio
async def test_account_window_usage(test_repo):
    acc_id = "acc-usage-window-test"
    await test_repo.upsert_account(acc_id, "safe@email.com")

    # Record usage events
    await test_repo.record_usage_event(
        request_id="req-1",
        account_id=acc_id,
        model_id="gemini-3.7-flash-medium",
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=250.0,
    )
    await test_repo.record_usage_event(
        request_id="req-2",
        account_id=acc_id,
        model_id="claude-sonnet-4-6",
        prompt_tokens=200,
        completion_tokens=100,
        latency_ms=450.0,
    )

    # 5-hour window usage
    w5 = await test_repo.get_account_window_usage(acc_id, hours=5)
    assert w5["requests"] == 2
    assert w5["prompt_tokens"] == 300
    assert w5["completion_tokens"] == 150
    assert w5["total_tokens"] == 450

    # 7-day window usage
    w7 = await test_repo.get_account_window_usage(acc_id, days=7)
    assert w7["requests"] == 2
    assert w7["total_tokens"] == 450

