# Antigravity Ecosystem & AGW V2 Workflow Master Guide

This guide provides an authoritative reference for the **Google Antigravity** platform, its open-source CLI, Python SDK, IDE agent architecture, and details how to run, optimize, and maintain this repository as an enterprise-grade **V2 Agentic Pipeline**.

---

## Part 1: Official Antigravity Ecosystem Reference

Google Antigravity is an AI-first software development platform created by Google DeepMind / Google AI. It spans multiple complementary surfaces:

```mermaid
graph TD
    subgraph Antigravity Ecosystem
        CLI["Antigravity CLI (agy)"]
        IDE["Antigravity IDE (VS Code Fork)"]
        APP["Antigravity 2.0 (Desktop Electron)"]
        SDK["Python SDK (google-antigravity)"]
    end

    subgraph Customizations Engine
        RULES[".agents/rules/ (GEMINI.md)"]
        SKILLS[".agents/skills/ (SKILL.md)"]
        PLUGINS[".agents/plugins/"]
        MCP["MCP Servers (mcp_config.json)"]
    end

    subgraph Antigravity Gateway V2 (This Project)
        AGW["AGW Proxy (Port 8999)"]
        ROUTER["Scheduler & Model Router"]
        STREAMER["SSE Keep-Alive Streamer (8s Heartbeat)"]
        CACHE["Thought Signature Cache"]
    end

    subgraph Upstream & Downstream
        GOOGLE["Google Cloud Code Assist"]
        HERMES["Hermes Agent (GUI / CLI)"]
        AGY_CLIENTS["Antigravity Agents / SDK"]
    end

    CLI --> CUSTOMIZATIONS
    IDE --> CUSTOMIZATIONS
    APP --> CUSTOMIZATIONS
    SDK --> AGW
    HERMES --> AGW
    AGW --> GOOGLE
```

### 1. Antigravity CLI (`agy`)
* **Overview**: The Antigravity CLI (`agy`) is a terminal-based autonomous pair-programming agent designed for developers who prefer working directly in shells (Bash, Zsh, PowerShell).
* **Key Commands**:
  - `agy`: Launches the interactive Terminal User Interface (TUI).
  - `agy --help`: Lists all command-line flags, subcommands, and headless options.
  - `/help`: Displays built-in slash commands inside the interactive session.
  - `/exit` or `Ctrl+D Ctrl+D`: Exits the session cleanly.
* **Configuration**:
  - CLI settings are persisted in `~/.gemini/antigravity-cli/settings.json`.
  - Supports configuring default models, tool approval policies, background task execution, and sandboxing.
* **Official Documentation Pointers**:
  - Main Documentation: `https://antigravity.google/docs`
  - CLI Features & Subagents: `https://antigravity.google/docs/cli/features`
  - CLI Best Practices: `https://antigravity.google/docs/cli/best-practices`
  - CLI Reference: `https://antigravity.google/docs/cli/reference`

---

### 2. The Bot Used in this IDE (Antigravity IDE & 2.0 Desktop)
The bot operating in this environment is **Antigravity**, a paired autonomous AI coding assistant. It operates across three distinct interaction modalities:

#### A. Passive Modality: Antigravity Tab (Autocomplete & Supercomplete)
- **Next-Intent Prediction**: Analyzes active code, open file tabs, recent terminal outputs, and diagnostics to predict multi-token completions before you type them.
- **Supercomplete**: Proposes large diffs (including line removals and replacements) in floating overlays.
- **Tab to Jump & Tab to Import**: Pressing `Tab` jumps to logical insertion points (e.g. function bodies) and automatically adds necessary library imports at the top of the file.

#### B. Instructive Modality: Inline Command (`Ctrl+I` / `Cmd+I`)
- **Localized Edits**: Highlight any code block and press `Ctrl+I` to refactor, explain, or generate targeted modifications restricted solely to that block.
- **Net-New Code Generation**: Press `Ctrl+I` on an empty line without selection to generate classes, functions, or tests at the cursor.

#### C. Collaborative Modality: Sidebar Chat & Autonomous Agent Mode
- **Autonomous Agent Loop**: Capable of reading/writing files, discovering project structure, executing shell commands, launching background daemons, monitoring long-running processes, and invoking MCP tools.
- **Planning Mode**: Automatically activates for multi-file architectural changes. Generates an `implementation_plan.md` artifact for user review and an interactive plan approval workflow.
- **Specialized Slash Commands**:
  - `/goal`: Runs long-running, multi-step tasks autonomously until complete.
  - `/grill-me`: Conducts an interactive interview to resolve design decisions before implementation.
  - `/schedule`: Runs recurring cron jobs or delayed timers.
  - `/learn`: Records corrections and workflows into persistent knowledge items.

---

### 3. Official Open-Source Python SDK (`google-antigravity`)
Google provides an open-source Python SDK to programmatically spawn and orchestrate Antigravity agents in your own scripts, CI/CD pipelines, and microservices:

