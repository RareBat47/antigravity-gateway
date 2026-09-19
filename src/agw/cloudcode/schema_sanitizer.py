"""Deep JSON Schema cleaner for Google Gemini and Claude tool calls.

Strips unsupported OpenAPI/JSON-Schema keywords that cause 400 INVALID_ARGUMENT
errors on Cloud Code Assist (such as const, anyOf, oneOf, allOf, multipleOf,
exclusiveMinimum, pattern, default, $schema, etc.).
"""

from typing import Any, Dict, List


DISALLOWED_KEYS = {
    "$schema",
    "$id",
    "definitions",
    "$defs",
    "pattern",
    "multipleOf",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minProperties",
    "maxProperties",
    "uniqueItems",
    "if",
    "then",
    "else",
    "not",
    "additionalProperties",
    "default",
    "title",
    "$ref",
    "examples",
    "example",
}


def clean_gemini_schema(schema: Any) -> Any:
    """Recursively clean schema dict for Gemini function declaration compatibility."""
    if not isinstance(schema, dict):
        if isinstance(schema, list):
            return [clean_gemini_schema(item) for item in schema]
        return schema

    cleaned: Dict[str, Any] = {}

    # Handle const -> enum
    if "const" in schema:
        val = schema["const"]
        if val is None:
            cleaned["nullable"] = True
        else:
            cleaned["enum"] = [val]
            if "type" not in schema:
                if isinstance(val, str):
                    cleaned["type"] = "string"
                elif isinstance(val, bool):
                    cleaned["type"] = "boolean"
                elif isinstance(val, int):
                    cleaned["type"] = "integer"
                elif isinstance(val, float):
                    cleaned["type"] = "number"

    # Handle type lists e.g. ["string", "null"]
    if "type" in schema:
        t = schema["type"]
        if isinstance(t, list):
            non_null = [x for x in t if x != "null"]
            cleaned["type"] = non_null[0].lower() if non_null else "string"
            if "null" in t:
                cleaned["nullable"] = True
        elif isinstance(t, str):
            if t.lower() == "null":
                cleaned["nullable"] = True
            else:
                cleaned["type"] = t.lower()

    # Handle anyOf / oneOf / allOf
    for combinator in ["anyOf", "oneOf", "allOf"]:
        if combinator in schema and isinstance(schema[combinator], list):
            items = schema[combinator]
            # Detect nullability across any combinator branch
            for sub in items:
                if isinstance(sub, dict):
                    if sub.get("type") == "null" or ("type" in sub and "null" in sub["type"]):
                        cleaned["nullable"] = True

            # Find first non-null concrete schema
            for sub in items:
                if isinstance(sub, dict):
                    sub_cleaned = clean_gemini_schema(sub)
                    sub_type = sub_cleaned.get("type")
                    if sub_type and sub_type != "null":
                        for k, v in sub_cleaned.items():
                            if k not in cleaned:
                                cleaned[k] = v
                        break

    # Copy allowed fields
    for k, v in schema.items():
        if k in DISALLOWED_KEYS or k in ("const", "anyOf", "oneOf", "allOf"):
            continue
        if k == "properties" and isinstance(v, dict):
            cleaned["properties"] = {pk: clean_gemini_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            cleaned["items"] = clean_gemini_schema(v)
        elif k not in cleaned:
            cleaned[k] = v

    # Ensure object type has properties if declared
    if cleaned.get("type") == "object" and "properties" not in cleaned:
        cleaned["properties"] = {}

    # Ensure array type has items schema
    if cleaned.get("type") == "array" and "items" not in cleaned:
        cleaned["items"] = {"type": "string"}

    return cleaned


def normalize_tool_parameters(parameters: Any) -> Dict[str, Any]:
    """Ensure parameters match Gemini expectation (object schema)."""
    if not isinstance(parameters, dict):
        return {"type": "object", "properties": {}}
    cleaned = clean_gemini_schema(parameters)
    if "type" not in cleaned:
        cleaned["type"] = "object"
    if cleaned.get("type") == "object" and "properties" not in cleaned:
        cleaned["properties"] = {}
    return cleaned
