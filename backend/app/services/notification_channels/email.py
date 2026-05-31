from __future__ import annotations

from sqlalchemy.orm import Session

from app.contracts.notifications import NotificationDeliveryResult, NotificationPayload
from app.logging_utils import log_event
from app.models import utc_now


class EmailNotifier:
    channel = "email"

    def send(
        self,
        session: Session,
        payload: NotificationPayload,
    ) -> NotificationDeliveryResult:
        # Stub channel: logs the delivery attempt instead of sending mail.
        # Replace with a real SMTP/transactional-email client once that
        # infrastructure exists in the platform.
        log_event(
            "admin_notification_email_stubbed",
            workspace_id=str(payload.workspace_id),
            trigger_code=payload.trigger_code,
            severity=payload.severity,
        )
        return NotificationDeliveryResult(
            channel="email",
            success=True,
            attempted_at=utc_now(),
        )
