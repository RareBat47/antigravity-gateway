"""Per-account and per-model-family isolated cooldown manager."""

import datetime
from typing import Any, Dict, List, Optional
from agw.constants import QUOTA_EXHAUSTED_BACKOFF_TIERS_SECONDS
from agw.db.repository import DatabaseRepository


class CooldownManager:
    """Manages isolated cooldowns per account and model family."""

    def __init__(
        self,
        repo: DatabaseRepository,
        default_cooldown_seconds: int = 60,
        tiers: Optional[List[int]] = None,
    ):
        self.repo = repo
        self.default_cooldown = default_cooldown_seconds
        self.tiers = tiers or list(QUOTA_EXHAUSTED_BACKOFF_TIERS_SECONDS)
        self._consecutive_rate_limits: Dict[str, int] = {}  # key: f"{account_id}:{family}" -> count

    def _make_key(self, account_id: str, family: str) -> str:
        return f"{account_id}:{family}"

    async def record_rate_limit(
        self,
        account_id: str,
        family: str,
        explicit_delay_seconds: Optional[int] = None,
        reason: str = "rate_limit_429",
    ) -> int:
        """
        Record rate limit, advance backoff tier, and set cooldown.
        Returns duration in seconds.
        """
        key = self._make_key(account_id, family)
        streak = self._consecutive_rate_limits.get(key, 0)
        tier_idx = min(streak, len(self.tiers) - 1)
        tier_delay = self.tiers[tier_idx]

        duration = explicit_delay_seconds if (explicit_delay_seconds and explicit_delay_seconds > 0) else tier_delay
        self._consecutive_rate_limits[key] = streak + 1

        await self.repo.set_cooldown(
            account_id=account_id,
            target_family=family,
            duration_seconds=duration,
            reason=reason,
        )
        return duration

    async def record_success(self, account_id: str, family: str) -> None:
        """Reset consecutive rate limit counter on success."""
        key = self._make_key(account_id, family)
        if key in self._consecutive_rate_limits:
            self._consecutive_rate_limits[key] = max(0, self._consecutive_rate_limits[key] - 1)

    async def is_cooling_down(self, account_id: str, family: str) -> bool:
        """Check if account is cooling down for specific family or globally."""
        active = await self.repo.get_active_cooldown(account_id, family)
        return active is not None

    async def get_cooldown_details(
        self, account_id: str, family: str
    ) -> Optional[Dict[str, Any]]:
        """Get details of active cooldown."""
        return await self.repo.get_active_cooldown(account_id, family)

    async def clear(self, account_id: str, family: Optional[str] = None) -> None:
        """Clear active cooldown."""
        if family:
            self._consecutive_rate_limits.pop(self._make_key(account_id, family), None)
        else:
            to_del = [k for k in self._consecutive_rate_limits if k.startswith(f"{account_id}:")]
            for k in to_del:
                del self._consecutive_rate_limits[k]
        await self.repo.clear_cooldown(account_id, family)
