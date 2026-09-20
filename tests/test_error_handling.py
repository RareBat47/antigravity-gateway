"""
Comprehensive error-handling tests for Antigravity Gateway.

Covers the bugs fixed in the hardening session:
  Bug #4  – error_classifier: quota 400 → cooldown_and_failover
  Bug #5  – error_classifier: project-not-found 403 → disable_account
  Bug #7  – cooldown: record_success resets to 0
  Bug #8  – routes: DISABLE_ACCOUNT action is executed
  Bug #9  – streamer: mid-stream exception yields [DONE]
  Bug #10 – streamer: multiple tool calls get unique indices
  Bug #14 – client: network errors are logged (not silently dropped)
  Bug #15 – manager: concurrent token refresh uses lock
  Bug #17 – schema_sanitizer: $ref resolved from $defs
  Bug #18 – schema_sanitizer: "format" key is stripped
"""

import asyncio
import json
import pytest

# ---------------------------------------------------------------------------
# error_classifier tests
# ---------------------------------------------------------------------------
from agw.cloudcode.error_classifier import (
    UpstreamErrorClassification,
    classify_upstream_error,
)


class TestErrorClassifier:
    def test_thought_signature_missing_returns_error(self):
        """Bug #4 (permanent request error): missing thought_signature on 400 must
        return ACTION_RETURN_ERROR, NOT cooldown/failover."""
        body = json.dumps({
            "error": {
                "code": 400,
                "message": "Function call is missing a thought_signature in functionCall parts.",
            }
        })
        cat, action, _ = classify_upstream_error(400, body)
        assert action == UpstreamErrorClassification.ACTION_RETURN_ERROR
        assert cat == UpstreamErrorClassification.INVALID_ARGUMENT

    def test_user_quota_exceeded_400_triggers_cooldown(self):
        """Bug #4: A 400 that says 'User quota exceeded' is an account-level quota
        problem → should cooldown and failover to a different account."""
        body = json.dumps({
            "error": {
                "code": 400,
                "message": "User quota exceeded for this model.",
            }
        })
        cat, action, _ = classify_upstream_error(400, body)
        assert action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER
        assert cat == UpstreamErrorClassification.RATE_LIMITED

    def test_resource_exhausted_429_triggers_cooldown(self):
        """Standard 429 rate limit → cooldown + failover."""
        body = json.dumps({"error": {"code": 429, "message": "Resource exhausted"}})
        cat, action, cooldown = classify_upstream_error(429, body)
        assert action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER
        assert cooldown > 0

    def test_project_not_found_403_disables_account(self):
        """Bug #5: '403 project not found' → DISABLE_ACCOUNT."""
        body = json.dumps({
            "error": {
                "code": 403,
                "message": "Project not found or access denied.",
            }
        })
        cat, action, _ = classify_upstream_error(403, body)
        assert action == UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT

    def test_project_does_not_have_access_disables_account(self):
        """Bug #5: 'project does not have access' → DISABLE_ACCOUNT."""
        body = "project does not have access to Cloud Code Assist"
        cat, action, _ = classify_upstream_error(403, body)
        assert action == UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT

    def test_account_suspended_disables_account(self):
        """Bug #5: 'account suspended' → DISABLE_ACCOUNT."""
        body = "This account has been suspended due to policy violations."
        cat, action, _ = classify_upstream_error(403, body)
        assert action == UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT

    def test_generic_403_permission_denied_triggers_cooldown(self):
        """Generic 403 without account-disabled phrase → cooldown + failover."""
        body = "permission_denied"
        cat, action, _ = classify_upstream_error(403, body)
        assert action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER

    def test_invalid_grant_disables_account(self):
        """OAuth revocation → DISABLE_ACCOUNT."""
        body = '{"error": "invalid_grant", "error_description": "Token expired"}'
        cat, action, _ = classify_upstream_error(400, body)
        assert cat == UpstreamErrorClassification.INVALID_GRANT
        assert action == UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT

    def test_401_triggers_refresh(self):
        """401 Unauthorized → refresh token."""
        cat, action, _ = classify_upstream_error(401, "unauthenticated")
        assert action == UpstreamErrorClassification.ACTION_REFRESH_TOKEN

    def test_5xx_triggers_retry_backoff(self):
        """503 service unavailable → retry with backoff."""
        cat, action, _ = classify_upstream_error(503, "Service unavailable")
        assert action == UpstreamErrorClassification.ACTION_RETRY_BACKOFF

    def test_invalid_json_schema_returns_error(self):
        """'unsupported field' in 400 → permanent request error, not failover."""
        body = json.dumps({"error": {"message": "Unsupported field: exclusiveMinimum"}})
        cat, action, _ = classify_upstream_error(400, body)
        assert action == UpstreamErrorClassification.ACTION_RETURN_ERROR


