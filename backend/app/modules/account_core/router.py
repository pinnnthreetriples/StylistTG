from __future__ import annotations

from fastapi import APIRouter

from app.modules.account_core.accounts_router import router as accounts_router
from app.modules.account_core.compat_router import router as compat_router

router = APIRouter()
# Specific paths (`/auth-state`, `/refresh-runtime`, `/jobs/latest`, ...) must be
# registered BEFORE the `/{account_id}` wildcard from accounts_router so they win
# during route matching.
router.include_router(compat_router)
router.include_router(accounts_router)

__all__ = ["router"]
