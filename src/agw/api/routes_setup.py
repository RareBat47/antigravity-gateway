"""Setup and onboarding endpoints."""
from fastapi import APIRouter, Depends, Request

from agw.api.middleware import get_admin_key_auth
from agw.security.identity import LocalIdentityManager
from agw.setup.state import SetupStateService


def create_setup_router(config, repo):
    router = APIRouter(prefix="/setup", tags=["Setup"])
    verify = get_admin_key_auth(config)

    @router.get("/status", dependencies=[Depends(verify)])
    async def setup_status():
        return await SetupStateService(config, repo).status()

    @router.post("/initialize", dependencies=[Depends(verify)])
    async def initialize():
        identity = LocalIdentityManager().ensure_identity(config)
        state = await SetupStateService(config, repo).status()
        return {"status": "initialized", "identity": identity, "setup": state}

    return router
