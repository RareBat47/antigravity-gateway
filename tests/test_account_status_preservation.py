"""Tests for account status update and metadata preservation."""

import pytest


@pytest.mark.asyncio
async def test_account_status_preservation(test_repo):
    # Setup initial account
    await test_repo.upsert_account(
        account_id="acc-pres-1",
        email_safe="user@example.com",
        display_name="Real User",
        project_id="proj-123",
        tier="ultra",
        status="active",
        enabled=True,
    )

    # 1. Update status to invalid_grant via update_account_status
    await test_repo.update_account_status("acc-pres-1", "invalid_grant", enabled=False)

    acc = await test_repo.get_account("acc-pres-1")
    assert acc["status"] == "invalid_grant"
    assert acc["enabled"] == 0
    # Crucially, email, display_name, project_id, tier must be preserved!
    assert acc["email_safe"] == "user@example.com"
    assert acc["display_name"] == "Real User"
    assert acc["project_id"] == "proj-123"
    assert acc["tier"] == "ultra"

    # 2. Test upsert with empty or placeholder email does not destroy existing safe email
    await test_repo.upsert_account(
        account_id="acc-pres-1",
        email_safe="revoked",
        tier="unknown",
        status="disabled",
        enabled=False,
    )

    acc_after = await test_repo.get_account("acc-pres-1")
    assert acc_after["email_safe"] == "user@example.com"
    assert acc_after["tier"] == "ultra"
    assert acc_after["status"] == "disabled"


@pytest.mark.asyncio
async def test_get_account_cooldowns_claude_and_gemini(test_repo):
    acc_id = "acc-multi-cd"
    await test_repo.upsert_account(acc_id, "safe@email.com")

    # Set active cooldowns for both claude and gemini
    await test_repo.set_cooldown(acc_id, "claude", 300, "rate_limited_claude")
    await test_repo.set_cooldown(acc_id, "gemini", 120, "rate_limited_gemini")

    all_cds = await test_repo.get_account_cooldowns(acc_id)
    families = [c["target_family"] for c in all_cds]
    assert "claude" in families
    assert "gemini" in families