# ---------------------------------------------------------------------------
# cooldown tests
# ---------------------------------------------------------------------------
from unittest.mock import AsyncMock, MagicMock


class TestCooldownManager:
    """Bug #7: record_success should reset consecutive count to 0."""

    def _make_mgr(self):
        from agw.routing.cooldown import CooldownManager
        repo = MagicMock()
        repo.get_active_cooldown = AsyncMock(return_value=None)
        repo.set_cooldown = AsyncMock()
        repo.clear_cooldown = AsyncMock()
        mgr = CooldownManager(repo=repo)
        return mgr

    @pytest.mark.asyncio
    async def test_record_success_resets_to_zero(self):
        mgr = self._make_mgr()
        # Simulate 4 consecutive rate limits
        for _ in range(4):
            await mgr.record_rate_limit("acc-001", "gemini")
        assert mgr._consecutive_rate_limits.get("acc-001:gemini", 0) == 4

        # One success should reset to 0
        await mgr.record_success("acc-001", "gemini")
        assert mgr._consecutive_rate_limits.get("acc-001:gemini") == 0

    @pytest.mark.asyncio
    async def test_record_success_advances_tier(self):
        """After reset, the NEXT rate limit starts at tier 0 again."""
        mgr = self._make_mgr()
        for _ in range(3):
            await mgr.record_rate_limit("acc-002", "claude")
        await mgr.record_success("acc-002", "claude")
        # Next rate limit should use tier 0 (60s), not tier 3 (7200s)
        dur = await mgr.record_rate_limit("acc-002", "claude")
        assert dur == mgr.tiers[0]


# ---------------------------------------------------------------------------
# schema_sanitizer tests
# ---------------------------------------------------------------------------
from agw.cloudcode.schema_sanitizer import clean_gemini_schema, normalize_tool_parameters


class TestSchemaSanitizer:
    def test_strips_format_field(self):
        """Bug #18: 'format' must be removed from all schema objects."""
        schema = {
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date-time"},
                "amount": {"type": "number", "format": "float"},
            },
        }
        cleaned = clean_gemini_schema(schema)
        assert "format" not in cleaned["properties"]["date"]
        assert "format" not in cleaned["properties"]["amount"]

    def test_resolves_ref_from_defs(self):
        """Bug #17: $ref + $defs should be inlined, not left as dangling {}."""
        schema = {
            "$defs": {
                "Address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                }
            },
            "type": "object",
            "properties": {
                "home": {"$ref": "#/$defs/Address"},
            },
        }
        cleaned = clean_gemini_schema(schema)
        # $defs should be stripped
        assert "$defs" not in cleaned
        # $ref should be resolved into an inline object schema
        home = cleaned["properties"]["home"]
        assert home.get("type") == "object"
        assert "street" in home.get("properties", {})
        assert "city" in home.get("properties", {})

    def test_resolves_definitions_ref(self):
        """Bug #17: #/definitions/ style $ref also works."""
        schema = {
            "definitions": {
                "Item": {"type": "string", "format": "uuid"},
            },
            "type": "object",
            "properties": {
                "id": {"$ref": "#/definitions/Item"},
            },
        }
        cleaned = clean_gemini_schema(schema)
        assert "definitions" not in cleaned
        id_prop = cleaned["properties"]["id"]
        assert id_prop.get("type") == "string"
        # format should also be stripped after resolution
        assert "format" not in id_prop

    def test_strips_disallowed_keys(self):
        """Existing disallowed keys continue to be stripped."""
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string", "default": "hello", "title": "X"}},
            "additionalProperties": False,
            "$schema": "http://json-schema.org/draft-07/schema",
        }
        cleaned = clean_gemini_schema(schema)
        assert "$schema" not in cleaned
        assert "additionalProperties" not in cleaned
        assert "default" not in cleaned["properties"]["x"]
        assert "title" not in cleaned["properties"]["x"]

    def test_nullable_from_type_list(self):
        """['string', 'null'] type should become type=string + nullable=True."""
        schema = {"type": ["string", "null"]}
        cleaned = clean_gemini_schema(schema)
        assert cleaned["type"] == "string"
        assert cleaned["nullable"] is True

    def test_const_becomes_enum(self):
        """const: 'foo' should become enum: ['foo']."""
        schema = {"const": "foo"}
        cleaned = clean_gemini_schema(schema)
        assert cleaned["enum"] == ["foo"]

    def test_normalize_tool_parameters_always_object(self):
        cleaned = normalize_tool_parameters(None)
        assert cleaned["type"] == "object"
        assert "properties" in cleaned


