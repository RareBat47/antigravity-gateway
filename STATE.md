# Project State & Evolution Ledger

**Project:** Arena Multi-Account OpenAI-Compatible Gateway  
**Current Version:** v0.2.0-alpha (Arena Refactor)  
**Status:** Active Prototyping / Stabilizing  
**Last Updated:** 2026-09-22  

## Current Working Capabilities
- **ArenaProvider Abstraction:** Modular provider interface (`RealArenaProvider` targeting `chat.lmsys.org/api` and `MockArenaProvider` for deterministic testing).
- **Direct OpenAI Protocol Passthrough:** Simplified `routes_v1.py` accepting OpenAI chat completion requests natively without legacy Gemini translations.
- **Account Scheduling & Failover:** Multi-account failover, tiered cooldown tracking, and rate-limit handling preserved on HTTP 429.
- **Credentials Vault & Auth Ingestion:** Direct manual injection via `/auth/manual` for raw browser session cookies (`cf_clearance`, `arena-auth-prod-v1`) stored in the AES-256 encrypted vault.
- **Smoke Baseline:** Clean DI initialization verified via `smoke_test.py`.

## Active Milestones / In Progress
- [x] Refactor architecture from Antigravity Google coupling to Arena.ai provider model.
- [x] Implement `/auth/manual` endpoint for cookie-based credentials ingestion.
- [ ] Cron Job 1: Align legacy unit tests in `tests/` with new `MockArenaProvider` schema.
- [ ] Cron Job 2: Real Arena provider live validation and Cloudflare Turnstile bypass handling.
- [ ] Add live cookie health validation / automatic expiry detection.

## Architecture & Tech Stack Notes
- **Runtime:** Python 3.11, FastAPI, Uvicorn, HTTPX.
- **Security:** AES-256 Fernet Vault for cookie credentials; SQLite for metadata and routing metrics.
- **Routing:** Hybrid weighted account scoring with isolated per-account/per-model cooldowns.

## Verification Baseline
- **Launch Server:** `python -m uvicorn agw.main:app --reload --port 8999`
- **Smoke Check:** `python smoke_test.py`
- **Unit Tests:** `pytest tests/`
