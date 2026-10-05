"""Tests for fuzzy model normalization and non-404 fallbacks."""

import pytest
from agw.routing.registry import ModelRegistry, normalize_model_id, DEFAULT_FALLBACK_MODEL


def test_fuzzy_model_normalization():
    # Vendor prefix stripping
    assert normalize_model_id("anthropic/claude-3-5-sonnet") == "claude-sonnet-4-6"
    assert normalize_model_id("anthropic/claude-3.5-sonnet-20241022") == "claude-sonnet-4-6"
    assert normalize_model_id("google/gemini-pro") == "gemini-3.1-pro-low"
    assert normalize_model_id("openai/gpt-4o") == "gpt-oss-120b-medium"

    # Common Claude IDE variations
    assert normalize_model_id("claude-3-7-sonnet-latest") == "claude-sonnet-4-6"
    assert normalize_model_id("claude-3-5-haiku-20241022") == "claude-sonnet-4-6"
    assert normalize_model_id("claude-3-opus-20240229") == "claude-opus-4-6-thinking"

    # OpenAI & GPT variations
    assert normalize_model_id("gpt-4o-mini") == "gemini-3.8-flash-high"
    assert normalize_model_id("chatgpt-4o-latest") == "gpt-oss-120b-medium"
    assert normalize_model_id("o1-mini") == "claude-opus-4-6-thinking"

    # Gemini variations
    assert normalize_model_id("gemini-2.0-flash-exp") == "gemini-3.8-flash-high"
    assert normalize_model_id("gemini-1.5-pro-latest") == "gemini-3.1-pro-low"


def test_model_registry_fallback_behavior():
    reg = ModelRegistry()

    # Known model gets exact upstream
    up, fam, _ = reg.resolve_upstream("claude-sonnet-4-6")
    assert up == "claude-sonnet-4-6"
    assert fam == "claude"

    # Fuzzy model resolves
    up_fuzzy, fam_fuzzy, _ = reg.resolve_upstream("claude-3-5-sonnet-20241022")
    assert up_fuzzy == "claude-sonnet-4-6"
    assert fam_fuzzy == "claude"

    # Completely unknown model with strict=False falls back gracefully
    up_unk, fam_unk, _ = reg.resolve_upstream("super-custom-unknown-model-12345", strict=False)
    assert up_unk == "gemini-3.8-flash-tiered"
    assert fam_unk == "gemini"

    # Strict=True still raises ValueError for explicit checking
    with pytest.raises(ValueError):
        reg.resolve_upstream("super-custom-unknown-model-12345", strict=True)
