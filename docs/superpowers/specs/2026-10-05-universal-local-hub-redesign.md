# Antigravity Gateway Universal Local Hub Redesign

**Status:** Approved architecture; implementation pending spec review
**Project:** Antigravity Gateway (`D:\Unlimited\AGY`)
**Target milestone:** v2.0 Universal Local Hub

## Goal

Transform AGY from a role-key-oriented gateway into a local-first AI control plane: a user installs it, opens a local dashboard, connects Google accounts through browser OAuth, enables integrations, and compatible local AI software uses one stable local endpoint without requiring users to understand provider roles, internal model IDs, or manual YAML editing.

## Product principles

1. **One normal path:** install, open dashboard, connect accounts, enable integrations.
2. **One local identity:** normal local clients use one generated local API key; role keys remain advanced-only.
3. **Automatic routing:** normal clients request `auto`, `fast`, `balanced`, `powerful`, or `reasoning`; the gateway selects a compatible model and account internally.
4. **Safe local defaults:** bind to loopback by default, generate non-default secrets, preserve existing vault/database data, and require explicit opt-in for remote access.
5. **Truthful integrations:** configuration screens report detected, configured, restart-required, unsupported, or failed rather than claiming universal automatic support.
6. **Compatibility first:** preserve OpenAI `/v1/*`, Anthropic `/v1/messages`, streaming, tools, reasoning, failover, quotas, and advanced keys.

## Current problems to solve

- `docs/HERMES-INTEGRATION.md`, dashboard-generated one-pagers, and README content expose stale role keys and model assignments.
- `config.yaml` currently has five role entries whose names and keys do not match the seven-role one-pager.
- Default secrets are literal `*-change-me` values.
- `local_trust: true` is too permissive as a permanent default and the server binds to `0.0.0.0`.
- Account linking is browser-assisted but the product does not have a persistent first-run onboarding state machine.
- `setup-pc` writes generic environment variables and a small set of config files but does not detect or verify supported clients.
- Model selection is still exposed primarily as exact internal IDs.
- Runtime-generated `docs/account-status.md` creates source-control noise.

## Target user experience

### First launch

1. `install.bat` creates or updates the virtual environment and dependencies.
2. AGY initializes a local config and encrypted local identity if absent.
3. AGY starts on `127.0.0.1:8999` by default.
4. Browser opens `/onboarding` or the dashboard detects incomplete setup.
5. User clicks **Connect Google Account**; OAuth callback returns to the local gateway.
6. The dashboard verifies the account, project, token refresh, and quota visibility.
7. User clicks **Enable Local Integrations**.
8. Dashboard displays exact integration results and any restart instructions.

### Normal client contract

OpenAI-compatible base URL:

```text
http://127.0.0.1:8999/v1
```

Anthropic-compatible base URL:

```text
http://127.0.0.1:8999
```

Generated local API key is used by clients. Normal model names:

```text
auto
fast
balanced
powerful
reasoning
```

Exact model IDs remain available through `/v1/models` and the advanced configuration page.

## Architecture

### Local identity service

Add a local identity manager responsible for:

- generating a high-entropy local gateway key on first launch;
- storing a hash or encrypted value in the existing vault/config boundary;
- exposing only masked metadata to the dashboard;
- migrating existing configured gateway/admin keys without printing them;
- supporting key rotation from the dashboard;
- distinguishing local-client authentication from admin-dashboard authentication.

For backward compatibility, existing valid master and role keys remain accepted. New installations do not use literal default secrets.

### Routing profiles

Add a profile registry with stable public names:

| Profile | Intended behavior |
|---|---|
| `auto` | Select best healthy route using capability, quota, health, latency, and request hints |
| `fast` | Prefer Flash-family routes and low latency |
| `balanced` | Balance quality, quota, health, and latency |
| `powerful` | Prefer Pro/Opus/Sonnet-capable routes |
| `reasoning` | Prefer models supporting thinking/reasoning |

Profile resolution returns a concrete internal model plus family. The existing scheduler remains responsible for account selection and failover. The public model requested by the client is preserved in response metadata where compatible; internal route selection is auditable in request events.

