# Quota Monitoring Guide — Antigravity Gateway

This document explains how the Antigravity Gateway interrogates Google Cloud Code Assist APIs to extract quota percentages, windows, and reset times.

---

## 1. Upstream Quota Discovery Mechanism

The gateway calls the internal RPC endpoint:
`POST https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels`
with the payload:
```json
{"project": "companion-project-id"}
```

The upstream API returns a dictionary of models, each containing a `quotaInfo` object:
```json
{
  "models": {
    "gemini-3.5-flash-low": {
      "displayName": "Gemini 3.5 Flash",
      "quotaInfo": {
        "remainingFraction": 0.854,
        "resetTime": "2026-09-20T06:00:00Z"
      }
    }
  }
}
```

- `remainingFraction`: Float between `0.0` (exhausted) and `1.0` (100% full).
- `resetTime`: ISO timestamp when the current window resets.

---

## 2. Background Quota Monitor Loop

- The `QuotaMonitor` runs as an asynchronous background loop every 300 seconds (configurable via `QUOTA_POLL_INTERVAL_SECONDS`).
- For each enabled account, it polls the latest quota fractions.
- Appends historical snapshots to the `quota_snapshots` table in SQLite.
- Saves the current state as JSON in `data/quota-state.json`.
- Generates an up-to-date Markdown status report in `docs/account-status.md`.

---

## 3. Human and Agent Status Report (`docs/account-status.md`)

```markdown
# Antigravity Account Status

Updated: 2026-09-20 01:30 UTC

| Account | Gemini | Claude | Status | Cooldown |
| :--- | :---: | :---: | :--- | :--- |
| Personal Pro | 85% | 72% | healthy | none |
| Backup Account | 98% | 15% | healthy | none |
| Work Account | unknown | 88% | healthy | none |
```

Hermes Agent reads this file via the `antigravity-quota` skill to quickly determine model availability before making queries.
