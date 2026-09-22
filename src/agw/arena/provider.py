import abc
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

class ArenaProvider(abc.ABC):
    """Abstract interface for communicating with Arena.ai."""

    @abc.abstractmethod
    async def fetch_available_models(self, access_token: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch model metadata and live quotas."""
        pass

    @abc.abstractmethod
    async def generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any], str]:
        """Execute non-streaming request. Returns (status_code, response_json, raw_text)."""
        pass

    @abc.abstractmethod
    async def stream_generate_content(
        self, access_token: str, envelope: Dict[str, Any]
    ) -> AsyncIterator[Tuple[int, str]]:
        """Execute streaming request with SSE. Yields (status_code, line_or_chunk)."""
        pass
