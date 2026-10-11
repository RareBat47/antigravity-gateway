# Antigravity Gateway (AGW) — Architectural Rules & Guidelines

This repository implements **Antigravity Gateway (AGW)**, a high-performance multi-account proxy bridging client agents (e.g. Hermes Agent, custom Python SDK agents) to Google's Cloud Code Assist endpoint via an OpenAI-compatible API (`/v1`).

## 1. Core Principles
- **OpenAI Standard Compliance**: All `/v1/chat/completions` requests must accept and return standard OpenAI JSON envelopes and SSE streaming chunks.
- **Model Filtering**: Strict role-based API keys enforce access to specific model families (`gemini`, `claude`, `gpt`). Non-permitted models must return `403 Forbidden`.
- **Thought Signature Persistence**: Gemini 2.5/3.x thought signatures must be cached in memory (`agw.protocol.signature_cache`) across multi-turn tool calling loops. Never strip or drop thought signatures.
- **SSE Heartbeat Keep-Alive**: When streaming responses, if upstream is thinking or compiling tool calls, emit standard empty-delta chunks every 8 seconds to prevent client-side idle timeouts (e.g., Hermes GUI 60s watchdog).
- **Upstream Resilience**: CloudCode HTTP client timeouts must default to 300 seconds to allow deep reasoning with large tool schema catalogs.

## 2. 5 Definitive Model Architecture
1. `claude-opus-4-6-thinking` (Key: Planning) — Deep architectural reasoning and long-horizon planning.
2. `gemini-3.8-flash-high` (Key: Coding) — Autonomous execution, multi-file refactoring, fast tool loops.
3. `gemini-3.1-pro-low` (Key: Pro) — Complex reasoning, precision code analysis, large context.
4. `claude-sonnet-4-6` (Key: Debugging) — Independent Claude coding, bug investigation, thinking.
5. `gpt-oss-120b-medium` (Key: GPT) — Open-weights diagnostic fallback and root-cause analysis.

## 3. Testing Standard
- Always verify changes with `pytest tests/` (all 61 unit tests must pass).
- Verify end-to-end Hermes compatibility with `python scripts/test_hermes_dedicated.py` (26+ checks must pass).
