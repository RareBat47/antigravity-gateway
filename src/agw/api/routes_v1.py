"""OpenAI-compatible v1 endpoints for Hermes and LLM clients."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from agw.accounts.manager import AccountManager
from agw.api.middleware import get_api_key_auth
from agw.arena.provider import ArenaProvider
from agw.cloudcode.error_classifier import (
    UpstreamErrorClassification,
    classify_upstream_error,
)
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository
from agw.routing.cooldown import CooldownManager
from agw.routing.health import AccountHealthTracker
from agw.routing.registry import ModelRegistry, normalize_model_id
from agw.routing.scheduler import AccountScheduler

logger = logging.getLogger("agw.v1")

def create_v1_router(
    config: AppConfig,
    repo: DatabaseRepository,
    account_mgr: AccountManager,
    cloudcode_client: ArenaProvider,
    model_registry: ModelRegistry,
    scheduler: AccountScheduler,
    cooldown_mgr: CooldownManager,
    health_tracker: AccountHealthTracker,
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["OpenAI v1"])
    require_auth = Depends(get_api_key_auth(config))

    @router.get("/models", dependencies=[require_auth])
    async def list_models(request: Request) -> Dict[str, Any]:
        """List available models."""
        models = model_registry.list_models_openai()
        
        if hasattr(request.state, "api_key_info"):
            allowed_fams = request.state.api_key_info.get("allowed_families", ["all"])
            allowed_mods = request.state.api_key_info.get("allowed_models", [])
            if "all" not in allowed_fams:
                filtered_models = []
                for m in models:
                    try:
                        _, fam, _ = model_registry.resolve_upstream(m["id"])
                        if fam in allowed_fams or m["id"] in allowed_mods:
                            filtered_models.append(m)
                    except ValueError:
                        pass
                models = filtered_models

        return {
            "object": "list",
            "data": models,
        }

    @router.post("/chat/completions", dependencies=[require_auth])
    async def chat_completions(request: Request) -> Response:
        try:
            req_data = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        model_id = normalize_model_id(req_data.get("model", ""))
        if not model_id:
            raise HTTPException(status_code=400, detail="Model must be specified")

        try:
            upstream_id, family, max_tokens = model_registry.resolve_upstream(model_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        if hasattr(request.state, "api_key_info"):
            allowed_fams = request.state.api_key_info.get("allowed_families", ["all"])
            allowed_mods = request.state.api_key_info.get("allowed_models", [])
            if "all" not in allowed_fams:
                if family not in allowed_fams and model_id not in allowed_mods:
                    raise HTTPException(
                        status_code=403,
                        detail={"error": {"message": f"Model {model_id} not permitted", "type": "auth_error"}},
                    )

        # Override the request model with upstream ID
        req_data["model"] = upstream_id

        # Normalize completion token parameters for upstream compatibility
        if "max_completion_tokens" in req_data and "max_tokens" not in req_data:
            req_data["max_tokens"] = req_data.pop("max_completion_tokens")

        is_stream = req_data.get("stream", False)
        attempted_accounts = []
        max_retries = config.scheduler.max_account_retries
        last_err_detail = "All candidate accounts failed."

        for attempt in range(max_retries + 1):
            selected_account = await scheduler.select_account(upstream_id, attempted_accounts)
            if not selected_account:
                last_err_detail = f"No available accounts for model {model_id} after {attempt} attempts."
                break

            acc_id = selected_account["id"]
            attempted_accounts.append(acc_id)

            try:
                access_tok = await account_mgr.get_access_token(acc_id)
            except Exception as e:
                logger.warning(f"Failed to get token for account {acc_id}: {e}")
                await repo.record_health_event(acc_id, "auth_error", str(e))
                continue

            start_t = time.time()

            if is_stream:
                try:
                    stream_iter = cloudcode_client.stream_generate_content(access_tok, req_data)
                    # 10s timeout on first token to prevent OpenCode from stalling on unresponsive accounts
                    status_code, first_line = await asyncio.wait_for(stream_iter.__anext__(), timeout=10.0)
                    
                    if status_code == 200:
                        async def stream_generator():
                            yield first_line
                            try:
                                async for _, line in stream_iter:
                                    yield line
                            except Exception as e:
                                logger.error(f"Stream interrupted: {e}")
                            finally:
                                health_tracker.record(acc_id, True, (time.time() - start_t) * 1000)

                        return StreamingResponse(
                            stream_generator(),
                            media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
                        )
                    
                    payload = {"error": first_line}
                    raw_text = first_line
                except StopAsyncIteration:
                    status_code, payload, raw_text = 500, {"error": "Empty stream"}, ""
                except Exception as e:
                    status_code, payload, raw_text = 503, {}, str(e)
            else:
                status_code, payload, raw_text = await cloudcode_client.generate_content(access_tok, req_data)
                if status_code == 200:
                    health_tracker.record(acc_id, True, (time.time() - start_t) * 1000)
                    return Response(
                        content=raw_text,
                        status_code=200,
                        media_type="application/json",
                        headers={"x-agw-account": acc_id}
                    )

            # Failure path for this account
            err_cat, err_action, cd_secs = classify_upstream_error(status_code, raw_text)
            logger.warning(
                f"[{acc_id}] Upstream error {status_code}: category={err_cat}, action={err_action} ({raw_text[:100]})"
            )

            health_tracker.record(acc_id, False, 0.0)

            if err_action == UpstreamErrorClassification.ACTION_RETURN_ERROR:
                return Response(
                    content=json.dumps({"error": {"message": raw_text, "type": "upstream_error", "code": status_code}}),
                    status_code=status_code,
                    media_type="application/json",
                )

            if err_action == UpstreamErrorClassification.ACTION_DISABLE_ACCOUNT:
                await account_mgr.enable_account(acc_id, False)
                await repo.record_health_event(acc_id, "disabled_by_system", raw_text[:200])

            if err_action == UpstreamErrorClassification.ACTION_COOLDOWN_AND_FAILOVER:
                await cooldown_mgr.record_rate_limit(acc_id, family, cd_secs)

            if err_action == UpstreamErrorClassification.ACTION_REFRESH_TOKEN:
                try:
                    await account_mgr.refresh_account_token(acc_id)
                except Exception as e:
                    logger.warning(f"[{acc_id}] Token refresh failed: {e}")
                    await cooldown_mgr.record_rate_limit(acc_id, family, cd_secs or 60)

            if attempt < max_retries:
                logger.info(f"Retrying request with a different account. Attempt {attempt + 1}/{max_retries}")
                continue

            last_err_detail = f"Failed after {max_retries + 1} attempts. Last error: {raw_text}"
            break

        return Response(
            content=json.dumps({"error": {"message": last_err_detail, "type": "gateway_exhaustion"}}),
            status_code=503,
            media_type="application/json",
        )

    return router
