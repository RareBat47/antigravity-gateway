# Universal Local Hub Polished Rebuild Implementation Plan

> **For agentic workers:** Implement task-by-task with tests and commits.

**Goal:** Turn AGY into a polished local-first hub with secure generated identity, automatic routing profiles, onboarding status, truthful integrations, and preserved API compatibility.

**Architecture:** Add focused services for local identity, routing profiles, onboarding status, and integration adapters. Keep existing CloudCode account scheduling and OpenAI/Anthropic protocol handlers intact, adding only compatibility layers at their boundaries. Use SQLite/config migration conservatively and preserve existing vault/account data.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite/aiosqlite, existing vault, pytest/pytest-asyncio, Windows batch/VBS helpers.

**Spec:** `docs/superpowers/specs/2026-10-05-universal-local-hub-redesign.md`

## Global Constraints

- Never delete `data/gateway.db`, `data/vault.enc`, `data/vault.key`, or existing config automatically.
- Preserve existing API routes, exact model IDs, advanced keys, account rotation, streaming, tools, and failover.
- New installs must not retain literal `*-change-me` secrets.
- Bind to `127.0.0.1` by default; remote mode remains explicit.
- Integration writes must be idempotent and create backups.
- Run `.venv/Scripts/pytest` after every implementation milestone and before completion.

### Task 1: Secure identity and configuration migration

**Files:**
- Create: `src/agw/security/identity.py`
- Modify: `src/agw/config.py`, `src/agw/main.py`
- Test: `tests/test_identity_migration.py`

Implement `LocalIdentityManager` with `ensure_identity(config)`, `is_default_secret(value)`, `masked_key(value)`, and `rotate_keys(config)`. Generate cryptographically random gateway/admin keys when values are empty or literal defaults, persist them through the existing config path without touching vault/account data, and expose only masked values. Add `server.host: 127.0.0.1` and `security.local_trust: false` defaults for new configs while preserving explicit legacy settings during migration.

### Task 2: Public routing profiles

**Files:**
- Create: `src/agw/routing/profiles.py`
- Modify: `src/agw/routing/registry.py`, `src/agw/api/routes_v1.py`, `src/agw/main.py`
- Test: `tests/test_routing_profiles.py`

Implement `RoutingProfile` definitions and `resolve_profile(model_id)`. Support `auto`, `fast`, `balanced`, `powerful`, and `reasoning`, while exact model IDs continue to resolve unchanged. Route profile names through the existing registry and enforce ACL checks against the resolved family. Add `GET /v1/routing/profiles`.

### Task 3: Persistent onboarding status

**Files:**
- Create: `src/agw/setup/state.py`, `src/agw/api/routes_setup.py`
- Modify: `src/agw/main.py`, `src/agw/db/schema.py`
- Test: `tests/test_setup_state.py`

Implement a recalculating `SetupStateService` with states `not_initialized`, `identity_ready`, `account_required`, `account_ready`, `integrations_pending`, `ready`, and `needs_attention`. Add `GET /setup/status` and `POST /setup/initialize`, authenticated for local/admin use. Status must inspect actual account and identity conditions instead of trusting stale process state.

### Task 4: Truthful integrations

**Files:**
- Create: `src/agw/integrations/manager.py`, `src/agw/api/routes_integrations.py`
- Modify: `src/agw/integrations/setup_pc.py`, `src/agw/main.py`
- Test: `tests/test_integrations_manager.py`

Introduce adapter results with `detect`, `preview`, `apply`, and `verify`. Cover OpenAI/Anthropic environment profiles, OpenCode, Continue, and startup registration. Ensure backups are created before modifying existing JSON/config files, writes are idempotent, and unsupported clients report `manual` or `unsupported`. Add setup integration endpoints.

### Task 5: Dashboard and documentation rebuild

**Files:**
- Modify: `src/agw/dashboard/dashboard.html`, `README.md`
- Create: `GETTING_STARTED.md`, `CLIENT_INTEGRATIONS.md`, `ADVANCED_OPERATIONS.md`
- Test: `tests/test_dashboard_contract.py`

Replace the role-key-first dashboard header with status, onboarding, routing profile, integration cards, and an advanced section. Remove secret-bearing generated one-pager as the primary path. Documentation must describe the install/connect/enable workflow, not hardcode secrets.

### Task 6: Installer and runtime verification

**Files:**
- Modify: `install.bat`, `run.bat`, `launch.ps1`, `.gitignore`
- Test: `tests/test_runtime_contract.py`

Make installation initialize config safely, start the gateway with the project virtual environment, and avoid killing unrelated processes. Ignore generated account-status output. Add smoke tests for health, `/v1/models`, `/v1/routing/profiles`, `/setup/status`, OpenAI profile routing, and Anthropic endpoint registration.

### Task 7: Final validation and release commit

Run the complete test suite, live gateway health and endpoint checks, inspect git diff, update `CHANGELOG.md`/`STATE.md`, and commit the polished rebuild with a descriptive message.
