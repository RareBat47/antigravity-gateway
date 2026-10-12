# Antigravity Gateway: Master Project Handover & Architecture Briefing

**Generated for OpenCode Agent Session**  
**Working Directory:** `/home/rarebat/Projects_secured/Secured_google_AI_extractor_api-format/antigravity-gateway-src/antigravity-gateway-main`  
**Git Remote:** `https://github.com/RareBat47/antigravity-gateway.git` (`main` branch)

---

## 1. Executive Overview & Purpose

The **Antigravity Gateway** is an enterprise-grade AI proxy, session multiplexer, and API extraction gateway. It combines multiple Google AI channels and accounts into unified OpenAI/Anthropic/Google-compatible API endpoints for downstream clients (such as OpenCode, Cursor, Continue, Claude Dev, and custom scripts).

It provides:
- **Zero-Cost Multi-Account Multiplexing**: Pools 7 enrolled Google accounts across 4 separate communication channels (28 total connection endpoints).
- **Automated Session Keep-Alive**: Background daemon extracts and updates encrypted session cookies from local Chromium profiles hourly, preventing session expiry.
- **Dynamic Quota Balancing & Failover**: Automatic switching when individual account quotas are exhausted.
- **Unified Endpoints**: Exposes `/v1/chat/completions`, `/v1/models`, `/v1/messages`, and `/admin/` dashboards.

---

## 2. The 4 Channels Supported

1. **`agy` (Google Antigravity / Cloud Code OAuth)**:
   - Protocol: Internal Google Cloud Code backend (`daily-cloudcode-pa.googleapis.com/v1internal:generateContent`).
   - Auth: Google OAuth Bearer tokens (`ya29...`) with refresh tokens in SQLite vault.
   - Models: Raw Claude Opus 4.6, Claude Sonnet 4.6, Gemini 3.8 Flash, Gemini 3.1 Pro High/Low, Gemini Pro Agent, Gemini 3.1 Flash Image.

2. **`gweb` (Google Gemini Web Multi-User Sessions)**:
   - Protocol: Reverse-engineered Gemini Web Chat API (`gemini.google.com/_/BardChatUi/data/batchexecute`).
   - Auth: Web session cookies (`__Secure-1PSID`, `__Secure-1PSIDTS`).
   - Quota: 2,400 credits per 5-hour rolling window per account (16,800 credits across all 7 accounts).
   - Features: Web grounding / live Google Search results, thinking scratchpad.

3. **`gcli` (Gemini CLI OAuth)**:
   - Protocol: Command-line OAuth client tokens.
   - High-speed fallback for Code Assist and text completions.

4. **`studio` (Google AI Studio API Keys)**:
   - Protocol: Official Google Generative Language REST API (`generativelanguage.googleapis.com`).
   - Dedicated API keys per account or fallback global key pool.
   - Models: Imagen 3.0 generation (`imagen-3.0-generate-002`), Gemini 2.5 Pro / Flash.

---

## 3. Registered Accounts & Infrastructure Status

All 7 accounts are enrolled and verified active in the encrypted SQLite database (`gateway.db`):
1. `arifinnabid47@gmail.com` (4/4 Channels Active)
2. `arifinnabidconsole47@gmail.com` (4/4 Channels Active)
3. `arifinnabid04@gmail.com` (4/4 Channels Active)
4. `2103117@student.ruet.ac.bd` (4/4 Channels Active)
5. `atrostaz02@gmail.com` (4/4 Channels Active)
6. `atrostaz03@gmail.com` (4/4 Channels Active)
7. `atrostaz05@gmail.com` (3/4 Channels Active, studio on global pool)

**System Services Running:**
- **Gateway Server**: `antigravity-gateway.service` running on `http://127.0.0.1:8999`.
- **Auto-Keeper Timer**: `antigravity-gweb-keeper.timer` running hourly user systemd service.
- **OpenCode Web Server**: PID `181800` on port `http://127.0.0.1:4096`.

