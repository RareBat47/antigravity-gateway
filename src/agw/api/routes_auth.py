"""Authentication/Onboarding routes for Arena accounts."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agw.accounts.manager import AccountManager
from agw.config import AppConfig

class ManualLoginRequest(BaseModel):
    display_name: str
    credentials: str

def create_auth_router(config: AppConfig, account_mgr: AccountManager) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Auth"])

    @router.post("/manual")
    async def manual_exchange(req: ManualLoginRequest):
        """Manually exchange cookies/credentials for Arena."""
        try:
            acc_info = await account_mgr.add_account_from_credentials(
                display_name=req.display_name,
                credentials_json=req.credentials,
            )
            return {"status": "success", "account": acc_info}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return router
