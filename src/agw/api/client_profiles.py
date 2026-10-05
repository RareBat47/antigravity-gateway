"""Named client API profiles with one shared complete model catalog."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ClientProfile(BaseModel):
    id: str
    name: str
    description: str
    protocol: str
    key: str


DEFAULT_CLIENT_PROFILES = (
    ("hermes", "Hermes Agent", "OpenAI-compatible endpoint exposing every active gateway model", "openai"),
    ("claude-code", "Claude Code", "Anthropic-compatible endpoint exposing every active gateway model", "anthropic"),
    ("opencode", "OpenCode", "OpenAI-compatible endpoint exposing every active gateway model", "openai"),
)


def profile_items(config: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": pid,
            "name": name,
            "description": description,
            "protocol": protocol,
            "base_url": "http://127.0.0.1:8999" if protocol == "anthropic" else "http://127.0.0.1:8999/v1",
            "model": "auto",
            "api_key": "use-generated-local-key",
        }
        for pid, name, description, protocol in DEFAULT_CLIENT_PROFILES
    ]
