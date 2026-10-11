# Antigravity Gateway

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI%20API-Compatible-412991.svg)](https://platform.openai.com/docs/api-reference)
[![Anthropic Compatible](https://img.shields.io/badge/Anthropic%20API-Compatible-d97706.svg)](https://docs.anthropic.com/en/api/getting-started)
[![Models: Curated 7](https://img.shields.io/badge/Models-Curated%207%20Flagships-success.svg)](#the-curated-7-model-catalog)
[![Context: 1M Tokens](https://img.shields.io/badge/Context-1%2C000%2C000%20Tokens-purple.svg)](#provider-2--claude-5-1m-mega-context)

A high-performance, self-hosted local inference gateway and load balancer that aggregates multiple **authorized Google Antigravity accounts** into OpenAI-compatible (`/v1/chat/completions`) and Anthropic-compatible (`/v1/messages`) APIs. 

It powers a seamless **dual-agent workflow**: running **Claude Code** (as the high-reasoning **Developer Brain**) and **OpenCode** (as the high-speed **Coding Engine**) simultaneously on your PC with zero rate-limit collisions, intelligent quota failover, and hardware-grade credential security.

---

> [!IMPORTANT]
> ### 💡 Installation Philosophy: *Use Antigravity for Installing This Software*
> **The recommended and fastest way to install, configure, and maintain this gateway is to let Google Antigravity pair-program with you.**  
> Simply clone this repository, open your terminal with Antigravity (`agy`), and instruct the agent to run the setup commands. Antigravity handles the Python venvs, Node.js dependencies, OAuth token extraction, and model provider routing automatically.

---

## 🚀 Quick Setup & Getting Started

Follow these steps to get the gateway, Claude Code, and OpenCode running simultaneously on your PC.

### Step 1: Install & Launch Gateway
```bash
# 1. Clone repository
git clone https://github.com/RareBat47/antigravity-gateway.git
cd antigravity-gateway

# 2. Set up virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# 3. Start the gateway daemon
python -m agw.main
```
* **Dashboard Hub**: [http://127.0.0.1:8999/admin/dashboard](http://127.0.0.1:8999/admin/dashboard)
* **Health Check**: [http://127.0.0.1:8999/health](http://127.0.0.1:8999/health)
* **Model Catalog**: `GET http://127.0.0.1:8999/v1/models`

### Step 2: Connect Google Accounts
Open the [Admin Web Dashboard](http://127.0.0.1:8999/admin/dashboard) and connect your Google Antigravity accounts (or run `python -m agw.cli.main accounts login`). The gateway automatically encrypts tokens with AES-256 in your local vault.

---

## 👥 Dual-Agent Operating Guide: Simultaneous Execution

Run **Claude Code** and **OpenCode** side-by-side without interference:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEVELOPER WORKSPACE                               │
├──────────────────────────────────────┬──────────────────────────────────────┤
│  🧠 CLAUDE CODE (Developer Brain)     │  ⚡ OPENCODE (Coding Only Engine)    │
│  • System architecture & planning    │  • Pure code execution & file edits  │
│  • Deep research & whole-repo audits │  • Sub-second interactive latency    │
│  • Models: Frontier 5.5 & 1M Mega    │  • Models: Gemini 3.8 Flash High     │
│  • MCP: Filesystem & Memory tools    │  • Skill: Agentic Pro Escalation     │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### 1. Claude Code CLI & GUI — The Developer Brain
Claude Code acts as your primary architect, lead developer, and researcher.

```bash
# Launch with Frontier 5.5 Flagship (claude-sonnet-5.5 / claude-opus-5.5)
claude-frontier

# Or launch with 1M Mega-Context for whole-repository audits (claude-sonnet-5[1m])
claude-mega

# Or standard CLI command (pre-configured to gateway in ~/.bashrc)
claude
```
* **Global Directive**: Pre-configured in `~/.claude/CLAUDE.md` to act as the master Developer Brain.
* **Integrated MCP Servers**: Automatic access to `@modelcontextprotocol/server-filesystem` and `@modelcontextprotocol/server-memory`.
* **Desktop GUI**: Configured in `~/.config/Claude/claude_desktop_config.json`.

### 2. OpenCode CLI & Web GUI — Pure Coding Engine
OpenCode is strictly constrained to **CODING ONLY** (no conversational filler, pure implementation, bug fixing, and test generation).

```bash
# Start OpenCode interactive terminal TUI (defaults to gemini-3.8-flash-high)
opencode

# Start OpenCode Web GUI in your browser
opencode web

# Execute a direct coding task via CLI
opencode run "Implement JWT validation middleware"
```
* **Locked Default Engine**: `gemini-3.8-flash-high` for sub-second responses and instant file modifications.
* **On-Demand Escalation**: Includes the `agentic-pro-escalation` skill. When facing complex architectural dilemmas or deep bugs, it dynamically escalates to `agentic-pro/gemini-pro-agent` or `agentic-pro/gemini-3.1-pro-low`, then immediately returns to speed flash.

---

## 📊 Product Working Methods & Architecture Flowchart

```mermaid
flowchart TD
    subgraph Clients["🖥️ Developer Interfaces"]
        CC["🧠 Claude Code CLI / GUI<br/><b>Developer Brain</b><br/><i>Architecture & Research</i>"]
        OC["⚡ OpenCode CLI / Web GUI<br/><b>Coding Only Engine</b><br/><i>Fast Code & File Diffs</i>"]
    end

    subgraph Gateway["🚪 Antigravity Gateway (127.0.0.1:8999)"]
        direction TB
        Auth["🛡️ Auth & Permissions<br/><i>Role-Key & Model Filtering</i>"]
        Normalizer["🔄 Model Normalizer & Registry<br/><i>Clean Alias Resolution</i>"]
        Sanitizer["🧹 OpenAPI & Schema Sanitizer<br/><i>Protobuf Whitelist & Thinking Filter</i>"]
        Scheduler["⚖️ Quota-Aware Hybrid Scheduler<br/><i>Health + Quota + Token Balancing</i>"]
        Cooldown["❄️ Isolated Per-Family Cooldown<br/><i>Claude & Gemini Independent Tiers</i>"]
    end

    subgraph Providers["🔑 4 Categorized Provider Groups"]
        P1["🔮 claude-frontier<br/><code>agw-frontier-local</code><br/>claude-sonnet-5.5 / claude-opus-5.5"]
        P2["🧠 mega-context-1m<br/><code>agw-megacontext-local</code><br/>claude-sonnet-5[1m] / claude-opus-5[1m]"]
        P3["⚡ gemini-speed-flash<br/><code>agw-speed-local</code><br/>gemini-3.8-flash-high"]
        P4["🛠️ gemini-agentic-pro<br/><code>agw-agentic-local</code><br/>gemini-pro-agent / gemini-3.1-pro-low"]
    end

    subgraph Backend["☁️ Google Antigravity Cloud Code Pool"]
        Vault["🔐 AES-256 Credential Vault"]
        AccPool["👥 Multi-Account Rotation Pool<br/>Account 1 | Account 2 | ... | Account N"]
        GoogleAPI["🌐 Google Cloud Code Assist RPC<br/><code>v1internal:streamGenerateContent</code>"]
    end

    CC -->|Anthropic Protocol /v1/messages| Auth
    OC -->|OpenAI Protocol /v1/chat/completions| Auth
    
    Auth --> Providers
    Providers --> Normalizer
    Normalizer --> Sanitizer
    Sanitizer --> Scheduler
    Scheduler <--> Cooldown
    Scheduler --> Vault
    Vault --> AccPool
    AccPool --> GoogleAPI
    GoogleAPI -->|Stream SSE / Output| Clients
```

---

## 🔑 The 4 Categorized Provider APIs & Proper Usage Guide

The gateway organizes its curated 7-model catalog into **4 dedicated Provider Groups**. Each group has its own dedicated API key, base URL, and strict rate-limit boundary:

| Provider Name | API Key | Base URL | Curated Models | Primary Role & Best For |
|---|---|---|---|---|
| **`claude-frontier`** | `agw-frontier-local` | `http://127.0.0.1:8999/v1` | `claude-sonnet-5.5`<br>`claude-opus-5.5` | **Frontier Flagship Reasoning**: Deep logic, systems architecture, comprehensive design docs, Claude Code developer brain. |
| **`mega-context-1m`** | `agw-megacontext-local` | `http://127.0.0.1:8999/v1` | `claude-sonnet-5[1m]`<br>`claude-opus-5[1m]` | **1M Token Mega-Context**: Ingesting entire code repositories, massive terminal log audits, multi-thousand page documents. |
| **`gemini-speed-flash`** | `agw-speed-local` | `http://127.0.0.1:8999/v1` | `gemini-3.8-flash-high` | **High-Speed Pure Coding**: Sub-second interactive latency, high-throughput edits, test generation, OpenCode default engine. |
| **`gemini-agentic-pro`** | `agw-agentic-local` | `http://127.0.0.1:8999/v1` | `gemini-pro-agent`<br>`gemini-3.1-pro-low` | **Autonomous Agentic & Pro Workflows**: Difficult bugs, multi-file refactoring, step-by-step diagnostic reasoning. |
| **`Master Gateway`** | `agw-local-dE9X...` | `http://127.0.0.1:8999/v1` | *All 7 Models* | **Unrestricted Administrative Access**: For management scripts and universal dashboard tools. |

---

## 🎯 Golden Rules for Proper API Consumption

To ensure optimal performance and avoid burning through account limits:

* ⚡ **Keep OpenCode strictly on `gemini-speed-flash`**:
  * Gemini 3.8 Flash High provides near-instantaneous streaming and handles 95% of all code authoring, typing, and refactoring with zero rate-limit anxiety.
* 🧠 **Reserve `mega-context-1m` for Whole-Repo Audits Only**:
  * 1,000,000 tokens consume quota significantly faster. Use `claude-mega` when you need to ingest an entire multi-folder codebase or analyze massive log traces. For day-to-day coding, stick to `claude-frontier`.
* 🛠️ **Use `gemini-agentic-pro` via the Escalation Protocol**:
  * When OpenCode encounters a tricky bug that fails after two attempts, escalate to `agentic-pro/gemini-pro-agent` to formulate a solution blueprint, then immediately revert to `speed-flash` to write the code.
* 🔒 **Client Isolation**:
  * Because each provider key is isolated by model family, if Claude experiences a temporary quota backoff, **OpenCode continues running on Gemini at full speed with zero interruption.**

---

## 🧩 Curated 7-Model Catalog Reference

| # | Model Identifier | Provider Group | Context Window | Max Output | Features |
|---|---|---|---|---|---|
| **#1** | `gemini-3.8-flash-high` | `gemini-speed-flash` | 1,048,576 | 65,536 | Sub-second latency, streaming, tool calling |
| **#5** | `gemini-3.1-pro-low` | `gemini-agentic-pro` | 1,048,576 | 65,536 | Pro reasoning, structural planning, tool calling |
| **#6** | `gemini-pro-agent` | `gemini-agentic-pro` | 1,048,576 | 65,536 | Autonomous multi-turn agent execution, tools |
| **#8** | `claude-sonnet-5.5` | `claude-frontier` | 200,000 | 16,384 | Flagship coding & reasoning, thinking tokens |
| **#9** | `claude-opus-5.5` | `claude-frontier` | 200,000 | 16,384 | Deep architectural synthesis, thinking tokens |
| **#13** | `claude-sonnet-5[1m]` | `mega-context-1m` | 1,000,000 | 16,384 | 1M mega-context, whole-codebase audits |
| **#14** | `claude-opus-5[1m]` | `mega-context-1m` | 1,000,000 | 16,384 | 1M mega-context, deep long-context reasoning |

---

## 🛡️ Core Engineering Highlights

### 1. Smart Quota-Aware Hybrid Scheduling
Requests are routed using a multi-factor scoring formula:
$$\text{Score} = w_{\text{health}} \cdot H - w_{\text{tokens}} \cdot \hat{T} + w_{\text{quota}} \cdot Q - w_{\text{lru}} \cdot \Delta t$$
Accounts with low remaining quota or recent failures are automatically deferred, giving healthy accounts priority while keeping depleted accounts on standby.

### 2. Isolated Per-Family Cooldowns
Upstream 429 rate limits on `claude` models only place the account in cooldown for the `claude` family. Its `gemini` quota remains active and accessible. Cooldowns step through progressive backoff tiers (`60s` $\to$ `300s` $\to$ `1800s` $\to$ `7200s`) and persist across restarts in SQLite.

### 3. Strict Protobuf Schema Sanitizer
Translates standard OpenAI and Claude tool declarations into Google's strict Cloud Code Protobuf schema. Strips unsupported draft schema fields (`propertyNames`, `additionalProperties`, etc.) and formats `thinkingConfig` budgets cleanly to avoid upstream 400 Bad Request errors.

### 4. Zero-Leakage Credential Security
Refresh tokens are stored with AES-256 encryption. Bearer tokens, secrets, and auth headers are automatically stripped and redacted across all log sinks.

---

## 🖥️ Admin Web Dashboard

Access the real-time dashboard at:
👉 **[http://127.0.0.1:8999/admin/dashboard](http://127.0.0.1:8999/admin/dashboard)**

* **Live Account Pool**: View Gmail IDs, free/pro account status, health scores, and individual connection statuses.
* **One-Click Health Check**: Manually ping and refresh all connections on demand.
* **Provider Categories Hub**: Copy keys and endpoints for `claude-frontier`, `mega-context-1m`, `gemini-agentic-pro`, and `gemini-speed-flash`.
* **Aggregated Usage & Cooldown Tracker**: Real-time stats on combined quota limits and accounts on cooldown with auto-clear timers.

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
