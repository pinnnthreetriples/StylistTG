from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import NeuroCommentCampaign, NeuroCommentLimit, new_id
from app.services.neuro_commenting import repository


@dataclass(frozen=True)
class EffectiveLimit:
    scope_type: str
    scope_id: str | None
    limit_type: str
    max_value: int
    window_seconds: int
    enabled: bool = True


class LimitsService:
    def list_limits(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[NeuroCommentLimit], int]:
        repository.require_campaign(session, campaign_id=campaign_id, workspace_id=workspace_id)
        query = session.query(NeuroCommentLimit).filter(
            NeuroCommentLimit.campaign_id == campaign_id
        )
        total = int(query.with_entities(func.count()).scalar() or 0)
        items = (
            query.order_by(NeuroCommentLimit.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return items, total

    def create_limit(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        payload: dict[str, Any],
    ) -> NeuroCommentLimit:
        repository.require_campaign(session, campaign_id=campaign_id, workspace_id=workspace_id)
        limit = NeuroCommentLimit(id=new_id(), campaign_id=campaign_id, **payload)
        session.add(limit)
        session.flush()
        return limit

    def update_limit(
        self,
        session: Session,
        *,
        limit_id: str,
        workspace_id: str,
        payload: dict[str, Any],
    ) -> NeuroCommentLimit:
        limit = self._require_limit(session, limit_id=limit_id, workspace_id=workspace_id)
        for key, value in payload.items():
            setattr(limit, key, value)
        limit.updated_at = datetime.now(UTC)
        session.flush()
        return limit

    def delete_limit(self, session: Session, *, limit_id: str, workspace_id: str) -> None:
        limit = self._require_limit(session, limit_id=limit_id, workspace_id=workspace_id)
        session.delete(limit)
        session.flush()

    def resolve_effective_limits(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
    ) -> list[EffectiveLimit]:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        explicit = (
            session.query(NeuroCommentLimit)
            .filter(
                NeuroCommentLimit.campaign_id == campaign_id,
                NeuroCommentLimit.enabled.is_(True),
            )
            .all()
        )
        limits = [
            EffectiveLimit(
                scope_type=item.scope_type,
                scope_id=item.scope_id,
                limit_type=item.limit_type,
                max_value=item.max_value,
                window_seconds=item.window_seconds,
                enabled=item.enabled,
            )
            for item in explicit
        ]
        configured = {(item.scope_type, item.scope_id, item.limit_type) for item in limits}
        for item in self._default_limits(campaign.id):
            key = (item.scope_type, item.scope_id, item.limit_type)
            if key not in configured:
                limits.append(item)
        return limits

    def _require_limit(
        self, session: Session, *, limit_id: str, workspace_id: str
    ) -> NeuroCommentLimit:
        limit = (
            session.query(NeuroCommentLimit)
            .join(NeuroCommentCampaign, NeuroCommentCampaign.id == NeuroCommentLimit.campaign_id)
            .filter(
                NeuroCommentLimit.id == limit_id,
                NeuroCommentCampaign.workspace_id == workspace_id,
            )
            .one_or_none()
        )
        if limit is None:
            raise ValueError("limit not found")
        return limit

    def _default_limits(self, campaign_id: str) -> list[EffectiveLimit]:
        return [
            EffectiveLimit(
                "campaign",
                campaign_id,
                "comments_per_hour",
                settings.neuro_comment_default_campaign_comments_per_hour,
                3600,
            ),
            EffectiveLimit(
                "campaign",
                campaign_id,
                "comments_per_day",
                settings.neuro_comment_default_campaign_comments_per_day,
                86400,
            ),
            EffectiveLimit(
                "campaign",
                campaign_id,
                "min_delay_between_comments",
                settings.neuro_comment_default_min_delay_between_comments_seconds,
                settings.neuro_comment_default_min_delay_between_comments_seconds,
            ),
            EffectiveLimit(
                "account",
                None,
                "comments_per_hour",
                settings.neuro_comment_default_account_comments_per_hour,
                3600,
            ),
            EffectiveLimit(
                "account",
                None,
                "comments_per_day",
                settings.neuro_comment_default_account_comments_per_day,
                86400,
            ),
            EffectiveLimit(
                "target",
                None,
                "comments_per_hour",
                settings.neuro_comment_default_target_comments_per_hour,
                3600,
            ),
        ]
