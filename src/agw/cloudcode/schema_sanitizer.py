"""Deep JSON Schema cleaner for Google Gemini and Claude tool calls.

Strips unsupported OpenAPI/JSON-Schema keywords that cause 400 INVALID_ARGUMENT
errors on Cloud Code Assist (such as const, anyOf, oneOf, allOf, multipleOf,
exclusiveMinimum, pattern, default, $schema, $ref, format, etc.) and resolves
$ref references inline from $defs before stripping both.
"""

from typing import Any, Dict, List, Optional


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
    # Bug #18: Gemini does not support arbitrary JSON Schema "format" values
    "format",
}


def _resolve_ref(schema: Any, defs: Dict[str, Any]) -> Any:
    """Resolve a single $ref against the provided $defs mapping.
    
    Bug #17: If a schema contains a $ref pointing to a $defs entry, inline
    the definition before stripping both $ref and $defs from the output.
    """
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if not ref or not isinstance(ref, str):
        return schema
    # Support "#/$defs/MyType" and "#/definitions/MyType" forms
    for prefix in ("#/$defs/", "#/definitions/", "#"):
        if ref.startswith(prefix):
            key = ref[len(prefix):]
            if key in defs:
                resolved = dict(defs[key])
                # Merge any sibling keys from the original schema (excluding $ref)
                for k, v in schema.items():
                    if k != "$ref":
                        resolved.setdefault(k, v)
                return resolved
    return schema


def _collect_defs(schema: Any) -> Dict[str, Any]:
    """Collect all definition entries from $defs / definitions at root level."""
    if not isinstance(schema, dict):
        return {}
    result: Dict[str, Any] = {}
    for key in ("$defs", "definitions"):
        val = schema.get(key)
        if isinstance(val, dict):
            result.update(val)
    return result


def clean_gemini_schema(schema: Any, _defs: Optional[Dict[str, Any]] = None) -> Any:
    """Recursively clean schema dict for Gemini function declaration compatibility."""
    if _defs is None:
        # Collect all definitions from the root before stripping anything
        _defs = _collect_defs(schema) if isinstance(schema, dict) else {}

    if not isinstance(schema, dict):
        if isinstance(schema, list):
            return [clean_gemini_schema(item, _defs) for item in schema]
        return schema

    # Bug #17: Resolve $ref inline before any other processing
    schema = _resolve_ref(schema, _defs)
    if not isinstance(schema, dict):
        return clean_gemini_schema(schema, _defs)

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
                    if sub.get("type") == "null" or (isinstance(sub.get("type"), list) and "null" in sub["type"]):
                        cleaned["nullable"] = True

            # Find first non-null concrete schema
            for sub in items:
                if isinstance(sub, dict):
                    sub_cleaned = clean_gemini_schema(sub, _defs)
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
            cleaned["properties"] = {pk: clean_gemini_schema(pv, _defs) for pk, pv in v.items()}
        elif k == "items":
            cleaned["items"] = clean_gemini_schema(v, _defs)
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
