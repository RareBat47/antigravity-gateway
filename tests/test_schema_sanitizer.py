"""Tests for Gemini JSON Schema cleaning and normalization."""

from agw.cloudcode.schema_sanitizer import clean_gemini_schema, normalize_tool_parameters


def test_clean_gemini_schema_strips_disallowed_keywords():
    raw_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "SearchFilter",
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "pattern": "^[a-zA-Z0-9]+$",
                "minLength": 3,
            },
            "limit": {
                "type": "integer",
                "multipleOf": 5,
                "exclusiveMinimum": 0,
            },
            "status": {
                "const": "active",
            },
        },
        "additionalProperties": False,
    }

    cleaned = clean_gemini_schema(raw_schema)
    assert "$schema" not in cleaned
    assert "additionalProperties" not in cleaned
    props = cleaned["properties"]
    assert "pattern" not in props["query"]
    assert "multipleOf" not in props["limit"]
    assert "exclusiveMinimum" not in props["limit"]
    # const should be converted to enum
    assert props["status"]["enum"] == ["active"]
    assert props["status"]["type"] == "string"


def test_normalize_tool_parameters():
    params = {
        "properties": {
            "location": {"type": "string", "description": "City name"}
        }
    }
    norm = normalize_tool_parameters(params)
    assert norm["type"] == "object"
    assert "location" in norm["properties"]
