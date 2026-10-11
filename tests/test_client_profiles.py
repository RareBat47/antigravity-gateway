from agw.api.client_profiles import profile_items
from agw.config import AppConfig
from agw.routing.registry import ModelRegistry, normalize_model_id


def test_client_profiles_are_unrestricted_and_separate():
    items = profile_items(AppConfig())
    assert {item["id"] for item in items} == {"hermes", "claude-code", "opencode"}
    assert all(item["model"] == "auto" for item in items)
    assert all(item["api_key"] == "use-generated-local-key" for item in items)


def test_retired_claude_ids_alias_to_verified_55_models():
    assert normalize_model_id("claude-opus-4-6-thinking") == "claude-opus-5.5"
    assert normalize_model_id("claude-sonnet-4-6") == "claude-sonnet-5.5"
    assert normalize_model_id("claude-3-5-sonnet-20241022") == "claude-sonnet-5.5"


def test_latest_catalog_excludes_unverified_high_opus_variant():
    ids = set(ModelRegistry().list_model_ids())
    assert "claude-opus-5.5" in ids
    assert "claude-sonnet-5.5" in ids
    assert "claude-opus-4-6-thinking" not in ids
    assert "claude-sonnet-4-6" not in ids
