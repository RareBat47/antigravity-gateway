# REST API Reference — Antigravity Gateway

This document provides the complete API specification for all public, client, and administrative endpoints.

---

## Public Endpoints

### 1. Health Check
`GET /health`
- **Auth**: None
- **Response**:
  ```json
  {
    "status": "ok",
    "active_accounts": 3,
    "total_accounts": 3,
    "total_requests": 5210
  }
  ```

---

## Client API (OpenAI-Compatible)
**Required Header**: `Authorization: Bearer <GATEWAY_API_KEY>`

### 2. List Models
`GET /v1/models`
- **Response**:
  ```json
  {
    "object": "list",
    "data": [
      {
        "id": "gemini-3.5-flash",
        "object": "model",
        "created": 1710000000,
        "owned_by": "antigravity-gateway",
        "description": "Google Gemini 3.5 Flash (Antigravity)"
      },
      {
        "id": "claude-sonnet-4-6",
        "object": "model",
        "created": 1710000000,
        "owned_by": "antigravity-gateway",
        "description": "Anthropic Claude 4.6 Sonnet via Antigravity"
      }
    ]
  }
  ```

### 3. Chat Completions
`POST /v1/chat/completions`
- **Request Body**: Standard OpenAI Chat Completion schema (`model`, `messages`, `stream`, `tools`, `tool_choice`, `temperature`, `max_tokens`).
- **Response**: Standard OpenAI `chat.completion` JSON object or SSE `text/event-stream`.
- **Response Headers**:
  - `x-agw-account`: ID of the account that fulfilled the request.

### 4. Usage Statistics
`GET /v1/usage`
- **Response**:
  ```json
  {
    "object": "usage",
    "total_usage": 4820194,
    "total_requests": 5210
  }
  ```

---

## Admin API
**Required Header**: `Authorization: Bearer <ADMIN_API_KEY>`

### 5. List Accounts
`GET /admin/accounts`

### 6. Add Account via Refresh Token
`POST /admin/accounts`
- **Body**:
  ```json
  {
    "refresh_token": "1//04...",
    "label": "account-2",
    "display_name": "Personal Pro Tier"
  }
  ```

### 7. Delete Account
`DELETE /admin/accounts/{account_id}`

### 8. Enable / Disable Account
`POST /admin/accounts/{account_id}/enable`
`POST /admin/accounts/{account_id}/disable`

### 9. Force Refresh Token
`POST /admin/accounts/{account_id}/refresh`

### 10. Get Account Quota
`GET /admin/accounts/{account_id}/quota`

### 11. System Health Report
`GET /admin/health`

### 12. Active Cooldowns
`GET /admin/cooldowns`
`POST /admin/accounts/{account_id}/cooldown/clear`

### 13. Admin Web Dashboard
`GET /admin/dashboard`
Serves the embedded glassmorphic administration web dashboard.
