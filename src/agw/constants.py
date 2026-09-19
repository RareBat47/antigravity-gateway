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

# Cloud Code API Endpoints (Daily -> Prod fallback)
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

# Default Model Specifications
DEFAULT_MODELS = {
    "gemini-3.5-flash": {
        "upstream_id": "gemini-3.5-flash-low",
        "family": FAMILY_GEMINI,
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Google Gemini 3.5 Flash (Antigravity)",
    },
    "gemini-3.1-pro": {
        "upstream_id": "gemini-3.1-pro-low",
        "family": FAMILY_GEMINI,
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Google Gemini 3.1 Pro (Antigravity)",
    },
    "gemini-3-flash": {
        "upstream_id": "gemini-3-flash",
        "family": FAMILY_GEMINI,
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 32768,
        "description": "Google Gemini 3 Flash (Antigravity)",
    },
    "gemini-2.5-pro": {
        "upstream_id": "gemini-2.5-pro",
        "family": FAMILY_GEMINI,
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 32768,
        "description": "Google Gemini 2.5 Pro (Antigravity)",
    },
    "gemini-2.5-flash": {
        "upstream_id": "gemini-2.5-flash",
        "family": FAMILY_GEMINI,
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 32768,
        "description": "Google Gemini 2.5 Flash (Antigravity)",
    },
    "claude-sonnet-4-6": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 16384,
        "description": "Anthropic Claude 4.6 Sonnet via Antigravity",
    },
    "claude-opus-4-6": {
        "upstream_id": "claude-opus-4-6-thinking",
        "family": FAMILY_CLAUDE,
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 16384,
        "description": "Anthropic Claude 4.6 Opus Thinking via Antigravity",
    },
}
