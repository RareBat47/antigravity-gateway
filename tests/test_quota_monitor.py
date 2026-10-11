"""Tests for quota monitoring, JSON state persistence, and Markdown reporting."""

import os
import pytest
from agw.quota.monitor import QuotaMonitor
from agw.quota.reporter import generate_markdown_report


@pytest.mark.asyncio
async def test_quota_monitor_and_reporting(test_repo, test_vault, mock_client, test_config):
    await test_repo.upsert_account("acc-q1", "user@google.com", display_name="Account 1")
    test_vault.store_token("acc-q1", "1//test_token")

    class MockAccountMgr:
        async def get_access_token(self, aid):
            return "mock_access_token"

    monitor = QuotaMonitor(
        repo=test_repo,
        cloudcode_client=mock_client,
        account_manager=MockAccountMgr(),
        interval_seconds=300,
        quota_state_path=test_config.storage.quota_state_path,
        status_report_path=test_config.storage.status_report_path,
    )

    snapshot = await monitor.refresh_account("acc-q1")
    assert snapshot is not None
    assert snapshot.account_id == "acc-q1"
    assert "gemini-3.5-flash-low" in snapshot.models
    assert snapshot.gemini_average_fraction is not None

    # Test markdown report generation
    report_md = generate_markdown_report(
        [
            {
                "display_name": "Account 1",
                "gemini_quota_str": "82%",
                "claude_quota_str": "61%",
                "health_status": "healthy",
                "cooldown_str": "none",
            }
        ],
        output_path=test_config.storage.status_report_path,
    )

    assert os.path.exists(test_config.storage.status_report_path)
    assert "| Account 1 | 82% | 61% | healthy | none |" in report_md
