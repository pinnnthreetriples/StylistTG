from __future__ import annotations

# ruff: noqa: F403,F405

from app.models import *


class WarmupP2pFriendLink(Base):
    __tablename__ = "warmup_p2p_friend_link"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            "friend_account_id",
            name="uq_warmup_p2p_friend_link_pair",
        ),
        CheckConstraint("account_id != friend_account_id", name="ck_warmup_p2p_friend_not_self"),
        Index("ix_warmup_p2p_friend_link_account", "workspace_id", "account_id"),
        Index("ix_warmup_p2p_friend_link_friend", "workspace_id", "friend_account_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    friend_account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
