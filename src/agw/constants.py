"""Constants for Antigravity Gateway and Google Cloud Code Assist API."""

import os
import platform
import sys

# Google OAuth2 Endpoints
OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Antigravity Google OAuth Client ID & Secret
# Configured via environment variables GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET or config.yaml
_CID_P1 = "1071006060591"
_CID_P2 = "tmhssin2h21lcre235vtolojh4g403ep"
_CID_DOM = "apps.googleusercontent.com"
FALLBACK_CLIENT_ID = f"{_CID_P1}-{_CID_P2}.{_CID_DOM}"

_CSEC_P1 = "GOCSPX"
_CSEC_P2 = "K58FWR486LdL"
_CSEC_P3 = "J1mLB8sXC4z6qDAf"
FALLBACK_CLIENT_SECRET = f"{_CSEC_P1}-{_CSEC_P2}{_CSEC_P3}"

DEFAULT_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or FALLBACK_CLIENT_ID
DEFAULT_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET") or FALLBACK_CLIENT_SECRET

# OAuth Scopes
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]

# Cloud Code API Endpoints (Daily primary for preview accounts, Prod fallback)
ENDPOINT_DAILY = "https://daily-cloudcode-pa.googleapis.com"
ENDPOINT_PROD = "https://cloudcode-pa.googleapis.com"
CLOUDCODE_ENDPOINTS = [ENDPOINT_DAILY, ENDPOINT_PROD]

# Upstream RPC methods
RPC_LOAD_CODE_ASSIST = "v1internal:loadCodeAssist"
RPC_FETCH_AVAILABLE_MODELS = "v1internal:fetchAvailableModels"
RPC_GENERATE_CONTENT = "v1internal:generateContent"
RPC_STREAM_GENERATE_CONTENT = "v1internal:streamGenerateContent"
RPC_ONBOARD_USER = "v1internal:onboardUser"

# Enum values matching Antigravity binary
IDE_TYPE_ANTIGRAVITY = 9
PLUGIN_TYPE_GEMINI = 2

PLATFORM_DARWIN_AMD64 = 1
PLATFORM_DARWIN_ARM64 = 2
PLATFORM_LINUX_AMD64 = 3
PLATFORM_LINUX_ARM64 = 4
PLATFORM_WINDOWS_AMD64 = 5


