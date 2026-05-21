from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Workspace


def is_safety_pipeline_v2_enabled(session: Session, workspace_id: str) -> bool:
    value = session.scalar(
        select(Workspace.safety_pipeline_v2_enabled).where(Workspace.id == workspace_id)
    )
    return bool(value)


__all__ = ["is_safety_pipeline_v2_enabled"]
