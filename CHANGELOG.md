# Changelog

All notable changes to the Arena Multi-Account Gateway project will be documented in this file.

## [0.2.0-alpha] - 2026-09-22

### Added
- `ArenaProvider` abstraction interface in `src/agw/arena/provider.py`.
- `MockArenaProvider` (`src/agw/arena/mock_provider.py`) returning OpenAI-compatible JSON/SSE streaming responses for automated testing.
- `RealArenaProvider` (`src/agw/arena/real_provider.py`) for routing completions directly to `chat.lmsys.org/api` with injected session cookies.
- `/auth/manual` endpoint in `src/agw/api/routes_auth.py` for headless credential and cookie ingestion into the encrypted vault.
- `OVERNIGHT_BUILD_REPORT.md` detailing architectural changes, testing status, and client integration settings.
- `smoke_test.py` for fast DI and application initialization checks.

### Changed
- Refactored `src/agw/api/routes_v1.py` into a direct pass-through for OpenAI chat completions, removing legacy Gemini-to-OpenAI bidirectional translation.
- Overhauled `src/agw/accounts/manager.py` to support raw cookie storage in place of Google OAuth PKCE tokens.
- Preserved multi-account scheduler, error classifier, and isolated account cooldown logic during 429 quota exhaustion.

## [0.1.0] - Prior Baseline
- Initial Antigravity CloudCode proxy baseline with Google OAuth PKCE, SQLite metadata, and Fernet token vault.
