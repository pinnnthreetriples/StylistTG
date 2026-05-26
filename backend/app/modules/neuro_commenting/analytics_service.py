from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentAccountStats,
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentChannelStats,
    NeuroCommentChannelRule,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
    new_id,
)
from app.modules.neuro_commenting.enums import NeuroEventLevel
from app.modules.neuro_commenting.repository import safe_event_data


class AnalyticsService:
    def write_event(
        self,
        session: Session,
        *,
        workspace_id: str,
        event_type: str,
        message: str,
        event_level: NeuroEventLevel = NeuroEventLevel.INFO,
        campaign_id: str | None = None,
        account_id: str | None = None,
        target_id: str | None = None,
        observed_post_id: str | None = None,
        generated_comment_id: str | None = None,
        attempt_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> NeuroCommentEvent:
        event = NeuroCommentEvent(
            id=new_id(),
            workspace_id=workspace_id,
            campaign_id=campaign_id,
            account_id=account_id,
            target_id=target_id,
            observed_post_id=observed_post_id,
            generated_comment_id=generated_comment_id,
            attempt_id=attempt_id,
            event_type=event_type,
            event_level=event_level.value,
            message=message,
            data_json=safe_event_data(data),
        )
        session.add(event)
        return event

    def record_generated_comment(
        self,
        session: Session,
        *,
        campaign: NeuroCommentCampaign,
        target: NeuroCommentTarget | None,
        comment: NeuroCommentGeneratedComment,
    ) -> None:
        if target is not None:
            channel_stats = self._channel_stats(
                session, campaign_id=campaign.id, target_id=target.id
            )
            channel_stats.comments_generated = (channel_stats.comments_generated or 0) + 1
        if comment.account_id is not None:
            account_stats = self._account_stats(
                session,
                campaign_id=campaign.id,
                account_id=comment.account_id,
            )
            account_stats.comments_generated = (account_stats.comments_generated or 0) + 1

    def campaign_stats(self, session: Session, *, campaign_id: str) -> dict[str, Any]:
        posts_seen = self._count(session, NeuroCommentObservedPost, campaign_id)
        generated = self._count(session, NeuroCommentGeneratedComment, campaign_id)
        pending = self._count_status(
            session, NeuroCommentGeneratedComment, campaign_id, "approval_status", "pending"
        )
        edited = self._count_status(
            session, NeuroCommentGeneratedComment, campaign_id, "approval_status", "edited"
        )
        approved = self._count_status(
            session, NeuroCommentGeneratedComment, campaign_id, "approval_status", "approved"
        )
        rejected = self._count_status(
            session, NeuroCommentGeneratedComment, campaign_id, "approval_status", "rejected"
        )
        sent = self._count_status(session, NeuroCommentAttempt, campaign_id, "status", "sent")
        failed = self._count_status(session, NeuroCommentAttempt, campaign_id, "status", "failed")
        skipped = self._count_status(session, NeuroCommentAttempt, campaign_id, "status", "skipped")
        flood_wait = self._count_flood_wait(session, campaign_id)
        return {
            "campaign_id": campaign_id,
            "posts_seen": posts_seen,
            "comments_generated": generated,
            "comments_pending": pending,
            "comments_edited": edited,
            "comments_approved": approved,
            "comments_rejected": rejected,
            "comments_sent": sent,
            "comments_failed": failed,
            "comments_skipped": skipped,
            "flood_wait_count": flood_wait,
            "success_rate": sent / max(sent + failed, 1),
            "approval_rate": approved / max(generated, 1),
            "generation_rate": generated / max(posts_seen, 1),
            "last_observed_at": self._max_dt(
                session, NeuroCommentObservedPost, campaign_id, "seen_at"
            ),
            "last_generated_at": self._max_dt(
                session, NeuroCommentGeneratedComment, campaign_id, "created_at"
            ),
            "last_sent_at": self._max_dt(session, NeuroCommentAttempt, campaign_id, "sent_at"),
        }

    def account_stats_page(
        self, session: Session, *, campaign_id: str, page: int = 1, limit: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        query = session.query(NeuroCommentCampaignAccount).filter(
            NeuroCommentCampaignAccount.campaign_id == campaign_id
        )
        total = int(query.with_entities(func.count()).scalar() or 0)
        rows = (
            query.outerjoin(
                NeuroCommentAccountStats,
                and_(
                    NeuroCommentAccountStats.campaign_id == NeuroCommentCampaignAccount.campaign_id,
                    NeuroCommentAccountStats.account_id == NeuroCommentCampaignAccount.account_id,
                ),
            )
            .with_entities(
                NeuroCommentCampaignAccount,
                NeuroCommentAccountStats,
            )
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return [
            {
                "account_id": campaign_account.account_id,
                "comments_generated": stats.comments_generated if stats else 0,
                "comments_sent": stats.comments_sent if stats else 0,
                "comments_failed": stats.comments_failed if stats else 0,
                "flood_wait_count": stats.flood_wait_count if stats else 0,
                "success_rate": stats.success_rate if stats else 0.0,
                "last_success_at": stats.last_success_at if stats else None,
                "last_failure_at": stats.last_failure_at if stats else None,
                "cooldown_until": campaign_account.cooldown_until,
                "status": campaign_account.status,
            }
            for campaign_account, stats in rows
        ], total

    def channel_stats_page(
        self,
        session: Session,
        *,
        campaign: NeuroCommentCampaign,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        query = session.query(NeuroCommentTarget).filter(
            NeuroCommentTarget.campaign_id == campaign.id
        )
        total = int(query.with_entities(func.count()).scalar() or 0)
        targets = query.offset((page - 1) * limit).limit(limit).all()
        target_ids = [target.id for target in targets]
        if not target_ids:
            return [], total
        observed_counts = self._counts_by_target(
            session, NeuroCommentObservedPost, target_ids=target_ids
        )
        generated_counts = self._counts_by_target(
            session, NeuroCommentGeneratedComment, target_ids=target_ids
        )
        attempt_stats = self._attempt_stats_by_target(session, target_ids=target_ids)
        rule_statuses = self._rule_statuses(
            session,
            workspace_id=campaign.workspace_id,
            target_refs=[target.channel_ref for target in targets],
        )
        rows: list[dict[str, Any]] = []
        for target in targets:
            stats = attempt_stats.get(target.id, {})
            sent = int(stats.get("sent", 0))
            failed = int(stats.get("failed", 0))
            rows.append(
                {
                    "target_id": target.id,
                    "channel_ref": target.channel_ref,
                    "title": target.title,
                    "posts_seen": observed_counts.get(target.id, 0),
                    "comments_generated": generated_counts.get(target.id, 0),
                    "comments_sent": sent,
                    "comments_failed": failed,
                    "flood_wait_count": int(stats.get("flood_wait", target.flood_wait_count)),
                    "health_score": target.health_score,
                    "success_rate": sent / max(sent + failed, 1),
                    "last_success_at": stats.get("last_success_at"),
                    "last_failure_at": stats.get("last_failure_at"),
                    "rule_status": rule_statuses.get(target.channel_ref, "none"),
                }
            )
        return rows, total

    def attempts_page(
        self, session: Session, *, campaign_id: str, page: int = 1, limit: int = 50
    ) -> tuple[list[NeuroCommentAttempt], int]:
        query = session.query(NeuroCommentAttempt).filter(
            NeuroCommentAttempt.campaign_id == campaign_id
        )
        total = int(query.with_entities(func.count()).scalar() or 0)
        return (
            query.order_by(NeuroCommentAttempt.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all(),
            total,
        )

    def failure_reasons(
        self, session: Session, *, campaign_id: str, page: int = 1, limit: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        grouped = (
            session.query(
                NeuroCommentAttempt.error_code,
                func.count(NeuroCommentAttempt.id).label("count"),
                func.max(NeuroCommentAttempt.failed_at).label("last_seen_at"),
            )
            .filter(
                NeuroCommentAttempt.campaign_id == campaign_id,
                NeuroCommentAttempt.error_code.is_not(None),
            )
            .group_by(NeuroCommentAttempt.error_code)
        )
        total = int(session.query(func.count()).select_from(grouped.subquery()).scalar() or 0)
        rows = (
            grouped.order_by(func.count(NeuroCommentAttempt.id).desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return [
            {"error_code": code, "count": int(count), "last_seen_at": last_seen}
            for code, count, last_seen in rows
        ], total

    def _channel_stats(
        self,
        session: Session,
        *,
        campaign_id: str,
        target_id: str,
    ) -> NeuroCommentChannelStats:
        stats = (
            session.query(NeuroCommentChannelStats)
            .filter(
                NeuroCommentChannelStats.campaign_id == campaign_id,
                NeuroCommentChannelStats.target_id == target_id,
            )
            .one_or_none()
        )
        if stats is None:
            stats = NeuroCommentChannelStats(
                id=new_id(), campaign_id=campaign_id, target_id=target_id
            )
            session.add(stats)
        return stats

    def _account_stats(
        self,
        session: Session,
        *,
        campaign_id: str,
        account_id: str,
    ) -> NeuroCommentAccountStats:
        stats = (
            session.query(NeuroCommentAccountStats)
            .filter(
                NeuroCommentAccountStats.campaign_id == campaign_id,
                NeuroCommentAccountStats.account_id == account_id,
            )
            .one_or_none()
        )
        if stats is None:
            stats = NeuroCommentAccountStats(
                id=new_id(), campaign_id=campaign_id, account_id=account_id
            )
            session.add(stats)
        return stats

    def _count(self, session: Session, model: Any, campaign_id: str) -> int:
        return int(session.query(model).filter(model.campaign_id == campaign_id).count())

    def _count_status(
        self, session: Session, model: Any, campaign_id: str, field: str, value: str
    ) -> int:
        return int(
            session.query(model)
            .filter(model.campaign_id == campaign_id, getattr(model, field) == value)
            .count()
        )

    def _count_flood_wait(self, session: Session, campaign_id: str) -> int:
        return int(
            session.query(NeuroCommentAttempt)
            .filter(
                NeuroCommentAttempt.campaign_id == campaign_id,
                (
                    (NeuroCommentAttempt.status == "flood_wait")
                    | (NeuroCommentAttempt.error_code == "FLOOD_WAIT")
                ),
            )
            .count()
        )

    def _max_dt(self, session: Session, model: Any, campaign_id: str, field: str):
        return (
            session.query(func.max(getattr(model, field)))
            .filter(model.campaign_id == campaign_id)
            .scalar()
        )

    def _counts_by_target(
        self, session: Session, model: Any, *, target_ids: list[str]
    ) -> dict[str, int]:
        rows = (
            session.query(model.target_id, func.count(model.id))
            .filter(model.target_id.in_(target_ids))
            .group_by(model.target_id)
            .all()
        )
        return {target_id: int(count) for target_id, count in rows}

    def _attempt_stats_by_target(
        self, session: Session, *, target_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        rows = (
            session.query(
                NeuroCommentAttempt.target_id,
                func.sum(case((NeuroCommentAttempt.status == "sent", 1), else_=0)),
                func.sum(case((NeuroCommentAttempt.status == "failed", 1), else_=0)),
                func.sum(case((NeuroCommentAttempt.error_code == "FLOOD_WAIT", 1), else_=0)),
                func.max(NeuroCommentAttempt.sent_at),
                func.max(NeuroCommentAttempt.failed_at),
            )
            .filter(NeuroCommentAttempt.target_id.in_(target_ids))
            .group_by(NeuroCommentAttempt.target_id)
            .all()
        )
        return {
            target_id: {
                "sent": int(sent or 0),
                "failed": int(failed or 0),
                "flood_wait": int(flood_wait or 0),
                "last_success_at": last_success_at,
                "last_failure_at": last_failure_at,
            }
            for target_id, sent, failed, flood_wait, last_success_at, last_failure_at in rows
        }

    def _rule_statuses(
        self, session: Session, *, workspace_id: str, target_refs: list[str]
    ) -> dict[str, str]:
        rows = (
            session.query(NeuroCommentChannelRule)
            .filter(
                NeuroCommentChannelRule.workspace_id == workspace_id,
                NeuroCommentChannelRule.target_ref.in_(target_refs),
                NeuroCommentChannelRule.rule_type.in_(["blacklist", "whitelist"]),
            )
            .order_by(NeuroCommentChannelRule.created_at.desc())
            .all()
        )
        statuses: dict[str, str] = {}
        for rule in rows:
            statuses.setdefault(rule.target_ref, rule.rule_type)
        return statuses

    def _rule_status(self, session: Session, *, workspace_id: str, target_ref: str) -> str:
        rule = (
            session.query(NeuroCommentChannelRule)
            .filter(
                NeuroCommentChannelRule.workspace_id == workspace_id,
                NeuroCommentChannelRule.target_ref == target_ref,
                NeuroCommentChannelRule.rule_type.in_(["blacklist", "whitelist"]),
            )
            .order_by(NeuroCommentChannelRule.created_at.desc())
            .first()
        )
        return rule.rule_type if rule is not None else "none"
