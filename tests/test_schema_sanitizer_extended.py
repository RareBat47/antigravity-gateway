"""Extended tests for schema sanitization edge cases."""

from agw.cloudcode.schema_sanitizer import clean_gemini_schema, normalize_tool_parameters


def test_clean_gemini_schema_handles_anyof_nullable():
    """Verify anyOf with null type sets nullable: True and avoids type: null."""
    raw_schema = {
        "type": "object",
        "properties": {
            "query": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string"},
                ],
                "title": "Query",
                "default": None,
            },
            "tags": {
                "type": "array",
                # missing items
            },
            "status": {
                "const": None,
            },
        },
    }

    cleaned = clean_gemini_schema(raw_schema)
    props = cleaned["properties"]

    # title and default stripped
    assert "title" not in props["query"]
    assert "default" not in props["query"]

    # anyOf with null converted to string type + nullable: True
    assert props["query"]["type"] == "string"
    assert props["query"]["nullable"] is True

    # array gets default items: string
    assert props["tags"]["type"] == "array"
    assert props["tags"]["items"]["type"] == "string"

    # const None converted to nullable
    assert props["status"]["nullable"] is True
    assert "enum" not in props["status"]
