from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountOnboardingBatch, AccountOnboardingItem
from app.modules.account_onboarding.adapters.base import ExecutionOutcome, PreviewItem, hash_value
from app.modules.account_onboarding.contracts import OnboardingCapabilityRead
from app.modules.account_onboarding.state import TERMINAL_ITEM_STATUSES
from app.services.phone_hints import phone_hint

ACTIVE_BATCH_STATUSES = {"created", "uploaded", "validating", "preview_ready", "confirmed", "queued", "running", "partially_completed"}


class PhoneListAdapter:
    source_type = "phone_bulk"

    def capability(self) -> OnboardingCapabilityRead:
        return OnboardingCapabilityRead(source_type="phone_bulk", can_preview=True, can_validate_structure=True, can_materialize_session=False, requires_reauth=False, supports_bulk=True, supports_artifact_upload=False, risk_level="medium", user_facing_support_level="full")

    def preview(self, session: Session, *, workspace_id: str, body: dict[str, object]) -> list[PreviewItem]:
        seen: set[str] = set()
        out: list[PreviewItem] = []
        for index, row in enumerate(body.get("phone_items") or []):
            if not isinstance(row, dict):
                out.append(_invalid(index, None))
                continue
            phone = normalize_phone(str(row.get("phone_number") or ""))
            label = str(row["label"]) if row.get("label") else None
            position = int(row.get("position") or index)
            if not phone:
                out.append(_invalid(position, label))
            elif phone in seen:
                out.append(PreviewItem(source_ref=phone, phone=phone, phone_hint=phone_hint(phone), position=position, validation_code="duplicate", validation_message="Duplicate in this batch.", label=label, risk_level="medium"))
            else:
                seen.add(phone)
                existing = session.execute(select(Account).where(Account.workspace_id == workspace_id, Account.external_ref == phone)).scalar_one_or_none()
                if existing:
                    out.append(PreviewItem(source_ref=phone, phone=phone, phone_hint=phone_hint(phone), position=position, validation_code="existing_account", validation_message="Account already exists.", label=label, account_id=existing.id, risk_level="medium"))
                elif _has_active_conflict(session, workspace_id, phone):
                    out.append(PreviewItem(source_ref=phone, phone=phone, phone_hint=phone_hint(phone), position=position, validation_code="active_conflict", validation_message="Phone is already in another active onboarding batch.", label=label, risk_level="medium"))
                else:
                    out.append(PreviewItem(source_ref=phone, phone=phone, phone_hint=phone_hint(phone), position=position, validation_message="Ready for authorization.", label=label, risk_level="medium"))
        return out

    def execute(self, item: AccountOnboardingItem) -> ExecutionOutcome:
        return ExecutionOutcome(status="waiting_code", code="waiting_code", message="Authorization code is required.")


def normalize_phone(value: str) -> str | None:
    digits = re.sub(r"\D+", "", value)
    return f"+{digits}" if len(digits) >= 10 else None


def _invalid(position: int, label: str | None) -> PreviewItem:
    return PreviewItem(source_ref=f"phone:{position}", position=position, validation_code="phone_invalid", validation_message="Invalid phone number.", label=label, risk_level="medium")


def _has_active_conflict(session: Session, workspace_id: str, phone: str) -> bool:
    return session.execute(select(AccountOnboardingItem.id).join(AccountOnboardingBatch, AccountOnboardingBatch.id == AccountOnboardingItem.batch_id).where(AccountOnboardingItem.workspace_id == workspace_id, AccountOnboardingItem.phone_normalized_hash == hash_value(phone), AccountOnboardingBatch.status.in_(ACTIVE_BATCH_STATUSES), AccountOnboardingItem.status.notin_(TERMINAL_ITEM_STATUSES)).limit(1)).scalar_one_or_none() is not None
