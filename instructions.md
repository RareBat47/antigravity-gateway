# Project: Antigravity Multi-Account Gateway for Hermes

## Mission

Build a production-quality, self-hosted gateway that allows my Hermes Agent running on an Azure VM to use Google Antigravity-accessible Gemini and Claude models through a single OpenAI-compatible API endpoint.

The gateway must support multiple Google/Antigravity accounts, persistent OAuth credentials, quota/usage monitoring, automatic account selection, cooldowns, failover, model routing, health monitoring, and an administrative API.

Do NOT modify Hermes unnecessarily. Hermes should see this system as a normal OpenAI-compatible provider.

The final architecture should be:

Windows PC / browser
│
│ Google OAuth
▼
Antigravity Gateway
├── Account Manager
├── OAuth/session manager
├── Quota monitor
├── Usage database
├── Account scheduler
├── Model router
├── Rate-limit/cooldown manager
├── Health monitor
└── OpenAI-compatible API
│
│ HTTPS / secure tunnel
▼
Azure VM
└── Hermes Agent
│
▼
https://gateway.example/v1

---

# 1. RESEARCH FIRST — DO NOT CODE IMMEDIATELY

Before implementing anything, clone and study these repositories.

## Primary reference

https://github.com/lomeliDev/antigravity-bridge

Study:

* OAuth implementation
* PKCE flow
* account storage
* multi-account architecture
* token refresh
* invalid_grant handling
* `/v1/chat/completions`
* streaming
* tool calling
* vision
* usage endpoints
* admin API
* account routing
* Hermes integration
* remote-server OAuth flow

This is particularly important because it already advertises:

* multi-account support
* OpenAI-compatible API
* automatic token refresh
* Hermes compatibility
* admin API
* `/v1/usage`
* `/v1/billing/subscription`

Do not blindly copy it. Extract the best architectural ideas.

## Secondary reference

https://github.com/usamashehab/antigravity-proxy

Study:

* minimal OAuth/token architecture
* Antigravity → Cloud Code Assist request translation
* model mapping
* OpenAI compatibility
* streaming
* tool/function calling
* OAuth refresh
* systemd deployment
* Hermes configuration

This repository explicitly demonstrates Hermes configuration against an Antigravity OpenAI-compatible proxy.

## Multi-account reference

https://github.com/thigas88/antigravity-proxy

Study:

* account management
* quota thresholds
* cooldowns
* rate-limit handling
* retry logic
* load balancing
* persistent token cache
* model-specific quota handling
* endpoint fallback

Pay particular attention to:

* `maxAccounts`
* `globalQuotaThreshold`
* per-account quota
* per-model quota
* cooldown logic
* retry/backoff behavior

## Hermes-specific reference

https://github.com/mrhisyammm/hermes-antigravity-auth

Study:

* Hermes plugin integration
* Antigravity account manager
* multiple accounts
* account rotation
* isolated cooldowns
* quota commands
* Hermes model registration
* account database structure

## Another Hermes implementation

https://github.com/kalyanace44/hermes-antigravity-auth-native

Study:

* isolated account store
* automatic proxy startup
* account rotation
* cooldown handling
* streaming
* tool calling
* thought-signature preservation
* Hermes slash commands

Do NOT assume these repositories are authoritative or safe merely because they exist. Verify their implementations and limitations.

---

# 2. SECURITY / TERMS REQUIREMENT

Before implementation, inspect each repository's license, documentation, and warnings.

This project must NOT attempt to bypass authentication, defeat quotas, evade security controls, forge credentials, or circumvent Google's access controls.

Use legitimate OAuth authorization and credentials belonging to accounts I am authorized to use.

Do not implement techniques intended to evade provider enforcement.

Do not expose OAuth refresh tokens, cookies, browser sessions, or credentials through the public API.

Never log:

* OAuth access tokens
* OAuth refresh tokens
* client secrets
* authorization codes
* cookies
* raw Authorization headers

If a referenced project uses questionable techniques, do not copy those techniques.

---

# 3. TARGET ARCHITECTURE

Build the gateway as an independent service.

Preferred architecture:

```
                CLIENTS
                   │
                   ▼
          ┌─────────────────┐
          │ Antigravity     │
          │ Gateway API     │
          └────────┬────────┘
                   │
   ┌───────────────┼────────────────┐
   ▼               ▼                ▼
```

Account Manager   Model Router    Quota Manager
│               │                │
└───────────────┼────────────────┘
▼
Account Pool
│
┌────────────┼────────────┐
▼            ▼            ▼
Account 1    Account 2    Account N
│            │            │
└────────────┼────────────┘
▼
Antigravity
│
▼
Google API

