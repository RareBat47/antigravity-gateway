# Antigravity Workspace Configuration

## Project: Antigravity Gateway (AGW)
- **Language**: Python 3.12 (asynchronous FastAPI, httpx, SQLite, cryptography)
- **Virtualenv**: `.venv`
- **Port**: `8999` (OpenAI-compatible `/v1` endpoint)
- **Target Integrations**: Hermes Agent, Antigravity CLI (`agy`), Antigravity Python SDK (`google-antigravity`)

## Guidelines & Rules
- Follow architectural guidelines in [.agents/rules/agw-architecture.md](.agents/rules/agw-architecture.md).
- Use operational runbooks in [.agents/skills/agw-ops/SKILL.md](.agents/skills/agw-ops/SKILL.md).
- Maintain 5 dedicated models: `claude-opus-4-6-thinking`, `gemini-3.8-flash-high`, `gemini-3.1-pro-low`, `claude-sonnet-4-6`, `gpt-oss-120b-medium`.
- Preserve SSE heartbeat keep-alive (8s intervals) and thought-signature caching across all streaming/tool modifications.
