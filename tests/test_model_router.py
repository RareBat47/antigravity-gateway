"""Tests for model registry and routing mappings."""

from agw.routing.registry import ModelRegistry


def test_model_registry_resolution():
    registry = ModelRegistry()

    # Gemini 3.8 Flash High
    up_id, family, max_toks = registry.resolve_upstream("gemini-3.8-flash-high")
    assert up_id == "gemini-3.8-flash-tiered"
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
    assert len(models) == 7
    ids = [m["id"] for m in models]
    expected_7 = [
        "gemini-3.8-flash-high",
        "gemini-3.7-flash-medium",
        "gemini-3.6-flash-medium",
        "gemini-3.1-pro-low",
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gpt-oss-120b-medium",
    ]
    for mid in expected_7:
        assert mid in ids