The API exposed to Hermes should remain stable even if the internal account implementation changes.

---

# 4. CORE API

Implement an OpenAI-compatible interface.

Minimum endpoints:

GET /v1/models

POST /v1/chat/completions

Support:

* streaming
* non-streaming
* multi-turn conversations
* system messages
* tool/function calls
* tool results
* structured output where backend supports it
* vision where backend supports it
* usage accounting

Also implement:

GET /health

GET /v1/usage

GET /admin/accounts

GET /admin/accounts/{id}

GET /admin/accounts/{id}/quota

POST /admin/accounts

POST /admin/accounts/{id}/enable

POST /admin/accounts/{id}/disable

POST /admin/accounts/{id}/refresh

POST /admin/accounts/{id}/reauth

GET /admin/health

GET /admin/usage

Protect all admin endpoints with a separate admin API key.

---

# 5. ACCOUNT MODEL

Create a persistent account registry.

Conceptually:

accounts:
id
email_hash_or_safe_identifier
display_name
status
enabled
oauth_state
token_state
quota_state
cooldown_state
health_state
created_at
updated_at
last_used_at
last_success_at
last_failure_at

Never store sensitive credentials in plaintext unless required by the legitimate OAuth implementation.

Prefer:

* OS keyring
* encrypted credential store
* restricted filesystem permissions
* environment-provided encryption key

If the reference project already has a secure mechanism, study it and improve it where necessary.

---

# 6. MULTI-ACCOUNT ROUTER

Implement an account scheduler.

The scheduler should consider:

1. account enabled/disabled
2. authentication validity
3. current cooldown
4. model compatibility
5. recent failures
6. remaining quota
7. account health
8. recent usage
9. configured priority

Example:

Request:
claude-sonnet-4-6

Router:

Account 1
quota: 8%
cooldown: none

Account 2
quota: 64%
cooldown: none

Account 3
quota: 90%
cooldown: active

Select Account 2.

Do NOT simply rotate round-robin.

Use weighted health/quota-aware scheduling.

---

# 7. QUOTA SYSTEM

Create a normalized internal quota representation.

For each account/model-family track, when available:

* remaining percentage
* remaining tokens/requests
* reset timestamp
* quota window
* last checked timestamp
* source
* confidence
* cooldown state

Support different quota windows.

Example:

Account A:

Gemini:
5-hour: 73%
weekly: 91%

Claude:
5-hour: 41%
weekly: 83%

Do not invent quota information when the upstream provider does not expose it.

If exact quota cannot be obtained, mark it:

quota_status: unknown

and let the scheduler use other signals.

---

# 8. QUOTA MONITOR

Implement a background quota monitor.

It should:

* periodically inspect account health/quota
* update persistent state
* avoid excessive polling
* back off after failures
* detect stale quota information
* expose quota through admin API
* optionally write human-readable Markdown reports

Create:

data/quota-state.json

and optionally:

docs/account-status.md

Example:

# Antigravity Account Status

Updated: YYYY-MM-DD HH:MM UTC

| Account   |  Gemini | Claude | Status   | Cooldown |
| --------- | ------: | -----: | -------- | -------- |
| account-1 |     82% |    61% | healthy  | none     |
| account-2 |     43% |    91% | healthy  | none     |
| account-3 | unknown |    77% | degraded | 120s     |

This file is primarily for humans and Hermes skills.

---

# 9. FAILURE HANDLING

Implement intelligent failure classification.

Examples:

401:
authentication problem

403:
permission/access problem

429:
rate/quota limiting

5xx:
upstream failure

network timeout:
transient failure

invalid_grant:
OAuth credential invalid/revoked

Do not blindly retry every error.

Use:

* exponential backoff
* jitter
* per-account cooldown
* per-model-family cooldown
* maximum retry count
* account failover

Example:

Account 1
↓
429
↓
cooldown Account 1 for model family
↓
try Account 2
↓
success

Do not mark the entire account dead if only one model family is rate-limited.

---

# 10. MODEL ROUTING

Create a model registry.

Example:

models:
gemini-3.1-pro
gemini-3.5-flash
claude-sonnet-4-6
claude-opus-4-6

Each model should map to:

* provider backend identifier
* model family
* capabilities
* streaming support
* vision support
* tools support
* thinking support
* quota family

Make the mapping configurable rather than hardcoded throughout the application.

---

# 11. HERMES INTEGRATION

Hermes should require only one provider.

Example conceptual configuration:

