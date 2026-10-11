# Client Integrations

AGY exposes standard local endpoints. Use the generated local key from the dashboard or the configured local environment profile; do not copy keys into source code.

## OpenAI-compatible clients

```text
Base URL: http://127.0.0.1:8999/v1
Model: auto
```

Python SDK example:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8999/v1", api_key="<local-key>")
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Anthropic-compatible clients

```text
Base URL: http://127.0.0.1:8999
Model: claude-sonnet-4-6 or reasoning
```

Endpoint:

```text
POST http://127.0.0.1:8999/v1/messages
```

## Supported automated presets

The dashboard can detect and configure OpenCode and Continue. Existing files are backed up and repeated application is idempotent.

Aider, Claude Code, Cursor, Cline, and Roo Code may require their own provider settings depending on installed version. The dashboard reports whether an adapter can configure them automatically instead of claiming unsupported changes succeeded.

## Troubleshooting

1. Check `http://127.0.0.1:8999/health`.
2. Confirm at least one account is connected and active.
3. Restart applications after changing environment variables.
4. Use `/docs` to inspect the live API contract.
