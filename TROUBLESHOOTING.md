# Troubleshooting Guide — Antigravity Gateway

This guide covers common operational challenges, upstream Google API errors, and step-by-step remediation procedures.

---

## 1. HTTP 401 Unauthorized

### Symptom
Hermes or curl returns:
```json
{"error": {"message": "Invalid or missing Gateway API key", "type": "auth_error"}}
```

### Remediation
1. Verify `GATEWAY_API_KEY` in `.env` or `config.yaml`.
2. Verify Hermes request header contains `Authorization: Bearer <GATEWAY_API_KEY>`.
3. If hitting `/admin/*`, ensure you provide `ADMIN_API_KEY`, not the client key.

---

## 2. HTTP 429 RESOURCE_EXHAUSTED & Account Pool Exhausted

### Symptom
Gateway returns:
```json
{"error": {"message": "All available accounts exhausted or rate-limited...", "type": "account_pool_exhausted"}}
```

### Remediation
1. Run `agw health` to view active cooldowns across your accounts.
2. Check `docs/account-status.md` to see remaining quota and reset times.
3. Switch model families: rate-limits on Claude models do not affect Gemini models.
4. Add another Google account to your pool:
   ```bash
   agw accounts login
   ```
5. If an account is stuck in an unnecessary cooldown, clear it:
   ```bash
   curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" http://localhost:8999/admin/accounts/{id}/cooldown/clear
   ```

---

## 3. Upstream 400 INVALID_ARGUMENT (Schema Rejected)

### Symptom
Tool calls fail with 400 BAD REQUEST from Google upstream.

### Cause
Google Gemini function calling rejects non-standard JSON schema keywords (such as `anyOf`, `allOf`, `multipleOf`, `const`, `if/then/else`).

### Remediation
The gateway automatically scrubs these keywords using `agw/cloudcode/schema_sanitizer.py`. If a client passes custom nested schemas that bypass normalization, verify the tool definition in your agent adheres to standard JSON Schema object types.

---

## 4. `invalid_grant` / Revoked OAuth Token

### Symptom
Token refresh logs show:
```
OAuth refresh failed (400): {"error": "invalid_grant"}
```

### Remediation
The Google account password was changed, or the OAuth grant was revoked by Google.
1. Re-link the account:
   ```bash
   agw accounts login
   ```
2. Or delete the revoked account:
   ```bash
   agw accounts remove <account_id>
   ```

---

## 5. `loadCodeAssist failed across all endpoints: None`

### Symptom
Adding a new Google account fails during authorization callback:
```
loadCodeAssist failed across all endpoints: None
```

### Cause
The Google account has never been used in the official Antigravity IDE (or Gemini Code Assist), so Google has not yet provisioned a Cloud AI Companion Project (`cloudaicompanionProject`) or accepted the Terms of Service for that account.

### Remediation
1. Open the **Antigravity IDE** (or VS Code with Google Gemini Code Assist).
2. Sign into the IDE **once** with the new Google account and accept any Terms of Service prompt.
3. Once logged into the IDE, return to Antigravity Gateway and link the account (`agw accounts login` or via dashboard).
4. **Note:** You do not need to keep the IDE open or stay logged in after this one-time step.

