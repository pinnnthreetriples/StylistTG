from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.contracts.notifications import NotificationDeliveryResult, NotificationPayload
from app.models import Workspace, utc_now


class WebhookNotifier:
    channel = "webhook"

    def __init__(self, *, client: httpx.Client | None = None, timeout_seconds: float = 5.0) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    def send(
        self,
        session: Session,
        payload: NotificationPayload,
    ) -> NotificationDeliveryResult | None:
        workspace = session.get(Workspace, str(payload.workspace_id))
        if workspace is None or not workspace.notification_webhook_url:
            return None
        own_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        try:
            response = client.post(
                workspace.notification_webhook_url,
                json=payload.model_dump(mode="json"),
            )
            if response.status_code >= 500:
                return NotificationDeliveryResult(
                    channel="webhook",
                    success=False,
                    error=f"webhook returned {response.status_code}",
                    attempted_at=utc_now(),
                )
            response.raise_for_status()
            return NotificationDeliveryResult(
                channel="webhook",
                success=True,
                attempted_at=utc_now(),
            )
        except httpx.HTTPError as exc:
            return NotificationDeliveryResult(
                channel="webhook",
                success=False,
                error=str(exc),
                attempted_at=utc_now(),
            )
        finally:
            if own_client:
                client.close()