provider:
custom

base_url:
https://YOUR-GATEWAY/v1

api_key:
YOUR_GATEWAY_KEY

default_model:
gemini-3.5-flash

Verify actual Hermes configuration syntax against the installed Hermes version before writing configuration.

Do not assume the syntax from an old repository is still correct.

Test:

1. Hermes → gateway health
2. Hermes → `/v1/models`
3. Hermes → simple completion
4. Hermes → streaming completion
5. Hermes → tool call
6. Hermes → model switch
7. Hermes → account failover

---

# 12. REMOTE WINDOWS ↔ AZURE DESIGN

The gateway must support two deployment modes.

## Mode A

Gateway runs on Windows.

Windows:

Antigravity Gateway
↓
secure HTTPS/tunnel
↓
Azure Hermes

## Mode B

Gateway runs on Azure.

Windows/browser:

OAuth authorization
↓
Azure Gateway
↓
Hermes

Prefer Mode B only if the OAuth architecture can securely operate remotely.

For remote OAuth, provide a browser-based or manual callback mechanism similar to the reference repositories.

Do NOT expose OAuth callbacks publicly without authentication and CSRF/PKCE protections.

---

# 13. NETWORK SECURITY

The API must NOT be exposed directly to the public Internet without authentication.

At minimum:

* API key authentication
* admin API key
* HTTPS
* request size limits
* timeout limits
* rate limiting
* secure headers
* CORS disabled unless required
* admin endpoint isolation
* structured audit logs

Never expose:

