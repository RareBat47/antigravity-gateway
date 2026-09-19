# Antigravity Gateway — Hermes Agent Complete Integration One-Pager

This is the all-in-one setup guide for integrating **Hermes Agent** (local or remote Azure VM) with **Antigravity Gateway**. It contains all role-based API keys, the setup prompt for Hermes, the complete 7-provider YAML configuration, tunnel setup, and verification tests.

---

## 1. Quick Gateway Overview

| Property | Value |
|---|---|
| **Protocol** | OpenAI-Compatible API (`/v1`) |
| **Base URL** | `http://127.0.0.1:8999/v1` (or your tunnel URL: `https://<YOUR_TUNNEL>/v1`) |
| **Admin Dashboard** | `http://127.0.0.1:8999/admin/dashboard` |
| **Master Admin Key** | `agw-admin-super-secret-key-change-me` |
| **Master Gateway Key** | `agw-hermes-secret-key-change-me` |
| **Capabilities** | Multi-account failover, Live quota monitoring, Streaming SSE (`stream: true`), Function/Tool calling (`tools`), Thinking/Reasoning (`reasoning_content`) |

---

## 2. All 7 Configured Role-Based API Keys

The gateway enforces model family permissions per key. If an agent tries to request a non-permitted model, the gateway safely returns `403 Forbidden` with a descriptive message.

| # | Role & Application | Provider Name | Allowed Families | API Key Token | Assigned Default Model | Reason / Optimization |
|---|---|---|---|---|---|---|
| **1** | **Planning Agent** | `Planning` | `claude` | `agw-plan-claude-9x82` | `claude-opus-4-6-thinking` | Deep architectural reasoning and long-horizon planning |
| **2** | **Coding Worker 1** | `Coding-1` | `gemini` | `agw-code-gemini-1-7b41` | `gemini-3.6-flash-low` | High-volume implementation, quick iterations (`gemini-3.8-flash-tiered` low) |
| **3** | **Coding Worker 2** | `Coding-2` | `gemini` | `agw-code-gemini-2-3f19` | `gemini-3.6-flash-medium` | General coding + agentic work (`gemini-3.8-flash-tiered` medium) |
| **4** | **Coding Worker 3** | `Coding-3` | `gemini` | `agw-code-gemini-3-8d52` | `gemini-3.6-flash-high` | Difficult implementation, refactors, multi-file reasoning (`gemini-3.8-flash-tiered` high) |
| **5** | **Coding Hybrid 1** | `Hybrid-1` | `gemini`, `gpt` | `agw-code-hybrid-1-4a29` | `gemini-pro-agent` | Strong Google agent-oriented alternative |
| **6** | **Coding Hybrid 2** | `Hybrid-2` | `claude`, `gemini`, `gpt` | `agw-code-hybrid-2-6e83` | `claude-sonnet-4-6` | Independent Claude coding path |
| **7** | **Debugging Agent** | `Debugging` | `all` (`claude`, `gemini`, `gpt`) | `agw-debug-all-9c37` | `claude-opus-4-6-thinking` | Deep root-cause analysis and difficult debugging |

---

## 3. Hermes Agent Setup Prompt (Feed to Hermes Agent)

Copy and paste this entire block directly into your Hermes Agent session or system prompt:

```text
You are connected to an Antigravity Multi-Account Gateway running at `http://127.0.0.1:8999/v1`.
The gateway provides 7 specialized role-based providers with model family permissions. Please configure your internal routing according to these exact provider names and model assignments:

1. PLANNING TASKS:
   - Provider Name: "Planning"
   - Base URL: "http://127.0.0.1:8999/v1"
   - API Key: "agw-plan-claude-9x82"
   - Model: "claude-opus-4-6-thinking" (also supports "claude-sonnet-4-6")
   - Role: Deep architectural reasoning, long-horizon planning, and system design.

2. HIGH-VOLUME CODING & AGENTIC WORK (Tiered Gemini Flash):
   - Provider "Coding-1": Key "agw-code-gemini-1-7b41", Model "gemini-3.6-flash-low" (High-volume implementation, quick iterations)
   - Provider "Coding-2": Key "agw-code-gemini-2-3f19", Model "gemini-3.6-flash-medium" (General coding + agentic work)
   - Provider "Coding-3": Key "agw-code-gemini-3-8d52", Model "gemini-3.6-flash-high" (Difficult implementation, refactors, multi-file reasoning)
   - Base URL: "http://127.0.0.1:8999/v1"

3. HYBRID AGENTS:
   - Provider "Hybrid-1": Key "agw-code-hybrid-1-4a29", Model "gemini-pro-agent" (Strong Google agent-oriented alternative)
   - Provider "Hybrid-2": Key "agw-code-hybrid-2-6e83", Model "claude-sonnet-4-6" (Independent Claude coding path)
   - Base URL: "http://127.0.0.1:8999/v1"

