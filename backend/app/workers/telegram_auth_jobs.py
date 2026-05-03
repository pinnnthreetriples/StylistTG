from __future__ import annotations

from app.db import SessionLocal
from app.services.telegram_auth_sessions import process_auth_action


def run_telegram_auth_job(auth_session_id: str, workspace_id: str, action: str, secret_value: str | None = None) -> str:
    with SessionLocal() as session:
        row = process_auth_action(
            session,
            auth_session_id=auth_session_id,
            workspace_id=workspace_id,
            action=action,
            secret_value=secret_value,
        )
        return row.status
