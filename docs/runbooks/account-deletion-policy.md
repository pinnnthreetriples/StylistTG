# Account Deletion Policy (F-E001)

> Source of truth for what happens when an account row is hard-deleted from
> `account`. Closes audit finding **F-E001** (no explicit `ON DELETE`
> behavior on safety-pipeline FKs).

Migration: `backend/migrations/versions/20260525_0054_account_safety_cascade.py`
Service: `app.services.account_lifecycle.hard_delete_account`
Test coverage: `backend/tests/test_account_safety_cascade.py`

## Per-table policy

| Table | Policy | Rationale |
| --- | --- | --- |
| `account_quarantines` | CASCADE | Quarantines are bound to a live account. |
| `account_status_observations` | CASCADE | Observation history is operational, not compliance. |
| `cross_module_load_buckets` | CASCADE | Per-account counters, disposable. |
| `account_ggr_scores` | CASCADE | Per-account snapshot, recomputed on demand. |
| `account_behavior_profile` | CASCADE | Baseline only meaningful with the account. |
| `bought_onboarding_state` | CASCADE | Onboarding state machine per account. |
| `account_safety_override` | CASCADE | Manual override only valid for the live account. |
| `account_lifecycle_event` | CASCADE | Operational history; full purge on hard delete. |
| `account_operation_log` | CASCADE | Operation log per account. |
| `account_auth_attempt` | CASCADE | Auth attempts per account. |
| `warmup_session` | CASCADE | Warmup history; warmup_event + warmup_task_run cascade transitively via warmup_session FK. |
| `neuro_comment_attempts` | **SET NULL** | Audit/compliance — attempt history must outlive the account. Column already nullable. |
| `neuro_comment_events` | **SET NULL** | Audit/compliance log. Column already nullable. |
| `neuro_comment_generated_comments` | **SET NULL** | Compliance — generated content trail must outlive the account. Column already nullable. |
| `sensitive_audit_event.account_id` | n/a (no FK) | Raw UUID column. Audit retention guaranteed by design — `hard_delete_account` writes the `account.deleted` event **before** the row is removed, and the FK-free column preserves the reference. |

## Migration mechanics

The migration drops and re-creates the 14 FKs above with explicit `ON DELETE`
clauses on **Postgres** only. SQLite test databases skip the DDL changes —
test deterministic cascade behavior is enforced at the ORM layer via the
explicit `delete()` / `update()` statements inside `hard_delete_account`.

The migration uses default constraint naming
(`<table>_<column>_fkey`). There is no SQLAlchemy naming convention in
this project, so the default Postgres FK names match the on-disk reality.

## Service contract

```python
hard_delete_account(
    session,
    account_id=...,
    workspace_id=...,
    actor_user_id=...,   # optional; for sensitive-audit attribution
    reason=...,          # mandatory string captured in the audit row
)
```

Behavior:

1. Verify `account_id` is visible under `workspace_id` — raise `ValueError`
   otherwise. Cross-tenant deletion is blocked at this gate.
2. For each table in the CASCADE list, issue a bulk `DELETE` keyed by
   `account_id`. Row counts captured in the return report.
3. For each table in the SET NULL list, issue a bulk `UPDATE` setting
   `account_id = NULL`. Row counts captured in the report.
4. Write a `sensitive_audit_event` with `action="account.deleted"`,
   `entity_type="account"`, the supplied `reason`, and the full row-count
   report in `metadata_json`.
5. `session.delete(account)` and commit.

The audit row references the (now-deleted) account by `account_id` —
because `sensitive_audit_event.account_id` is a free-form UUID column with
no FK, the reference survives indefinitely.

## Verifying in Postgres after upgrade

After applying migration `20260525_0054`:

```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid IN (
    'account_quarantines'::regclass,
    'account_status_observations'::regclass,
    'cross_module_load_buckets'::regclass,
    'account_ggr_scores'::regclass,
    'account_behavior_profile'::regclass,
    'bought_onboarding_state'::regclass,
    'account_safety_override'::regclass,
    'account_lifecycle_event'::regclass,
    'account_operation_log'::regclass,
    'account_auth_attempt'::regclass,
    'warmup_session'::regclass,
    'neuro_comment_attempts'::regclass,
    'neuro_comment_events'::regclass,
    'neuro_comment_generated_comments'::regclass
)
AND contype = 'f'
ORDER BY conrelid::regclass::text, conname;
```

Every row should show `ON DELETE CASCADE` or `ON DELETE SET NULL` — never
`ON DELETE NO ACTION` (the implicit default that caused F-E001).

## Operator decisions captured here

The audit issue (#160) called out three tables that needed explicit operator
sign-off because their cascade choice carries compliance impact:

- `neuro_comment_attempts.account_id` → **SET NULL** (audit retention).
- `neuro_comment_events.account_id` → **SET NULL** (audit retention).
- `warmup_session.account_id` → **CASCADE**. Warmup history is operational
  rather than audit; the parallel `warmup_event` / `warmup_task_run` rows
  cascade via the `warmup_session.id` FK chain. If a future compliance
  requirement demands warmup retention, switch this to SET NULL and make
  the column nullable in a follow-up migration.

`sensitive_audit_event.account_id` retains the account UUID after deletion
by construction — no FK is involved, so there is nothing to cascade.

## Rollback

`alembic downgrade -1` restores the pre-`0054` FK definitions (no
`ON DELETE` clause). On SQLite the migration is a no-op, so `downgrade()`
is also a no-op.
