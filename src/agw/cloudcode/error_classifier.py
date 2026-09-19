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


def classify_upstream_error(
    status_code: int,
    response_body: str,
) -> Tuple[str, str, int]:
    """
    Classify error into (category, recommended_action, cooldown_seconds).
    """
    body_lower = response_body.lower() if response_body else ""

    # Invalid Grant (OAuth revoked / expired)
    if "invalid_grant" in body_lower:
        return (
            UpstreamErrorClassification.INVALID_GRANT,
            UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT,
            86400,
        )

    # 401 Unauthorized
    if status_code == 401 or "unauthenticated" in body_lower:
        return (
            UpstreamErrorClassification.TOKEN_EXPIRED,
            UpstreamErrorClassification.ACTION_REFRESH_TOKEN,
            5,
        )

    # 403 Forbidden
    if status_code == 403 or "permission_denied" in body_lower:
        if "disabled" in body_lower or "terms of service" in body_lower or "violation" in body_lower:
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

    # 429 Rate Limit / Quota Exceeded
    if status_code == 429 or "resource_exhausted" in body_lower or "quota" in body_lower:
        delay = parse_quota_reset_delay(response_body)
        cooldown_sec = delay if (delay and delay > 0) else 60
        return (
            UpstreamErrorClassification.RATE_LIMITED,
            UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER,
            cooldown_sec,
        )

    # 5xx Server Error
    if 500 <= status_code < 600:
        return (
            UpstreamErrorClassification.UPSTREAM_UNAVAILABLE,
            UpstreamErrorClassification.ACTION_RETRY_BACKOFF,
            10,
        )

    # 400 Bad Request
    if status_code == 400:
        return (
            UpstreamErrorClassification.INVALID_ARGUMENT,
            UpstreamErrorClassification.ACTION_RETURN_ERROR,
            0,
        )

    return (
        UpstreamErrorClassification.UNKNOWN,
        UpstreamErrorClassification.ACTION_FAILOVER,
        30,
    )
