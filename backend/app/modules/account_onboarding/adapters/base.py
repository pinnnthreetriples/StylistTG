from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.modules.account_onboarding.contracts import OnboardingCapabilityRead


@dataclass(frozen=True, slots=True)
class PreviewItem:
    source_ref: str
    position: int
    phone: str | None = None
    phone_hint: str | None = None
    username_hint: str | None = None
    telegram_user_id_hint: str | None = None
    label: str | None = None
    validation_code: str | None = None
    validation_message: str | None = None
    risk_level: str = "low"
    requires_reauth: bool = False
    account_id: str | None = None
    artifact_id: str | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "source_ref": self.source_ref,
            "position": self.position,
            "phone": self.phone,
            "phone_hint": self.phone_hint,
            "username_hint": self.username_hint,
            "telegram_user_id_hint": self.telegram_user_id_hint,
            "label": self.label,
            "validation_code": self.validation_code,
            "validation_message": self.validation_message,
            "risk_level": self.risk_level,
            "requires_reauth": self.requires_reauth,
            "account_id": self.account_id,
            "artifact_id": self.artifact_id,
        }


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    status: str
    code: str | None = None
    message: str | None = None
    payload: dict[str, Any] | None = None


class AccountOnboardingAdapter(Protocol):
    source_type: str

    def capability(self) -> OnboardingCapabilityRead:
        ...

    def preview(self, session: Session, *, workspace_id: str, body: dict[str, Any]) -> list[PreviewItem]:
        ...

    def execute(self, item: Any) -> ExecutionOutcome:
        ...


def hash_value(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()
