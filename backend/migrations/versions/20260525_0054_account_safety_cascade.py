"""Account deletion cascade policy for safety-pipeline FKs (F-E001).

Closes audit finding F-E001: hard ``DELETE FROM account WHERE id=...`` used to
fail or leave orphan rows because none of the safety-pipeline FKs declared
``ON DELETE``. This migration re-creates every safety-pipeline FK and the
adjacent operational FKs with an explicit policy:

* **CASCADE** — pipeline state and operational history that is meaningless
  without the parent account: quarantines, status observations, load buckets,
  GGR snapshots, behavior profile, bought onboarding state, safety override,
  account_lifecycle_event, account_operation_log, account_auth_attempt, and
  warmup_session (warmup_event / warmup_task_run already cascade from
  warmup_session.id at the ORM layer).
* **SET NULL** — audit / compliance rows that must outlive the account:
  neuro_comment_attempts, neuro_comment_events,
  neuro_comment_generated_comments. These columns are already nullable in
  the model; the migration only changes the ON DELETE clause.

``sensitive_audit_event.account_id`` is a raw UUID column (no FK), so it is
already account-deletion safe and not touched here.

The existing FK constraint names vary depending on whether they were emitted
by ``create_table()`` (auto-numbered) or by an explicit
``op.create_foreign_key()`` call earlier in the history, so the migration
reflects the live schema to find the current constraint name per (table,
column) instead of hardcoding ``<table>_<column>_fkey``.

Revision ID: 20260525_0054
Revises: 20260523_0053
Create Date: 2026-05-25
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "20260525_0054"
down_revision = "20260523_0053"
branch_labels = None
depends_on = None


# (table_name, column_name, ondelete_policy)
_FK_POLICIES: tuple[tuple[str, str, str], ...] = (
    # Pipeline state — disposable.
    ("account_quarantines", "account_id", "CASCADE"),
    ("account_status_observations", "account_id", "CASCADE"),
    ("cross_module_load_buckets", "account_id", "CASCADE"),
    ("account_ggr_scores", "account_id", "CASCADE"),
    ("account_behavior_profile", "account_id", "CASCADE"),
    ("bought_onboarding_state", "account_id", "CASCADE"),
    ("account_safety_override", "account_id", "CASCADE"),
    # Operational history — full purge on account delete.
    ("account_lifecycle_event", "account_id", "CASCADE"),
    ("account_operation_log", "account_id", "CASCADE"),
    ("account_auth_attempt", "account_id", "CASCADE"),
    ("warmup_session", "account_id", "CASCADE"),
    # Audit / compliance — column already nullable; null it out on parent delete.
    ("neuro_comment_attempts", "account_id", "SET NULL"),
    ("neuro_comment_events", "account_id", "SET NULL"),
    ("neuro_comment_generated_comments", "account_id", "SET NULL"),
)


def _find_fk_name(bind, table: str, column: str) -> str | None:
    """Return the existing FK constraint name on (table, column) -> account.id."""
    inspector = inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if fk.get("referred_table") == "account" and column in (
            fk.get("constrained_columns") or []
        ):
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite tests drive cascade discipline at the ORM layer through
        # hard_delete_account(); the DB-level CASCADE/SET NULL is a defense-in-
        # depth safety net for production Postgres only.
        return

    for table, column, policy in _FK_POLICIES:
        existing = _find_fk_name(bind, table, column)
        if existing is None:
            # No prior FK to account.id on this column — skip rather than fail
            # so the migration is resilient to schema drift between branches.
            continue
        op.drop_constraint(existing, table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_{column}_fkey",
            table,
            "account",
            [column],
            ["id"],
            ondelete=policy,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table, column, _policy in _FK_POLICIES:
        existing = _find_fk_name(bind, table, column)
        if existing is None:
            continue
        op.drop_constraint(existing, table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_{column}_fkey",
            table,
            "account",
            [column],
            ["id"],
        )
