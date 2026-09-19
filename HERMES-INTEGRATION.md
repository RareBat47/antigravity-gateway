# Hermes Agent Integration Guide — Antigravity Gateway

This guide covers integrating the Antigravity Multi-Account Gateway with Hermes Agent running on an Azure VM or local workstation.

---

## 1. Zero Hermes Modification Guarantee

Hermes Agent interacts with this gateway purely as a standard **OpenAI-compatible** provider. No code modifications or monkey patches are made to Hermes.

---

## 2. Hermes Configuration

In your Hermes configuration file (`~/.hermes/config.yaml`):

```yaml
model:
  provider: antigravity
  default: gemini-3.5-flash
  base_url: http://127.0.0.1:8999/v1
  api_key: "agw-hermes-secret-key-change-me"

providers:
  antigravity:
    base_url: http://127.0.0.1:8999/v1
    api_key: "agw-hermes-secret-key-change-me"
    api_mode: openai
```

If connecting over a remote tunnel (e.g. from Azure VM to your Windows PC):
```yaml
model:
  provider: antigravity
  default: gemini-3.5-flash
  base_url: https://gateway.yourdomain.com/v1
  api_key: "agw-hermes-secret-key-change-me"
```

---

## 3. Installing Operational Skills in Hermes

Copy the pre-packaged skills into Hermes's skills directory:

```bash
# On Linux / macOS:
cp -r skills/* ~/.hermes/skills/

# On Windows:
Copy-Item -Recurse skills\* $env:USERPROFILE\.hermes\skills\
```

### Available Skills
1. `antigravity-status`: Inspect gateway connectivity, active account count, and traffic.
2. `antigravity-quota`: Inspect remaining percentages and reset times.
3. `antigravity-accounts`: List, enable, disable, and refresh accounts.
4. `antigravity-routing`: View model mapping and scheduler behavior.
5. `antigravity-health`: Monitor account health scores and latencies.
6. `antigravity-troubleshooting`: Diagnose and resolve errors.

---

## 4. Testing End-to-End Hermes Integration

1. Start Hermes Agent:
   ```bash
   hermes
   ```
2. Test a basic prompt:
   ```
   > /model gemini-3.5-flash
   > What is the capital of France?
   ```
3. Test tool calling:
   ```
   > List the files in the current directory.
   ```
4. Test model switching:
   ```
   > /model claude-sonnet-4-6
   > Write a Python binary search implementation.
   ```
