"""Cloud Code Assist RPC request envelope builder."""

from typing import Any, Dict, List, Optional


DEFAULT_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
]


def build_rpc_envelope(
    project_id: str,
    upstream_model_id: str,
    contents: List[Dict[str, Any]],
    system_instruction: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
    generation_config: Optional[Dict[str, Any]] = None,
    safety_settings: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Wrap content and configurations into the Cloud Code Assist request envelope."""
    req_body: Dict[str, Any] = {
        "contents": contents,
        "safetySettings": safety_settings or DEFAULT_SAFETY_SETTINGS,
    }

    if system_instruction:
        req_body["systemInstruction"] = system_instruction
    if tools:
        req_body["tools"] = tools
    if tool_config:
        req_body["toolConfig"] = tool_config
    if generation_config:
        req_body["generationConfig"] = generation_config

    envelope = {
        "project": project_id,
        "model": upstream_model_id,
        "request": req_body,
        "requestType": "REQUEST_TYPE_CHAT",
    }
    return envelope
