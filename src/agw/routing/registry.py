"""Dynamic model registry, fuzzy matcher, and mapping definitions."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from agw.constants import DEFAULT_MODELS, FAMILY_CLAUDE, FAMILY_GEMINI, FAMILY_GPT

logger = logging.getLogger("agw.routing.registry")

Tuple_Upstream = Tuple[str, str, int]

DEFAULT_FALLBACK_MODEL = "gemini-3.8-flash-high"


MODEL_ALIASES: Dict[str, str] = {
    # Default & Generic Aliases
    "default": "gemini-3.8-flash-high",
    "auto": "gemini-3.8-flash-high",
    "antigravity": "gemini-3.8-flash-high",
    "coding": "gemini-3.8-flash-high",
    "planning": "claude-opus-5-5-medium",
    "debugging": "claude-sonnet-5-5-medium",
    "pro": "gemini-3.1-pro-low",

    # Claude 5.5 Generation Aliases
    "claude-opus-5-5": "claude-opus-5-5-medium",
    "claude-opus-5.5": "claude-opus-5-5-medium",
    "claude-5-5-opus": "claude-opus-5-5-medium",
    "claude-5.5-opus": "claude-opus-5-5-medium",
    "claude-sonnet-5-5": "claude-sonnet-5-5-medium",
    "claude-sonnet-5.5": "claude-sonnet-5-5-medium",
    "claude-5-5-sonnet": "claude-sonnet-5-5-medium",
    "claude-5.5-sonnet": "claude-sonnet-5-5-medium",
    # Claude compatibility aliases now route to the verified 5.5 generation
    "claude-sonnet": "claude-sonnet-5-5-medium",
    "claude-sonnet-4.6": "claude-sonnet-5-5-medium",
    "claude-3-7-sonnet": "claude-sonnet-5-5-medium",
    "claude-3.7-sonnet": "claude-sonnet-5-5-medium",
    "claude-3-5-sonnet": "claude-sonnet-5-5-medium",
    "claude-3.5-sonnet": "claude-sonnet-5-5-medium",
    "claude-3-5-sonnet-20241022": "claude-sonnet-5-5-medium",
    "claude-3-5-sonnet-20240620": "claude-sonnet-5-5-medium",
    "claude-3-7-sonnet-20250219": "claude-sonnet-5-5-medium",
    "claude-3-5-haiku": "claude-sonnet-5-5-medium",
    "claude-3-5-haiku-20241022": "claude-sonnet-5-5-medium",
    "claude-3-haiku": "claude-sonnet-5-5-medium",
    "claude-3-haiku-20240307": "claude-sonnet-5-5-medium",
    "claude-opus": "claude-opus-5-5-medium",
    "claude-opus-4-6": "claude-opus-5-5-medium",
    "claude-3-opus": "claude-opus-5-5-medium",
    "claude-3-opus-20240229": "claude-opus-5-5-medium",
    "claude-3.0-opus": "claude-opus-5-5-medium",
    "claude-code": "claude-sonnet-5-5-medium",
    "claude-opus-4-6-thinking": "claude-opus-5-5-medium",
    "claude-sonnet-4-6": "claude-sonnet-5-5-medium",
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
    "gemini-2.0-flash-exp": "gemini-3.8-flash-high",
    "gemini-2.0-flash-thinking": "gemini-3.8-flash-high",
    "gemini-2.0-flash-thinking-exp": "gemini-3.8-flash-high",
    "gemini-1.5-flash": "gemini-3.8-flash-high",
    "gemini-1.5-flash-latest": "gemini-3.8-flash-high",
    # Gemini Pro Reasoning Aliases
    "gemini-3.1-pro": "gemini-3.1-pro-low",
    "gemini-3.1-pro-high": "gemini-pro-agent",
    "gemini-pro": "gemini-3.1-pro-low",
    "gemini-2.5-pro": "gemini-3.1-pro-low",
    "gemini-2.0-pro": "gemini-3.1-pro-low",
    "gemini-1.5-pro": "gemini-3.1-pro-low",
    "gemini-1.5-pro-latest": "gemini-3.1-pro-low",
    # GPT-OSS 120B (Medium)
    "gpt-oss": "gpt-oss-120b-medium",
    "gpt-oss-120b": "gpt-oss-120b-medium",
    "gpt-4o": "gpt-oss-120b-medium",
    "gpt-4o-mini": "gemini-3.8-flash-high",
    "gpt-4": "gpt-oss-120b-medium",
    "gpt-4-turbo": "gpt-oss-120b-medium",
    "gpt-3.5-turbo": "gemini-3.8-flash-high",
    "o1": "claude-opus-5-5-medium",
    "o1-preview": "claude-opus-5-5-medium",
    "o1-mini": "claude-opus-5-5-medium",
    "o3": "claude-opus-5-5-medium",
    "o3-mini": "claude-opus-5-5-medium",
    "chatgpt-4o-latest": "gpt-oss-120b-medium",
}


def fuzzy_normalize_model_id(model_id: str) -> Optional[str]:
    """Pattern-based fuzzy model matcher for diverse IDEs and agent toolchains."""
    cleaned = model_id.strip().lower()

    # Strip provider prefixes: anthropic/, openai/, google/, models/
    for prefix in ("models/", "anthropic/", "openai/", "google/", "meta/", "deepseek/"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]

    # Remove trailing date stamps like -20241022 or -latest
    cleaned = re.sub(r"-\d{8}$", "", cleaned)
    if cleaned.endswith("-latest"):
        cleaned = cleaned[:-7]

    if cleaned in MODEL_ALIASES:
        return MODEL_ALIASES[cleaned]

    # Pattern heuristics
    if "opus" in cleaned:
        return "claude-opus-5-5-medium"

    if "sonnet" in cleaned or "haiku" in cleaned:
        return "claude-sonnet-5-5-medium"

    if "claude" in cleaned:
        return "claude-sonnet-5-5-medium"

    if "pro" in cleaned and ("gemini" in cleaned or "google" in cleaned or "agent" in cleaned):
        return "gemini-3.1-pro-low"

    if "flash" in cleaned or "gemini" in cleaned:
        return "gemini-3.8-flash-high"

    if any(k in cleaned for k in ("gpt", "o1", "o3", "chatgpt")):
        return "gpt-oss-120b-medium"

    return None


def normalize_model_id(model_id: str) -> str:
    """Normalize model identifier by removing prefixes and resolving aliases."""
    cleaned = model_id.strip()
    if cleaned.startswith("models/"):
        cleaned = cleaned[7:]
    if cleaned in DEFAULT_MODELS:
        return cleaned
    if cleaned in MODEL_ALIASES:
        return MODEL_ALIASES[cleaned]
    fuzzy = fuzzy_normalize_model_id(cleaned)
    if fuzzy:
        return fuzzy
    return cleaned


class ModelRegistry:
    """Manages models supported by the gateway with dynamic auto-registration."""

    def __init__(self, custom_models: Optional[Dict[str, Any]] = None):
        self._models = dict(DEFAULT_MODELS)
        if custom_models:
            self._models.update(custom_models)

    def register_model(self, model_id: str, definition: Dict[str, Any]) -> None:
        """Register or update a model definition dynamically."""
        self._models[model_id] = definition

    def get_model(self, model_id: str, fallback_to_default: bool = False) -> Optional[Dict[str, Any]]:
        """Get model definition by ID or alias."""
        normalized = normalize_model_id(model_id)
        model = self._models.get(normalized) or self._models.get(model_id)
        if not model and fallback_to_default:
            return self._models.get(DEFAULT_FALLBACK_MODEL)
        return model

    def list_model_ids(self) -> List[str]:
        """Return list of supported model IDs."""
        return list(self._models.keys())

    def resolve_upstream(self, model_id: str, strict: bool = True) -> Tuple_Upstream:
        """Resolve requested model to (upstream_id, family, max_output_tokens)."""
        normalized = normalize_model_id(model_id)
        model = self.get_model(normalized) or self.get_model(model_id)
        if not model:
            if strict:
                raise ValueError(f"Model '{model_id}' is not supported or not enabled on this gateway.")
            logger.info("Unrecognized model '%s'; falling back to '%s'", model_id, DEFAULT_FALLBACK_MODEL)
            model = self._models.get(DEFAULT_FALLBACK_MODEL, {})
            normalized = DEFAULT_FALLBACK_MODEL
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
        return normalized in self._models or model_id in self._models or bool(fuzzy_normalize_model_id(model_id))

