"""Hybrid Account Scheduler with quota awareness, health weighting, and failover."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from agw.config import SchedulerSettings
from agw.db.repository import DatabaseRepository
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker

logger = logging.getLogger("agw.scheduler")


class AccountScheduler:
    """Intelligently routes requests to the best available Antigravity account."""

    def __init__(
        self,
        repo: DatabaseRepository,
        cooldown_mgr: CooldownManager,
        health_tracker: AccountHealthTracker,
        settings: SchedulerSettings,
        vault: Any,
    ):
        self.repo = repo
        self.cooldown_mgr = cooldown_mgr
        self.health_tracker = health_tracker
        self.settings = settings
        self.vault = vault
        self._last_used_timestamps: Dict[str, float] = {}

    def _calculate_score(
        self,
        account: Dict[str, Any],
        model_family: str,
        quota_snapshot: Optional[Dict[str, Any]],
    ) -> float:
        """
        Calculate weighted score:
        score = (Health * w_h) + (TokenCapacity * w_t) + (Quota * w_q) + (LRU * w_lru)
        """
        acc_id = account["id"]
        w = self.settings.weights

        # 1. Health Score (0 - 100)
        health_score = self.health_tracker.get_health_score(acc_id)

        # 2. Token Capacity (Simulated token bucket or inverse consecutive failures)
        consec_failures = account.get("consecutive_failures", 0)
        token_score = max(0.0, 100.0 - (consec_failures * 30.0))

        # 3. Quota Score (0 - 100)
        quota_score = 50.0  # Default if unknown
        if quota_snapshot:
            # Check remaining fraction
            rem_frac = quota_snapshot.get("remaining_fraction")
            if rem_frac is not None:
                if rem_frac < self.settings.global_quota_threshold:
                    quota_score = (rem_frac * 100.0) - 100.0  # Heavy penalty while preserving relative quota order
                else:
                    quota_score = rem_frac * 100.0

        # 4. LRU Freshness
        last_used = self._last_used_timestamps.get(acc_id, 0.0)
        now = time.time()
        idle_seconds = max(0.0, now - last_used)
        # Normalize idle time (e.g. capped at 300 seconds -> 0 to 100)
        lru_score = min(100.0, (idle_seconds / 300.0) * 100.0)

        # Account priority boost
        priority_boost = (account.get("priority", 1) - 1) * 10.0

        total = (
            (health_score * w.health)
            + (token_score * w.tokens)
            + (quota_score * w.quota)
            + (lru_score * w.lru)
            + priority_boost
        )
        return total

    async def get_candidate_accounts(
        self,
        model_family: str,
        exclude_account_ids: Optional[List[str]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Filter and rank candidate accounts for the requested model family.
        Returns ranked list of (account_dict, score).
        """
        all_accounts = await self.repo.list_accounts()
        excluded = set(exclude_account_ids or [])
        candidates = []
        exhausted_candidates = []

        for acc in all_accounts:
            acc_id = acc["id"]
            if acc_id in excluded:
                continue

            # Must be enabled
            if not acc.get("enabled", 1):
                continue

            # Must have credentials in vault
            if not self.vault.has_token(acc_id):
                continue

            # Must not be on cooldown for this model family
            if await self.cooldown_mgr.is_cooling_down(acc_id, model_family):
                continue

            # Check latest quota
            quotas = await self.repo.get_latest_quota(acc_id)
            family_quotas = [q for q in quotas if q.get("model_family") == model_family]
            quota_record = family_quotas[0] if family_quotas else None

            is_exhausted = False
            # Check if critically exhausted (< threshold)
            if quota_record and quota_record.get("remaining_fraction") is not None:
                rem = quota_record["remaining_fraction"]
                if rem < self.settings.global_quota_threshold:
                    is_exhausted = True

            score = self._calculate_score(acc, model_family, quota_record)
            if is_exhausted:
                exhausted_candidates.append((acc, score))
            else:
                candidates.append((acc, score))

        # If healthy candidates are available, prefer them and skip exhausted accounts
        ranked = candidates if candidates else exhausted_candidates
        # Sort descending by score
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    async def select_account(
        self,
        model_family: str,
        exclude_account_ids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Select the single best account for a request."""
        candidates = await self.get_candidate_accounts(model_family, exclude_account_ids)
        if not candidates:
            return None

        best_account = candidates[0][0]
        self._last_used_timestamps[best_account["id"]] = time.time()
        return best_account