* **GitHub Repository**: [google-antigravity/antigravity-sdk-python](https://github.com/google-antigravity/antigravity-sdk-python)
* **Installation**:
  ```bash
  pip install google-antigravity
  ```
* **Programmatic Example**:
  ```python
  import asyncio
  import sys
  from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig

  async def main():
      config = LocalAgentConfig(
          system_instructions="Expert code assistant",
          capabilities=CapabilitiesConfig()  # Enables write/exec tools
      )
      async with Agent(config) as agent:
          response = await agent.chat("Analyze the codebase and propose optimizations.")
          async for token in response:
              sys.stdout.write(token)
              sys.stdout.flush()

          # Stream reasoning and tool executions
          async for thought in response.thoughts:
              print(f"[Reasoning] {thought}")
          async for call in response.tool_calls:
              print(f"[Tool Call] {call.name} -> {call.args}")

  if __name__ == "__main__":
      asyncio.run(main())
  ```

---

### 4. Customization Architecture (Skills, Rules, Plugins)
Antigravity discovers and prioritizes customizations in the following order:
1. **Workspace Project Root** (`.agents/rules/`, `.agents/skills/`, `GEMINI.md`)
2. **Declared Workspace Configs** (`skills.json`, `plugins.json`)
3. **Global User Discovery** (`~/.gemini/config/skills/`, `~/.gemini/config/rules/`)
4. **Built-in System Customizations**

Customizations utilize **Progressive Disclosure**: Only skill names and short descriptions are initially loaded into context. The full instructions are only injected when relevant, minimizing token consumption.

---

## Part 2: Antigravity Gateway (AGW) V2 Pipeline

This repository implements the **Antigravity Gateway (AGW)**. It acts as an OpenAI-compatible multiplexer that exposes Google's Cloud Code Assist models (`Gemini 3.8 Flash`, `Gemini 3.1 Pro`, `Claude Sonnet/Opus`, `GPT-OSS 120B`) to external autonomous frameworks like **Hermes Agent**.

### Key V2 Optimizations Implemented

| Optimization | Problem Solved in V1 | V2 Implementation in AGW |
|---|---|---|
| **SSE Heartbeat Keep-Alive** | Hermes GUI disconnected after 60s of model reasoning with *"no stream output for 60s"* | Wrapped stream in 8-second interval emitting empty delta chunks (`choices[0].delta = {}`), keeping client watchdogs alive. |
| **Thought Signature Persistence** | Gemini 2.5/3.x rejected multi-turn tool calling with `400 Bad Request: Missing thought_signature` | In-memory `ThoughtSignatureCache` tracks signatures across function calling turns. |
| **Upstream Timeout Hardening** | 120s timeout caused `ReadTimeout` during 20+ tool schema synthesis | Default `CloudCodeClient` timeout upgraded to **300 seconds** with custom `httpx.Timeout`. |
| **5 Definitive Worker Roles** | Unrestricted access caused rate limits, invalid models, and routing confusion | 5 isolated API keys with strict ACL model blocking and tailored model families. |
| **Hybrid Scheduling** | Single accounts quickly hit 429 quota exhaustion | Token-weighted, health-tracked round-robin with exponential cooldown tiers. |

---

## Part 3: The 5 Dedicated V2 Model Personas

| # | Role & Key Name | API Key Token | Model ID | Upstream Model | Primary Function |
|---|---|---|---|---|---|
| 1 | **Planning** | `agw-plan-claude-9x82` | `claude-opus-4-6-thinking` | `claude-opus-4-6-thinking` | System architecture, long-horizon planning, design docs. |
| 2 | **Coding** | `agw-code-gemini-3-8d52` | `gemini-3.8-flash-high` | `gemini-3.8-flash-tiered` | Autonomous coding worker, high-speed multi-file tool loops. |
| 3 | **Pro** | `agw-code-hybrid-1-4a29` | `gemini-3.1-pro-low` | `gemini-3.1-pro-low` | Deep Google Pro reasoning, complex mathematics, logic. |
| 4 | **Debugging** | `agw-code-hybrid-2-6e83` | `claude-sonnet-4-6` | `claude-sonnet-4-6` | Bug isolation, deep thinking, code refactoring. |
| 5 | **GPT** | `agw-debug-all-9c37` | `gpt-oss-120b-medium` | `gpt-oss-120b-medium` | Open-weights diagnostic fallback & general tasks. |

---

## Part 4: V2 Operational Playbook

### 1. Launching the Gateway Daemon
To start the gateway daemon in the background:
```powershell
$env:PYTHONPATH = "D:\Unlimited\AGY\src"
.venv\Scripts\python.exe -m agw.main
```
The server listens on `http://0.0.0.0:8999`.

### 2. Verifying System Health
```powershell
curl -s http://127.0.0.1:8999/health
```

### 3. Running the Verification Suites
- **Fast Unit Tests**:
  ```powershell
  .venv\Scripts\pytest tests/
  ```
- **End-to-End Hermes Verification**:
  ```powershell
  .venv\Scripts\python.exe scripts/test_hermes_dedicated.py
  ```

### 4. Inspecting Quota & Health
- **Live Markdown Report**: `docs/account-status.md`
- **Raw JSON State**: `data/quota-state.json`
- **Audit Logs**: Gateway console output automatically redacts API keys and access tokens.

---

## Part 5: Workspace Customizations in this Repository

This repository includes native Antigravity workspace customizations:
* [`.agents/rules/agw-architecture.md`](../.agents/rules/agw-architecture.md): Enforces architectural guidelines, model constraints, and testing protocols for any agent working in this repo.
* [`.agents/skills/agw-ops/SKILL.md`](../.agents/skills/agw-ops/SKILL.md): Equips Antigravity with autonomous runbooks to test, start, monitor, and diagnose the gateway.
* [`GEMINI.md`](../GEMINI.md): Defines the root repository configuration and integration targets.
