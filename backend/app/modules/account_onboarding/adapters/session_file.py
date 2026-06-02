from __future__ import annotations

from pathlib import PurePath

from sqlalchemy.orm import Session

from app.models import AccountOnboardingItem
from app.modules.account_onboarding.adapters.base import ExecutionOutcome, PreviewItem
from app.modules.account_onboarding.contracts import OnboardingCapabilityRead

WHITELISTED_SUFFIXES = {".json", ".session.json"}


class SessionFileAdapter:
    source_type = "session_file"

    def capability(self) -> OnboardingCapabilityRead:
        return OnboardingCapabilityRead(
            source_type="session_file",
            can_preview=True,
            can_validate_structure=True,
            can_materialize_session=False,
            requires_reauth=True,
            supports_bulk=False,
            supports_artifact_upload=True,
            risk_level="high",
            user_facing_support_level="preview_only",
        )

    def preview(
        self, session: Session, *, workspace_id: str, body: dict[str, object]
    ) -> list[PreviewItem]:
        del session, workspace_id
        artifact_id = body.get("artifact_id")
        filename = str(body.get("filename") or "")
        allowed = _allowed_filename(filename)
        return [
            PreviewItem(
                source_ref=f"session_file:{artifact_id or filename or 'missing'}",
                position=0,
                artifact_id=str(artifact_id) if artifact_id else None,
                validation_code="artifact_missing"
                if not artifact_id
                else "session_file_preview"
                if allowed
                else "session_file_unsupported",
                validation_message="Session file format is whitelisted for preview; manual authorization is still required."
                if allowed and artifact_id
                else "Session file format is unsupported and will not be attached.",
                requires_reauth=allowed and bool(artifact_id),
                risk_level="high",
            )
        ]

    def execute(self, item: AccountOnboardingItem) -> ExecutionOutcome:
        return ExecutionOutcome(
            status="requires_reauth",
            code="session_file_requires_reauth",
            message="Session files are preview-only; manual authorization is required.",
        )


def _allowed_filename(filename: str) -> bool:
    lower = PurePath(filename).name.lower()
    return lower.endswith(".session.json") or PurePath(lower).suffix in WHITELISTED_SUFFIXES
