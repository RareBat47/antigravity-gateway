from typing import Optional, List
from agw.arena.provider import ArenaProvider
from agw.arena.mock_provider import MockArenaProvider


def get_arena_provider(endpoints: Optional[List[str]] = None, timeout: float = 300.0, use_mock: bool = False) -> ArenaProvider:
    """
    Always returns MockArenaProvider for now.

    WHY: Arena.ai does not expose a public /api/chat/completions REST endpoint.
    All Arena interactions happen through authenticated browser sessions (Supabase SSR cookies +
    Cloudflare clearance). The real provider requires a Playwright/browser session approach
    to POST requests via the frontend JS fetch path, not a direct HTTP API call.

    NEXT STEP: When you are ready to add real Arena accounts:
    1. Open arena.ai in Chrome with DevTools open (Network tab).
    2. Send a message in Direct Chat mode.
    3. Capture the exact XHR POST request URL, headers, and payload format.
    4. Paste them into the Dashboard -> Add Arena Account with those cookie values.
    5. Update RealArenaProvider with the correct discovered endpoint.

    FOR NOW: MockArenaProvider makes OpenCode fully functional so you can code
    and test the full pipeline end-to-end today.
    """
    return MockArenaProvider()
