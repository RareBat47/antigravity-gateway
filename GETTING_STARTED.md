# Antigravity Gateway

## Install once

1. Clone this repository.
2. Run `install.bat`.
3. Start with `run.bat`.
4. Open `http://127.0.0.1:8999/admin/dashboard`.
5. Connect your Google accounts.
6. Use the dashboard's local integration setup.

Normal clients use:

- OpenAI-compatible base URL: `http://127.0.0.1:8999/v1`
- Anthropic-compatible base URL: `http://127.0.0.1:8999`
- Model: `auto`

The gateway selects a healthy model/account route automatically. Exact model IDs and advanced role keys are available only in the advanced configuration area.

## Health check

```bash
curl http://127.0.0.1:8999/health
```

## Routing profiles

- `auto`: best available route
- `fast`: Flash-first route
- `balanced`: quality/latency balance
- `powerful`: high-quality route
- `reasoning`: thinking-capable route

## Account connection

Use **Connect Google Account** in the dashboard. Credentials remain in the encrypted local vault; they are not placed in documentation or client config files.

## Windows startup

Use the dashboard integration action or run `scripts/install_startup.bat` when you explicitly want background startup. Use `scripts/uninstall_startup.bat` to remove it.
