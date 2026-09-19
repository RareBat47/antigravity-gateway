"""Background quota monitor service."""

import asyncio
import datetime
import logging
from typing import Any, Dict, List, Optional

from agw.cloudcode.client import CloudCodeClient
from agw.constants import FAMILY_CLAUDE, FAMILY_GEMINI
from agw.db.repository import DatabaseRepository
from agw.quota.models import AccountQuotaSnapshot, ModelQuotaInfo
from agw.quota.reporter import generate_markdown_report, save_quota_state_json

logger = logging.getLogger("agw.quota")


class QuotaMonitor:
    """Monitors account quota and writes status reports."""

    def __init__(
        self,
        repo: DatabaseRepository,
        cloudcode_client: CloudCodeClient,
        account_manager: Any,
        interval_seconds: int = 300,
        quota_state_path: str = "data/quota-state.json",
        status_report_path: str = "docs/account-status.md",
    ):
        self.repo = repo
        self.client = cloudcode_client
        self.account_manager = account_manager
        self.interval = interval_seconds
        self.quota_state_path = quota_state_path
        self.status_report_path = status_report_path
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._latest_snapshots: Dict[str, AccountQuotaSnapshot] = {}

    def start(self) -> None:
        """Start background polling task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Quota monitor started (polling every {self.interval}s)")

    async def stop(self) -> None:
        """Stop background polling task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Quota monitor stopped")

    async def refresh_account(self, account_id: str) -> Optional[AccountQuotaSnapshot]:
        """Poll and update quota for a single account."""
        acc = await self.repo.get_account(account_id)
        if not acc:
            return None

        try:
            token = await self.account_manager.get_access_token(account_id)
            project_id = acc.get("project_id")
            data = await self.client.fetch_available_models(token, project_id)
            models_data = data.get("models", {})

            model_quotas: Dict[str, ModelQuotaInfo] = {}
            gemini_fractions = []
            claude_fractions = []

            for model_id, mdata in models_data.items():
                family = FAMILY_CLAUDE if "claude" in model_id.lower() else FAMILY_GEMINI
                q_info = mdata.get("quotaInfo", {})
                rem_frac = q_info.get("remainingFraction")
                reset_t = q_info.get("resetTime")

                if rem_frac is None and reset_t:
                    rem_frac = 0.0

                if rem_frac is not None:
                    if family == FAMILY_CLAUDE:
                        claude_fractions.append(rem_frac)
                    else:
                        gemini_fractions.append(rem_frac)

                info = ModelQuotaInfo(
                    model_id=model_id,
                    model_family=family,
                    remaining_fraction=rem_frac,
                    reset_time=reset_t,
                )
                model_quotas[model_id] = info

                # Persist snapshot to database
                await self.repo.record_quota_snapshot(
                    account_id=account_id,
                    model_id=model_id,
                    model_family=family,
                    remaining_fraction=rem_frac,
                    reset_time=reset_t,
                )

            gemini_avg = sum(gemini_fractions) / len(gemini_fractions) if gemini_fractions else None
            claude_avg = sum(claude_fractions) / len(claude_fractions) if claude_fractions else None

            snapshot = AccountQuotaSnapshot(
                account_id=account_id,
                email_safe=acc.get("email_safe", ""),
                tier=acc.get("tier", "unknown"),
                models=model_quotas,
                gemini_average_fraction=gemini_avg,
                claude_average_fraction=claude_avg,
            )
            self._latest_snapshots[account_id] = snapshot
            return snapshot

        except Exception as e:
            logger.warning(f"Failed to refresh quota for account {account_id}: {e}")
            return None

    async def refresh_all(self) -> None:
        """Poll quota for all active accounts and write report."""
        accounts = await self.repo.list_accounts()
        statuses: List[Dict[str, Any]] = []

        for acc in accounts:
            acc_id = acc["id"]
            if acc.get("enabled", 1):
                await self.refresh_account(acc_id)

            snapshot = self._latest_snapshots.get(acc_id)
            gemini_str = f"{int(round(snapshot.gemini_average_fraction * 100))}%" if (snapshot and snapshot.gemini_average_fraction is not None) else "unknown"
            claude_str = f"{int(round(snapshot.claude_average_fraction * 100))}%" if (snapshot and snapshot.claude_average_fraction is not None) else "unknown"

            # Check all active cooldowns (gemini, claude, all)
            active_cds = await self.repo.get_account_cooldowns(acc_id)
            cooldown_str = "none"
            if active_cds:
                details = [f"{c['target_family']}: {c.get('reason', 'cooldown')}" for c in active_cds]
                cooldown_str = f"active ({', '.join(details)})"

            # Health
            status_str = "healthy"
            if not acc.get("enabled", 1):
                status_str = "disabled"
            elif acc.get("consecutive_failures", 0) > 2:
                status_str = "degraded"

            statuses.append({
                "account_id": acc_id,
                "display_name": acc.get("display_name") or acc_id,
                "gemini_quota_str": gemini_str,
                "claude_quota_str": claude_str,
                "health_status": status_str,
                "cooldown_str": cooldown_str,
            })

        # Save JSON state
        save_quota_state_json(
            {
                acc_id: (s.model_dump(mode="json") if hasattr(s, "model_dump") else s.dict())
                for acc_id, s in self._latest_snapshots.items()
            },
            self.quota_state_path,
        )

        # Save Markdown report
        generate_markdown_report(statuses, self.status_report_path)

    async def _run_loop(self) -> None:
        """Background loop."""
        # Initial wait of 5s on startup
        await asyncio.sleep(5)
        while self._running:
            try:
                await self.refresh_all()
            except Exception as e:
                logger.error(f"Error in quota monitor loop: {e}")
            await asyncio.sleep(self.interval)
