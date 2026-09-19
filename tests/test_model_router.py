"""Tests for model registry and routing mappings."""

from agw.routing.registry import ModelRegistry


def test_model_registry_resolution():
    registry = ModelRegistry()

    # Gemini 3.5 Flash
    up_id, family, max_toks = registry.resolve_upstream("gemini-3.5-flash")
    assert up_id == "gemini-3.5-flash-low"
    assert family == "gemini"
    assert max_toks >= 32768

    # Claude 4.6 Sonnet
    c_id, c_family, c_toks = registry.resolve_upstream("claude-sonnet-4-6")
    assert c_id == "claude-sonnet-4-6"
    assert c_family == "claude"
    assert c_toks >= 16384


def test_list_models_openai():
    registry = ModelRegistry()
    models = registry.list_models_openai()
    assert len(models) >= 5
    ids = [m["id"] for m in models]
    assert "gemini-3.5-flash" in ids
    assert "claude-sonnet-4-6" in ids
