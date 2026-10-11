---
name: agw-ops
description: Operational runbooks and diagnostic workflows for Antigravity Gateway (AGW). Use when managing, starting, testing, or debugging the AGW daemon, checking account health, or auditing Hermes agent connectivity.
---

# AGW Operations & Diagnostics

This skill provides step-by-step operational instructions for maintaining and testing Antigravity Gateway.

## 1. Quick Health Check
Check if the AGW server is currently running and healthy:
```powershell
curl -s http://127.0.0.1:8999/health
```
Expected response:
```json
{"status":"ok","active_accounts":6,"total_accounts":6,"total_requests":...}
```

## 2. Running Test Suites
### A. Fast Unit & Protocol Tests (Pytest)
```powershell
.venv\Scripts\pytest tests/
```
All 61 tests across routing, auth, cooldown, schema sanitizing, and streaming must pass.

### B. End-to-End Hermes Dedicated Verification
```powershell
.venv\Scripts\python.exe scripts/test_hermes_dedicated.py
```
Validates:
- Phase 1: Basic Chat Completions across all 5 models
- Phase 2: OpenAI Tool Calling Declarations
- Phase 3: Multi-turn State & Thought Signature Persistence
- Phase 4: Streaming SSE Response Integrity with 8s Heartbeats
- Phase 5: Live Hermes CLI Profile Integration
- Phase 6: Strict ACL & Model Blocking (HTTP 403 / 404)

## 3. Starting / Restarting the Daemon
When starting AGW as a background daemon:
```powershell
$env:PYTHONPATH = "D:\Unlimited\AGY\src"
.venv\Scripts\python.exe -m agw.main
```
The server binds to `0.0.0.0:8999` and serves OpenAI endpoints at `/v1/chat/completions` and `/v1/models`.

## 4. Quota and Account Monitoring
View the live Markdown status report:
```powershell
Get-Content docs/account-status.md
```
Or check the JSON state:
```powershell
Get-Content data/quota-state.json
```
