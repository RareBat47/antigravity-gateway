"""Dynamic model registry and mapping definitions."""

from typing import Any, Dict, List, Optional, Tuple
from agw.constants import DEFAULT_MODELS, FAMILY_CLAUDE, FAMILY_GEMINI

Tuple_Upstream = Tuple[str, str, int]


MODEL_ALIASES: Dict[str, str] = {
    # Claude 5.5 Generation Aliases
    "claude-opus-5-5": "claude-opus-5-5-medium",
    "claude-opus-5.5": "claude-opus-5-5-medium",
    "claude-5-5-opus": "claude-opus-5-5-medium",
    "claude-5.5-opus": "claude-opus-5-5-medium",
    "claude-sonnet-5-5": "claude-sonnet-5-5-medium",
    "claude-sonnet-5.5": "claude-sonnet-5-5-medium",
    "claude-5-5-sonnet": "claude-sonnet-5-5-medium",
    "claude-5.5-sonnet": "claude-sonnet-5-5-medium",
    # Claude 4.6 Generation Aliases
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-sonnet-4.6": "claude-sonnet-4-6",
    "claude-3-7-sonnet": "claude-sonnet-4-6",
    "claude-3.7-sonnet": "claude-sonnet-4-6",
    "claude-3-5-sonnet": "claude-sonnet-4-6",
    "claude-3.5-sonnet": "claude-sonnet-4-6",
    "claude-opus": "claude-opus-4-6-thinking",
    "claude-opus-4-6": "claude-opus-4-6-thinking",
    "claude-3-opus": "claude-opus-4-6-thinking",
    "claude-3.0-opus": "claude-opus-4-6-thinking",
    # Gemini 3.8 / 3.7 / 3.6 Flash Aliases
    "gemini-flash": "gemini-3.8-flash-high",
    "gemini-3.8-flash": "gemini-3.8-flash-high",
    "gemini-3.8-flash-tiered": "gemini-3.8-flash-high",
    "gemini-3.8-flash-tiered-high": "gemini-3.8-flash-high",
    "gemini-3.7-flash": "gemini-3.8-flash-high",
    "gemini-3.7-flash-medium": "gemini-3.8-flash-high",
    "gemini-3.6-flash": "gemini-3.6-flash-high",
    "gemini-3.5-flash": "gemini-3.8-flash-high",
    "gemini-2.5-flash": "gemini-3.8-flash-high",
    "gemini-2.0-flash": "gemini-3.8-flash-high",
    "gemini-1.5-flash": "gemini-3.8-flash-high",
    # Gemini Pro Reasoning Aliases
    "gemini-3.1-pro": "gemini-3.1-pro-low",
    "gemini-3.1-pro-high": "gemini-pro-agent",
    "gemini-pro": "gemini-3.1-pro-low",
    "gemini-2.5-pro": "gemini-3.1-pro-low",
    "gemini-1.5-pro": "gemini-3.1-pro-low",
    # GPT-OSS 120B (Medium)
    "gpt-oss": "gpt-oss-120b-medium",
    "gpt-oss-120b": "gpt-oss-120b-medium",
    "gpt-4o": "gpt-oss-120b-medium",
}


def normalize_model_id(model_id: str) -> str:
    """Normalize model identifier by removing prefixes and resolving aliases."""
    cleaned = model_id.strip()
    if cleaned.startswith("models/"):
        cleaned = cleaned[7:]
    return MODEL_ALIASES.get(cleaned, cleaned)


class ModelRegistry:
    """Manages models supported by the gateway with dynamic auto-registration."""

    def __init__(self, custom_models: Optional[Dict[str, Any]] = None):
        self._models = dict(DEFAULT_MODELS)
        if custom_models:
            self._models.update(custom_models)

    def register_model(self, model_id: str, definition: Dict[str, Any]) -> None:
        """Register or update a model definition dynamically."""
        self._models[model_id] = definition

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model definition by ID or alias."""
        normalized = normalize_model_id(model_id)
        return self._models.get(normalized) or self._models.get(model_id)

    def list_model_ids(self) -> List[str]:
        """Return list of supported model IDs."""
        return list(self._models.keys())

    def resolve_upstream(self, model_id: str) -> Tuple_Upstream:
        """Resolve requested model to (upstream_id, family, max_output_tokens)."""
        normalized = normalize_model_id(model_id)
        model = self.get_model(normalized) or self.get_model(model_id)
        if not model:
            raise ValueError(f"Model '{model_id}' is not supported or not enabled on this gateway.")
        return (
            model.get("upstream_id", normalized),
            model.get("family", FAMILY_GEMINI),
            model.get("max_output_tokens", 32768),
        )

    def list_models_openai(self) -> List[Dict[str, Any]]:
        """List models in OpenAI /v1/models format."""
        items = []
        for model_id, data in self._models.items():
            items.append({
                "id": model_id,
                "object": "model",
                "created": 1710000000,
                "owned_by": "antigravity-gateway",
                "permission": [],
                "root": model_id,
                "parent": None,
                "description": data.get("description", model_id),
            })
        return items

    def is_valid_model(self, model_id: str) -> bool:
        """Check if model exists in registry."""
        normalized = normalize_model_id(model_id)
        return normalized in self._models or model_id in self._models

