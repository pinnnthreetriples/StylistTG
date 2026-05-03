from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas import TdlibRuntimeStatusRead
from app.services.auth_context import AuthContext, require_authenticated
from app.services.tdlib_runtime import detect_tdlib_runtime

router = APIRouter(prefix="/api/tdlib", tags=["tdlib-runtime"])


@router.get("/runtime", response_model=TdlibRuntimeStatusRead)
def get_tdlib_runtime(_auth: AuthContext = Depends(require_authenticated)):
    return TdlibRuntimeStatusRead(**detect_tdlib_runtime().to_safe_dict())
