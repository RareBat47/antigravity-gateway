"""Friendly public routing profiles mapped to concrete gateway models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agw.routing.registry import ModelRegistry


@dataclass(frozen=True)
class RoutingProfile:
    name: str
    description: str
    preferred_models: tuple[str, ...]
    required_capability: str | None = None


PROFILES = {
    "auto": RoutingProfile("auto", "Best available route for this request", ("gemini-3.8-flash-high", "claude-sonnet-5-5-medium", "gemini-3.1-pro-low")),
    "fast": RoutingProfile("fast", "Fast Flash-first route", ("gemini-3.8-flash-high", "gemini-3.6-flash-medium")),
    "balanced": RoutingProfile("balanced", "Quality and latency balanced", ("claude-sonnet-5-5-medium", "gemini-3.8-flash-high", "gemini-3.1-pro-low")),
    "powerful": RoutingProfile("powerful", "Highest-quality route", ("claude-opus-5-5-medium", "gemini-3.1-pro-low", "claude-sonnet-5-5-medium")),
    "reasoning": RoutingProfile("reasoning", "Reasoning-capable route", ("claude-opus-5-5-medium", "gemini-3.1-pro-low", "claude-sonnet-5-5-medium"), "thinking"),
}


def profile_items() -> list[dict[str, Any]]:
    return [{"id": p.name, "description": p.description, "preferred_models": list(p.preferred_models), "required_capability": p.required_capability} for p in PROFILES.values()]


def resolve_profile(requested: str, registry: ModelRegistry) -> tuple[str, str, int]:
    profile = PROFILES.get(requested.strip().lower())
    if not profile:
        return registry.resolve_upstream(requested, strict=False)
    for model_id in profile.preferred_models:
        if registry.get_model(model_id):
            return registry.resolve_upstream(model_id)
    return registry.resolve_upstream("gemini-3.8-flash-high", strict=False)
