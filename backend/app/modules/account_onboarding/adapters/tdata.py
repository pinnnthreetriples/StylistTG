from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AccountOnboardingItem
from app.modules.account_onboarding.adapters.base import ExecutionOutcome, PreviewItem
from app.modules.account_onboarding.contracts import OnboardingCapabilityRead


class TdataArchiveAdapter:
    source_type = "tdata_archive"

    def capability(self) -> OnboardingCapabilityRead:
        return OnboardingCapabilityRead(
            source_type="tdata_archive",
            can_preview=True,
            can_validate_structure=True,
            can_materialize_session=False,
            requires_reauth=True,
            supports_bulk=False,
            supports_artifact_upload=True,
            risk_level="high",
            user_facing_support_level="requires_reauth",
        )

    def preview(
        self, session: Session, *, workspace_id: str, body: dict[str, object]
    ) -> list[PreviewItem]:
        del session, workspace_id
        artifact_id = body.get("artifact_id")
        return [
            PreviewItem(
                source_ref=f"tdata_archive:{artifact_id or 'missing'}",
                position=0,
                artifact_id=str(artifact_id) if artifact_id else None,
                validation_code="artifact_missing" if not artifact_id else "tdata_requires_reauth",
                validation_message="tdata import is preview-only and requires manual reauthorization."
                if artifact_id
                else "tdata archive artifact is required.",
                requires_reauth=bool(artifact_id),
                risk_level="high",
            )
        ]

    def execute(self, item: AccountOnboardingItem) -> ExecutionOutcome:
        return ExecutionOutcome(
            status="requires_reauth",
            code="tdata_requires_reauth",
            message="tdata conversion is not enabled; manual authorization is required.",
        )
