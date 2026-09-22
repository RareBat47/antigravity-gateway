import json
import yaml

CATEGORIZED_MODELS = {
    # === 1. OpenAI (32 Models) ===
    # The GPT-5 Lineage
    "gpt-5-chat": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5 Chat (Frontier General)", "intelligence": 98},
    "gpt-5.5-instant": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.5 Instant (Fast Frontier)", "intelligence": 99},
    "gpt-5.2": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.2 (General Frontier)", "intelligence": 98},
    "gpt-5.1": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.1 (General Frontier)", "intelligence": 97},
    "gpt-5-high": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5 High (Complex Reasoning)", "intelligence": 98},
    "gpt-5-medium": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5 Medium (Balanced)", "intelligence": 96},
    "gpt-5-mini-high": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5 Mini High (Efficient)", "intelligence": 95},
    "gpt-5-nano-high": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5 Nano High (Ultra-fast)", "intelligence": 93},
    "gpt-5.1-high": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.1 High", "intelligence": 98},
    "gpt-5.1-medium": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.1 Medium", "intelligence": 96},
    "gpt-5.2-high": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.2 High", "intelligence": 99},
    "gpt-5.4-mini-high": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.4 Mini High", "intelligence": 96},
    "gpt-5.4-nano-high": {"family": "openai", "category": "OpenAI", "subcategory": "GPT-5 Lineage", "display": "GPT-5.4 Nano High", "intelligence": 94},
    # Codex (Software Engineering)
    "gpt-5.3-codex": {"family": "openai", "category": "OpenAI", "subcategory": "Codex (Software Engineering)", "display": "GPT-5.3 Codex (Flagship SWE)", "intelligence": 99},
    "gpt-5.2-codex": {"family": "openai", "category": "OpenAI", "subcategory": "Codex (Software Engineering)", "display": "GPT-5.2 Codex (Autonomous Coding)", "intelligence": 98},
    "gpt-5.1-codex": {"family": "openai", "category": "OpenAI", "subcategory": "Codex (Software Engineering)", "display": "GPT-5.1 Codex", "intelligence": 97},
    "gpt-5.1-codex-max": {"family": "openai", "category": "OpenAI", "subcategory": "Codex (Software Engineering)", "display": "GPT-5.1 Codex Max (Full Repo Context)", "intelligence": 98},
    "gpt-5.1-codex-mini": {"family": "openai", "category": "OpenAI", "subcategory": "Codex (Software Engineering)", "display": "GPT-5.1 Codex Mini (Fast Edits)", "intelligence": 95},
    # Search-Grounded
    "gpt-5-search": {"family": "openai", "category": "OpenAI", "subcategory": "Search-Grounded", "display": "GPT-5 Search", "intelligence": 96},
    "gpt-5.1-search": {"family": "openai", "category": "OpenAI", "subcategory": "Search-Grounded", "display": "GPT-5.1 Search", "intelligence": 97},
    "gpt-5.2-search": {"family": "openai", "category": "OpenAI", "subcategory": "Search-Grounded", "display": "GPT-5.2 Search", "intelligence": 98},
    # Open Weights
    "gpt-oss-120b": {"family": "openai", "category": "OpenAI", "subcategory": "Open Weights", "display": "GPT-OSS 120B", "intelligence": 86},
    "gpt-oss-20b": {"family": "openai", "category": "OpenAI", "subcategory": "Open Weights", "display": "GPT-OSS 20B", "intelligence": 82},
    # Reasoning & Earlier Frontier
    "o3-mini": {"family": "openai", "category": "OpenAI", "subcategory": "Reasoning & Earlier Frontier", "display": "o3 Mini (STEM & Reasoning)", "intelligence": 95},
    "o3-2025-04-16": {"family": "openai", "category": "OpenAI", "subcategory": "Reasoning & Earlier Frontier", "display": "o3 Flagship (Deep Thought)", "intelligence": 97},
    "o3-search": {"family": "openai", "category": "OpenAI", "subcategory": "Reasoning & Earlier Frontier", "display": "o3 Search", "intelligence": 96},
    "o4-mini-2025-04-16": {"family": "openai", "category": "OpenAI", "subcategory": "Reasoning & Earlier Frontier", "display": "o4 Mini", "intelligence": 96},
    "gpt-4.1-2025-04-14": {"family": "openai", "category": "OpenAI", "subcategory": "Reasoning & Earlier Frontier", "display": "GPT-4.1", "intelligence": 92},
    "gpt-4.1-mini-2025-04-14": {"family": "openai", "category": "OpenAI", "subcategory": "Reasoning & Earlier Frontier", "display": "GPT-4.1 Mini", "intelligence": 88},

    # === 2. Anthropic / Claude (10 Models) ===
    # Claude 5 Series
    "claude-sonnet-5": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 5 Series", "display": "Claude Sonnet 5 (Frontier Agentic)", "intelligence": 100},
    "claude-sonnet-5-search": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 5 Series", "display": "Claude Sonnet 5 Search", "intelligence": 100},
    # Claude 4.6 & 4.5 Series
    "claude-sonnet-4-6": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4.6 & 4.5 Series", "display": "Claude Sonnet 4.6 (Thinking & Coding)", "intelligence": 97},
    "claude-sonnet-4-6-search": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4.6 & 4.5 Series", "display": "Claude Sonnet 4.6 Search", "intelligence": 97},
    "claude-sonnet-4-5-20250929": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4.6 & 4.5 Series", "display": "Claude Sonnet 4.5", "intelligence": 96},
    "claude-sonnet-4-5-20250929-thinking-32k": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4.6 & 4.5 Series", "display": "Claude Sonnet 4.5 Thinking (32k)", "intelligence": 96},
    "claude-sonnet-4-5-search": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4.6 & 4.5 Series", "display": "Claude Sonnet 4.5 Search", "intelligence": 96},
    "claude-haiku-4-5-20251001": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4.6 & 4.5 Series", "display": "Claude Haiku 4.5", "intelligence": 92},
    # Claude 4 Series
    "claude-sonnet-4-20250514": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4 Series", "display": "Claude Sonnet 4", "intelligence": 94},
    "claude-sonnet-4-20250514-thinking-32k": {"family": "claude", "category": "Anthropic / Claude", "subcategory": "Claude 4 Series", "display": "Claude Sonnet 4 Thinking (32k)", "intelligence": 94},

    # === 3. Google / Gemini (19 Models) ===
    # Gemini 3.x Series
    "gemini-3.8-flash-high": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.8 Flash High (Fast Agentic)", "intelligence": 92},
    "gemini-3.8-flash-medium": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.8 Flash Medium", "intelligence": 91},
    "gemini-3.8-flash-low": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.8 Flash Low", "intelligence": 89},
    "gemini-3.7-flash": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.7 Flash", "intelligence": 91},
    "gemini-3.6-flash": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.6 Flash", "intelligence": 90},
    "gemini-3.5-flash-high": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.5 Flash High", "intelligence": 90},
    "gemini-3.5-flash": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.5 Flash", "intelligence": 89},
    "gemini-3.5-flash-lite": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.5 Flash Lite", "intelligence": 87},
    "gemini-3.1-pro-preview": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.1 Pro (Deep Reasoning)", "intelligence": 95},
    "gemini-3.1-flash-lite": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3.1 Flash Lite", "intelligence": 86},
    "gemini-3-flash": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3 Flash", "intelligence": 88},
    "gemini-3-flash-grounding": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini 3 Flash Grounding", "intelligence": 88},
    "gemini-omni-flash": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 3.x Series", "display": "Gemini Omni Flash", "intelligence": 90},
    # Gemini 2.x Series
    "gemini-2.5-pro": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 2.x Series", "display": "Gemini 2.5 Pro (1M+ Context)", "intelligence": 93},
    "gemini-2.5-pro-grounding": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 2.x Series", "display": "Gemini 2.5 Pro Grounding", "intelligence": 93},
    "gemini-2.5-flash": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 2.x Series", "display": "Gemini 2.5 Flash", "intelligence": 88},
    "gemini-2.0-flash-001": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemini 2.x Series", "display": "Gemini 2.0 Flash", "intelligence": 87},
    # Gemma Open Models
    "gemma-3-27b-it": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemma Open Models", "display": "Gemma 3 27B IT", "intelligence": 85},
    "gemma-3n-e4b-it": {"family": "gemini", "category": "Google / Gemini", "subcategory": "Gemma Open Models", "display": "Gemma 3n E4B IT", "intelligence": 82},

    # === 4. xAI / Grok (8 Models) ===
    # Agentic & Thinking
    "grok-4.20-beta-0309-reasoning": {"family": "xai", "category": "xAI / Grok", "subcategory": "Agentic & Thinking", "display": "Grok 4.20 Beta Reasoning", "intelligence": 96},
    "grok-4.20-multi-agent-beta-0309": {"family": "xai", "category": "xAI / Grok", "subcategory": "Agentic & Thinking", "display": "Grok 4.20 Multi-Agent", "intelligence": 96},
    "grok-4.3": {"family": "xai", "category": "xAI / Grok", "subcategory": "Agentic & Thinking", "display": "Grok 4.3 (Real-Time Tools)", "intelligence": 95},
    "grok-4.6": {"family": "xai", "category": "xAI / Grok", "subcategory": "Agentic & Thinking", "display": "Grok 4.6 (Frontier xAI)", "intelligence": 96},
    "grok-build-0.1": {"family": "xai", "category": "xAI / Grok", "subcategory": "Agentic & Thinking", "display": "Grok Build 0.1 (Agentic Coding)", "intelligence": 94},
    # Search
    "grok-4-search": {"family": "xai", "category": "xAI / Grok", "subcategory": "Search", "display": "Grok 4 Search", "intelligence": 93},
    "grok-4-1-fast-search": {"family": "xai", "category": "xAI / Grok", "subcategory": "Search", "display": "Grok 4.1 Fast Search", "intelligence": 92},
    "grok-4.5-search": {"family": "xai", "category": "xAI / Grok", "subcategory": "Search", "display": "Grok 4.5 Search", "intelligence": 94},

    # === 5. Alibaba / Qwen (15 Models) ===
    # Dedicated Coding Specialist
    "qwen3-coder-480b-a35b-instruct": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Dedicated Coding Specialist", "display": "Qwen3 Coder 480B (Flagship SWE)", "intelligence": 98},
    "qwen3.5-122b-a10b-code": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Dedicated Coding Specialist", "display": "Qwen3.5 122B Code", "intelligence": 95},
    "qwen3.5-35b-a3b-code": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Dedicated Coding Specialist", "display": "Qwen3.5 35B Code", "intelligence": 93},
    "qwen3.5-27b-code": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Dedicated Coding Specialist", "display": "Qwen3.5 27B Code", "intelligence": 92},
    # Qwen 3.x Flagships & Reasoning
    "qwen3.7-max": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen 3.7 Max (Frontier Qwen)", "intelligence": 97},
    "qwen3.7-plus": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen 3.7 Plus", "intelligence": 96},
    "qwen3.6-plus": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen 3.6 Plus", "intelligence": 95},
    "qwen3.6-max-preview": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen 3.6 Max Preview", "intelligence": 96},
    "qwen3-max-thinking": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen3 Max Thinking", "intelligence": 96},
    "qwen3-max-preview": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen3 Max Preview", "intelligence": 95},
    "qwen3-next-80b-a3b-thinking": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen3 Next 80B Thinking", "intelligence": 94},
    "qwen3-next-80b-a3b-instruct": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen3 Next 80B Instruct", "intelligence": 93},
    "qwen3.5-397b-a17b": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen3.5 397B MoE", "intelligence": 94},
    "qwen3-235b-a22b-thinking-2507": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "Qwen3 235B Thinking", "intelligence": 93},
    "qwq-32b": {"family": "qwen", "category": "Alibaba / Qwen", "subcategory": "Qwen 3.x Flagships & Reasoning", "display": "QwQ 32B (Open Reasoning)", "intelligence": 92},

    # === 6. Moonshot / Kimi (5 Models) ===
    "kimi-k2.7-code": {"family": "kimi", "category": "Moonshot / Kimi", "subcategory": "Specialized SWE", "display": "Kimi K2.7 Code (Top Frontend & SWE)", "intelligence": 96},
    "kimi-k2-thinking-turbo": {"family": "kimi", "category": "Moonshot / Kimi", "subcategory": "Reasoning", "display": "Kimi K2 Thinking Turbo", "intelligence": 95},
    "kimi-k2.6": {"family": "kimi", "category": "Moonshot / Kimi", "subcategory": "General Frontier", "display": "Kimi K2.6", "intelligence": 94},
    "kimi-k2-0905-preview": {"family": "kimi", "category": "Moonshot / Kimi", "subcategory": "Preview", "display": "Kimi K2 Preview (0905)", "intelligence": 93},
    "kimi-k2-0711-preview": {"family": "kimi", "category": "Moonshot / Kimi", "subcategory": "Preview", "display": "Kimi K2 Preview (0711)", "intelligence": 92},

    # === 7. Mistral (5 Models) ===
    # Code & Dev
    "devstral-2": {"family": "mistral", "category": "Mistral", "subcategory": "Code & Dev", "display": "Devstral 2 (Mistral Code Engine)", "intelligence": 94},
    "devstral-medium-2507": {"family": "mistral", "category": "Mistral", "subcategory": "Code & Dev", "display": "Devstral Medium", "intelligence": 92},
    # General
    "mistral-large-3": {"family": "mistral", "category": "Mistral", "subcategory": "General Frontier", "display": "Mistral Large 3 (European Frontier)", "intelligence": 94},
    "mistral-medium-3.5": {"family": "mistral", "category": "Mistral", "subcategory": "General Frontier", "display": "Mistral Medium 3.5", "intelligence": 91},
    "mistral-medium-2508": {"family": "mistral", "category": "Mistral", "subcategory": "General Frontier", "display": "Mistral Medium (2508)", "intelligence": 90},

    # === 8. DeepSeek & Zhipu (ZAI) (4 Models) ===
    "deepseek-v4-flash-max": {"family": "deepseek", "category": "DeepSeek & Zhipu", "subcategory": "DeepSeek", "display": "DeepSeek V4 Flash Max (Next-Gen Open)", "intelligence": 97},
    "glm-5.1": {"family": "zai", "category": "DeepSeek & Zhipu", "subcategory": "Zhipu GLM", "display": "GLM-5.1 (Zhipu Flagship)", "intelligence": 95},
    "glm-5": {"family": "zai", "category": "DeepSeek & Zhipu", "subcategory": "Zhipu GLM", "display": "GLM-5", "intelligence": 94},
    "glm-4.7": {"family": "zai", "category": "DeepSeek & Zhipu", "subcategory": "Zhipu GLM", "display": "GLM-4.7", "intelligence": 93},

    # === 9. NVIDIA & Specialized Labs (10 Models) ===
    # NVIDIA
    "cosmos3-super-agentic": {"family": "nvidia", "category": "NVIDIA & Labs", "subcategory": "NVIDIA", "display": "NVIDIA Cosmos 3 Super Agentic", "intelligence": 94},
    "nvidia-nemotron-3-nano-30b-a3b-bf16": {"family": "nvidia", "category": "NVIDIA & Labs", "subcategory": "NVIDIA", "display": "Nemotron 3 Nano 30B", "intelligence": 89},
    "august26-chatbot1": {"family": "nvidia", "category": "NVIDIA & Labs", "subcategory": "NVIDIA", "display": "August26 Chatbot Canary", "intelligence": 92},
    # Poolside (Dedicated Code Lab)
    "laguna-m.1-v2": {"family": "poolside", "category": "NVIDIA & Labs", "subcategory": "Poolside Code Lab", "display": "Poolside Laguna M.1 v2", "intelligence": 95},
    "laguna-xs-2.1": {"family": "poolside", "category": "NVIDIA & Labs", "subcategory": "Poolside Code Lab", "display": "Poolside Laguna XS 2.1", "intelligence": 93},
    # Bytedance
    "k2": {"family": "bytedance", "category": "NVIDIA & Labs", "subcategory": "Bytedance", "display": "Bytedance K2", "intelligence": 92},
    "lhotse": {"family": "bytedance", "category": "NVIDIA & Labs", "subcategory": "Bytedance", "display": "Bytedance Lhotse", "intelligence": 91},
    "groudon": {"family": "bytedance", "category": "NVIDIA & Labs", "subcategory": "Bytedance", "display": "Bytedance Groudon", "intelligence": 91},
    # Amazon
    "amazon.nova-pro-v1:0": {"family": "amazon", "category": "NVIDIA & Labs", "subcategory": "Amazon", "display": "Amazon Nova Pro v1.0", "intelligence": 92},
    "nova-2-lite": {"family": "amazon", "category": "NVIDIA & Labs", "subcategory": "Amazon", "display": "Amazon Nova 2 Lite", "intelligence": 88}
}

# Save as JSON for backend/constants
with open("D:/arena-gateway-workspace/src/agw/categorized_models.json", "w", encoding="utf-8") as f:
    json.dump(CATEGORIZED_MODELS, f, indent=2)

print(f"Saved {len(CATEGORIZED_MODELS)} categorized models!")
