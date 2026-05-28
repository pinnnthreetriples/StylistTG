from __future__ import annotations

from fastapi import APIRouter

from app.modules.account_safety.accounts_router import router as accounts_router
from app.modules.account_safety.policy_router import router as policy_router

router = APIRouter()
router.include_router(accounts_router)
router.include_router(policy_router)

__all__ = ["router"]
