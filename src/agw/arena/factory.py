from typing import Optional, List
from agw.arena.provider import ArenaProvider
from agw.arena.mock_provider import MockArenaProvider
from agw.arena.real_provider import RealArenaProvider


def get_arena_provider(endpoints: Optional[List[str]] = None, timeout: float = 300.0, use_mock: bool = False) -> ArenaProvider:
    """Return RealArenaProvider unless use_mock is True."""
    if use_mock:
        return MockArenaProvider()
    return RealArenaProvider(endpoints=endpoints, timeout=timeout)
