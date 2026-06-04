from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AccountOnboardingItem
from app.modules.account_onboarding.adapters.base import ExecutionOutcome, PreviewItem
from app.modules.account_onboarding.contracts import OnboardingCapabilityRead
from app.services.tdlib_runtime import detect_tdlib_runtime


class TdlibDirectoryAdapter:
    source_type = "tdlib_directory"

    def capability(self) -> OnboardingCapabilityRead:
        full = tdlib_import_available()
        return OnboardingCapabilityRead(
            source_type="tdlib_directory",
            can_preview=True,
            can_validate_structure=True,
            can_materialize_session=full,
            requires_reauth=not full,
            supports_bulk=False,
            supports_artifact_upload=True,
            risk_level="high",
            user_facing_support_level="full" if full else "preview_only",
        )

    def preview(
        self, session: Session, *, workspace_id: str, body: dict[str, object]
    ) -> list[PreviewItem]:
        del session, workspace_id
        artifact_id = body.get("artifact_id")
        if not artifact_id:
            return [
                PreviewItem(
                    source_ref="tdlib:missing",
                    position=0,
                    validation_code="artifact_missing",
                    validation_message="TDLib artifact is required.",
                    risk_level="high",
                )
            ]
        cap = self.capability()
        return [
            PreviewItem(
                source_ref=f"tdlib_directory:{artifact_id}",
                position=0,
                artifact_id=str(artifact_id),
                validation_code="tdlib_preview"
                if cap.can_materialize_session
                else "tdlib_artifact_verifier_not_enabled",
                validation_message="TDLib artifact is quarantined and ready for backend-only verification."
                if cap.can_materialize_session
                else "TDLib artifact preview only; imported-artifact verification is not enabled.",
                requires_reauth=cap.requires_reauth,
                risk_level="high",
            )
        ]

    def execute(self, item: AccountOnboardingItem) -> ExecutionOutcome:
        del item
        runtime = detect_tdlib_runtime()
        if not settings.account_onboarding_tdlib_import_enabled:
            return ExecutionOutcome(
                status="requires_reauth",
                code="tdlib_artifact_verifier_not_enabled",
                message="Imported TDLib artifact verification is not enabled.",
            )
        if not runtime.readonly_smoke_available:
            return ExecutionOutcome(
                status="requires_reauth",
                code=runtime.error_code or "tdlib_not_configured",
                message="Readonly TDLib verification is not enabled.",
            )
        return ExecutionOutcome(
            status="requires_reauth",
            code="tdlib_verification_unavailable",
            message="Readonly TDLib verification did not produce a ready session.",
        )


def tdlib_import_available() -> bool:
    runtime = detect_tdlib_runtime()
    return bool(
        settings.account_onboarding_tdlib_import_enabled and runtime.readonly_smoke_available
    )