4. DEBUGGING & ROOT CAUSE ANALYSIS (All Models Allowed):
   - Provider Name: "Debugging"
   - Base URL: "http://127.0.0.1:8999/v1"
   - API Key: "agw-debug-all-9c37"
   - Model: "claude-opus-4-6-thinking" (also supports "gemini-3.6-flash-high", "claude-sonnet-4-6", "gpt-4o")
   - Role: Deep root-cause analysis, complex bug diagnosing, and stack trace investigations.

Always include "Authorization: Bearer <API_KEY>" and use streaming ("stream": true) with OpenAI tool calling.
```

---

## 4. Hermes Agent Configuration (`~/.hermes/config.yaml`)

Add this complete provider block to your Hermes Agent configuration file:

```yaml
providers:
  # 1. Planning (Claude Opus 4.6 Thinking)
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

## 5. Environment Variables Setup (`.env`)

For environments that load configuration via `.env`:

```bash
# Gateway Base Endpoint
OPENAI_BASE_URL="http://127.0.0.1:8999/v1"

# Planning:
# OPENAI_API_KEY="agw-plan-claude-9x82"
# DEFAULT_MODEL="claude-opus-4-6-thinking"

# Coding-1:
# OPENAI_API_KEY="agw-code-gemini-1-7b41"
# DEFAULT_MODEL="gemini-3.6-flash-low"

# Coding-2:
# OPENAI_API_KEY="agw-code-gemini-2-3f19"
# DEFAULT_MODEL="gemini-3.6-flash-medium"

# Coding-3:
# OPENAI_API_KEY="agw-code-gemini-3-8d52"
# DEFAULT_MODEL="gemini-3.6-flash-high"

# Hybrid-1:
# OPENAI_API_KEY="agw-code-hybrid-1-4a29"
# DEFAULT_MODEL="gemini-pro-agent"

# Hybrid-2:
# OPENAI_API_KEY="agw-code-hybrid-2-6e83"
# DEFAULT_MODEL="claude-sonnet-4-6"

# Debugging:
# OPENAI_API_KEY="agw-debug-all-9c37"
# DEFAULT_MODEL="claude-opus-4-6-thinking"
```

---

## 6. Remote Azure VM Tunnel Setup

If Hermes Agent is on an Azure VM and the Antigravity Gateway is running on your local Windows machine:

### Option 1: Cloudflare Tunnel (Recommended — Automatic HTTPS)
1. On your Windows machine, run:
   ```powershell
   winget install Cloudflare.cloudflared
   cloudflared tunnel --url http://127.0.0.1:8999
   ```
2. Copy the generated public URL: `https://<YOUR_TUNNEL>.trycloudflare.com`.
3. In Hermes on Azure, set `base_url`:
   ```yaml
   base_url: "https://<YOUR_TUNNEL>.trycloudflare.com/v1"
   ```

### Option 2: Reverse SSH Tunnel
1. On your Windows workstation:
   ```powershell
   ssh -N -R 8999:localhost:8999 azureuser@<AZURE_VM_IP>
   ```
2. In Hermes on Azure, use localhost:
   ```yaml
   base_url: "http://127.0.0.1:8999/v1"
   ```

---

## 7. Verification cURL Tests

### Test Planning Key (Claude Opus Thinking):
```bash
curl http://127.0.0.1:8999/v1/chat/completions \
  -H "Authorization: Bearer agw-plan-claude-9x82" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-opus-4-6-thinking", "messages": [{"role": "user", "content": "Ping"}]}'
```

### Test Coding-1 Key (Gemini Flash Low):
```bash
curl http://127.0.0.1:8999/v1/chat/completions \
  -H "Authorization: Bearer agw-code-gemini-1-7b41" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini-3.6-flash-low", "messages": [{"role": "user", "content": "Ping"}]}'
```

### Test Hybrid-1 Key (Gemini Pro Agent):
```bash
curl http://127.0.0.1:8999/v1/chat/completions \
  -H "Authorization: Bearer agw-code-hybrid-1-4a29" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini-pro-agent", "messages": [{"role": "user", "content": "Ping"}]}'
```

### Test Hybrid-2 Key (Claude Sonnet 4.6):
```bash
curl http://127.0.0.1:8999/v1/chat/completions \
  -H "Authorization: Bearer agw-code-hybrid-2-6e83" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "Ping"}]}'
```

### Test Debugging Key (Claude Opus Thinking):
```bash
curl http://127.0.0.1:8999/v1/chat/completions \
  -H "Authorization: Bearer agw-debug-all-9c37" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-opus-4-6-thinking", "messages": [{"role": "user", "content": "Diagnose: connection refused"}]}'
```