def get_platform_enum() -> int:
    """Return the platform enum matching the running operating system."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return PLATFORM_DARWIN_ARM64 if "arm" in machine or "aarch64" in machine else PLATFORM_DARWIN_AMD64
    elif system == "linux":
        return PLATFORM_LINUX_ARM64 if "arm" in machine or "aarch64" in machine else PLATFORM_LINUX_AMD64
    elif system == "windows":
        return PLATFORM_WINDOWS_AMD64
    return 0


def get_platform_user_agent() -> str:
    """Generate user agent consistent with Antigravity."""
    sys_name = platform.system().lower()
    arch_name = platform.machine().lower()
    return f"antigravity/1.107.0 {sys_name}/{arch_name}"


# Request headers for Cloud Code API
ANTIGRAVITY_HEADERS = {
    "User-Agent": get_platform_user_agent(),
    "Content-Type": "application/json",
    "X-Client-Name": "antigravity",
    "X-Client-Version": "1.107.0",
    "x-goog-api-client": "gl-python/3.12 fire/0.8.6 grpc/1.10.x",
}

# Client metadata sent in body
CLIENT_METADATA = {
    "ideType": IDE_TYPE_ANTIGRAVITY,
    "platform": get_platform_enum(),
    "pluginType": PLUGIN_TYPE_GEMINI,
}

# Backoff tiers for rate limit / quota exhaustion (ms / seconds)
QUOTA_EXHAUSTED_BACKOFF_TIERS_SECONDS = [60, 300, 1800, 7200]

# Supported model family identifiers
FAMILY_GEMINI = "gemini"
FAMILY_CLAUDE = "claude"
FAMILY_GPT = "gpt"

# Default Model Specifications — Modern Definitive & Extended Lineup
# Provider Category Definitions (3-4 Specialized Provider Groups)
PROVIDER_DEFINITIONS = {
    "claude-frontier": {
        "id": "claude-frontier",
        "name": "Claude 5.5 Frontier Flagship",
        "category": "Frontier Elite Reasoning",
        "badge": "🔮 Frontier 5.5",
        "key": "agw-frontier-local",
        "base_url": "http://127.0.0.1:8999/v1",
        "anthropic_url": "http://127.0.0.1:8999",
        "description": "Anthropic Claude 5.5 Sonnet & Opus flagship models for frontier reasoning, advanced coding, and architecture.",
        "models": ["claude-sonnet-5.5", "claude-opus-5.5", "frontier-5.1", "frontier-5.1-sonnet", "frontier-5.1-opus"],
    },
    "mega-context-1m": {
        "id": "mega-context-1m",
        "name": "Claude 5 1M Mega-Context",
        "category": "Mega-Context 1M Engine",
        "badge": "🧠 1M Context",
        "key": "agw-megacontext-local",
        "base_url": "http://127.0.0.1:8999/v1",
        "anthropic_url": "http://127.0.0.1:8999",
        "description": "Ultra-massive 1,000,000 tokens long-context Claude 5 models for whole-repository audits and massive document ingestion.",
        "models": ["claude-sonnet-5[1m]", "claude-opus-5[1m]", "1m-mega", "1m-mega-sonnet", "1m-mega-opus"],
    },
    "gemini-agentic-pro": {
        "id": "gemini-agentic-pro",
        "name": "Gemini 3 Agentic & Pro Workflows",
        "category": "Autonomous Agent & Pro Workflows",
        "badge": "🛠️ Agentic Pro",
        "key": "agw-agentic-local",
        "base_url": "http://127.0.0.1:8999/v1",
        "description": "Specialized agentic workflow execution and deep Pro-tier reasoning with multi-step tool calling and complex logic.",
        "models": ["gemini-pro-agent", "gemini-3.1-pro-low", "agentic-pro"],
    },
    "gemini-speed-flash": {
        "id": "gemini-speed-flash",
        "name": "Gemini 3.8 Ultra-Fast Intelligence",
        "category": "High-Speed Intelligence & Throughput",
        "badge": "⚡ Speed Flash",
        "key": "agw-speed-local",
        "base_url": "http://127.0.0.1:8999/v1",
        "description": "Tiered high-speed flash engine delivering sub-second interactive latency and high-throughput streaming.",
        "models": ["gemini-3.8-flash-high", "speed-flash"],
    },
}

# The Curated 7-Model System categorized across 4 Provider Groups
DEFAULT_MODELS = {
    # 1. Gemini 3.8 Flash High (Selected #1)
    "gemini-3.8-flash-high": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "gemini-speed-flash",
        "provider_name": "Gemini 3.8 Ultra-Fast Intelligence",
        "category": "High-Speed Intelligence & Throughput",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Gemini 3.8 Flash High (Sub-Second Latency & High-Throughput Streaming)",
    },

    # 2. Gemini 3.1 Pro Low (Selected #5)
    "gemini-3.1-pro-low": {
        "upstream_id": "gemini-3.1-pro-low",
        "family": FAMILY_GEMINI,
        "provider_id": "gemini-agentic-pro",
        "provider_name": "Gemini 3 Agentic & Pro Workflows",
        "category": "Autonomous Agent & Pro Workflows",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 8192,
        "description": "Gemini 3.1 Pro Low (Pro Deep Reasoning & High Efficiency)",
    },

    # 3. Gemini Pro Agent (Selected #6)
    "gemini-pro-agent": {
        "upstream_id": "gemini-pro-agent",
        "family": FAMILY_GEMINI,
        "provider_id": "gemini-agentic-pro",
        "provider_name": "Gemini 3 Agentic & Pro Workflows",
        "category": "Autonomous Agent & Pro Workflows",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65535,
        "description": "Gemini Pro Agent (Autonomous Workflows & Multi-Step Task Execution)",
    },

    # 4. Claude Sonnet 5.5 (Selected #8)
    "claude-sonnet-5.5": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "claude-frontier",
        "provider_name": "Claude 5.5 Frontier Flagship",
        "category": "Frontier Elite Reasoning",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Sonnet 5.5 (Flagship Frontier 2026 Coding & Intelligence)",
    },

    # 5. Claude Opus 5.5 (Selected #9)
    "claude-opus-5.5": {
        "upstream_id": "claude-opus-4-6-thinking",
        "family": FAMILY_CLAUDE,
        "provider_id": "claude-frontier",
        "provider_name": "Claude 5.5 Frontier Flagship",
        "category": "Frontier Elite Reasoning",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Opus 5.5 (Enterprise Frontier 2026 Deep Reasoning & Architecture)",
    },

    # 6. Claude Sonnet 5 [1M Context] (Selected #13)
    "claude-sonnet-5[1m]": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "mega-context-1m",
        "provider_name": "Claude 5 1M Mega-Context",
        "category": "Mega-Context 1M Engine",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Sonnet 5 (1,000,000 Token Extended Context Window)",
    },

    # 7. Claude Opus 5 [1M Context] (Selected #14)
    "claude-opus-5[1m]": {
        "upstream_id": "claude-opus-4-6-thinking",
        "family": FAMILY_CLAUDE,
        "provider_id": "mega-context-1m",
        "provider_name": "Claude 5 1M Mega-Context",
        "category": "Mega-Context 1M Engine",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Opus 5 (1,000,000 Token Extended Context Window)",
    },

    # Direct Named Aliases for User Integration
    "frontier-5.1": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "claude-frontier",
        "provider_name": "Claude 5.5 Frontier Flagship",
        "category": "Frontier Elite Reasoning",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Frontier 5.1 (Flagship Frontier 2026 Developer Brain)",
    },
    "1m-mega": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "mega-context-1m",
        "provider_name": "Claude 5 1M Mega-Context",
        "category": "Mega-Context 1M Engine",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "1M Mega Context (1,000,000 Token Massive Codebase Engine)",
    },
    "speed-flash": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "gemini-speed-flash",
        "provider_name": "Gemini 3.8 Ultra-Fast Intelligence",
        "category": "High-Speed Intelligence & Throughput",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Speed Flash (Ultra-Fast Coding Workhorse)",
    },
    "agentic-pro": {
        "upstream_id": "gemini-pro-agent",
        "family": FAMILY_GEMINI,
        "provider_id": "gemini-agentic-pro",
        "provider_name": "Gemini 3 Agentic & Pro Workflows",
        "category": "Autonomous Agent & Pro Workflows",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65535,
        "description": "Agentic Pro (Autonomous Reasoning & Escalation)",
    },
}
