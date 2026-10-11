"""Database repository for accounts, metrics, cooldowns, and logs."""

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiosqlite

from agw.db.schema import INIT_SCHEMA_SQL


class DatabaseRepository:
    """Async database repository using aiosqlite."""

    def __init__(self, db_path: str = "data/gateway.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """Execute schema DDL and configure SQLite for concurrent access."""
        async with aiosqlite.connect(self.db_path) as db:
            # Bug #22: WAL mode allows concurrent reads alongside a writer,
            # eliminating "database is locked" errors under parallel requests.
            # busy_timeout gives write operations a 5s grace window before failing.
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("PRAGMA synchronous=NORMAL")  # Safe with WAL
            await db.executescript(INIT_SCHEMA_SQL)
            await db.commit()

    # --- Account Operations ---

    async def upsert_account(
        self,
        account_id: str,
        email_safe: str,
        display_name: Optional[str] = None,
        project_id: Optional[str] = None,
        tier: str = "unknown",
        status: str = "active",
        enabled: bool = True,
    ) -> None:
        """Insert or update account record."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO accounts (id, email_safe, display_name, project_id, tier, status, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    email_safe=CASE WHEN excluded.email_safe IN ('revoked', '') THEN accounts.email_safe ELSE excluded.email_safe END,
                    display_name=coalesce(excluded.display_name, accounts.display_name),
                    project_id=coalesce(excluded.project_id, accounts.project_id),
                    tier=CASE WHEN excluded.tier = 'unknown' THEN accounts.tier ELSE excluded.tier END,
                    status=excluded.status,
                    enabled=excluded.enabled,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (account_id, email_safe, display_name, project_id, tier, status, 1 if enabled else 0),
            )
            await db.commit()

    async def update_account_status(
        self,
        account_id: str,
        status: str,
        enabled: Optional[bool] = None,
    ) -> None:
        """Update account status and optionally enable/disable without overwriting profile/metadata."""
        async with aiosqlite.connect(self.db_path) as db:
            if enabled is not None:
                await db.execute(
                    "UPDATE accounts SET status = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, 1 if enabled else 0, account_id),
                )
            else:
                await db.execute(
                    "UPDATE accounts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, account_id),
                )
            await db.commit()

    async def update_account_profile(
        self,
        account_id: str,
        email_safe: str,
        display_name: Optional[str] = None,
    ) -> None:
        """Update account email and display name."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET email_safe = ?, display_name = coalesce(?, display_name), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (email_safe, display_name, account_id),
            )
            await db.commit()

    async def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Fetch single account by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_accounts(self) -> List[Dict[str, Any]]:
        """List all registered accounts."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM accounts ORDER BY created_at ASC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def set_account_enabled(self, account_id: str, enabled: bool) -> None:
        """Enable or disable account."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (1 if enabled else 0, account_id),
            )
            await db.commit()

    async def delete_account(self, account_id: str) -> None:
        """Delete account record and associated data."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            await db.commit()

    async def record_account_usage(
        self,
        account_id: str,
        tokens: int,
        success: bool,
    ) -> None:
        """Update account stats upon request completion."""
        async with aiosqlite.connect(self.db_path) as db:
            if success:
                await db.execute(
                    """
                    UPDATE accounts SET
                        last_used_at = CURRENT_TIMESTAMP,
                        last_success_at = CURRENT_TIMESTAMP,
                        consecutive_failures = 0,
                        total_requests = total_requests + 1,
                        total_tokens = total_tokens + ?
                    WHERE id = ?
                    """,
                    (tokens, account_id),
                )
            else:
                await db.execute(
                    """
                    UPDATE accounts SET
                        last_used_at = CURRENT_TIMESTAMP,
                        last_failure_at = CURRENT_TIMESTAMP,
                        consecutive_failures = consecutive_failures + 1,
                        total_requests = total_requests + 1
                    WHERE id = ?
                    """,
                    (account_id,),
                )
            await db.commit()

    # --- Credential Metadata ---

    async def update_token_metadata(
        self,
        account_id: str,
        expires_at: int,
        has_refresh_token: bool = True,
    ) -> None:
        """Update access token expiry."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO oauth_credentials_metadata (account_id, expires_at, has_refresh_token, last_refreshed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(account_id) DO UPDATE SET
                    expires_at = excluded.expires_at,
                    has_refresh_token = excluded.has_refresh_token,
                    last_refreshed_at = CURRENT_TIMESTAMP
                """,
                (account_id, expires_at, 1 if has_refresh_token else 0),
            )
            await db.commit()

    async def get_token_metadata(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get token expiry metadata."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM oauth_credentials_metadata WHERE account_id = ?", (account_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    # --- Cooldown Operations ---

    async def set_cooldown(
        self,
        account_id: str,
        target_family: str,
        duration_seconds: int,
        reason: str = "rate_limited",
    ) -> None:
        """Set or update cooldown until future timestamp."""
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration_seconds)
        until_str = until.strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO cooldowns (account_id, target_family, cooldown_until, reason, level)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(account_id, target_family) DO UPDATE SET
                    cooldown_until = excluded.cooldown_until,
                    reason = excluded.reason,
                    level = cooldowns.level + 1
                """,
                (account_id, target_family, until_str, reason),
            )
            await db.commit()

    async def get_active_cooldown(
        self, account_id: str, target_family: str
    ) -> Optional[Dict[str, Any]]:
        """Check if account is actively on cooldown for a model family or all families."""
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM cooldowns
                WHERE account_id = ? AND (target_family = ? OR target_family = 'all')
                  AND cooldown_until > ?
                ORDER BY cooldown_until DESC LIMIT 1
                """,
                (account_id, target_family, now_str),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_account_cooldowns(self, account_id: str) -> List[Dict[str, Any]]:
        """Fetch all currently active cooldowns for an account across all families."""
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM cooldowns WHERE account_id = ? AND cooldown_until > ? ORDER BY cooldown_until DESC",
                (account_id, now_str),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def clear_cooldown(self, account_id: str, target_family: Optional[str] = None) -> None:
        """Clear active cooldown."""
        async with aiosqlite.connect(self.db_path) as db:
            if target_family:
                await db.execute(
                    "DELETE FROM cooldowns WHERE account_id = ? AND target_family = ?",
                    (account_id, target_family),
                )
            else:
                await db.execute("DELETE FROM cooldowns WHERE account_id = ?", (account_id,))
            await db.commit()

    async def list_all_active_cooldowns(self) -> List[Dict[str, Any]]:
        """List all currently active cooldowns."""
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM cooldowns WHERE cooldown_until > ?", (now_str,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Quota Snapshots ---

    async def record_quota_snapshot(
        self,
        account_id: str,
        model_id: str,
        model_family: str,
        remaining_fraction: Optional[float],
        reset_time: Optional[str],
        source: str = "cloudcode",
    ) -> None:
        """Save a new quota record."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO quota_snapshots (account_id, model_id, model_family, remaining_fraction, reset_time, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (account_id, model_id, model_family, remaining_fraction, reset_time, source),
            )
            await db.commit()

    async def get_latest_quota(self, account_id: str) -> List[Dict[str, Any]]:
        """Get the latest quota snapshot for all models belonging to an account."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT q.* FROM quota_snapshots q
                INNER JOIN (
                    SELECT model_id, MAX(id) as max_id
                    FROM quota_snapshots
                    WHERE account_id = ?
                    GROUP BY model_id
                ) latest ON q.id = latest.max_id
                """,
                (account_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Usage & Health Events ---

    async def record_usage_event(
        self,
        request_id: str,
        account_id: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        status_code: int = 200,
        is_streaming: bool = False,
    ) -> None:
        """Log usage event for metrics and auditing."""
        total_tokens = prompt_tokens + completion_tokens
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO usage_events (request_id, account_id, model_id, prompt_tokens, completion_tokens, total_tokens, latency_ms, status_code, is_streaming)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, account_id, model_id, prompt_tokens, completion_tokens, total_tokens, latency_ms, status_code, 1 if is_streaming else 0),
            )
            await db.commit()

    async def record_health_event(
        self,
        account_id: str,
        event_type: str,
        error_message: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Record health check or execution result."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO health_events (account_id, event_type, error_message, latency_ms)
                VALUES (?, ?, ?, ?)
                """,
                (account_id, event_type, error_message, latency_ms),
            )
            await db.commit()

    async def get_usage_summary(self) -> Dict[str, Any]:
        """Aggregate usage metrics across all accounts."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as total_requests,
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(completion_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(latency_ms) as avg_latency_ms
                FROM usage_events
                """
            )
            row = await cursor.fetchone()
            res = dict(row) if row else {}
            return {k: (v if v is not None else 0) for k, v in res.items()}

    async def get_account_window_usage(
        self,
        account_id: str,
        hours: Optional[int] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Aggregate usage metrics for a specific account over a rolling window."""
        modifier = f"-{hours} hours" if hours is not None else (f"-{days} days" if days is not None else "-5 hours")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as requests,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(total_tokens) as total_tokens
                FROM usage_events
                WHERE account_id = ? AND created_at >= datetime('now', ?)
                """,
                (account_id, modifier),
            )
            row = await cursor.fetchone()
            res = dict(row) if row else {}
            return {
                "requests": res.get("requests") or 0,
                "prompt_tokens": res.get("prompt_tokens") or 0,
                "completion_tokens": res.get("completion_tokens") or 0,
                "total_tokens": res.get("total_tokens") or 0,
            }

