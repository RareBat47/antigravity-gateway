"""OpenAI-compatible v1 endpoints for Hermes and LLM clients."""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from agw.accounts.manager import AccountManager
from agw.api.middleware import get_api_key_auth
from agw.cloudcode.client import CloudCodeClient
from agw.cloudcode.envelope import build_rpc_envelope
from agw.cloudcode.error_classifier import (
    UpstreamErrorClassification,
    classify_upstream_error,
)
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository
from agw.protocol.mapper import (
    build_generation_config,
    gemini_response_to_openai,
    oai_messages_to_gemini,
)
from agw.protocol.streamer import parse_and_transform_sse_stream
from agw.protocol.tools import oai_tool_choice_to_gemini, oai_tools_to_gemini
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker
from agw.routing.registry import ModelRegistry
from agw.routing.scheduler import AccountScheduler

logger = logging.getLogger("agw.v1")


def create_v1_router(
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
    router = APIRouter(prefix="/v1", tags=["OpenAI Compatible API"], dependencies=[Depends(verify_key)])

    @router.get("/models")
    async def list_models(request: Request):
        """OpenAI-compatible /v1/models endpoint filtered by API key permissions."""
        all_models = model_registry.list_models_openai()
        key_info = getattr(request.state, "api_key_info", None)
        if not key_info:
            return {"object": "list", "data": all_models}

        allowed_fams = [f.lower() for f in key_info.get("allowed_families", ["all"])]
        allowed_models = key_info.get("allowed_models", [])
        if "all" in allowed_fams:
            return {"object": "list", "data": all_models}

        filtered = []
        for m in all_models:
            mid = m["id"]
            _, m_fam, _ = model_registry.resolve_upstream(mid)
            if m_fam in allowed_fams or mid in allowed_models:
                filtered.append(m)
        return {
            "object": "list",
            "data": filtered,
        }

    @router.get("/models/{model_id:path}")
    async def get_model(model_id: str, request: Request):
        """OpenAI-compatible /v1/models/{model_id} endpoint."""
        m = model_registry.get_model(model_id)
        if not m:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

        key_info = getattr(request.state, "api_key_info", None)
        if key_info:
            allowed_fams = [f.lower() for f in key_info.get("allowed_families", ["all"])]
            allowed_models = key_info.get("allowed_models", [])
            _, m_fam, _ = model_registry.resolve_upstream(model_id)
            if "all" not in allowed_fams and m_fam not in allowed_fams and model_id not in allowed_models:
                raise HTTPException(status_code=403, detail=f"Access to model '{model_id}' is restricted for this API key")

        return {
            "id": model_id,
            "object": "model",
            "created": 1710000000,
            "owned_by": "antigravity-gateway",
        }

    @router.get("/usage")
    async def get_usage():
        """OpenAI-compatible usage endpoint."""
        summary = await repo.get_usage_summary()
        return {
            "object": "usage",
            "total_usage": summary.get("total_tokens", 0),
            "total_requests": summary.get("total_requests", 0),
        }

    @router.get("/billing/subscription")
    async def get_subscription():
        """OpenAI-compatible subscription stub for clients checking billing."""
        return {
            "object": "billing_subscription",
            "has_payment_method": True,
            "canceled": False,
            "access_until": 2000000000,
            "hard_limit_usd": 999999.0,
            "plan": {"title": "Antigravity Multi-Account Gateway", "id": "unlimited"},
        }

    @router.post("/chat/completions")
    async def chat_completions(request: Request):
        """OpenAI-compatible /v1/chat/completions with multi-account routing and failover."""
        body = await request.json()
        model_id = body.get("model", "gemini-3.5-flash")
        is_streaming = bool(body.get("stream", False))

        upstream_id, family, max_tokens = model_registry.resolve_upstream(model_id)

        # Enforce API Key permissions
        key_info = getattr(request.state, "api_key_info", None)
        if key_info:
            allowed_fams = [f.lower() for f in key_info.get("allowed_families", ["all"])]
            allowed_models = key_info.get("allowed_models", [])
            if (
                "all" not in allowed_fams
                and family.lower() not in allowed_fams
                and model_id not in allowed_models
            ):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": {
                            "message": f"Model '{model_id}' (family '{family}') is not permitted for API key '{key_info.get('name')}'. Allowed families: {allowed_fams}",
                            "type": "permission_denied",
                        }
                    },
                )

        messages = body.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="messages cannot be empty")

        # 1. Transform protocol messages
        contents, system_inst = await oai_messages_to_gemini(messages, model_id)
        tools = oai_tools_to_gemini(body.get("tools", []))
        tool_config = oai_tool_choice_to_gemini(body.get("tool_choice"))
        gen_config = build_generation_config(body, max_tokens)

        # 2. Multi-Account Execution with Automatic Failover
        attempted_accounts: List[str] = []
        max_attempts = config.scheduler.max_account_retries
        last_error_detail = "No eligible Antigravity accounts available"

        req_id = f"chatcmpl-{int(time.time()*1000)}"

        for attempt in range(max_attempts):
            # Select best account considering health, quota, cooldowns
            selected_account = await scheduler.select_account(
                model_family=family,
                exclude_account_ids=attempted_accounts,
            )

            if not selected_account:
                break

            acc_id = selected_account["id"]
            attempted_accounts.append(acc_id)
            project_id = selected_account.get("project_id", "")

            # Build Cloud Code Assist request envelope
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

            # Handle Streaming Request
            if is_streaming:
                stream_iter = cloudcode_client.stream_generate_content(access_tok, envelope)
                
                # Check first item from stream to verify status
                first_status, first_line = await anext(stream_iter, (500, "Empty stream"))
                
                if first_status == 200:
                    # Account succeeded
                    latency_ms = (time.time() - start_t) * 1000.0
                    health_tracker.record(acc_id, True, latency_ms)
                    await cooldown_mgr.record_success(acc_id, family)
                    await repo.record_account_usage(acc_id, 0, True)
                    await repo.record_usage_event(
                        request_id=req_id,
                        account_id=acc_id,
                        model_id=model_id,
                        prompt_tokens=0,
                        completion_tokens=0,
                        latency_ms=latency_ms,
                        status_code=200,
                        is_streaming=True,
                    )

                    async def stream_wrapper():
                        # Yield first item then rest
                        async def combined_gen():
                            yield first_status, first_line
                            async for item in stream_iter:
                                yield item

                        async for chunk in parse_and_transform_sse_stream(combined_gen(), model_id, req_id):
                            yield chunk

                    return StreamingResponse(
                        stream_wrapper(),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no",
                            "x-agw-account": acc_id,
                        },
                    )

                # Streaming failed at onset
                err_category, action, cooldown_sec = classify_upstream_error(first_status, first_line)
                logger.warning(
                    f"Streaming error on account {acc_id} ({first_status}): {err_category}, action={action}"
                )
                health_tracker.record(acc_id, False)

                if action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER:
                    dur = await cooldown_mgr.record_rate_limit(acc_id, family, cooldown_sec)
                    logger.info(f"Cooling down account {acc_id} for family '{family}' for {dur}s")

                await repo.record_account_usage(acc_id, 0, False)
                await repo.record_health_event(acc_id, err_category, first_line)
                last_error_detail = f"Upstream HTTP {first_status}: {first_line[:150]}"
                continue

            # Handle Non-Streaming Request
            status_code, payload, raw_text = await cloudcode_client.generate_content(access_tok, envelope)
            latency_ms = (time.time() - start_t) * 1000.0

            if status_code == 200:
                health_tracker.record(acc_id, True, latency_ms)
                await cooldown_mgr.record_success(acc_id, family)
                
                resp_oai = gemini_response_to_openai(payload, model_id, req_id)
                usage = resp_oai.get("usage", {})
                
                await repo.record_account_usage(acc_id, usage.get("total_tokens", 0), True)
                await repo.record_usage_event(
                    request_id=req_id,
                    account_id=acc_id,
                    model_id=model_id,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    latency_ms=latency_ms,
                    status_code=200,
                    is_streaming=False,
                )

                response = Response(
                    content=json.dumps(resp_oai),
                    media_type="application/json",
                )
                response.headers["x-agw-account"] = acc_id
                return response

            # Failure Handling
            err_category, action, cooldown_sec = classify_upstream_error(status_code, raw_text)
            logger.warning(
                f"Request failed on account {acc_id} (HTTP {status_code}): {err_category}, action={action}"
            )
            health_tracker.record(acc_id, False, latency_ms)

            if action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER:
                dur = await cooldown_mgr.record_rate_limit(acc_id, family, cooldown_sec)
                logger.info(f"Account {acc_id} cooled down for '{family}' for {dur}s")
            elif action == UpstreamErrorClassification.ACTION_REFRESH_TOKEN:
                try:
                    await account_mgr.refresh_account_token(acc_id)
                except Exception:
                    pass

            await repo.record_account_usage(acc_id, 0, False)
            await repo.record_health_event(acc_id, err_category, raw_text[:200], latency_ms)
            last_error_detail = f"Upstream HTTP {status_code}: {raw_text[:150]}"

        # If loop exhausts, check if accounts exist but are in cooldown
        if not attempted_accounts:
            all_accounts = await repo.list_accounts()
            active_cooldowns = await repo.list_all_active_cooldowns()
            family_cds = [
                c for c in active_cooldowns
                if c.get("target_family") in (family, "all")
            ]
            if family_cds:
                earliest_exp = min(c.get("cooldown_until", "") for c in family_cds)
                last_error_detail = (
                    f"All connected accounts for model family '{family}' are in cooldown "
                    f"due to upstream rate limits (resets around {earliest_exp} UTC). "
                    f"Tip: Add 1-2 additional Google accounts in /admin/dashboard for automatic failover."
                )
            elif not all_accounts:
                last_error_detail = "No Google accounts are connected. Please click '+ Add Google Account' in /admin/dashboard."
            else:
                last_error_detail = f"Connected accounts are disabled or lack credentials for family '{family}'."

        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "message": f"All available accounts exhausted or rate-limited. {last_error_detail}",
                    "type": "account_pool_exhausted",
                    "code": 503,
                }
            },
        )

    return router
