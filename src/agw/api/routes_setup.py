"""Setup and onboarding endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request

from agw.api.middleware import get_admin_key_auth
from agw.security.identity import LocalIdentityManager
from agw.setup.state import SetupStateService


def _is_loopback(request: Request) -> bool:
    return bool(request.client and request.client.host in {"127.0.0.1", "::1", "localhost", "testclient"})


def create_setup_router(config, repo):
    router = APIRouter(prefix="/setup", tags=["Setup"])
    verify = get_admin_key_auth(config)

    @router.get("/status")
    async def setup_status(request: Request):
        # Bootstrap status is intentionally local-only so a first-run user can proceed
        # before the generated admin key has been displayed/stored in a client.
        if not _is_loopback(request):
            await verify(request)
        return await SetupStateService(config, repo).status()

    @router.post("/initialize")
    async def initialize(request: Request):
        if not _is_loopback(request):
            await verify(request)
        identity = LocalIdentityManager().ensure_identity(config)
        state = await SetupStateService(config, repo).status()
        return {"status": "initialized", "identity": identity, "setup": state}

    return router
