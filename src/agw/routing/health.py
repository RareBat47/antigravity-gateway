"""Account health tracker and reliability scoring."""

import time
from typing import Dict, List


class AccountHealthTracker:
    """Tracks account health, latencies, and success scores."""

    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self._history: Dict[str, List[bool]] = {}  # account_id -> list of recent successes
        self._latencies: Dict[str, List[float]] = {}

    def record(self, account_id: str, success: bool, latency_ms: float = 0.0) -> None:
        """Record outcome of request."""
        if account_id not in self._history:
            self._history[account_id] = []
            self._latencies[account_id] = []

        hist = self._history[account_id]
        hist.append(success)
        if len(hist) > self.window_size:
            hist.pop(0)

        if latency_ms > 0:
            lats = self._latencies[account_id]
            lats.append(latency_ms)
            if len(lats) > self.window_size:
                lats.pop(0)

    def get_health_score(self, account_id: str) -> float:
        """Calculate health score between 0.0 and 100.0."""
        hist = self._history.get(account_id)
        if not hist:
            return 100.0  # Fresh account assumed healthy
        success_count = sum(1 for x in hist if x)
        return (success_count / len(hist)) * 100.0

    def get_avg_latency(self, account_id: str) -> float:
        """Return average recent latency in ms."""
        lats = self._latencies.get(account_id)
        if not lats:
            return 0.0
        return sum(lats) / len(lats)
