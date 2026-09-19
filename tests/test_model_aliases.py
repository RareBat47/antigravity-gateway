"""Tests for model aliases and models/ prefix resolution."""

from agw.routing.registry import ModelRegistry


def test_model_alias_resolution():
    registry = ModelRegistry()

    # Stripping models/ prefix
    up_id, family, toks = registry.resolve_upstream("models/gemini-3.8-flash-high")
    assert up_id == "gemini-3.8-flash-tiered"
    assert family == "gemini"

    # Gemini aliases
    up_37, fam_37, _ = registry.resolve_upstream("gemini-3.7-flash")
    assert up_37 == "gemini-3.7-flash-tiered"
    assert fam_37 == "gemini"

    # Claude aliases
    up_c35, fam_c35, _ = registry.resolve_upstream("claude-3-5-sonnet")
    assert up_c35 == "claude-sonnet-4-6"
    assert fam_c35 == "claude"

    up_c37, fam_c37, _ = registry.resolve_upstream("claude-3.7-sonnet")
    assert up_c37 == "claude-sonnet-4-6"
    assert fam_c37 == "claude"
