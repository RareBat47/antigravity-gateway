"""Tests for isolated cooldowns, scheduler weights, and automatic account failover."""

import pytest
from agw.config import SchedulerSettings
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker
from agw.routing.scheduler import AccountScheduler


@pytest.mark.asyncio
async def test_isolated_cooldown_and_failover(test_repo, test_vault):
    cooldown_mgr = CooldownManager(test_repo, default_cooldown_seconds=60)
    health_tracker = AccountHealthTracker()
    settings = SchedulerSettings()

    scheduler = AccountScheduler(
        repo=test_repo,
        cooldown_mgr=cooldown_mgr,
        health_tracker=health_tracker,
        settings=settings,
        vault=test_vault,
    )

    # Setup 2 accounts
    await test_repo.upsert_account("acc-1", "user1@google.com", display_name="Account 1")
    await test_repo.upsert_account("acc-2", "user2@google.com", display_name="Account 2")
    test_vault.store_token("acc-1", "1//token1")
    test_vault.store_token("acc-2", "1//token2")

    # 1. Both available initially
    acc = await scheduler.select_account("claude")
    assert acc is not None
    assert acc["id"] in ("acc-1", "acc-2")

    # 2. Trigger rate limit on Account 1 specifically for Claude
    dur = await cooldown_mgr.record_rate_limit("acc-1", "claude", 60)
    assert dur == 60

    # Account 1 must be on cooldown for Claude
    assert await cooldown_mgr.is_cooling_down("acc-1", "claude") is True
    # Account 1 must NOT be on cooldown for Gemini
    assert await cooldown_mgr.is_cooling_down("acc-1", "gemini") is False

    # 3. Requesting Claude now MUST select Account 2
    selected_claude = await scheduler.select_account("claude")
    assert selected_claude is not None
    assert selected_claude["id"] == "acc-2"

    # 4. Requesting Gemini can still select Account 1!
    candidates_gemini = await scheduler.get_candidate_accounts("gemini")
    cand_ids = [c[0]["id"] for c in candidates_gemini]
    assert "acc-1" in cand_ids