### Onboarding state

Persist onboarding state in a small SQLite table or versioned settings record rather than process memory. Required states:

- `not_initialized`
- `identity_ready`
- `account_required`
- `account_ready`
- `integrations_pending`
- `ready`
- `needs_attention`

The state must be recalculable from actual system conditions so a deleted config file or revoked token does not leave onboarding falsely complete.

### Integration manager

Create one integration service with adapters. Each adapter implements:

- `detect() -> DetectionResult`
- `preview() -> ChangeSet`
- `apply() -> ApplyResult`
- `verify() -> VerifyResult`

Initial adapters:

- OpenAI-compatible environment profile
- Anthropic-compatible environment profile
- OpenCode config
- Continue config
- Claude Code environment guidance/config where supported
- Aider environment guidance/config where supported

Unsupported applications must be reported as manual or unsupported rather than silently modified. Existing config files must be backed up before edits, and writes must be idempotent.

### Security modes

Default mode:

- server host `127.0.0.1`;
- local API key required for normal API requests, with dashboard onboarding allowed through a local browser session mechanism;
- no remote CORS or tunnel behavior;
- no permissive arbitrary-key trust.

Remote mode is explicit and must require:

- non-loopback bind address or tunnel configuration;
- strict API key validation;
- non-default gateway/admin secrets;
- a warning in the dashboard and CLI.

A compatibility `local_trust` option may remain for migration, but it defaults to false for new installs and is labeled unsafe/legacy.

### Dashboard

The primary dashboard landing view shows:

- gateway status and endpoint cards;
- onboarding progress;
- connected/healthy/attention account counts;
- routing profile selector;
- integration cards with status and actions;
- advanced settings collapsed by default;
- role keys, exact model IDs, quotas, tunnels, and diagnostics under advanced sections.

The old generated one-pager is removed from the primary UI. A sanitized advanced connection reference can be generated on demand without exposing secrets by default.

## API additions

Add authenticated local/admin endpoints:

- `GET /setup/status` — current onboarding and readiness state;
- `POST /setup/initialize` — idempotently initialize identity and settings;
- `GET /setup/integrations` — adapter detection/status results;
- `POST /setup/integrations/apply` — apply selected adapters after explicit user action;
- `POST /setup/integrations/{name}/verify` — verify one integration;
- `GET /v1/routing/profiles` — public profile metadata;
- `POST /admin/keys/rotate` — rotate local/admin keys with confirmation and migration window;
- `GET /admin/advanced/connection-reference` — sanitized reference with masked credentials.

Existing `/auth/*`, `/admin/*`, `/v1/chat/completions`, `/v1/messages`, `/v1/models`, and `/health` remain compatible.

## Migration rules

- Never delete `data/gateway.db`, `data/vault.enc`, `data/vault.key`, or existing config automatically.
- Back up config before migration.
- Preserve existing connected accounts and tokens.
- Preserve existing valid API keys as advanced compatibility keys.
- Detect literal default secrets and replace them only after generating and persisting secure replacements; provide a migration notice.
- Migrate `0.0.0.0` to `127.0.0.1` only when the user has not explicitly configured remote access.
- Keep runtime account status outside normal source-controlled documentation, or mark it generated and ignored.

## Verification requirements

The rebuild is complete only when all of the following are verified:

1. Fresh temporary install initializes without literal default secrets.
2. Existing database/vault migration preserves all account IDs and encrypted credentials.
3. `/health` works after restart.
4. OpenAI `auto` and profile requests route successfully through the existing mock client tests.
5. Anthropic `/v1/messages` works for non-streaming and streaming paths.
6. Existing exact model IDs and advanced keys remain compatible.
7. Setup status reflects actual account and integration state.
8. Integration apply is idempotent and creates backups.
9. Localhost and remote authentication behavior are tested separately.
10. Full test suite passes and a live request is exercised against the running gateway.

## Out of scope for v2.0

- Packaging a signed MSI installer.
- Automatically configuring applications that provide no supported local config or environment interface.
- Remote multi-user tenancy.
- Changing the upstream account-authentication protocol.
- Removing advanced role-based keys entirely.
