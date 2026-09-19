# Antigravity Multi-Account Gateway for Hermes Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI%20API-Compatible-412991.svg)](https://platform.openai.com/docs/api-reference)
[![Hermes Agent](https://img.shields.io/badge/Hermes%20Agent-Native%207--Provider-ff6b00.svg)](https://hermesagent.com)
[![Tests: 31 Passing](https://img.shields.io/badge/Tests-31%20Passing-success.svg)](tests/)

A self-hosted, production-grade multi-account proxy and load balancer that exposes Google Antigravity-accessible models (**Gemini 3.5 Flash**, **Gemini 3.6/3.8 Flash Tiered**, **Gemini 3.1 Pro**, **Gemini Pro Agent**, and **Claude 4.6 Opus Thinking & Sonnet**) through an OpenAI-compatible REST endpoint (`/v1/chat/completions`).

The gateway provides intelligent account scheduling, live quota tracking, isolated per-model-family cooldowns, transparent automatic failover, AES-256 encrypted credential vaults, strict zero-secret logging redaction, an administrative dashboard, and a dedicated CLI (`agw`).

---

## Table of Contents

- [Why Antigravity Gateway?](#why-antigravity-gateway)
- [Architecture & Request Lifecycle](#architecture--request-lifecycle)
- [Hermes Agent 7-Provider Matrix](#hermes-agent-7-provider-matrix)
- [Model Registry & Aliases](#model-registry--aliases)
- [Core Engineering Features](#core-engineering-features)
  - [1. Smart Quota-Aware Scheduling](#1-smart-quota-aware-scheduling)
  - [2. Isolated Per-Family Cooldowns](#2-isolated-per-family-cooldowns)
  - [3. Deep Reasoning & Thinking Token Streaming](#3-deep-reasoning--thinking-token-streaming)
  - [4. OpenAPI Tool Schema Sanitizer](#4-openapi-tool-schema-sanitizer)
  - [5. Zero-Leakage Credential Vault](#5-zero-leakage-credential-vault)
- [Installation & Quick Start](#installation--quick-start)
- [Hermes Agent Configuration](#hermes-agent-configuration)
- [Remote Tunneling (Windows Workstation to Azure VM)](#remote-tunneling-windows-workstation-to-azure-vm)
- [Admin Web Dashboard](#admin-web-dashboard)
- [CLI Reference (`agw`)](#cli-reference-agw)
- [API Reference](#api-reference)
- [Testing & Validation](#testing--validation)
- [Troubleshooting & Gotchas](#troubleshooting--gotchas)
- [Documentation Index](#documentation-index)
- [License](#license)

---

## Why Antigravity Gateway?

Autonomous coding agents like **Hermes Agent**, **LibreChat**, **Cline**, and **Cursor** require high context windows, deep reasoning, and aggressive tool calling capabilities. While Google Antigravity grants generous access to world-class Claude and Gemini models, relying on a single account or standard web interface presents serious challenges:

1. **Quota Throttles**: Single-account rate limits (HTTP 429) bring autonomous agent pipelines to a dead stop.
2. **Protocol Disparity**: Upstream Google Cloud Code Assist requires proprietary internal gRPC/JSON envelopes (`v1internal:generateContent`, `v1internal:streamGenerateContent`) that standard agentic frameworks cannot natively consume.
3. **Tool Calling & Schema Fragility**: Cloud Code rejects OpenAPI schemas containing keywords like `default`, `title`, `$ref`, or nested nullable unions (`anyOf`).
4. **Reasoning Collisions**: Thinking and reasoning tokens often pollute the assistant message text or crash parsers expecting plain text strings.

**Antigravity Gateway solves this by acting as a fault-tolerant intermediary.** It aggregates multiple Google accounts into a single high-throughput endpoint with seamless multi-turn streaming, robust tool calling, and automated account failover.

---

## Architecture & Request Lifecycle

```
                           Hermes Agent / IDE Clients / Azure VM
                                             │
                                             ▼
                             http://127.0.0.1:8999/v1
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
               [ /v1/models ]                           [ /v1/chat/completions ]
                       │                                           │
                       │                        ┌──────────────────┴──────────────────┐
                       │                        ▼                                     ▼
                       │               [ Auth Middleware ]                   [ Role-Key Validator ]
                       │               Validates Bearer token                Enforces model family permissions
                       │                        │
                       │                        ▼
                       │             [ Model Normalizer & Registry ]
                       │             Resolves aliases (e.g. claude-opus-4-6 -> claude-opus-4-6-thinking)
                       │                        │
                       └────────────────────────┼─────────────────────────────────────┐
                                                ▼                                     │
                                    [ Account Scheduler ]                             │
                                    Evaluates candidate accounts via:                 │
                                      • Health Score (weight: 2.0)                    │
                                      • Token Load Balancing (weight: 5.0)            │
                                      • Remaining Quota Fraction (weight: 3.0)        │
                                      • Least Recently Used (weight: 0.1)             │
                                                │
                                                ▼
                                    [ AES-256 Encrypted Vault ]
                                    Decrypts refresh token & acquires access token
                                                │
                                                ▼
                                    [ Protocol Mapper & Sanitizer ]
                                      • Sanitizes tool definitions (strips disallowed keys)
                                      • Alternates turns (user/assistant/function)
                                      • Extracts system prompts
                                                │
                                                ▼
                                    [ Cloud Code Client ]
                                    Dispatches to daily-cloudcode-pa / cloudcode-pa
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        ▼                                               ▼
             [ HTTP 200 OK Response ]                        [ Upstream 429 / 5xx Error ]
                        │                                               │
                        ▼                                               ▼
             [ Streaming SSE Parser ]                        [ Cooldown Manager ]
             • Emits reasoning_content delta                 • Records backoff tier for family
             • Emits content text delta                      • Auto-switches to next eligible account
             • Emits tool_calls with args                    • Retries transparently (up to 3x)
             • Finalizes with finish_reason
                        │
                        ▼
             Client Receives Response
```

---

## Hermes Agent 7-Provider Matrix

The gateway natively provides 7 role-specialized provider keys configured with strict model family permissions. This architecture allows Hermes Agent to distribute tasks across specialized roles without hitting rate limits on a single model family:

| Provider Name | API Key Token | Allowed Families | Default Model | Upstream Target | Role & Specialization |
|---|---|---|---|---|---|
| **`Planning`** | `agw-plan-claude-9x82` | `claude` | `claude-opus-4-6-thinking` | `claude-opus-4-6-thinking` | Deep architectural reasoning and long-horizon system planning |
| **`Coding-1`** | `agw-code-gemini-1-7b41` | `gemini` | `gemini-3.6-flash-low` | `gemini-3.6-flash-low` | High-volume implementation, quick edits, small iterations |
| **`Coding-2`** | `agw-code-gemini-2-3f19` | `gemini` | `gemini-3.6-flash-medium` | `gemini-3.6-flash-medium` | General coding, autonomous turn execution, repo exploration |
| **`Coding-3`** | `agw-code-gemini-3-8d52` | `gemini` | `gemini-3.6-flash-high` | `gemini-3.6-flash-high` | Difficult implementation, multi-file refactoring, reasoning |
| **`Hybrid-1`** | `agw-code-hybrid-1-4a29` | `gemini`, `gpt` | `gemini-pro-agent` | `gemini-pro-agent` | Strong Google agent-oriented alternative worker |
| **`Hybrid-2`** | `agw-code-hybrid-2-6e83` | `claude`, `gemini`, `gpt` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Independent Claude coding path |
| **`Debugging`** | `agw-debug-all-9c37` | `all` (`claude`, `gemini`, `gpt`) | `claude-opus-4-6-thinking` | `claude-opus-4-6-thinking` | Deep root-cause analysis, complex stack trace diagnoses |

---

## Model Registry & Aliases

The gateway exposes a built-in model registry that translates standard model IDs and common aliases into verified upstream identifiers:

| Model ID | Aliases Recognized | Upstream Target | Context Window | Max Output | Capabilities |
|---|---|---|---|---|---|
| `claude-opus-4-6-thinking` | `claude-opus-4-6`, `claude-opus`, `claude-3-opus`, `claude-3.0-opus` | `claude-opus-4-6-thinking` | 200,000 | 16,384 | Tools, Streaming, Vision, Thinking |
| `claude-sonnet-4-6` | `claude-3-7-sonnet`, `claude-3.7-sonnet`, `claude-3-5-sonnet`, `claude-3.5-sonnet`, `claude-sonnet` | `claude-sonnet-4-6` | 200,000 | 16,384 | Tools, Streaming, Vision |
| `gemini-3.8-flash-tiered` | `gemini-3.8-flash` | `gemini-3.8-flash-tiered` | 1,048,576 | 65,536 | Tools, Streaming, Vision, Thinking |
| `gemini-3.6-flash-low` | `gemini-3.8-flash-low`, `gemini-3.8-flash-tiered-low` | `gemini-3.6-flash-low` | 1,048,576 | 65,536 | Tools, Streaming, Vision |
| `gemini-3.6-flash-medium` | `gemini-3.8-flash-medium`, `gemini-3.8-flash-tiered-medium` | `gemini-3.6-flash-medium` | 1,048,576 | 65,536 | Tools, Streaming, Vision |
| `gemini-3.6-flash-high` | `gemini-3.8-flash-high`, `gemini-3.8-flash-tiered-high` | `gemini-3.6-flash-high` | 1,048,576 | 65,536 | Tools, Streaming, Vision, Thinking |
| `gemini-pro-agent` | — | `gemini-pro-agent` | 1,048,576 | 65,536 | Tools, Streaming, Vision, Thinking |
| `gemini-3.5-flash` | `gemini-flash` | `gemini-3.5-flash-low` | 1,048,576 | 65,536 | Tools, Streaming, Vision, Thinking |
| `gemini-3.1-pro` | `gemini-pro` | `gemini-3.1-pro-low` | 1,048,576 | 65,536 | Tools, Streaming, Vision, Thinking |
| `gemini-2.5-pro` | `gemini-1.5-pro` | `gemini-2.5-pro` | 1,048,576 | 32,768 | Tools, Streaming, Vision |
| `gemini-2.5-flash` | `gemini-1.5-flash` | `gemini-2.5-flash` | 1,048,576 | 32,768 | Tools, Streaming, Vision |
| `gpt-4o` | — | `gemini-2.5-pro` | 128,000 | 32,768 | Compatibility alias |

All models automatically strip the `models/` prefix if passed by client SDKs (e.g. `models/claude-opus-4-6`).

---

## Core Engineering Features

### 1. Smart Quota-Aware Scheduling

Rather than naive round-robin routing, the gateway evaluates candidate accounts dynamically per request using a hybrid weighted algorithm:

$$\text{Score} = w_{\text{health}} \cdot H - w_{\text{tokens}} \cdot \hat{T} + w_{\text{quota}} \cdot Q - w_{\text{lru}} \cdot \Delta t$$

- **Health Score ($H$)**: Success rate ratio over recent requests.
- **Token Load Balancing ($\hat{T}$)**: Normalized token consumption over the past hour.
- **Quota Fraction ($Q$)**: Live remaining quota percentage queried from upstream.
- **Exhaustion Guard**: When an account drops below `global_quota_threshold` (default 5%), a severe penalty is applied, prioritizing healthy accounts while maintaining relative ranking for emergency fallback.

### 2. Isolated Per-Family Cooldowns

Upstream rate limits are model-family specific:
- An account that encounters HTTP 429 on Claude is placed on cooldown **only for the `claude` family**.
- Its Gemini quota remains 100% active and available to serve requests.
- **Backoff Tier Escalation**: Cooldown durations escalate across progressive tiers (`60s` $\to$ `300s` $\to$ `1800s` $\to$ `7200s`) and are persisted in SQLite, surviving gateway reboots.

### 3. Deep Reasoning & Thinking Token Streaming

For reasoning models (`claude-opus-4-6-thinking`, `gemini-3.6-flash-high`, `gemini-3.5-flash`):
- Internal `thought` flags and reasoning parts are separated from standard output.
- Streaming chunks emit thinking text in standard `delta.reasoning_content` format.
- Thought tokens are strictly prevented from leaking into `delta.content`.
- The final SSE chunk reliably delivers `finish_reason: "stop"` or `finish_reason: "tool_calls"`.

### 4. OpenAPI Tool Schema Sanitizer

Google Cloud Code Assist imposes strict validation on function declarations. The gateway's built-in sanitizer cleans schemas before dispatch:
- Strips unsupported properties (`default`, `title`, `$ref`, `examples`, `example`).
- Resolves nullable unions: converts `anyOf: [{"type": "null"}, {"type": "string"}]` to `type: "string", nullable: true`.
- Enforces array items typing (assigns default `{"type": "string"}` if missing).
- Normalizes integer and boolean types.

### 5. Zero-Leakage Credential Vault

- **AES-256 Encryption**: Refresh tokens are stored encrypted using Fernet keys stored with `0600` permissions.
- **Database Safety**: The SQLite database only stores public metadata (`email_safe`, `display_name`, `tier`, usage statistics).
- **Log Masking**: Custom logging filters intercept and redact Bearer tokens, refresh tokens, and client secrets across all log sinks.

---

## Installation & Quick Start

### Prerequisites
- Python 3.11 or higher
- Git
- At least one Google Account with Antigravity / Cloud Code Assist access

### 1. Clone & Install
```bash
git clone https://github.com/RareBat47/antigravity-gateway.git
cd antigravity-gateway

# Set up virtual environment
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install package dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Configure Environment
```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Review `config.yaml` to ensure your admin and gateway keys are set.

### 3. Connect Your Google Account(s)
You can link accounts using the CLI or the Web Dashboard:

**Via CLI**:
```bash
python -m agw.cli.main accounts login
```
A browser window will open asking you to log into Google and grant Antigravity permissions.

**Via Dashboard**:
Start the server and visit `http://127.0.0.1:8999/admin/dashboard`, then click **+ Add Google Account**.

### 4. Launch Gateway Server
```bash
python -m uvicorn agw.main:app --host 127.0.0.1 --port 8999
```

---

## Hermes Agent Configuration

Copy and paste this provider configuration block directly into your Hermes configuration file (`~/.hermes/config.yaml`):

```yaml
providers:
  # 1. Planning Provider (Claude Opus 4.6 Thinking)
  Planning:
    type: openai
    base_url: "http://127.0.0.1:8999/v1"
    api_key: "agw-plan-claude-9x82"
    default_model: "claude-opus-4-6-thinking"
    models:
      - id: claude-opus-4-6-thinking
        name: "Anthropic Claude 4.6 Opus Thinking"
        capabilities: ["tools", "streaming", "thinking", "vision"]
      - id: claude-sonnet-4-6
        name: "Anthropic Claude 4.6 Sonnet"
        capabilities: ["tools", "streaming", "thinking", "vision"]

  # 2. Coding Worker 1 (Gemini Flash Low Tier)
  Coding-1:
    type: openai
    base_url: "http://127.0.0.1:8999/v1"
    api_key: "agw-code-gemini-1-7b41"
    default_model: "gemini-3.6-flash-low"
    models:
      - id: gemini-3.6-flash-low
        name: "Google Gemini 3.8 Flash (Low Tier)"
        capabilities: ["tools", "streaming", "vision"]
      - id: gemini-3.8-flash-tiered
        capabilities: ["tools", "streaming", "vision"]

  # 3. Coding Worker 2 (Gemini Flash Medium Tier)
  Coding-2:
    type: openai
    base_url: "http://127.0.0.1:8999/v1"
    api_key: "agw-code-gemini-2-3f19"
    default_model: "gemini-3.6-flash-medium"
    models:
      - id: gemini-3.6-flash-medium
        name: "Google Gemini 3.8 Flash (Medium Tier)"
        capabilities: ["tools", "streaming", "vision"]
      - id: gemini-3.8-flash-tiered
        capabilities: ["tools", "streaming", "vision"]

  # 4. Coding Worker 3 (Gemini Flash High Tier / Agent)
  Coding-3:
    type: openai
    base_url: "http://127.0.0.1:8999/v1"
    api_key: "agw-code-gemini-3-8d52"
    default_model: "gemini-3.6-flash-high"
    models:
      - id: gemini-3.6-flash-high
        name: "Google Gemini 3.8 Flash (High Tier / Agent)"
        capabilities: ["tools", "streaming", "thinking", "vision"]
      - id: gemini-3.8-flash-tiered
        capabilities: ["tools", "streaming", "thinking", "vision"]

  # 5. Hybrid Worker 1 (Gemini Pro Agent)
  Hybrid-1:
    type: openai
    base_url: "http://127.0.0.1:8999/v1"
    api_key: "agw-code-hybrid-1-4a29"
    default_model: "gemini-pro-agent"
    models:
      - id: gemini-pro-agent
        name: "Google Gemini Pro Agent"
        capabilities: ["tools", "streaming", "thinking", "vision"]

  # 6. Hybrid Worker 2 (Claude Sonnet 4.6)
  Hybrid-2:
    type: openai
    base_url: "http://127.0.0.1:8999/v1"
    api_key: "agw-code-hybrid-2-6e83"
    default_model: "claude-sonnet-4-6"
    models:
      - id: claude-sonnet-4-6
        name: "Anthropic Claude 4.6 Sonnet"
        capabilities: ["tools", "streaming", "vision"]

  # 7. Debugging Worker (Claude Opus 4.6 Thinking & All Models)
  Debugging:
    type: openai
    base_url: "http://127.0.0.1:8999/v1"
    api_key: "agw-debug-all-9c37"
    default_model: "claude-opus-4-6-thinking"
    models:
      - id: claude-opus-4-6-thinking
        name: "Anthropic Claude 4.6 Opus Thinking"
        capabilities: ["tools", "streaming", "thinking", "vision"]
      - id: gemini-3.6-flash-high
        capabilities: ["tools", "streaming", "thinking", "vision"]
      - id: claude-sonnet-4-6
        capabilities: ["tools", "streaming", "thinking", "vision"]
      - id: gpt-4o
        capabilities: ["tools", "streaming", "vision"]
```

---

## Remote Tunneling (Windows Workstation to Azure VM)

If Hermes Agent is hosted on a remote Azure VM and the Antigravity Gateway runs on your local workstation:

### Option A: Cloudflare Tunnel (Recommended)
Zero port forwarding, end-to-end HTTPS:
```powershell
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://127.0.0.1:8999
```
Copy the generated URL (e.g. `https://your-tunnel.trycloudflare.com`) and update `base_url` in Hermes:
```yaml
base_url: "https://your-tunnel.trycloudflare.com/v1"
```

### Option B: SSH Reverse Tunnel
From your local machine:
```powershell
ssh -N -R 8999:localhost:8999 azureuser@<AZURE_VM_IP>
```
In Hermes on the Azure VM, connect to localhost:
```yaml
base_url: "http://127.0.0.1:8999/v1"
```

---

## Admin Web Dashboard

Open `http://127.0.0.1:8999/admin/dashboard` in any browser to access the management interface:

- **Live Status Cards**: Total requests, token throughput, average latency, and active cooldown count.
- **Account Health Monitoring**: Health percentage bars, tier badges, and cooldown timers per account.
- **Live Account Actions**: Trigger manual OAuth re-authentication, refresh tokens, reset cooldowns, or delete accounts.
- **Configured API Keys Table**: View active role keys, allowed model families, and copy tokens with one click.
- **Hermes Setup Center**: One-click copyable YAML configurations, `.env` files, cURL tests, and downloadable markdown guides.

---

## CLI Reference (`agw`)

The `agw` CLI provides command-line control over gateway administration:

```bash
# List all accounts, tiers, and health metrics
python -m agw.cli.main accounts list

# Connect a new Google account via OAuth
python -m agw.cli.main accounts login

# Re-authenticate an existing account
python -m agw.cli.main accounts reauth <account_id>

# Refresh an account's OAuth token
python -m agw.cli.main accounts refresh <account_id>

# Enable or disable an account
python -m agw.cli.main accounts enable <account_id>
python -m agw.cli.main accounts disable <account_id>

# Clear active cooldowns for an account
python -m agw.cli.main accounts clear-cooldown <account_id>

# List all registered models and aliases
python -m agw.cli.main models

# Send a test completion request
python -m agw.cli.main test --model gemini-3.6-flash-low
python -m agw.cli.main test --model claude-opus-4-6-thinking

# View recent usage and request audit logs
python -m agw.cli.main logs
```

---

## API Reference

### OpenAI-Compatible Endpoints (`/v1`)

- `POST /v1/chat/completions`: Standard chat completion endpoint supporting `stream: true`, `tools`, and `tool_choice`.
- `GET /v1/models`: List all models and their capabilities in standard OpenAI format.

### Admin Endpoints (`/admin`) — Requires `ADMIN_API_KEY`

- `GET /admin/health`: Returns overall gateway health, total accounts, and active cooldowns.
- `GET /admin/usage`: Aggregated request counts, tokens served, and average response latency.
- `GET /admin/accounts`: Detailed list of connected accounts, quota status, and error logs.
- `GET /admin/api-keys`: List of configured role-based API keys and family permissions.
- `POST /admin/accounts/{id}/refresh`: Force an immediate OAuth token refresh.
- `POST /admin/accounts/{id}/cooldown/clear`: Reset active cooldowns for an account.
- `POST /admin/accounts/{id}/enable` / `POST /admin/accounts/{id}/disable`: Toggle account participation in scheduling.
- `DELETE /admin/accounts/{id}`: Remove an account and its credentials from the vault.

---

## Testing & Validation

The repository includes an extensive test suite verifying protocol compliance, schema handling, quota logic, and account persistence:

```bash
# Run all tests
pytest -v

# Run specific test modules
pytest tests/test_openai_protocol.py
pytest tests/test_streaming.py
pytest tests/test_schema_sanitizer.py
pytest tests/test_thinking_reasoning.py
pytest tests/test_multi_api_keys.py
pytest tests/test_quota_threshold_scheduling.py
```

### Live Test cURL Examples

```bash
# Test Planning Role (Claude Opus 4.6 Thinking)
curl http://127.0.0.1:8999/v1/chat/completions \
  -H "Authorization: Bearer agw-plan-claude-9x82" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-opus-4-6-thinking", "messages": [{"role": "user", "content": "Respond with OK"}]}'

# Test Coding-1 Role (Gemini 3.8 Flash Low)
curl http://127.0.0.1:8999/v1/chat/completions \
  -H "Authorization: Bearer agw-code-gemini-1-7b41" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini-3.6-flash-low", "messages": [{"role": "user", "content": "Respond with OK"}]}'
```

---

## Troubleshooting & Gotchas

| Symptom | Cause | Solution |
|---|---|---|
| **HTTP 403 Forbidden: "Model family not permitted"** | An API key attempted to request a model outside its `allowed_families`. | Check the key used against the [Provider Matrix](#hermes-agent-7-provider-matrix) or update `allowed_families` in `config.yaml`. |
| **HTTP 503: "All available accounts exhausted"** | All accounts are currently in cooldown or rate-limited. | Link additional Google accounts or clear cooldowns via `agw accounts clear-cooldown <id>`. |
| **HTTP 400: "Model not supported"** | Direct use of unmapped model identifier. | Use `claude-opus-4-6-thinking` instead of raw `claude-opus-4-6`. The gateway normalizes known aliases automatically. |
| **"Invalid grant" / 401 on token refresh** | Google OAuth refresh token has expired or was revoked. | Run `agw accounts reauth <account_id>` to re-authenticate the account. |
| **Tool calling schema error (400)** | Schema contains forbidden keys or missing array types. | Handled automatically by `SchemaSanitizer`. If using custom tools, ensure arrays declare an `items` type. |

---

## Documentation Index

- [HERMES-INTEGRATION.md](docs/HERMES-INTEGRATION.md) — Comprehensive one-pager integration guide for Hermes Agent
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Detailed subsystem architecture and data flow
- [SECURITY.md](docs/SECURITY.md) — Cryptographic vault design, zero-leak logging, and threat model
- [OPERATIONS.md](docs/OPERATIONS.md) — Deployment, systemd units, and production monitoring
- [ACCOUNT-MANAGEMENT.md](docs/ACCOUNT-MANAGEMENT.md) — OAuth2 authentication lifecycle and vault management
- [QUOTA-MONITORING.md](docs/QUOTA-MONITORING.md) — Upstream quota inspection and polling mechanisms
- [API.md](docs/API.md) — Full OpenAPI specification and Admin REST API documentation
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — Step-by-step diagnostic guide for errors and edge cases

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
