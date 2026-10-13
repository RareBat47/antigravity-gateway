"""Hybrid Account Scheduler with quota awareness, health weighting, and failover."""

import datetime
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
        self._in_flight_requests: Dict[str, int] = {}
        self._rr_index: int = 0

    def acquire_request(self, account_id: str) -> None:
        """Track in-flight concurrent request to penalize overloaded accounts."""
        self._in_flight_requests[account_id] = self._in_flight_requests.get(account_id, 0) + 1
        self._last_used_timestamps[account_id] = time.time()

    def release_request(self, account_id: str) -> None:
        """Release concurrent in-flight slot when request/stream finishes."""
        current = self._in_flight_requests.get(account_id, 1)
        self._in_flight_requests[account_id] = max(0, current - 1)

    def get_in_flight(self, account_id: str) -> int:
        """Return count of active requests executing on this account."""
        return self._in_flight_requests.get(account_id, 0)

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

        # 4. LRU Freshness (Enhanced with strong rotation factor)
        last_used = self._last_used_timestamps.get(acc_id, 0.0)
        now = time.time()
        idle_seconds = max(0.0, now - last_used)
        # Normalize idle time (e.g. capped at 120 seconds -> 0 to 100)
        lru_score = min(100.0, (idle_seconds / 120.0) * 100.0)

        # 5. Active In-Flight Penalty (Protects against concurrent session piling)
        in_flight = self._in_flight_requests.get(acc_id, 0)
        in_flight_penalty = in_flight * 80.0  # Massive penalty if currently serving another session

        # Account priority boost
        priority_boost = (account.get("priority", 1) - 1) * 10.0

        # Effective LRU multiplier: scaled up from 0.1 to 2.5 to ensure sessions fan out
        lru_weight = max(2.5, w.lru * 25.0)

        total = (
            (health_score * w.health)
            + (token_score * w.tokens)
            + (quota_score * w.quota)
            + (lru_score * lru_weight)
            + priority_boost
            - in_flight_penalty
        )
        return total

    async def get_candidate_accounts(
        self,
        model_family: str,
        exclude_account_ids: Optional[List[str]] = None,
        requested_model_id: Optional[str] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Filter and rank candidate accounts for the requested model family and specific model.
        Returns ranked list of (account_dict, score).
        """
        all_accounts = await self.repo.list_accounts()
        excluded = set(exclude_account_ids or [])
        candidates = []
        exhausted_candidates = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)

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
            quota_record = None

            # 1. Match specific upstream model if requested (highest priority — exact match)
            if requested_model_id:
                for q in quotas:
                    if q.get("model_id") == requested_model_id:
                        quota_record = q
                        break

            # 2. If exact upstream model had rem=0 but reset_time has elapsed, treat as recovered
            if quota_record and quota_record.get("remaining_fraction", 1.0) < self.settings.global_quota_threshold:
                reset_t = quota_record.get("reset_time")
                if reset_t:
                    try:
                        r_dt = datetime.datetime.fromisoformat(reset_t.replace("Z", "+00:00"))
                        if now_utc >= r_dt:
                            # Window has rolled over — treat as recovered, don't penalize
                            quota_record = dict(quota_record)
                            quota_record["remaining_fraction"] = 0.8
                    except Exception:
                        pass

            # 3. If no exact match found, fall back to the BEST (highest remaining) dev-facing
            #    quota for the family — NOT the worst (min) — to avoid one exhausted model
            #    poisoning the whole account for the family.
            if not quota_record:
                dev_quotas = [
                    q for q in quotas
                    if q.get("model_family") == model_family
                    and not str(q.get("model_id", "")).lower().startswith(("chat_", "tab_", "inline_", "completion_"))
                    and q.get("remaining_fraction") is not None
                ]
                if dev_quotas:
                    # Use the HIGHEST remaining fraction — one exhausted model shouldn't
                    # mark the whole account unavailable for other models in the family.
                    dev_quotas.sort(key=lambda x: x["remaining_fraction"], reverse=True)
                    quota_record = dev_quotas[0]
                else:
                    family_quotas = [q for q in quotas if q.get("model_family") == model_family]
                    quota_record = family_quotas[0] if family_quotas else None

            is_exhausted = False
            # Check if critically exhausted (< threshold)
            if quota_record and quota_record.get("remaining_fraction") is not None:
                rem = quota_record["remaining_fraction"]
                reset_t = quota_record.get("reset_time")
                # Check if reset time has already elapsed (belt-and-suspenders for fallback path)
                if rem < self.settings.global_quota_threshold and reset_t:
                    try:
                        r_dt = datetime.datetime.fromisoformat(reset_t.replace("Z", "+00:00"))
                        if now_utc >= r_dt:
                            # Quota window has rolled over — treat as recovered
                            rem = 0.8
                            quota_record = dict(quota_record)
                            quota_record["remaining_fraction"] = 0.8
                    except Exception:
                        pass

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
        requested_model_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Select the optimal account using Least-Connections + LRU Idle Rotation.
        Guarantees that multiple concurrent sessions fan out across all healthy accounts.
        """
        candidates = await self.get_candidate_accounts(
            model_family=model_family,
            exclude_account_ids=exclude_account_ids,
            requested_model_id=requested_model_id,
        )
        if not candidates:
            return None

        # Filter for viable candidates (non-negative score)
        viable = [c for c in candidates if c[1] > 0]
        pool = viable if viable else candidates

        # Multi-session load balancing sort:
        # 1. Least active in-flight requests (primary: 0 active wins over 1 active)
        # 2. Oldest last-used timestamp (secondary: idle longer wins)
        # 3. Overall health & quota score (tertiary: higher wins)
        def sort_key(item):
            acc, score = item
            aid = acc["id"]
            in_flight = self._in_flight_requests.get(aid, 0)
            last_used = self._last_used_timestamps.get(aid, 0.0)
            return (in_flight, last_used, -score)

        pool.sort(key=sort_key)
        best_account = pool[0][0]

        # Instantly acquire in-flight slot so rapid concurrent requests disperse
        self.acquire_request(best_account["id"])
        return best_account
