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


def is_developer_facing_model(model_id: str) -> bool:
    """Filter out internal preview IDs that pollute quota calculations."""
    mid = model_id.lower()
    return not mid.startswith(("chat_", "tab_", "inline_", "completion_"))


def classify_model_family(model_id: str) -> str:
    """Accurately classify upstream model family."""
    mid = model_id.lower()
    if "claude" in mid:
        return FAMILY_CLAUDE
    if "gpt" in mid:
        return "gpt"
    return FAMILY_GEMINI


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

    def _recalculate_snapshot_fractions(self, snapshot: AccountQuotaSnapshot) -> None:
        """Recalculate weighted fractions using developer-facing models."""
        gemini_dev = []
        gemini_pro = []
        gemini_flash = []
        claude_dev = []
        gemini_resets = []
        claude_resets = []

        now_utc = datetime.datetime.now(datetime.timezone.utc)

        for mid, m in snapshot.models.items():
            fam = m.model_family
            rem = m.remaining_fraction
            reset_t = m.reset_time

            # Check if reset time has already passed
            if rem is not None and rem < 0.05 and reset_t:
                try:
                    r_dt = datetime.datetime.fromisoformat(reset_t.replace("Z", "+00:00"))
                    if now_utc >= r_dt:
                        # Reset has occurred
                        rem = 0.8
                        m.remaining_fraction = 0.8
                except Exception:
                    pass

            if is_developer_facing_model(mid):
                if fam == FAMILY_CLAUDE and rem is not None:
                    claude_dev.append(rem)
                    if reset_t and rem < 0.95:
                        claude_resets.append(reset_t)
                elif fam == FAMILY_GEMINI and rem is not None:
                    gemini_dev.append(rem)
                    if "pro" in mid.lower():
                        gemini_pro.append(rem)
                    if "flash" in mid.lower():
                        gemini_flash.append(rem)
                    if reset_t and rem < 0.95:
                        gemini_resets.append(reset_t)

        snapshot.gemini_average_fraction = sum(gemini_dev) / len(gemini_dev) if gemini_dev else None
        snapshot.claude_average_fraction = sum(claude_dev) / len(claude_dev) if claude_dev else None
        snapshot.gemini_pro_fraction = sum(gemini_pro) / len(gemini_pro) if gemini_pro else snapshot.gemini_average_fraction
        snapshot.gemini_flash_fraction = sum(gemini_flash) / len(gemini_flash) if gemini_flash else snapshot.gemini_average_fraction
        snapshot.gemini_reset_time = sorted(gemini_resets)[0] if gemini_resets else None
        snapshot.claude_reset_time = sorted(claude_resets)[0] if claude_resets else None

    def record_reactive_exhaustion(
        self, account_id: str, model_id: str, family: str, reset_time: str
    ) -> None:
        """Immediately update in-memory snapshot upon live upstream 429 rate limit."""
        snap = self._latest_snapshots.get(account_id)
        if snap:
            info = snap.models.get(model_id) or ModelQuotaInfo(
                model_id=model_id,
                model_family=family,
                remaining_fraction=0.0,
                reset_time=reset_time,
                source="reactive_429",
            )
            info.remaining_fraction = 0.0
            info.reset_time = reset_time
            info.last_checked = datetime.datetime.now(datetime.timezone.utc)
            snap.models[model_id] = info
            self._recalculate_snapshot_fractions(snap)

    async def refresh_account(self, account_id: str) -> Optional[AccountQuotaSnapshot]:
        """Poll and update quota for a single account."""
        acc = await self.repo.get_account(account_id)
        if not acc:
            return None

        # Skip disabled accounts
        if not acc.get("enabled", 1):
            return self._latest_snapshots.get(account_id)

        try:
            token = await self.account_manager.get_access_token(account_id)
            project_id = acc.get("project_id")
            data = await self.client.fetch_available_models(token, project_id)
            models_data = data.get("models", {})

            model_quotas: Dict[str, ModelQuotaInfo] = {}

            for model_id, mdata in models_data.items():
                family = classify_model_family(model_id)
                q_info = mdata.get("quotaInfo", {})
                rem_frac = q_info.get("remainingFraction")
                reset_t = q_info.get("resetTime")

                if rem_frac is None and reset_t:
                    rem_frac = 0.0

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

            snapshot = AccountQuotaSnapshot(
                account_id=account_id,
                email_safe=acc.get("email_safe", ""),
                tier=acc.get("tier", "unknown"),
                models=model_quotas,
            )
            self._recalculate_snapshot_fractions(snapshot)
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
        try:
            save_quota_state_json(
                {
                    acc_id: (s.model_dump(mode="json") if hasattr(s, "model_dump") else s.dict())
                    for acc_id, s in self._latest_snapshots.items()
                },
                self.quota_state_path,
            )
        except Exception as e:
            # Bug #20: Don't crash the monitor loop on file write errors
            logger.warning(f"Failed to save quota state JSON: {e}")

        # Save Markdown report
        try:
            generate_markdown_report(statuses, self.status_report_path)
        except Exception as e:
            logger.warning(f"Failed to generate markdown report: {e}")

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
