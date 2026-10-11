"""Tests for quota threshold enforcement in AccountScheduler."""

import pytest
from agw.config import SchedulerSettings
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker
from agw.routing.scheduler import AccountScheduler


@pytest.mark.asyncio
async def test_scheduler_skips_critically_exhausted_accounts(test_repo, test_vault):
    cooldown_mgr = CooldownManager(test_repo)
    health_tracker = AccountHealthTracker()
    settings = SchedulerSettings(global_quota_threshold=0.05)

    scheduler = AccountScheduler(
        repo=test_repo,
        cooldown_mgr=cooldown_mgr,
        health_tracker=health_tracker,
        settings=settings,
        vault=test_vault,
    )

    # Setup 2 accounts
    await test_repo.upsert_account("acc-exhausted", "exhausted@google.com", display_name="Exhausted Account")
    await test_repo.upsert_account("acc-healthy", "healthy@google.com", display_name="Healthy Account")
    test_vault.store_token("acc-exhausted", "1//tok1")
    test_vault.store_token("acc-healthy", "1//tok2")

    # Record quota: acc-exhausted has 1% (below 5% threshold), acc-healthy has 60%
    await test_repo.record_quota_snapshot(
        account_id="acc-exhausted",
        model_id="gemini-3.5-flash-low",
        model_family="gemini",
        remaining_fraction=0.01,
        reset_time=None,
    )
    await test_repo.record_quota_snapshot(
        account_id="acc-healthy",
        model_id="gemini-3.5-flash-low",
        model_family="gemini",
        remaining_fraction=0.60,
        reset_time=None,
    )

    candidates = await scheduler.get_candidate_accounts("gemini")
    cand_ids = [c[0]["id"] for c in candidates]

    # acc-healthy must be selected first and acc-exhausted must be excluded from active candidates
    assert cand_ids == ["acc-healthy"]
    selected = await scheduler.select_account("gemini")
    assert selected["id"] == "acc-healthy"


@pytest.mark.asyncio
async def test_scheduler_fallback_when_all_exhausted(test_repo, test_vault):
    cooldown_mgr = CooldownManager(test_repo)
    health_tracker = AccountHealthTracker()
    settings = SchedulerSettings(global_quota_threshold=0.05)

    scheduler = AccountScheduler(
        repo=test_repo,
        cooldown_mgr=cooldown_mgr,
        health_tracker=health_tracker,
        settings=settings,
        vault=test_vault,
    )

    # Both accounts exhausted
    await test_repo.upsert_account("acc-low1", "low1@google.com")
    await test_repo.upsert_account("acc-low2", "low2@google.com")
    test_vault.store_token("acc-low1", "1//tok1")
    test_vault.store_token("acc-low2", "1//tok2")

    await test_repo.record_quota_snapshot(
        account_id="acc-low1",
        model_id="claude-sonnet-4-6",
        model_family="claude",
        remaining_fraction=0.02,
        reset_time=None,
    )
    await test_repo.record_quota_snapshot(
        account_id="acc-low2",
        model_id="claude-sonnet-4-6",
        model_family="claude",
        remaining_fraction=0.04,
        reset_time=None,
    )

    selected = await scheduler.select_account("claude")
    # Fallback still gracefully selects the best available candidate (acc-low2 with 4% > acc-low1 with 2%)
    assert selected is not None
    assert selected["id"] == "acc-low2"