/admin/*
OAuth credentials
token stores
internal debugging endpoints

to unauthenticated clients.

If using Cloudflare Tunnel, Tailscale, SSH reverse tunnel, or another secure tunnel, document the selected option and why.

---

# 14. OBSERVABILITY

Create structured logs.

Example:

2026-09-20T01:20:01Z
request_id=abc123
model=gemini-3.5-flash
account=account-2
status=success
latency_ms=4210

For failures:

request_id=abc124
model=claude-sonnet-4-6
account=account-2
status=429
action=cooldown_and_failover
next_account=account-4

Never include secrets.

Add:

* request count
* success rate
* failure rate
* latency
* account usage
* failover count
* cooldown count
* quota refresh timestamp

---

# 15. HERMES SKILLS

Create dedicated Hermes skills for operating the gateway.

At minimum:

skills/
├── antigravity-status/
├── antigravity-quota/
├── antigravity-accounts/
├── antigravity-routing/
├── antigravity-health/
└── antigravity-troubleshooting/

Each skill should contain an MD file explaining:

* purpose
* when to use it
* commands/API calls
* expected output
* failure handling
* security considerations
* examples

Especially create:

antigravity-quota/SKILL.md

and

antigravity-accounts/SKILL.md

so Hermes can understand:

"Which accounts exist?"

"Which accounts are healthy?"

"Which models have usable quota?"

"When should I switch accounts?"

"How do I add a new account?"

"How do I disable a broken account?"

---

# 16. SELF-DOCUMENTATION

The project must maintain:

README.md

ARCHITECTURE.md

SECURITY.md

OPERATIONS.md

TROUBLESHOOTING.md

API.md

ACCOUNT-MANAGEMENT.md

QUOTA-MONITORING.md

HERMES-INTEGRATION.md

DECISIONS.md

The documentation should be updated as implementation decisions change.

---

# 17. TESTING

Build automated tests for:

OAuth state handling

account persistence

token refresh

quota parsing

model routing

account selection

cooldowns

429 handling

401 handling

403 handling

5xx retry

network timeout

failover

streaming

tool calls

vision

admin authentication

API authentication

concurrent requests

account persistence after restart

gateway restart

stale quota data

invalid/revoked account

No test should use real credentials in the repository.

Create mock upstream providers for automated tests.

---

# 18. PERFORMANCE

The gateway must support concurrent Hermes requests.

Do not serialize all requests globally.

Concurrency should be controlled per account/model where appropriate.

Avoid unnecessary quota API calls.

Use caching.

Use async I/O where it materially improves throughput.

---

# 19. DATABASE

Start with SQLite unless research shows a better reason.

Suggested tables:

accounts

oauth_credentials_metadata

quota_snapshots

usage_events

cooldowns

model_registry

routing_events

health_events

Do not store raw OAuth secrets in ordinary database rows.

Use encrypted credential storage separately.

---

# 20. ADMIN DASHBOARD

If practical, create a lightweight web dashboard.

Show:

Accounts

Authentication status

Gemini quota

Claude quota

Cooldowns

Last request

Last error

Model availability

Gateway health

Request statistics

Failover events

The dashboard must never display raw tokens.

---

# 21. CLI

Create an administration CLI such as:

agw accounts list

agw accounts add

agw accounts remove

agw accounts enable

agw accounts disable

agw accounts login

agw accounts refresh

agw quota

agw quota --account ACCOUNT

agw models

agw health

agw logs

agw test

Use clear exit codes.

---

# 22. DEPLOYMENT

Support Linux systemd deployment.

Provide:

systemd/antigravity-gateway.service

Also provide:

.env.example

config.example.yaml

install.sh

uninstall.sh

upgrade.sh

backup.sh

restore.sh

The service must run as a dedicated non-root user.

Use restrictive permissions for:

configuration

credential files

database

logs

---

# 23. DEVELOPMENT WORKFLOW

Work in phases.

PHASE 0:
Research all reference repositories.

PHASE 1:
Architecture and security design.

PHASE 2:
Minimal OAuth/account manager.

PHASE 3:
Single-account OpenAI-compatible API.

PHASE 4:
Multi-account support.

PHASE 5:
Quota monitoring.

PHASE 6:
Smart routing and cooldowns.

PHASE 7:
Hermes integration.

PHASE 8:
Admin API.

PHASE 9:
Dashboard/CLI.

PHASE 10:
Automated testing.

PHASE 11:
Production deployment.

PHASE 12:
Documentation and operational skills.

After every phase:

* run tests
* inspect logs
* update documentation
* record decisions
* do not move forward with known broken functionality unless explicitly documented

---

# 24. IMPORTANT: DON'T REINVENT WORK THAT ALREADY EXISTS

Before implementing a subsystem, determine whether one of the reference repositories already provides a working implementation.

For each subsystem, create a short decision record:

Subsystem:
OAuth

Reference:
antigravity-bridge

Decision:
reuse / adapt / rewrite

Reason:
...

Do this for:

OAuth

account storage

quota collection

routing

cooldowns

OpenAI protocol

streaming

tool calls

vision

Hermes integration

remote authentication

admin API

---

# 25. REPOSITORY REFERENCES

Primary:

https://github.com/lomeliDev/antigravity-bridge

https://github.com/usamashehab/antigravity-proxy

https://github.com/thigas88/antigravity-proxy

Hermes-specific:

https://github.com/mrhisyammm/hermes-antigravity-auth

https://github.com/kalyanace44/hermes-antigravity-auth-native

Additional reference:

https://github.com/allenlinli/antigravity-manager

Study its multi-account dashboard, OAuth management, quota monitoring, and API proxy architecture.

Do not blindly combine repositories.

First understand them.

---

# 26. FINAL ACCEPTANCE CRITERIA

The project is considered complete only when:

[ ] Gateway starts reliably.

[ ] OAuth account can be added.

[ ] OAuth credentials survive restart.

[ ] Token refresh works.

[ ] Multiple accounts can be configured.

[ ] `/v1/models` works.

[ ] `/v1/chat/completions` works.

[ ] Streaming works.

[ ] Tool calls work.

[ ] Vision works where backend supports it.

[ ] Account quota can be inspected.

[ ] Account health can be inspected.

[ ] Smart account selection works.

[ ] Rate-limit cooldown works.

[ ] Failed account automatically fails over.

[ ] Per-model-family cooldown works.

[ ] Gateway survives restart.

[ ] Hermes can use the gateway.

[ ] Hermes can switch models.

[ ] Hermes can trigger failover transparently.

[ ] Admin API is authenticated.

[ ] Public API is authenticated.

[ ] No secrets appear in logs.

[ ] Automated tests pass.

[ ] systemd deployment works.

[ ] Backup/restore works.

[ ] Documentation is complete.

[ ] Hermes operational skills are installed.

---

# 27. OPERATING PRINCIPLE

The most important design rule:

Hermes should NOT need to know which Antigravity account is being used.

Hermes asks:

"Give me model X."

The gateway decides:

"Account 4 currently has the appropriate authentication, quota, health and cooldown state, so use Account 4."

If Account 4 fails:

"Account 4 is temporarily unavailable. Select another eligible account."

This abstraction must remain intact throughout the implementation.

Begin by researching the repositories and producing:

1. architecture comparison
2. security assessment
3. component reuse matrix
4. proposed architecture
5. implementation roadmap
6. risks and unknowns

Do NOT begin writing production code until this research/design phase is complete.

After the design is presented, proceed autonomously through the implementation phases, testing each phase before continuing.
