# Antigravity Multi-Account Gateway for Hermes Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Hermes Compatible](https://img.shields.io/badge/Hermes%20Agent-Compatible-orange.svg)](https://hermesagent.com)

A self-hosted, production-quality multi-account gateway that empowers **Hermes Agent** (and any standard OpenAI-compatible client) to leverage Google Antigravity-accessible **Gemini 3.5 Flash**, **Gemini 3.1 Pro**, and **Claude 4.6 (Sonnet & Opus)** models through a single, resilient endpoint (`/v1/chat/completions`).

The gateway operates as an intelligent multi-account orchestrator with encrypted OAuth credential persistence, real-time quota tracking, quota-aware smart scheduling, per-model-family isolated cooldowns, transparent automatic failover, an administrative dashboard, and a dedicated CLI (`agw`).

---

## Architecture Overview

```
                        Clients (Hermes Agent / Azure VM)
                                       │
                                       ▼
                       https://gateway.yourdomain.com/v1
                                       │
                        ┌──────────────┴──────────────┐
                        ▼                             ▼
                 [ /v1/models ]            [ /v1/chat/completions ]
                        │                             │
       ┌────────────────┴─────────────────────────────┴────────────────┐
       ▼                                                               ▼
[ Account Scheduler ] ◄── [ Quota Monitor ] ◄── [ Cooldown Manager ]
  - Health (weight: 2)     - Live polling via      - Isolated per-family
  - Tokens (weight: 5)       fetchAvailableModels  - Tiered backoff
  - Quota  (weight: 3)     - Markdown reporting    - 60s/300s/1800s/7200s
  - LRU    (weight: 0.1)   - Stale threshold       - Auto account failover
       │
       ▼
[ Encrypted Credential Vault ] (Fernet AES-256 at rest)
       │
┌──────┴───────────────────────────────────────────────────────┐
▼                              ▼                               ▼
Account 1                      Account 2                       Account N
(Personal Google Pro)          (Workspace Account)             (Secondary Account)
└──────┬───────────────────────┴───────────────────────────────┘
       ▼
Google Cloud Code Assist API (daily-cloudcode-pa / cloudcode-pa)
```

---

## Key Features

- 🔄 **Unified OpenAI Interface**: Full support for `/v1/models`, `/v1/chat/completions`, streaming SSE chunks, structured tool/function calling, multimodal vision, and reasoning tokens.
- 🛡️ **Zero Secret Leakage**: Strict redaction logging filter guarantees authorization tokens, client secrets, and refresh credentials never appear in server logs or stdout.
- 🔐 **Encrypted Vault**: OAuth refresh tokens are encrypted at rest using AES-256 (Fernet) with strict `0600` filesystem permissions separate from database metadata.
- ⚖️ **Quota-Aware Smart Scheduler**: Automatically selects the healthiest account with sufficient remaining quota using hybrid weighted scoring rather than naive round-robin.
- ❄️ **Isolated Cooldowns**: A rate limit (HTTP 429) encountered on Claude cools down **only** the Claude family for that account. Gemini models remain completely operational!
- ⚡ **Transparent Failover**: If an upstream error occurs, the gateway catches the exception, registers the cooldown, and retries the request across remaining eligible accounts seamlessly.
- 📊 **Real-Time Quota Monitor**: Periodically interrogates upstream quota metadata and generates live human- and Hermes-readable status reports in `docs/account-status.md`.
- 💻 **Admin Web Dashboard**: Glassmorphic dark-mode web console for monitoring accounts, quotas, cooldowns, and request metrics.
- ⌨️ **Administrative CLI (`agw`)**: Comprehensive CLI tool to list, add, remove, enable, disable, and refresh accounts.
- 🧠 **Dedicated Hermes Skills**: Pre-packaged operational skills (`antigravity-status`, `antigravity-quota`, `antigravity-accounts`, `antigravity-routing`, `antigravity-health`, `antigravity-troubleshooting`).

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/RareBat47/antigravity-gateway.git
cd antigravity-gateway

# Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Configuration

Copy the example environment file and customize your API keys:

```bash
cp .env.example .env
```

Key configuration options:
- `GATEWAY_API_KEY`: Secret key used by Hermes Agent / client requests.
- `ADMIN_API_KEY`: Secret key used for admin endpoints and the dashboard.
- `GATEWAY_PORT`: Port to listen on (default `8999`).

### 3. Connect a Google Account

Start the gateway:
```bash
uvicorn agw.main:app --host 0.0.0.0 --port 8999
```

Link an account via browser OAuth:
```bash
agw accounts login
```
Or open `http://localhost:8999/admin/dashboard` in your browser and click **+ Add Google Account**.

---

## Configuring Hermes Agent

Hermes Agent connects directly to the gateway as an OpenAI-compatible provider. In your Hermes `config.yaml` (typically in `~/.hermes/config.yaml`):

```yaml
model:
  provider: custom
  default: gemini-3.5-flash
  base_url: http://YOUR-GATEWAY-IP:8999/v1
  api_key: YOUR_GATEWAY_API_KEY

providers:
  custom:
    base_url: http://YOUR-GATEWAY-IP:8999/v1
    api_key: YOUR_GATEWAY_API_KEY
    api_mode: openai
```

---

## Supported Models

| Friendly Name | Upstream Model | Family | Capabilities | Max Output Tokens |
| :--- | :--- | :--- | :--- | :--- |
| `gemini-3.5-flash` | `gemini-3.5-flash-low` | Gemini | Tools, Streaming, Vision, Thinking | 65,536 |
| `gemini-3.1-pro` | `gemini-3.1-pro-low` | Gemini | Tools, Streaming, Vision, Thinking | 65,536 |
| `gemini-3-flash` | `gemini-3-flash` | Gemini | Tools, Streaming, Vision | 32,768 |
| `claude-sonnet-4-6` | `claude-sonnet-4-6` | Claude | Tools, Streaming, Vision | 16,384 |
| `claude-opus-4-6` | `claude-opus-4-6-thinking` | Claude | Tools, Streaming, Vision, Thinking | 16,384 |

---

## Testing

Run the full automated test suite:

```bash
pytest -v
```

---

## Documentation Index

- [ARCHITECTURE.md](ARCHITECTURE.md) — Subsystem architecture and message flow
- [SECURITY.md](SECURITY.md) — Threat model, zero-secret logging, and cryptographic design
- [OPERATIONS.md](OPERATIONS.md) — Systemd service, deployment, and maintenance
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Root-cause fixes for 401, 429, and 400 errors
- [API.md](API.md) — Complete OpenAPI & Admin REST API reference
- [ACCOUNT-MANAGEMENT.md](ACCOUNT-MANAGEMENT.md) — Multi-account lifecycle and PKCE auth
- [QUOTA-MONITORING.md](QUOTA-MONITORING.md) — Upstream quota interrogation and tracking
- [HERMES-INTEGRATION.md](HERMES-INTEGRATION.md) — Hermes Agent configuration and skills
- [DECISIONS.md](DECISIONS.md) — Architecture decision records (ADRs)

---

## License

MIT License. Copyright (c) 2026 RareBat47.
