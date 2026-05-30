from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Account, Asset, Job
from app.modules.account_editing.errors import (
    AccountNotFoundError,
    account_editing_error_from_legacy_message,
)
from app.modules.account_shared.interfaces import lookup_account
from app.services.assets import get_asset
from app.services.execution_policy import ExecutionUsableAdapter
from app.services.jobs import (
    find_active_duplicate_job,
    finalize_job_creation,
    normalize_profile_payload,
    validate_account_for_job,
)
from app.services.limits import check_workspace_limit
from app.modules.account_profile_state.interfaces import latest_applied_profile_photo_asset_id


class AccountEditingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_account(self, *, account_id: str, workspace_id: str | None = None) -> Account | None:
        return lookup_account(self._session, account_id, workspace_id=workspace_id)

    def require_account(self, *, account_id: str, workspace_id: str | None = None) -> Account:
        account = self.get_account(account_id=account_id, workspace_id=workspace_id)
        if account is None:
            raise AccountNotFoundError()
        return account

    def validate_account_for_job(
        self,
        *,
        account_id: str,
        workspace_id: str | None = None,
        execution_adapter: ExecutionUsableAdapter | None = None,
    ) -> Account:
        try:
            return validate_account_for_job(
                self._session,
                account_id,
                workspace_id=workspace_id,
                execution_adapter=execution_adapter,
            )
        except ValueError as exc:
            typed_error = account_editing_error_from_legacy_message(str(exc))
            if typed_error is not None:
                raise typed_error from exc
            raise

    def find_active_duplicate_job(self, *, account_id: str, intent_hash: str) -> Job | None:
        return find_active_duplicate_job(self._session, account_id, intent_hash)

    def finalize_job_creation(
        self,
        job: Job,
        *,
        requested_by_user_id: str | None,
        request_id: str | None,
        log_event_name: str,
    ) -> Job:
        return finalize_job_creation(
            self._session,
            job,
            requested_by_user_id=requested_by_user_id,
            request_id=request_id,
            log_event_name=log_event_name,
        )

    def get_asset(self, *, asset_id: str | None, workspace_id: str | None = None) -> Asset | None:
        return get_asset(self._session, asset_id, workspace_id=workspace_id)

    def normalize_profile_payload(
        self, payload: dict[str, Any], *, workspace_id: str | None = None
    ) -> dict[str, Any]:
        return normalize_profile_payload(self._session, payload, workspace_id=workspace_id)

    def latest_applied_profile_photo_asset_id(self, account_id: str) -> str | None:
        return latest_applied_profile_photo_asset_id(self._session, account_id)

    def check_workspace_job_limit(self, workspace_id: str) -> None:
        check_workspace_limit(self._session, workspace_id, "jobs_per_day")
