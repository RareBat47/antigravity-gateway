"""
Reconfigure Hermes Agent Main Configuration & Profiles for Strictly 5 Models
- Coding:     gemini-3.8-flash-high  (Key: agw-code-gemini-3-8d52)
- Pro:        gemini-3.1-pro-low     (Key: agw-code-hybrid-1-4a29)
- Planning:   claude-opus-4-6-thinking (Key: agw-plan-claude-9x82)
- Debugging:  claude-sonnet-4-6      (Key: agw-code-hybrid-2-6e83)
- GPT:        gpt-oss-120b-medium    (Key: agw-debug-all-9c37)
"""

import os
import shutil
from pathlib import Path
import yaml

localapp = Path(os.environ["LOCALAPPDATA"]) / "hermes"
main_config_path = localapp / "config.yaml"

DEDICATED_PROVIDERS = {
    "Coding": {
        "base_url": "http://127.0.0.1:8999/v1",
        "api_key": "agw-code-gemini-3-8d52",
        "key_env": "HERMES_ANTIGRAVITY_CODING_API_KEY",
        "api_mode": "chat_completions",
    },
    "Pro": {
        "base_url": "http://127.0.0.1:8999/v1",
        "api_key": "agw-code-hybrid-1-4a29",
        "key_env": "HERMES_ANTIGRAVITY_PRO_API_KEY",
        "api_mode": "chat_completions",
    },
    "Planning": {
        "base_url": "http://127.0.0.1:8999/v1",
        "api_key": "agw-plan-claude-9x82",
        "key_env": "HERMES_ANTIGRAVITY_PLANNING_API_KEY",
        "api_mode": "chat_completions",
    },
    "Debugging": {
        "base_url": "http://127.0.0.1:8999/v1",
        "api_key": "agw-code-hybrid-2-6e83",
        "key_env": "HERMES_ANTIGRAVITY_DEBUGGING_API_KEY",
        "api_mode": "chat_completions",
    },
    "GPT": {
        "base_url": "http://127.0.0.1:8999/v1",
        "api_key": "agw-debug-all-9c37",
        "key_env": "HERMES_ANTIGRAVITY_GPT_API_KEY",
        "api_mode": "chat_completions",
    },
}

OLD_PROVIDER_NAMES = ["Coding-1", "Coding-2", "Coding-3", "Hybrid-1", "Hybrid-2"]

# 1. Update Main Hermes config.yaml
print("1. Reconfiguring Hermes main config.yaml...")
with open(main_config_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

if "model" not in cfg:
    cfg["model"] = {}

cfg["model"]["provider"] = "custom:Coding"
cfg["model"]["default"] = "gemini-3.8-flash-high"

if "aliases" not in cfg["model"]:
    cfg["model"]["aliases"] = {}
cfg["model"]["aliases"].update({
    "coding": "gemini-3.8-flash-high",
    "pro": "gemini-3.1-pro-low",
    "planning": "claude-opus-4-6-thinking",
    "debugging": "claude-sonnet-4-6",
    "gpt": "gpt-oss-120b-medium",
})

# Remove old providers from main config
if "providers" not in cfg:
    cfg["providers"] = {}
for old in OLD_PROVIDER_NAMES:
    cfg["providers"].pop(old, None)
cfg["providers"].update(DEDICATED_PROVIDERS)

# Update fallback providers
cfg["fallback_providers"] = [
    {"provider": "custom:Pro", "model": "gemini-3.1-pro-low"},
    {"provider": "custom:Planning", "model": "claude-opus-4-6-thinking"},
]

with open(main_config_path, "w", encoding="utf-8") as f:
    yaml.dump(cfg, f, sort_keys=False, default_flow_style=False)
print("  Main config updated successfully.")

# 2. Update Profile Configurations
PROFILES_MAP = {
    "architect-worker": ("custom:Planning", "claude-opus-4-6-thinking"),
    "code-runner": ("custom:Coding", "gemini-3.8-flash-high"),
    "dev-dedicated": ("custom:Coding", "gemini-3.8-flash-high"),
    "ctrader-quant-developer": ("custom:Pro", "gemini-3.1-pro-low"),
}

profiles_dir = localapp / "profiles"
for prof_name, (prov, model) in PROFILES_MAP.items():
    p_path = profiles_dir / prof_name / "config.yaml"
    if p_path.is_file():
        print(f"2. Updating profile {prof_name} -> {prov} ({model})...")
        shutil.copyfile(p_path, str(p_path) + ".bak")
        with open(p_path, "r", encoding="utf-8") as pf:
            p_cfg = yaml.safe_load(pf) or {}

        if "model" not in p_cfg:
            p_cfg["model"] = {}
        p_cfg["model"]["provider"] = prov
        p_cfg["model"]["default"] = model
        p_cfg["model"].pop("base_url", None)
        p_cfg["model"].pop("api_key", None)

        if "providers" not in p_cfg:
            p_cfg["providers"] = {}
        for old in OLD_PROVIDER_NAMES:
            p_cfg["providers"].pop(old, None)
        p_cfg["providers"].update(DEDICATED_PROVIDERS)

        with open(p_path, "w", encoding="utf-8") as pf:
            yaml.dump(p_cfg, pf, sort_keys=False, default_flow_style=False)
        print(f"  Profile {prof_name} reconfigured.")

print("Hermes configuration and profiles successfully updated for the 5-model lineup!")
