"""Shared SQLAlchemy helpers for neuro commenting foundation migrations."""

from __future__ import annotations

# pyright: reportReturnType=false

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")
json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def timestamp_columns() -> tuple[sa.Column[sa.DateTime], sa.Column[sa.DateTime]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
