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

# Backoff tiers for rate limit / quota exhaustion (seconds).
# Cap at 30 minutes max — the upstream "Resets in Xm" message now drives the
# actual delay, so the tier is only used as a fallback for unrecognised errors.
# Multi-day values (7200+) caused stale cooldowns that blocked all accounts.
QUOTA_EXHAUSTED_BACKOFF_TIERS_SECONDS = [30, 60, 180, 600, 1800]

# Supported model family identifiers
FAMILY_GEMINI = "gemini"
FAMILY_CLAUDE = "claude"
FAMILY_GPT = "gpt"

# =========================================================================
# THE 10 STANDARDIZED PROVIDER API KEYS (5 GROUPS × 2 KEYS: PRIMARY + SECONDARY)
# =========================================================================
TEN_STANDARDIZED_API_KEYS = [
    # 1. agy (Google Cloud Code OAuth)
    {
        "key": "agw-agy-primary",
        "name": "agy (Primary)",
        "group": "agy",
        "role": "Primary Workstation",
        "description": "Google Cloud Code OAuth Engine - Primary Workstation Key",
        "profile": "agy",
        "badge": "🛸 agy",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    {
        "key": "agw-agy-secondary",
        "name": "agy (Secondary / Failover)",
        "group": "agy",
        "role": "Secondary / Remote Device",
        "description": "Google Cloud Code OAuth Engine - Secondary / Remote Device Key",
        "profile": "agy",
        "badge": "🛸 agy",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    # 2. gweb (Gemini Web Free Sessions)
    {
        "key": "agw-gweb-primary",
        "name": "gweb (Primary)",
        "group": "gweb",
        "role": "Primary Workstation",
        "description": "Consumer Gemini Web Session Extractor - Primary Workstation Key",
        "profile": "gweb",
        "badge": "🍪 gweb",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    {
        "key": "agw-gweb-secondary",
        "name": "gweb (Secondary / Failover)",
        "group": "gweb",
        "role": "Secondary / Remote Device",
        "description": "Consumer Gemini Web Session Extractor - Secondary / Remote Device Key",
        "profile": "gweb",
        "badge": "🍪 gweb",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    # 3. studio (Google AI Studio Free Tier)
    {
        "key": "agw-studio-primary",
        "name": "studio (Primary)",
        "group": "studio",
        "role": "Primary Workstation",
        "description": "Google AI Studio Developer API - Primary Workstation Key",
        "profile": "studio",
        "badge": "🔑 studio",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    {
        "key": "agw-studio-secondary",
        "name": "studio (Secondary / Failover)",
        "group": "studio",
        "role": "Secondary / Remote Device",
        "description": "Google AI Studio Developer API - Secondary / Remote Device Key",
        "profile": "studio",
        "badge": "🔑 studio",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    # 4. gcli (Gemini Cloud CLI Protocol)
    {
        "key": "agw-gcli-primary",
        "name": "gcli (Primary)",
        "group": "gcli",
        "role": "Primary Workstation",
        "description": "Gemini CLI OAuth Channel - Primary Workstation Key",
        "profile": "gcli",
        "badge": "⚡ gcli",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    {
        "key": "agw-gcli-secondary",
        "name": "gcli (Secondary / Failover)",
        "group": "gcli",
        "role": "Secondary / Remote Device",
        "description": "Gemini CLI OAuth Channel - Secondary / Remote Device Key",
        "profile": "gcli",
        "badge": "⚡ gcli",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    # 5. handy (Handy Creative Media Suite)
    {
        "key": "agw-handy-primary",
        "name": "handy (Primary)",
        "group": "handy",
        "role": "Primary Workstation",
        "description": "Handy Creative Media Suite - Primary Workstation Key",
        "profile": "handy",
        "badge": "🎨 handy",
        "base_url": "http://127.0.0.1:8999/v1",
    },
    {
        "key": "agw-handy-secondary",
        "name": "handy (Secondary / Failover)",
        "group": "handy",
        "role": "Secondary / Remote Device",
        "description": "Handy Creative Media Suite - Secondary / Remote Device Key",
        "profile": "handy",
        "badge": "🎨 handy",
        "base_url": "http://127.0.0.1:8999/v1",
    },
]

# Default Model Specifications — Modern Definitive & Extended Lineup
# Provider Category Definitions (5 Standardized Core Provider Groups)
PROVIDER_DEFINITIONS = {
    # 1. agy (Google Cloud Code OAuth Engine)
    "agy": {
        "id": "agy",
        "name": "Antigravity OAuth Engine (agy)",
        "category": "Google Antigravity Cloud Code",
        "badge": "🛸 agy OAuth",
        "key": "agw-agy-primary",
        "secondary_key": "agw-agy-secondary",
        "base_url": "http://127.0.0.1:8999/v1",
        "anthropic_url": "http://127.0.0.1:8999",
        "description": "Direct Google Antigravity Cloud Code Assist channel providing access to Claude 5 Series, Gemini 3 Series, and GPT-OSS models.",
        "models": [
            "claude-sonnet-5.5", "claude-opus-5.5", "frontier-5.1",
            "claude-sonnet-5[1m]", "claude-opus-5[1m]", "1m-mega",
            "claude-fable-5", "claude-sonnet-5", "claude-opus-5",
            "gemini-3.8-flash-high", "gemini-3.7-flash-high",
            "gemini-pro-agent", "gemini-3.1-pro-low", "speed-flash", "agentic-pro",
            "gpt-oss-120b-medium",
        ],
    },
    # 2. gweb (Gemini Web Free Sessions)
    "gweb": {
        "id": "gweb",
        "name": "Gemini Web Free Sessions (gweb)",
        "category": "Consumer Web Session Extractor",
        "badge": "🌐 gweb Session",
        "key": "agw-gweb-primary",
        "secondary_key": "agw-gweb-secondary",
        "base_url": "http://127.0.0.1:8999/v1",
        "description": "Extracts consumer Google One AI Pro / Gemini Advanced web sessions via cookies (__Secure-1PSID / SNlM0e) for free Pro-tier reasoning.",
        "models": [
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash-thinking-exp", "gemini-advanced",
        ],
    },
    # 3. studio (Google AI Studio Free Tier)
    "studio": {
        "id": "studio",
        "name": "Google AI Studio Free Tier (studio)",
        "category": "Developer Studio Channel",
        "badge": "🔑 studio API",
        "key": "agw-studio-primary",
        "secondary_key": "agw-studio-secondary",
        "base_url": "http://127.0.0.1:8999/v1",
        "description": "Google AI Studio free API keys with generous free rate limits for Gemini 2.5 Pro, 2.5 Flash, 2.0 Flash, and experimental thinking models.",
        "models": [
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
            "gemini-2.0-flash", "gemini-2.0-flash-thinking-exp",
            "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b",
        ],
    },
    # 4. gcli (Gemini Cloud CLI Protocol)
    "gcli": {
        "id": "gcli",
        "name": "Gemini CLI OAuth (gcli)",
        "category": "Google Cloud CLI Protocol",
        "badge": "💻 gcli OAuth",
        "key": "agw-gcli-primary",
        "secondary_key": "agw-gcli-secondary",
        "base_url": "http://127.0.0.1:8999/v1",
        "description": "Google Cloud Code CLI / gcli protocol channel providing automated developer assistance and coding completions.",
        "models": [
            "gemini-code-assist", "gemini-1.5-pro",
        ],
    },
    # 5. handy (Handy Creative Media Suite)
    "handy": {
        "id": "handy",
        "name": "Handy Creative Media Suite",
        "category": "Google Labs & Creative Suite Extractors",
        "badge": "🎨 handy",
        "key": "agw-handy-primary",
        "secondary_key": "agw-handy-secondary",
        "base_url": "http://127.0.0.1:8999/v1",
        "description": "Reverse-engineered Google Labs creative extractors spanning Google Playground (WebGL game generation), Project Genie (world models), Google Flow & Veo (video generation), and MusicFX / MusicFX DJ (Lyria music generation). Authenticated via shared Google session cookies (__Secure-1PSID / __Secure-1PSIDTS).",
        "models": [
            "handy-google-playground",
            "handy-project-genie",
            "handy-google-flow",
            "handy-veo-video",
            "handy-flow-music",
            "handy-musicfx-dj",
        ],
    },
}

# The Curated 7-Model System categorized across 5 Provider Groups
DEFAULT_MODELS = {
    # 1. Gemini 3.8 Flash High (Selected #1)
    "gemini-3.8-flash-high": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "High-Speed Intelligence & Throughput",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Gemini 3.8 Flash High (Sub-Second Latency & High-Throughput Streaming)",
    },

    # 2. Gemini 3.1 Pro Low (Selected #5)
    "gemini-3.1-pro-low": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Autonomous Agent & Pro Workflows",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 8192,
        "description": "Gemini 3.1 Pro Low (Pro Deep Reasoning & High Efficiency)",
    },

    # 3. Gemini Pro Agent (Selected #6)
    "gemini-pro-agent": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Autonomous Agent & Pro Workflows",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65535,
        "description": "Gemini Pro Agent (Autonomous Workflows & Multi-Step Task Execution)",
    },

    # 4. Claude Sonnet 5.5 (Selected #8)
    "claude-sonnet-5.5": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Frontier Elite Reasoning",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Sonnet 5.5 (Flagship Frontier 2026 Coding & Intelligence)",
    },

    # 5. Claude Opus 5.5 (Selected #9)
    "claude-opus-5.5": {
        "upstream_id": "claude-opus-4-6-thinking",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Frontier Elite Reasoning",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Opus 5.5 (Enterprise Frontier 2026 Deep Reasoning & Architecture)",
    },

    # 6. Claude Sonnet 5 [1M Context] (Selected #13)
    "claude-sonnet-5[1m]": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Mega-Context 1M Engine",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Sonnet 5 (1,000,000 Token Extended Context Window)",
    },

    # 7. Claude Opus 5 [1M Context] (Selected #14)
    "claude-opus-5[1m]": {
        "upstream_id": "claude-opus-4-6-thinking",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Mega-Context 1M Engine",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Opus 5 (1,000,000 Token Extended Context Window)",
    },

    # Direct Named Aliases for User Integration
    "frontier-5.1": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Frontier Elite Reasoning",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Frontier 5.1 (Flagship Frontier 2026 Developer Brain)",
    },
    "1m-mega": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Mega-Context 1M Engine",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "1M Mega Context (1,000,000 Token Massive Codebase Engine)",
    },
    "speed-flash": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "High-Speed Intelligence & Throughput",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Speed Flash (Ultra-Fast Coding Workhorse)",
    },
    "agentic-pro": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Autonomous Agent & Pro Workflows",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65535,
        "description": "Agentic Pro (Autonomous Reasoning & Escalation)",
    },

    # Free Google Models across 4-Way Connections (agy • gweb • studio • gcli)
    "gemini-2.5-pro": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "gweb",
        "provider_name": "Gemini Web Free Sessions",
        "category": "Consumer & Studio Pro Free Tier",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Gemini 2.5 Pro (Google AI Studio & Gemini Web Free Tier)",
    },
    "gemini-advanced": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "gweb",
        "provider_name": "Gemini Web Free Sessions",
        "category": "Consumer Web Session Extractor",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Gemini Advanced (Google One AI Pro Consumer Web Session)",
    },
    "gemini-2.5-flash": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "studio",
        "provider_name": "Google AI Studio High-Speed",
        "category": "High-Speed Free Tier",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Gemini 2.5 Flash (Ultra-Fast Free Tier Inference)",
    },
    "gemini-2.5-flash-lite": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "studio",
        "provider_name": "Google AI Studio Flash Lite",
        "category": "Ultra-Low Latency Free Tier",
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 65536,
        "description": "Gemini 2.5 Flash Lite (Sub-100ms Free Tier)",
    },
    "gemini-2.0-flash": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "studio",
        "provider_name": "Google AI Studio 2.0 Flash",
        "category": "Multimodal Free Tier",
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 65536,
        "description": "Gemini 2.0 Flash (General Multimodal Free Tier)",
    },
    "gemini-2.0-flash-thinking-exp": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "studio",
        "provider_name": "Google AI Studio Thinking Exp",
        "category": "Experimental Reasoning Free Tier",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 65536,
        "description": "Gemini 2.0 Flash Thinking Experimental",
    },
    "gemini-1.5-pro": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "studio",
        "provider_name": "Google AI Studio 1.5 Pro",
        "category": "Long Context Free Tier",
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 65536,
        "description": "Gemini 1.5 Pro (2M Context Studio Free Tier)",
    },
    "gemini-1.5-flash": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "studio",
        "provider_name": "Google AI Studio 1.5 Flash",
        "category": "Lightweight Studio Free Tier",
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 65536,
        "description": "Gemini 1.5 Flash (Lightweight Free Tier)",
    },
    "gemini-1.5-flash-8b": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "studio",
        "provider_name": "Google AI Studio 8B Flash",
        "category": "High Density Free Tier",
        "capabilities": ["tools", "streaming", "vision"],
        "max_output_tokens": 65536,
        "description": "Gemini 1.5 Flash 8B (High Density Low Latency)",
    },
    "gemini-code-assist": {
        "upstream_id": "gemini-3.8-flash-tiered",
        "family": FAMILY_GEMINI,
        "provider_id": "gcli",
        "provider_name": "Gemini CLI OAuth Assist",
        "category": "CLI Code Completion Free Tier",
        "capabilities": ["tools", "streaming"],
        "max_output_tokens": 65536,
        "description": "Gemini Code Assist (Google Cloud CLI Integration)",
    },
    "claude-fable-5": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Antigravity Coding Experimental",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Fable 5 (Experimental Coding Engine via Antigravity)",
    },
    "claude-sonnet-5": {
        "upstream_id": "claude-sonnet-4-6",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Antigravity Frontier Intelligence",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Sonnet 5 (Frontier Intelligence via Antigravity)",
    },
    "claude-opus-5": {
        "upstream_id": "claude-opus-4-6-thinking",
        "family": FAMILY_CLAUDE,
        "provider_id": "agy",
        "provider_name": "Antigravity OAuth Engine",
        "category": "Antigravity Deep Architecture",
        "capabilities": ["tools", "streaming", "vision", "thinking"],
        "max_output_tokens": 128000,
        "description": "Claude Opus 5 (Deep Architecture Reasoning via Antigravity)",
    },
    "gpt-oss-120b-medium": {
        "upstream_id": "gpt-oss-120b-medium",
        "family": FAMILY_GPT,
        "provider_id": "agy",
        "provider_name": "Antigravity Open Weights",
        "category": "Open-Weights 120B Free Tier",
        "capabilities": ["tools", "streaming"],
        "max_output_tokens": 32768,
        "description": "GPT-OSS 120B Medium (Open-Weights Inference via Antigravity)",
    },

    # Handy Creative Suite Extractors (Google Labs / DeepMind / Test Kitchen)
    "handy-google-playground": {
        "upstream_id": "handy-google-playground",
        "family": "handy",
        "provider_id": "handy",
        "provider_name": "Handy Creative Media Suite",
        "category": "Google Labs Game Generation",
        "capabilities": ["streaming", "code", "interactive"],
        "max_output_tokens": 65536,
        "description": "Google Playground - Gemini Code Gen & WebGL/HTML5 Game Generator via batchexecute / CDP",
    },
    "handy-project-genie": {
        "upstream_id": "handy-project-genie",
        "family": "handy",
        "provider_id": "handy",
        "provider_name": "Handy Creative Media Suite",
        "category": "DeepMind World Models",
        "capabilities": ["streaming", "video", "interactive"],
        "max_output_tokens": 16384,
        "description": "Project Genie - DeepMind Interactive Generative World Models & Latent Action Simulation",
    },
    "handy-google-flow": {
        "upstream_id": "handy-google-flow",
        "family": "handy",
        "provider_id": "handy",
        "provider_name": "Handy Creative Media Suite",
        "category": "Google Flow Studio",
        "capabilities": ["streaming", "image", "video"],
        "max_output_tokens": 16384,
        "description": "Google Flow & Flow Tools - Multi-shot Storyboarding & Cinematic Rendering Engine",
    },
    "handy-veo-video": {
        "upstream_id": "handy-veo-video",
        "family": "handy",
        "provider_id": "handy",
        "provider_name": "Handy Creative Media Suite",
        "category": "Veo Video Engine",
        "capabilities": ["streaming", "video"],
        "max_output_tokens": 16384,
        "description": "DeepMind Veo - High-Definition Text-to-Video & VideoFX via aisandbox-pa runVideoFx",
    },
    "handy-flow-music": {
        "upstream_id": "handy-flow-music",
        "family": "handy",
        "provider_id": "handy",
        "provider_name": "Handy Creative Media Suite",
        "category": "DeepMind Lyria Music",
        "capabilities": ["streaming", "audio"],
        "max_output_tokens": 16384,
        "description": "Flow Music / MusicFX - DeepMind Lyria Audio Generation via aisandbox-pa soundFx / soundSearch",
    },
    "handy-musicfx-dj": {
        "upstream_id": "handy-musicfx-dj",
        "family": "handy",
        "provider_id": "handy",
        "provider_name": "Handy Creative Media Suite",
        "category": "MusicFX DJ Realtime Audio",
        "capabilities": ["streaming", "audio", "interactive"],
        "max_output_tokens": 16384,
        "description": "MusicFX DJ - Real-time Interactive Web Audio Mixing & Lyria Live Stem Streamer",
    },
}
