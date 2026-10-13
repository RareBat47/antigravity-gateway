"""Dual-Layer Load Balancer for Antigravity Gateway.

Architecture:
  Level 1 (Provider Routing): Determines provider group (handy, agy, gweb, studio, gcli)
    based on model definition, request path, API key profile, and group health/capacity.
  Level 2 (Account & Key Selection): Selects specific healthy account and credential
    using Least-Connections, LRU rotation, and pre-flight telemetry checks.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from agw.telemetry.store import SharedTelemetryStore
from agw.routing.scheduler import AccountScheduler

logger = logging.getLogger("agw.routing.balancer")


class DualLayerLoadBalancer:
    """Orchestrates 2-tier load balancing between upstream groups and account credentials."""

    def __init__(
        self,
        scheduler: AccountScheduler,
        telemetry_store: SharedTelemetryStore,
    ):
        self.scheduler = scheduler
        self.telemetry = telemetry_store

    def resolve_level1_group(
        self,
        model_id: str,
        family: str,
        key_info: Optional[Dict[str, Any]] = None,
        model_def: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Level 1 Routing: Resolve which physical upstream pipe / provider group to target.
        Groups: 'handy' | 'agy' | 'gweb' | 'studio' | 'gcli'
        """
        m_lower = str(model_id).lower()
        key_prof = (key_info.get("profile") or "").lower() if key_info else ""
        m_prov = ((model_def or {}).get("provider_id") or "").lower()

        # Handy Media has dedicated models & prefix
        if family == "handy" or m_lower.startswith("handy-") or key_prof == "handy":
            return "handy"

        # AI Studio API keys channel
        if key_prof == "studio" or m_prov == "studio" or "studio" in m_lower:
            return "studio"

        # Gemini Web reverse-engineered session cookies
        if key_prof == "gweb" or m_prov == "gweb" or "web" in m_lower or "advanced" in m_lower:
            return "gweb"

        # Gemini Cloud CLI protocol
        if key_prof == "gcli" or m_prov == "gcli" or "code-assist" in m_lower:
            return "gcli"

        # Default is agy (Google Cloud Code OAuth engine)
        return "agy"

    async def select_level2_account(
        self,
        group: str,
        model_family: str,
        upstream_model_id: str,
        attempted_accounts: List[str],
        max_concurrent_leases: int = 8,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Level 2 Routing & Pre-Flight Check:
        1. Query scheduler for highest-scoring candidate account.
        2. Perform pre-flight lease check via SharedTelemetryStore.
        3. Hot-swap to next candidate if lease threshold exceeded.
        """
        candidates = await self.scheduler.get_candidate_accounts(
            model_family=model_family,
            exclude_account_ids=attempted_accounts,
            requested_model_id=upstream_model_id,
        )

        if not candidates:
            return None, "No candidate accounts available in pool"

        for acc, score in candidates:
            acc_id = acc["id"]

            # Pre-flight lease check on shared state store
            has_capacity = await self.telemetry.acquire_lease(
                account_id=acc_id,
                group=group,
                max_concurrent=max_concurrent_leases,
            )

            if not has_capacity:
                logger.debug(f"Account {acc_id} at max concurrent leases ({max_concurrent_leases}), trying next.")
                continue

            # Selected account with guaranteed pre-flight capacity
            self.scheduler.acquire_request(acc_id)
            return acc, None

        # If all candidates at max leases, fall back to best candidate without dropping request
        best_acc = candidates[0][0]
        self.scheduler.acquire_request(best_acc["id"])
        return best_acc, None

    async def release_execution(self, account_id: str, group: str) -> None:
        """Release concurrency lease and scheduler in-flight counter."""
        self.scheduler.release_request(account_id)
        await self.telemetry.release_lease(account_id, group)
