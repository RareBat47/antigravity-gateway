"""Anthropic-compatible /v1/messages and /messages endpoints for Claude Code CLI and modern IDEs."""

import json
import logging
import secrets
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agw.accounts.manager import AccountManager
from agw.api.middleware import get_api_key_auth
from agw.cloudcode.client import CloudCodeClient
from agw.cloudcode.envelope import build_rpc_envelope
from agw.cloudcode.error_classifier import UpstreamErrorClassification, classify_upstream_error
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository
from agw.protocol.anthropic_mapper import (
    anthropic_to_openai_request,
    openai_to_anthropic_response,
    parse_and_transform_anthropic_sse_stream,
)
from agw.protocol.mapper import (
    build_generation_config,
    gemini_response_to_openai,
    oai_messages_to_gemini,
)
from agw.protocol.tools import oai_tool_choice_to_gemini, oai_tools_to_gemini
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker
from agw.routing.registry import ModelRegistry, normalize_model_id
from agw.routing.scheduler import AccountScheduler

logger = logging.getLogger("agw.anthropic")


def create_anthropic_router(
    config: AppConfig,
    repo: DatabaseRepository,
    account_mgr: AccountManager,
    cloudcode_client: CloudCodeClient,
    model_registry: ModelRegistry,
    scheduler: AccountScheduler,
    cooldown_mgr: CooldownManager,
    health_tracker: AccountHealthTracker,
) -> APIRouter:
    verify_key = get_api_key_auth(config)
    router = APIRouter(tags=["Anthropic Compatible API"], dependencies=[Depends(verify_key)])

    async def handle_messages_request(request: Request):
        """Unified handler for Anthropic Messages requests."""
        try:
            anthropic_body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail={"error": {"type": "invalid_request_error", "message": "Request body is not valid JSON"}},
            )

        # Convert to internal OpenAI-like format
        body = anthropic_to_openai_request(anthropic_body)
        raw_model = anthropic_body.get("model", "claude-sonnet-5.5")
        is_streaming = bool(body.get("stream", False))

        m_def = model_registry.get_model(raw_model, fallback_to_default=True)
        upstream_id, family, max_tokens = model_registry.resolve_upstream(raw_model, strict=False)

        # Enforce API Key permissions & smart key adaptation
        key_info = getattr(request.state, "api_key_info", None)
        if key_info:
            allowed_fams = [f.lower() for f in key_info.get("allowed_families", ["all"])]
            allowed_models = key_info.get("allowed_models", [])
            advertise_all = key_info.get("advertise_all_models", False)
            normalized_mid = normalize_model_id(raw_model)

            # If key is scoped specifically to mega-context (1M) and client sent default sonnet/opus
            if "claude-sonnet-5[1m]" in allowed_models and (raw_model not in allowed_models and normalized_mid not in allowed_models):
                if "opus" in raw_model.lower():
                    raw_model = "claude-opus-5[1m]"
                else:
                    raw_model = "claude-sonnet-5[1m]"
                normalized_mid = raw_model
                upstream_id, family, max_tokens = model_registry.resolve_upstream(raw_model, strict=False)

            if not advertise_all and allowed_models:
                if normalized_mid not in allowed_models and raw_model not in allowed_models:
                    raise HTTPException(
                        status_code=403,
                        detail={"error": {"type": "permission_error", "message": f"Model '{raw_model}' is not permitted for this API key. Allowed: {allowed_models}"}},
                    )
            elif not advertise_all and "all" not in allowed_fams and family.lower() not in allowed_fams:
                raise HTTPException(
                    status_code=403,
                    detail={"error": {"type": "permission_error", "message": f"Model family '{family}' is not permitted for this API key."}},
                )

        messages = body.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail={"error": {"type": "invalid_request_error", "message": "messages cannot be empty"}})

        # Transform to Gemini format
        contents, system_inst = await oai_messages_to_gemini(messages, raw_model)
        tools = oai_tools_to_gemini(body.get("tools", []))
        tool_config = oai_tool_choice_to_gemini(body.get("tool_choice"))
        gen_config = build_generation_config(body, max_tokens)

        # Check account pool
        all_accounts = await repo.list_accounts()
        if not all_accounts:
            raise HTTPException(
                status_code=503,
                detail={"error": {"type": "overloaded_error", "message": "No Google accounts connected. Please connect an account in the dashboard."}},
            )

        attempted_accounts: List[str] = []
        max_attempts = config.scheduler.max_account_retries
        last_error_detail = "All available accounts are currently in cooldown"
        req_id = f"msg_{secrets.token_hex(12)}"

        for _ in range(max_attempts):
            selected_account = await scheduler.select_account(
                model_family=family,
                exclude_account_ids=attempted_accounts,
            )
            if not selected_account:
                break

            acc_id = selected_account["id"]
            attempted_accounts.append(acc_id)
            project_id = selected_account.get("project_id", "")

            envelope = build_rpc_envelope(
                project_id=project_id,
                upstream_model_id=upstream_id,
                contents=contents,
                system_instruction=system_inst,
                tools=tools,
                tool_config=tool_config,
                generation_config=gen_config,
            )

            try:
                access_tok = await account_mgr.get_access_token(acc_id)
            except Exception as e:
                logger.warning(f"Failed to get token for account {acc_id}: {e}")
                await repo.record_health_event(acc_id, "auth_error", str(e))
                continue

            start_t = time.time()

            if is_streaming:
                stream_iter = cloudcode_client.stream_generate_content(access_tok, envelope)
                first_status, first_line = await anext(stream_iter, (500, "Empty stream"))

                if first_status == 200:
                    latency_ms = (time.time() - start_t) * 1000.0
                    health_tracker.record(acc_id, True, latency_ms)
                    await cooldown_mgr.record_success(acc_id, family)
                    await repo.record_account_usage(acc_id, 0, True)

                    usage_out: List[Dict[str, Any]] = []

                    async def stream_wrapper():
                        async def combined_gen():
                            yield first_status, first_line
                            async for item in stream_iter:
                                yield item

                        async for chunk in parse_and_transform_anthropic_sse_stream(
                            combined_gen(),
                            model_id=raw_model,
                            request_id=req_id,
                            usage_out=usage_out,
                        ):
                            yield chunk

                        if usage_out:
                            tokens = usage_out[0].get("total_tokens", 0)
                            await repo.record_account_usage(acc_id, tokens, True)

                    return StreamingResponse(
                        stream_wrapper(),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no",
                            "anthropic-version": "2023-06-01",
                        },
                    )
                else:
                    logger.warning(f"Claude stream failed with status {first_status}: {first_line}")
                    err_category, action, cooldown_sec = classify_upstream_error(first_status, first_line)
                    health_tracker.record(acc_id, False, (time.time() - start_t) * 1000.0)
                    if action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER:
                        await cooldown_mgr.record_rate_limit(acc_id, family, cooldown_sec)
                    elif action == UpstreamErrorClassification.ACTION_REFRESH_TOKEN:
                        try:
                            await account_mgr.refresh_account_token(acc_id)
                        except Exception:
                            pass
                    elif action == UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT:
                        await account_mgr.enable_account(acc_id, False)
                    last_error_detail = err_category
                    continue
            else:
                # Non-streaming
                status, data, raw_text = await cloudcode_client.generate_content(access_tok, envelope)
                latency_ms = (time.time() - start_t) * 1000.0

                if status == 200:
                    oai_resp = gemini_response_to_openai(data, raw_model, req_id)
                    tokens = oai_resp.get("usage", {}).get("total_tokens", 0)

                    health_tracker.record(acc_id, True, latency_ms)
                    await cooldown_mgr.record_success(acc_id, family)
                    await repo.record_account_usage(acc_id, tokens, True)

                    anthropic_resp = openai_to_anthropic_response(oai_resp, raw_model)
                    return JSONResponse(content=anthropic_resp, headers={"anthropic-version": "2023-06-01"})
                else:
                    err_category, action, cooldown_sec = classify_upstream_error(status, raw_text or str(data))
                    health_tracker.record(acc_id, False, latency_ms)
                    if action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER:
                        await cooldown_mgr.record_rate_limit(acc_id, family, cooldown_sec)
                    elif action == UpstreamErrorClassification.ACTION_REFRESH_TOKEN:
                        try:
                            await account_mgr.refresh_account_token(acc_id)
                        except Exception:
                            pass
                    elif action == UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT:
                        await account_mgr.enable_account(acc_id, False)
                    last_error_detail = err_category
                    continue

        raise HTTPException(
            status_code=503,
            detail={"error": {"type": "overloaded_error", "message": f"Anthravity Gateway upstream failure: {last_error_detail}"}},
        )

    # Route at /v1/messages and /messages
    router.add_api_route("/v1/messages", handle_messages_request, methods=["POST"])
    router.add_api_route("/messages", handle_messages_request, methods=["POST"])

    return router
