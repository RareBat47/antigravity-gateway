# Account Management Guide — Antigravity Gateway

This document covers account registry design, OAuth authorization flows, credential storage security, and account lifecycle management.

---

## 1. Account Model & Storage

Accounts are partitioned cleanly into two tiers:

1. **Metadata Store (SQLite — `data/gateway.db`)**:
   - `id`: Internal unique account ID (e.g. `acc-8f2c3d1e`).
   - `email_safe`: Anonymized email representation (`use***@domain.com`).
   - `display_name`: Human-readable nickname.
   - `project_id`: Discovered Google Cloud Code companion project ID.
   - `tier`: Subscription tier (`free`, `pro`, `ultra`).
   - `status`: `active`, `degraded`, or `invalid_grant`.
   - `enabled`: Integer toggle (1 for enabled, 0 for disabled).
   - `consecutive_failures`: Failure streak counter for health scoring.
   - `total_requests`, `total_tokens`: Cumulative throughput.

2. **Credential Vault (`data/vault.enc`)**:
   - Encrypted dictionary mapping `account_id` to the encrypted OAuth `refresh_token`.
   - Never exposed via any API endpoint.

---

## 2. Adding Accounts

> **Important — Account Pre-activation**:
> Each Google Account must be signed into the **Antigravity IDE** (or VS Code with Gemini Code Assist) at least **once** prior to linking with the Gateway. This allows Google to provision the backing Companion Project (`cloudaicompanionProject`) and accept the Gemini Terms of Service. You do not need to keep the IDE open or stay logged in afterwards.

### Method 1: Interactive Browser Login (Recommended)
```bash
agw accounts login
```
Generates a PKCE challenge, opens your default browser to Google's consent screen, and listens for the authorization callback.

### Method 2: Headless / Remote Server Code Exchange
If running on an Azure VM without a local desktop browser:
1. Run `agw accounts login`.
2. Copy the displayed `auth_url` and open it in your local PC browser.
3. After granting consent, copy the authorization `code` parameter from the redirect URL.
4. Paste the code into the prompt on the remote VM.

### Method 3: Direct Refresh Token Enrollment
If you already possess an authorized OAuth refresh token:
```bash
agw accounts add --refresh-token "1//04..." --label "work-account" --display-name "Work Pro"
```

---

## 3. Account Lifecycle Management

- **Disable Account**: Prevents scheduler from routing requests to this account while preserving all tokens and historical usage.
  ```bash
  agw accounts disable <account_id>
  ```
- **Enable Account**: Returns account to the active scheduler candidate pool.
  ```bash
  agw accounts enable <account_id>
  ```
- **Force Token Refresh**: Refreshes access token immediately and tests upstream connectivity.
  ```bash
  agw accounts refresh <account_id>
  ```
- **Remove Account**: Deletes the account metadata from SQLite and permanently purges the refresh token from `vault.enc`.
  ```bash
  agw accounts remove <account_id>
  ```