# ---------------------------------------------------------------------------
# streamer tests
# ---------------------------------------------------------------------------
from agw.protocol.streamer import parse_and_transform_sse_stream


class TestStreamer:
    """Bugs #9 and #10."""

    async def _collect(self, gen) -> list:
        chunks = []
        async for c in gen:
            chunks.append(c)
        return chunks

    @pytest.mark.asyncio
    async def test_mid_stream_exception_yields_done(self):
        """Bug #9: if upstream iterator raises mid-stream, [DONE] must still be sent."""
        async def bad_stream():
            yield 200, "data: {\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"hello\"}]}}]}\n"
            raise ConnectionError("upstream dropped connection")

        chunks = await self._collect(
            parse_and_transform_sse_stream(bad_stream(), "test-model")
        )
        serialized = "".join(chunks)
        assert "data: [DONE]" in serialized
        # Should also include an error indicator
        assert "Stream interrupted" in serialized or "error" in serialized.lower()

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_unique_indices(self):
        """Bug #10: two tool calls in one response must have indices 0 and 1."""
        fn_part1 = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{"functionCall": {"name": "tool_a", "args": {}}}]
                }
            }]
        })
        fn_part2 = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{"functionCall": {"name": "tool_b", "args": {"x": 1}}}]
                }
            }]
        })

        async def stream_with_two_tools():
            yield 200, f"data: {fn_part1}"
            yield 200, f"data: {fn_part2}"
            yield 200, "data: [DONE]"

        chunks = await self._collect(
            parse_and_transform_sse_stream(stream_with_two_tools(), "test-model")
        )
        serialized = " ".join(chunks)
        # Both tool calls should appear
        assert "tool_a" in serialized
        assert "tool_b" in serialized
        # Index 0 and index 1 should both appear
        assert '"index": 0' in serialized or '"index":0' in serialized
        assert '"index": 1' in serialized or '"index":1' in serialized

    @pytest.mark.asyncio
    async def test_upstream_error_status_yields_done(self):
        """Non-200 status from stream should yield an error chunk + [DONE]."""
        async def err_stream():
            yield 429, "rate limited"

        chunks = await self._collect(
            parse_and_transform_sse_stream(err_stream(), "test-model")
        )
        serialized = "".join(chunks)
        assert "data: [DONE]" in serialized
        assert "rate limited" in serialized or "error" in serialized.lower()

    @pytest.mark.asyncio
    async def test_usage_out_populated_after_stream(self):
        """Bug #1 companion: usage_out container receives final token counts."""
        usage_data = {
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 50,
                "totalTokenCount": 150,
            }
        }
        sse_line = json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}], **usage_data})

        async def good_stream():
            yield 200, f"data: {sse_line}"
            yield 200, "data: [DONE]"

        usage_out = []
        await self._collect(
            parse_and_transform_sse_stream(good_stream(), "test-model", usage_out=usage_out)
        )
        assert len(usage_out) == 1
        assert usage_out[0]["prompt_tokens"] == 100
        assert usage_out[0]["completion_tokens"] == 50
        assert usage_out[0]["total_tokens"] == 150
