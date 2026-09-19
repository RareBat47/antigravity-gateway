"""Dynamic model registry and mapping definitions."""

from typing import Any, Dict, List, Optional, Tuple
from agw.constants import DEFAULT_MODELS, FAMILY_CLAUDE, FAMILY_GEMINI

Tuple_Upstream = Tuple[str, str, int]


class ModelRegistry:
    """Manages models supported by the gateway."""

    def __init__(self, custom_models: Optional[Dict[str, Any]] = None):
        self._models = dict(DEFAULT_MODELS)
        if custom_models:
            self._models.update(custom_models)

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model definition by ID."""
        return self._models.get(model_id)

    def resolve_upstream(self, model_id: str) -> Tuple_Upstream:
        """Resolve requested model to (upstream_id, family, max_output_tokens)."""
        model = self.get_model(model_id)
        if not model:
            # Fallback heuristic
            is_claude = "claude" in model_id.lower()
            return (
                model_id,
                FAMILY_CLAUDE if is_claude else FAMILY_GEMINI,
                16384 if is_claude else 32768,
            )
        return (
            model.get("upstream_id", model_id),
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
        return model_id in self._models
