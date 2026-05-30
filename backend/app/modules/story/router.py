from __future__ import annotations

from fastapi import APIRouter

from app.modules.story.capabilities_router import router as capabilities_router
from app.modules.story.drafts_router import router as drafts_router
from app.modules.story.posts_router import router as posts_router

router = APIRouter()
router.include_router(capabilities_router)
router.include_router(drafts_router)
router.include_router(posts_router)

__all__ = ["router"]
