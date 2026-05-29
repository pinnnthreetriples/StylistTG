from __future__ import annotations

from fastapi import APIRouter

from app.modules.account_safety.accounts_router import router as accounts_router
from app.modules.account_safety.policy_router import router as policy_router
from app.modules.account_safety.quarantine_router import router as quarantine_router
from app.modules.account_safety.runtime_router import router as runtime_router
from app.modules.account_safety.status_router import router as status_router

router = APIRouter()
router.include_router(accounts_router)
router.include_router(policy_router)
router.include_router(quarantine_router)
router.include_router(runtime_router)
router.include_router(status_router)

__all__ = ["router"]
