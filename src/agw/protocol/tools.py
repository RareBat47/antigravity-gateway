"""OpenAI tool calling <-> Google Gemini function calling mapper."""

import json
from typing import Any, Dict, List, Optional
from agw.cloudcode.schema_sanitizer import normalize_tool_parameters


def oai_tools_to_gemini(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI tool declarations to Gemini tools array."""
    function_declarations = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        fn = tool.get("function", {})
        name = fn.get("name")
        if not name:
            continue

        raw_params = fn.get("parameters", {})
        cleaned_params = normalize_tool_parameters(raw_params)

        decl = {
            "name": name,
            "description": fn.get("description", ""),
            "parameters": cleaned_params,
        }
        function_declarations.append(decl)

    if not function_declarations:
        return []
    return [{"functionDeclarations": function_declarations}]


def oai_tool_choice_to_gemini(tool_choice: Any) -> Optional[Dict[str, Any]]:
    """Convert OpenAI tool_choice parameter to Gemini toolConfig."""
    if not tool_choice:
        return None

    if isinstance(tool_choice, str):
        if tool_choice == "auto":
            return {"functionCallingConfig": {"mode": "AUTO"}}
        elif tool_choice == "none":
            return {"functionCallingConfig": {"mode": "NONE"}}
        elif tool_choice == "required":
            return {"functionCallingConfig": {"mode": "ANY"}}

    if isinstance(tool_choice, dict):
        fn = tool_choice.get("function", {})
        name = fn.get("name")
        if name:
            return {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": [name],
                }
            }

    return None


def extract_gemini_tool_calls(parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract OpenAI-formatted tool_calls from Gemini response parts."""
    tool_calls = []
    for idx, part in enumerate(parts):
        fn_call = part.get("functionCall")
        if not fn_call:
            continue

        call_id = f"call_{idx}_{fn_call.get('name', 'fn')}"
        args = fn_call.get("args", {})
        args_str = json.dumps(args) if isinstance(args, dict) else str(args)

        tc_dict: Dict[str, Any] = {
            "id": call_id,
            "type": "function",
            "function": {
                "name": fn_call.get("name"),
                "arguments": args_str,
            },
        }
        sig = (
            part.get("thoughtSignature")
            or part.get("thought_signature")
            or fn_call.get("thoughtSignature")
            or fn_call.get("thought_signature")
        )
        if sig:
            tc_dict["thought_signature"] = sig
            tc_dict["thoughtSignature"] = sig

        tool_calls.append(tc_dict)
    return tool_calls
