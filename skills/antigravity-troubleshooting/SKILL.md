---
name: antigravity-troubleshooting
description: Step-by-step diagnostic workflows for resolving authentication failures, 429 rate limits, 400 schema errors, and network disconnects.
---

# Antigravity Troubleshooting Skill

## Common Failure Scenarios and Fixes

### 1. HTTP 401 Unauthorized from Gateway
- **Cause**: The client API key or admin key does not match the gateway configuration.
- **Fix**: Check `GATEWAY_API_KEY` in Hermes `config.yaml` against `GATEWAY_API_KEY` in the gateway `.env` or `config.yaml`.

### 2. HTTP 429 RESOURCE_EXHAUSTED / Account Pool Exhausted
- **Cause**: All registered accounts have exhausted their current quota window or hit Google Cloud Code rate limits.
- **Fix**:
  1. Inspect reset times with `agw quota`.
  2. Add another account to the pool via `agw accounts login`.
  3. If rate-limited on Claude, switch to Gemini: `gemini-3.5-flash` or `gemini-3.1-pro`.

### 3. Upstream HTTP 400 INVALID_ARGUMENT (Tool Call Schema Error)
- **Cause**: Upstream Gemini rejected an unsupported JSON Schema property (e.g. `anyOf`, `allOf`, `multipleOf`).
- **Fix**: Verify `agw/cloudcode/schema_sanitizer.py` is active. Ensure tool parameter definitions conform to standard object schemas with explicit properties.

### 4. `invalid_grant` / Account Token Revoked
- **Cause**: The Google password was changed, OAuth session expired, or permissions were revoked.
- **Fix**:
  1. Re-authenticate the account: `agw accounts login` or `agw accounts refresh {id}`.
  2. If permanently broken, remove it: `agw accounts remove {id}`.

### 5. Remote Connection Failures (Azure VM -> Gateway)
- **Cause**: Port 8999 is blocked by firewall, or the secure tunnel is down.
- **Fix**:
  1. Test connectivity from Azure VM: `curl -I https://gateway.yourdomain.com/health`
  2. Verify Cloudflare Tunnel or Tailscale status on both machines.
  3. Ensure reverse proxy passes standard `Upgrade: websocket` and `Accept: text/event-stream` headers.
