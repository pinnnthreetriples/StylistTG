from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountOnboardingBatch, AccountOnboardingItem
from app.models import AuthBatch, AuthBatchItem
from app.modules.account_onboarding.adapters.base import ExecutionOutcome, PreviewItem, hash_value
from app.modules.account_onboarding.contracts import OnboardingCapabilityRead
from app.modules.account_onboarding.state import TERMINAL_ITEM_STATUSES
from app.adapters.tdlib_auth import normalize_phone_number
from app.services.phone_hints import phone_hint

ACTIVE_BATCH_STATUSES = {
    "created",
    "uploaded",
    "validating",
    "preview_ready",
    "confirmed",
    "queued",
    "running",
    "partially_completed",
}


class PhoneListAdapter:
    source_type = "phone_bulk"

    def capability(self) -> OnboardingCapabilityRead:
        return OnboardingCapabilityRead(
            source_type="phone_bulk",
            can_preview=True,
            can_validate_structure=True,
            can_materialize_session=True,
            requires_reauth=False,
            supports_bulk=True,
            supports_artifact_upload=False,
            risk_level="medium",
            user_facing_support_level="full",
        )

    def preview(
        self, session: Session, *, workspace_id: str, body: dict[str, object]
    ) -> list[PreviewItem]:
        raw_items = body.get("phone_items")
        phone_items: list[object] = (
            cast(list[object], raw_items) if isinstance(raw_items, list) else []
        )
        seen: set[str] = set()
        out: list[PreviewItem] = []
        for index, raw_row in enumerate(phone_items):
            if not isinstance(raw_row, dict):
                out.append(_invalid(index, None))
                continue
            row = cast(dict[str, object], raw_row)
            phone = normalize_phone(str(row.get("phone_number") or ""))
            label = str(row["label"]) if row.get("label") else None
            raw_position = row.get("position")
            position = raw_position if type(raw_position) is int else index
            if not phone:
                out.append(_invalid(position, label))
            elif phone in seen:
                out.append(
                    PreviewItem(
                        source_ref=phone,
                        phone=phone,
                        phone_hint=phone_hint(phone),
                        position=position,
                        validation_code="duplicate",
                        validation_message="Duplicate in this batch.",
                        label=label,
                        risk_level="medium",
                    )
                )
            else:
                seen.add(phone)
                existing = session.execute(
                    select(Account).where(
                        Account.workspace_id == workspace_id, Account.external_ref == phone
                    )
                ).scalar_one_or_none()
                if existing:
                    out.append(
                        PreviewItem(
                            source_ref=phone,
                            phone=phone,
                            phone_hint=phone_hint(phone),
                            position=position,
                            validation_code="existing_account",
                            validation_message="Account already exists.",
                            label=label,
                            account_id=existing.id,
                            risk_level="medium",
                        )
                    )
                elif _has_active_conflict(session, workspace_id, phone):
                    out.append(
                        PreviewItem(
                            source_ref=phone,
                            phone=phone,
                            phone_hint=phone_hint(phone),
                            position=position,
                            validation_code="active_conflict",
                            validation_message="Phone is already in another active onboarding batch.",
                            label=label,
                            risk_level="medium",
                        )
                    )
                else:
                    out.append(
                        PreviewItem(
                            source_ref=phone,
                            phone=phone,
                            phone_hint=phone_hint(phone),
                            position=position,
                            label=label,
                            risk_level="medium",
                        )
                    )
        return out

    def execute(self, item: AccountOnboardingItem) -> ExecutionOutcome:
        return ExecutionOutcome(
            status="failed",
            code="phone_auth_bridge_not_started",
            message="Phone auth bridge was not started for this item.",
        )


def normalize_phone(value: str) -> str | None:
    try:
        return normalize_phone_number(value)
    except ValueError:
        return None


def _invalid(position: int, label: str | None) -> PreviewItem:
    return PreviewItem(
        source_ref=f"phone:{position}",
        position=position,
        validation_code="phone_invalid",
        validation_message="Invalid phone number.",
        label=label,
        risk_level="medium",
    )


def _has_active_conflict(session: Session, workspace_id: str, phone: str) -> bool:
    onboarding_conflict = (
        session.execute(
            select(AccountOnboardingItem.id)
            .join(
                AccountOnboardingBatch, AccountOnboardingBatch.id == AccountOnboardingItem.batch_id
            )
            .where(
                AccountOnboardingItem.workspace_id == workspace_id,
                AccountOnboardingItem.phone_normalized_hash == hash_value(phone),
                AccountOnboardingBatch.status.in_(ACTIVE_BATCH_STATUSES),
                AccountOnboardingItem.status.notin_(TERMINAL_ITEM_STATUSES),
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
    if onboarding_conflict:
        return True
    return (
        session.execute(
            select(AuthBatchItem.id)
            .join(AuthBatch, AuthBatch.id == AuthBatchItem.batch_id)
            .where(
                AuthBatch.workspace_id == workspace_id,
                AuthBatchItem.phone_number == phone,
                AuthBatchItem.status.notin_(
                    {"authorized", "failed", "cancelled", "skipped", "timed_out"}
                ),
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
