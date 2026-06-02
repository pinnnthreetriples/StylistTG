from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AccountOnboardingItem
from app.modules.account_onboarding.adapters.base import ExecutionOutcome, PreviewItem
from app.modules.account_onboarding.contracts import OnboardingCapabilityRead


class JsonMetadataAdapter:
    source_type = "json_metadata"

    def capability(self) -> OnboardingCapabilityRead:
        return OnboardingCapabilityRead(source_type="json_metadata", can_preview=True, can_validate_structure=True, can_materialize_session=False, requires_reauth=True, supports_bulk=True, supports_artifact_upload=True, risk_level="low", user_facing_support_level="requires_reauth")

    def preview(self, _session: Session, *, workspace_id: str, body: dict[str, Any]) -> list[PreviewItem]:
        data = body.get("metadata_json")
        rows = data if isinstance(data, list) else [data]
        if not rows or any(not isinstance(row, dict) for row in rows):
            return [PreviewItem(source_ref="json:invalid", position=0, validation_code="metadata_invalid", validation_message="JSON metadata must be an object or a list of objects.", requires_reauth=True)]
        return [PreviewItem(source_ref=f"json:{i}", position=i, username_hint=str(row.get("username")) if row.get("username") else None, telegram_user_id_hint=str(row.get("telegram_user_id")) if row.get("telegram_user_id") else None, validation_code="metadata_only", validation_message="Metadata preview only. Manual authorization is required.", requires_reauth=True) for i, row in enumerate(rows)]

    def execute(self, item: AccountOnboardingItem) -> ExecutionOutcome:
        return ExecutionOutcome(status="requires_reauth", code="metadata_requires_reauth", message="Metadata-only accounts require manual authorization.")
