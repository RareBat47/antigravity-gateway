# Advanced Operations

The normal workflow does not require role keys or manual YAML editing. This document covers advanced operation only.

## API endpoints

- OpenAI: `http://127.0.0.1:8999/v1`
- Anthropic: `http://127.0.0.1:8999/v1/messages`
- Dashboard: `http://127.0.0.1:8999/admin/dashboard`
- Swagger: `http://127.0.0.1:8999/docs`

## Routing profiles

Use `GET /v1/routing/profiles` to inspect the supported public profiles. Exact upstream model IDs remain available for compatibility.

## Security

New installations bind to loopback and generate secrets. Remote access requires an explicit bind/tunnel decision and strict API authentication. Never publish local API keys in documentation or commit them to source control.

## Account lifecycle

Use the dashboard or `agw accounts` commands for OAuth connection, refresh, enable/disable, and removal. The encrypted vault and SQLite metadata must be backed up before manual maintenance.

## Diagnostics

```bash
.venv/Scripts/python -m agw.cli.main health
.venv/Scripts/python -m agw.cli.main quota
.venv/Scripts/python -m agw.cli.main models
```

Runtime quota status is generated and should not be committed as source documentation.
