"""Mock upstream Cloud Code Assist server for offline testing."""

import json
from typing import Any, Dict, List, Optional


class MockCloudCodeClient:
    """Simulates upstream Cloud Code API without making real HTTP requests."""

    def __init__(self):
        self.load_code_assist_response = ("mock-project-12345", "pro")
        self.available_models_response = {
            "models": {
                "gemini-3.5-flash-low": {
                    "displayName": "Gemini 3.5 Flash",
                    "quotaInfo": {"remainingFraction": 0.82, "resetTime": "2026-09-20T04:00:00Z"},
                },
                "gemini-3.1-pro-low": {
                    "displayName": "Gemini 3.1 Pro",
                    "quotaInfo": {"remainingFraction": 0.75, "resetTime": "2026-09-20T04:00:00Z"},
                },
                "claude-sonnet-4-6": {
                    "displayName": "Claude 4.6 Sonnet",
                    "quotaInfo": {"remainingFraction": 0.61, "resetTime": "2026-09-20T05:00:00Z"},
                },
                "claude-opus-4-6-thinking": {
                    "displayName": "Claude 4.6 Opus Thinking",
                    "quotaInfo": {"remainingFraction": 0.50, "resetTime": "2026-09-20T05:00:00Z"},
                },
            }
        }
        self.generate_content_override: Optional[tuple] = None
        self.fail_with_429 = False
        self.fail_with_401 = False
        self.fail_with_503 = False
        self.recorded_envelopes: List[Dict[str, Any]] = []

    async def load_code_assist(self, access_token: str):
        if self.fail_with_401:
            raise RuntimeError("loadCodeAssist failed (HTTP 401): unauthenticated")
        return self.load_code_assist_response

    async def fetch_available_models(self, access_token: str, project_id: Optional[str] = None):
        return self.available_models_response

    async def generate_content(self, access_token: str, envelope: Dict[str, Any]):
        self.recorded_envelopes.append(envelope)

        if self.generate_content_override:
            return self.generate_content_override

        if self.fail_with_429:
            return (
                429,
                {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED: quotaResetDelay: 2.5s"}},
                '{"error": "RESOURCE_EXHAUSTED: quotaResetDelay: 2.5s"}',
            )

        if self.fail_with_503:
            return 503, {}, "Upstream service temporarily unavailable"

        # Success mock response
        mock_response = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "Hello from mock Antigravity upstream!"}],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 15,
                "candidatesTokenCount": 8,
                "totalTokenCount": 23,
            },
        }
        return 200, mock_response, json.dumps(mock_response)

    async def stream_generate_content(self, access_token: str, envelope: Dict[str, Any]):
        self.recorded_envelopes.append(envelope)

        if self.fail_with_429:
            yield 429, "RESOURCE_EXHAUSTED: Rate limited"
            return

        mock_event_1 = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Hello "}]},
                    "finishReason": None,
                }
            ]
        }
        mock_event_2 = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "streaming world!"}]},
                    "finishReason": "STOP",
                }
            ]
        }

        yield 200, f"data: {json.dumps(mock_event_1)}"
        yield 200, f"data: {json.dumps(mock_event_2)}"
        yield 200, "data: [DONE]"
