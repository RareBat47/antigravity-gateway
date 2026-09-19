# Architecture Decision Records (ADRs) — Antigravity Gateway

This document records the architectural evaluations, reference comparisons, and engineering decisions made across all gateway subsystems.

---

## ADR 01: OAuth Authentication & PKCE Flow
- **Subsystem**: OAuth & PKCE
- **Reference**: `lomeliDev/antigravity-bridge` & `thigas88/antigravity-proxy`
- **Decision**: **Adapt**
- **Reason**: Standard RFC 7636 PKCE is implemented cleanly in Python. We adapted the PKCE flow to support both local browser redirects (via loopback HTTP server) and headless manual authorization code copy-pasting for remote Azure VMs.

---

## ADR 02: Account Credential Storage
- **Subsystem**: Account & Token Storage
- **Reference**: `lomeliDev/antigravity-bridge` (plaintext `accounts.json`) vs `allenlinli/antigravity-manager`
- **Decision**: **Rewrite**
- **Reason**: Storing raw refresh tokens in plaintext JSON is a severe security vulnerability. We implemented a decoupled architecture: SQLite for public metadata (masked emails, tiers, stats) and a standalone Fernet AES-256 encrypted vault (`data/vault.enc`) with 0600 permissions for refresh tokens.

---

## ADR 03: Quota Collection & Monitoring
- **Subsystem**: Quota Interrogation
- **Reference**: `thigas88/antigravity-proxy` (`v1internal:fetchAvailableModels`)
- **Decision**: **Adapt**
- **Reason**: `thigas88` identified that passing `{"project": projectId}` to `v1internal:fetchAvailableModels` accurately returns `quotaInfo.remainingFraction` and `resetTime`. We adapted this logic into a background asynchronous polling loop in Python with automatic markdown report generation in `docs/account-status.md`.

---

## ADR 04: Multi-Account Routing & Scheduling
- **Subsystem**: Account Scheduler
- **Reference**: `thigas88/antigravity-proxy` Hybrid Strategy
- **Decision**: **Adapt**
- **Reason**: Naive round-robin exhausts rate-limited accounts repeatedly. We adapted the hybrid weighted scoring formula: `Score = (Health × 2) + (Tokens × 5) + (Quota × 3) + (LRU × 0.1)`, prioritizing accounts that have sufficient quota, high reliability, and low recent usage.

---

## ADR 05: Isolated Cooldowns & Rate-Limit Handling
- **Subsystem**: Cooldowns & Failover
- **Reference**: `thigas88/antigravity-proxy` & `hermes-antigravity-auth-native`
- **Decision**: **Adapt**
- **Reason**: A 429 error on Claude should never disable Gemini. We implemented isolated cooldown tracking indexed by `(account_id, model_family)` with tiered exponential backoff (60s -> 300s -> 1800s -> 7200s) and automatic request failover.

---

## ADR 06: OpenAI Protocol & Streaming
- **Subsystem**: Protocol Adapter & SSE
- **Reference**: `lomeliDev/antigravity-bridge` & `usamashehab/antigravity-proxy`
- **Decision**: **Adapt**
- **Reason**: Adapted FastAPI asynchronous streaming with SSE chunks, yielding both standard `delta.content` chunks and `delta.reasoning_content` (thought deltas) for Gemini 3.5 Flash and Claude Opus thinking models.

---

## ADR 07: Tool Calling & Schema Sanitization
- **Subsystem**: Function Calling
- **Reference**: `lomeliDev/antigravity-bridge` & `thigas88/antigravity-proxy`
- **Decision**: **Reuse/Adapt**
- **Reason**: Cloud Code Assist rejects non-standard JSON schema keywords with 400 INVALID_ARGUMENT. We incorporated deep schema sanitization that recursively strips `anyOf`, `allOf`, `oneOf`, `const`, `multipleOf`, and `pattern`.

---

## ADR 08: Multimodal Vision
- **Subsystem**: Vision & Image Input
- **Reference**: `lomeliDev/antigravity-bridge`
- **Decision**: **Reuse/Adapt**
- **Reason**: Converts base64 image data URLs and remote HTTP URLs into Gemini `inlineData` parts (`mimeType` and base64 data).

---

## ADR 09: Hermes Agent Integration
- **Subsystem**: Hermes Provider Integration
- **Reference**: Native Hermes custom provider configuration
- **Decision**: **Implement as Pure OpenAI Provider**
- **Reason**: Hermes should not require custom code modification. Hermes connects to the gateway as an ordinary OpenAI-compatible provider with standard YAML config.

---

## ADR 10: Remote Authentication (Windows ↔ Azure)
- **Subsystem**: Remote OAuth Flow
- **Reference**: `antigravity-bridge` manual login endpoint
- **Decision**: **Implement Dual Mode**
- **Reason**: Mode A (Gateway on Windows, Hermes on Azure via Cloudflare Tunnel) and Mode B (Gateway on Azure with browserless PKCE code copy-paste).

---

## ADR 11: Administrative API & Web Dashboard
- **Subsystem**: Admin Interface
- **Reference**: `antigravity-manager` (Electron) vs `antigravity-bridge`
- **Decision**: **Rewrite**
- **Reason**: Replaced heavy desktop Electron dependency with an embedded, zero-dependency lightweight web dashboard served directly from FastAPI at `/admin/dashboard`.

---

## ADR 12: CLI Tool (`agw`)
- **Subsystem**: Command Line Interface
- **Reference**: Custom requirement
- **Decision**: **Implement**
- **Reason**: Implemented `agw` using `click` and `rich` with full subcommands for accounts, quota, models, health, logs, and testing.
