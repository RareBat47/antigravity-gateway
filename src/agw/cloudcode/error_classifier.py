"""Intelligent failure and error classification for upstream Google API responses."""

import re
from typing import Optional, Tuple


class UpstreamErrorClassification:
    AUTH_ERROR = "AUTH_ERROR"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_GRANT = "INVALID_GRANT"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNKNOWN = "UNKNOWN"

    ACTION_FAILOVER = "failover"
    ACTION_COOLDOWN_AND_FAILOVER = "cooldown_and_failover"
    ACTION_REFRESH_TOKEN = "refresh_token"
    ACTION_DISABLE_ACCOUNT = "disable_account"
    ACTION_RETRY_BACKOFF = "retry_backoff"
    ACTION_RETURN_ERROR = "return_error"


def parse_quota_reset_delay(error_text: str) -> Optional[int]:
    """Extract wait duration in seconds from upstream rate-limit message."""
    if not error_text:
        return None

    # Matches: quotaResetDelay: 750.5ms or 2.5s
    m_delay = re.search(r'quotaResetDelay["\s:]+([0-9.]+)(ms|s)', error_text, re.IGNORECASE)
    if m_delay:
        val = float(m_delay.group(1))
        unit = m_delay.group(2).lower()
        return int(val / 1000.0) if unit == "ms" else max(1, int(val))

    # Matches: quota will reset after 120s or 5m
    m_reset = re.search(r'quota will reset after\s+([0-9]+)\s*(s|m|h)?', error_text, re.IGNORECASE)
    if m_reset:
        val = int(m_reset.group(1))
        unit = (m_reset.group(2) or "s").lower()
        if unit == "m":
            return val * 60
        elif unit == "h":
            return val * 3600
        return val

    return None


# Keywords that indicate the model schema / request itself is malformed — the
# error is permanent for THIS request and should not trigger account failover.
_PERMANENT_REQUEST_ERROR_PHRASES = (
    "thought_signature",
    "thoughtsignature",
    "function call is missing",
    "invalid json",
    "json schema",
    "schema validation",
    "unsupported field",
    "invalid argument",
    "unrecognized field",
)

# Keywords that indicate a per-account quota is exhausted — a different account
# should be tried (cooldown + failover), NOT a permanent error for the request.
_QUOTA_EXHAUSTED_PHRASES = (
    "resource_exhausted",
    "quota exceeded",
    "user quota",
    "rate limit",
    "too many requests",
    "quota limit",
)

# Phrases that indicate the account itself is permanently unusable.
_ACCOUNT_DISABLED_PHRASES = (
    "disabled",
    "terms of service",
    "violation",
    "account not found",
    "project not found",
    "project does not have access",
    "has not been used",
    "service not enabled",
    "account suspended",
    "billing disabled",
)


def classify_upstream_error(
    status_code: int,
    response_body: str,
) -> Tuple[str, str, int]:
    """
    Classify error into (category, recommended_action, cooldown_seconds).

    Priority order:
    1. Invalid grant — always disable account
    2. 401 Unauthenticated — always refresh token
    3. Account-disabled phrases in 403 — disable account
    4. Other 403 — cooldown and failover
    5. Permanent request errors (e.g. thought_signature) — return error to client
    6. Quota/rate exhaustion (429 or quota phrase) — cooldown and failover
    7. 5xx — retry with backoff
    8. Remaining 400s — return error to client
    9. Unknown — failover
    """
    body_lower = response_body.lower() if response_body else ""

    # --- 1. OAuth Revocation ---
    if "invalid_grant" in body_lower:
        return (
            UpstreamErrorClassification.INVALID_GRANT,
            UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT,
            86400,
        )

    # --- 2. Token Expired (unauthenticated) ---
    if status_code == 401 or "unauthenticated" in body_lower:
        return (
            UpstreamErrorClassification.TOKEN_EXPIRED,
            UpstreamErrorClassification.ACTION_REFRESH_TOKEN,
            5,
        )

    # --- 3 & 4. 403 Forbidden ---
    if status_code == 403 or "permission_denied" in body_lower:
        if any(phrase in body_lower for phrase in _ACCOUNT_DISABLED_PHRASES):
            return (
                UpstreamErrorClassification.ACCOUNT_DISABLED,
                UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT,
                86400 * 7,
            )
        return (
            UpstreamErrorClassification.AUTH_ERROR,
            UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER,
            300,
        )

    # --- 5. Permanent request-level errors (these are the CALLER's fault, not
    # the account's) — checking BEFORE the quota check because the body may
    # also contain "quota" text inside a thought_signature error message.
    if any(phrase in body_lower for phrase in _PERMANENT_REQUEST_ERROR_PHRASES):
        return (
            UpstreamErrorClassification.INVALID_ARGUMENT,
            UpstreamErrorClassification.ACTION_RETURN_ERROR,
            0,
        )

    # --- 6. Quota / Rate Limit exhaustion (account-level, try next account) ---
    if status_code == 429 or any(phrase in body_lower for phrase in _QUOTA_EXHAUSTED_PHRASES):
        delay = parse_quota_reset_delay(response_body)
        cooldown_sec = delay if (delay and delay > 0) else 60
        return (
            UpstreamErrorClassification.RATE_LIMITED,
            UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER,
            cooldown_sec,
        )

    # --- 7. 5xx Server Error ---
    if 500 <= status_code < 600:
        return (
            UpstreamErrorClassification.UPSTREAM_UNAVAILABLE,
            UpstreamErrorClassification.ACTION_RETRY_BACKOFF,
            10,
        )

    # --- 8. 400 Bad Request (no matching quota/permanent phrase above) ---
    if status_code == 400:
        return (
            UpstreamErrorClassification.INVALID_ARGUMENT,
            UpstreamErrorClassification.ACTION_RETURN_ERROR,
            0,
        )

    # --- 9. Unknown ---
    return (
        UpstreamErrorClassification.UNKNOWN,
        UpstreamErrorClassification.ACTION_FAILOVER,
        30,
    )
