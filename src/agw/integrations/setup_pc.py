"""System-wide auto-configuration for developer tools on Windows and POSIX."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("agw.integrations")

GATEWAY_OPENAI_URL = "http://127.0.0.1:8999/v1"
GATEWAY_ANTHROPIC_URL = "http://127.0.0.1:8999"
GATEWAY_DEFAULT_KEY = "agw-local-key"


def set_user_environment_variable(name: str, value: str) -> bool:
    """Set persistent user environment variable on Windows or current session on Unix."""
    try:
        if sys.platform == "win32":
            # Set in registry for permanent user sessions via PowerShell
            ps_cmd = f"[Environment]::SetEnvironmentVariable('{name}', '{value}', 'User')"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True, capture_output=True)
        # Also update current process env
        os.environ[name] = value
        return True
    except Exception as e:
        logger.warning(f"Failed to set environment variable {name}: {e}")
        return False


def configure_opencode() -> str:
    """Configure OpenCode globally in ~/.config/opencode/opencode.json."""
    home = Path.home()
    target_dir = home / ".config" / "opencode"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "opencode.json"

    data = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "antigravity": {
                "name": "Antigravity Gateway",
                "type": "openai",
                "baseURL": GATEWAY_OPENAI_URL,
                "apiKey": GATEWAY_DEFAULT_KEY,
                "models": {
                    "claude-opus-5-5-medium": {"name": "Claude Opus 5.5 (Medium)"},
                    "claude-sonnet-5-5-medium": {"name": "Claude Sonnet 5.5 (Medium)"},
                    "claude-opus-4-6-thinking": {"name": "Claude Opus 4.6 (Thinking)"},
                    "claude-sonnet-4-6": {"name": "Claude Sonnet 4.6 (Thinking)"},
                    "gemini-3.8-flash-high": {"name": "Gemini 3.8 Flash High"},
                    "gemini-3.6-flash-high": {"name": "Gemini 3.6 Flash High"},
                    "gemini-3.1-pro-low": {"name": "Gemini 3.1 Pro Low"},
                    "gemini-pro-agent": {"name": "Gemini Pro Agent"},
                    "gpt-oss-120b-medium": {"name": "GPT-OSS 120B (Medium)"},
                },
            }
        },
    }

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return str(target_file)


def configure_vscode_continue() -> str:
    """Configure Continue extension in ~/.continue/config.json."""
    home = Path.home()
    target_dir = home / ".continue"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "config.json"

    existing: Dict[str, Any] = {}
    if target_file.is_file():
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    models = existing.get("models", [])
    agw_model_titles = {
        "Antigravity: Gemini 3.8 Flash High",
        "Antigravity: Claude Sonnet 4.6",
        "Antigravity: Claude Opus 4.6",
        "Antigravity: Gemini 3.1 Pro",
    }
    # Keep non-antigravity models
    updated_models = [m for m in models if m.get("title") not in agw_model_titles]

    new_entries = [
        {
            "title": "Antigravity: Gemini 3.8 Flash High",
            "provider": "openai",
            "model": "gemini-3.8-flash-high",
            "apiBase": GATEWAY_OPENAI_URL,
            "apiKey": GATEWAY_DEFAULT_KEY,
        },
        {
            "title": "Antigravity: Claude Sonnet 4.6",
            "provider": "openai",
            "model": "claude-sonnet-4-6",
            "apiBase": GATEWAY_OPENAI_URL,
            "apiKey": GATEWAY_DEFAULT_KEY,
        },
        {
            "title": "Antigravity: Claude Opus 4.6",
            "provider": "openai",
            "model": "claude-opus-4-6-thinking",
            "apiBase": GATEWAY_OPENAI_URL,
            "apiKey": GATEWAY_DEFAULT_KEY,
        },
        {
            "title": "Antigravity: Gemini 3.1 Pro",
            "provider": "openai",
            "model": "gemini-3.1-pro-low",
            "apiBase": GATEWAY_OPENAI_URL,
            "apiKey": GATEWAY_DEFAULT_KEY,
        },
    ]
    updated_models.extend(new_entries)
    existing["models"] = updated_models

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    return str(target_file)


def run_full_pc_setup() -> Dict[str, Any]:
    """Execute complete automated PC integration."""
    results: Dict[str, Any] = {
        "env_vars": {},
        "files_written": [],
        "tools_configured": [],
    }

    # 1. Environment variables
    env_vars = {
        "OPENAI_BASE_URL": GATEWAY_OPENAI_URL,
        "OPENAI_API_BASE": GATEWAY_OPENAI_URL,
        "OPENAI_API_KEY": GATEWAY_DEFAULT_KEY,
        "ANTHROPIC_BASE_URL": GATEWAY_ANTHROPIC_URL,
        "ANTHROPIC_API_KEY": GATEWAY_DEFAULT_KEY,
    }
    for k, v in env_vars.items():
        ok = set_user_environment_variable(k, v)
        results["env_vars"][k] = "set" if ok else "failed"

    results["tools_configured"].append("System-wide OpenAI & Anthropic SDKs")
    results["tools_configured"].append("Claude Code CLI (via ANTHROPIC_BASE_URL)")
    results["tools_configured"].append("Aider (via OPENAI_BASE_URL & ANTHROPIC_BASE_URL)")

    # 2. OpenCode
    try:
        p1 = configure_opencode()
        results["files_written"].append(p1)
        results["tools_configured"].append("OpenCode (~/.config/opencode/opencode.json)")
    except Exception as e:
        logger.warning(f"Error configuring OpenCode: {e}")

    # 3. VS Code Continue
    try:
        p2 = configure_vscode_continue()
        results["files_written"].append(p2)
        results["tools_configured"].append("VS Code Continue (~/.continue/config.json)")
    except Exception as e:
        logger.warning(f"Error configuring VS Code Continue: {e}")

    return results