---

## 4. Discovered Models Catalog & Evidence

Querying `daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels` discovered 25 upstream models:

### A. Flagship Frontier & Reasoning
- `claude-opus-4-6-thinking`: 250,000 context, native thinking, vertex `claude-opus-4-6@default`.
- `claude-sonnet-4-6`: 250,000 context, native thinking, vertex `claude-sonnet-4-6@default`.
- `gemini-3.1-pro-high` & `gemini-3.1-pro-low`: 1,048,576 context, thinking enabled.
- `gemini-2.5-pro`: 1,048,576 context.

### B. High-Speed Coding & Agents
- `gemini-3.8-flash-tiered`: 1,048,576 context, thinking enabled.
- `gemini-pro-agent`: Tailored for multi-turn tool calling and agent loops.
- `gemini-3.6-flash-high`, `gemini-3.6-flash-medium`, `gemini-3.6-flash-low`: 1M context.
- `gpt-oss-120b-medium`: 131,072 context on Vertex.

### C. Image & Video Generation
- **Image Generation Verified Live**: `gemini-3.1-flash-image` generated a 1,002,452 byte JPEG in live tests. AI Studio has `imagen-3.0-generate-002`.
- **Video Generation**: `veo-2.0-generate-001` client code is wired; Google currently gates upstream access via enterprise waitlists. Multimodal video ingestion is supported up to 1-2 hours of video input.

---

## 5. Reverse-Engineered Creative AI Capabilities (Google Labs)

The user is interested in integrating additional Google creative platforms:
1. **Google Playground (`playground.google`)**: No-code 2D/3D game builder using Gemini code-gen + WebGL.
2. **Project Genie**: DeepMind world model (`myscience/open-genie`, `FLAIROx/jafar`).
3. **Google Flow Suite (`flow.google.com`)**: AI creative studio for cinematic video assets (`gflow-cli`, `flowkit`, `batchexecute`).
4. **Flow Music / MusicFX (`labs.google/fx/tools/music-fx`)**: Text-to-audio engine using DeepMind Lyria. Community extractors: `debasishtripathy13/Google-Music-FX-unofficial-` and `0x7o/AITestKitchen`.
5. **MusicFX DJ**: Real-time mixing board with 16 prompt weights and live Web Audio synthesis.

> **Key Architectural Synergy**: All these Google Labs tools use the exact same cookie authentication (`__Secure-1PSID`, `__Secure-1PSIDTS`) that the gateway's `gweb_auto_keeper` already automatically extracts from Chromium!

---

## 6. Codebase File Map

- `src/antigravity/app.py`: FastAPI application entrypoint, CORS, exception handlers.
- `src/antigravity/client.py`: Upstream HTTP client handling all 4 channels, token refreshing, and raw response parsing.
- `src/antigravity/database/repository.py`: SQLite repository (`gateway.db`) managing accounts, channels, quotas, and AES-256 encrypted secrets.
- `src/antigravity/routes_admin.py`: Administration APIs (`/admin/accounts-probe-all-global`, `/admin/refresh-all`, `/admin/metrics`).
- `src/antigravity/static/dashboard.html`: Web management interface.
- `scripts/gweb_auto_keeper.py`: Automated Chromium cookie extraction, database injection, and gateway hot-reloading script.
- `tests/`: Complete pytest test suite (78 tests passing).

---

## 7. Development Guidelines for OpenCode

1. **Keep Tests Green**: Always run `pytest tests/` after modifying gateway code.
2. **Vault Security**: Never store raw credentials in plaintext; all sensitive values must go through `encrypt_value()` in `repository.py`.
3. **Git Cleanliness**: Changes are tracked on `main`. Remote repository is `RareBat47/antigravity-gateway`.
4. **Service Health**: When updating backend routes or models, run `systemctl --user restart antigravity-gateway.service` and verify via `curl http://127.0.0.1:8999/healthz`.
