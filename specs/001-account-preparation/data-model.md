# Data Model: Account Preparation Module

## Preparation Strategy

Represents a reusable plan selected by an operator.

Fields:
- `id`: unique identifier
- `workspace_id`: owning workspace; nullable only for global presets if supported by service policy
- `name`: Russian operator-facing name
- `description`: optional Russian description
- `tier_limits_json`: structured limits by day range
- `target_channels_json`: retained for future compatibility but empty and unused by current execution
- `is_preset`: true for built-in strategies
- `created_at`, `updated_at`: timestamps

Relationships:
- One strategy can be used by many preparation sessions.
- Workspace-scoped strategy belongs to one workspace.

Validation:
- Name is required.
- Strategy names must be unique within a workspace.
- Presets must not enable behavior imitation or unsafe live actions.

## Preparation Session

Represents one account's 14-day preparation lifecycle.

Fields:
- `id`
- `workspace_id`
- `account_id`
- `strategy_id`
- `status`: draft, validating, scheduled, active, paused_risk, paused_manual, completed, failed
- `current_day`: 0 through 14
- `cadence_hours`: minimum interval between daily steps
- `next_step_at`: earliest next worker step time
- `last_step_at`: last successful step time
- `started_at`, `paused_at`, `completed_at`
- `next_attempt_at`: retry gate for risk/failure pauses
- `flood_wait_count`: reserved for future live execution risk events
- `consecutive_failures`
- `worker_id`
- `created_at`, `updated_at`

Relationships:
- Belongs to one workspace.
- Belongs to one account.
- Uses one preparation strategy.
- Has many events.
- Has many task runs.

Validation:
- Only one active session per workspace/account for statuses validating, scheduled, active, paused_risk, paused_manual.
- Completed and failed sessions do not block future sessions.
- Current day is always 0..14.
- Cadence is at least 1 hour.

State transitions:
- create: scheduled
- scheduled -> active when worker executes first due step
- scheduled/active -> paused_manual by operator pause
- scheduled/active -> paused_risk on system risk or circuit breaker policy
- paused_manual/paused_risk -> scheduled on valid resume
- active/scheduled -> completed when day 14 is reached
- any non-terminal active state -> failed on unrecoverable error

## Preparation Event

Immutable audit record for the module.

Fields:
- `id`
- `workspace_id`
- `session_id`
- `event_type`
- `payload_json`
- `created_at`

Event types:
- `session_created`
- `readiness_checked`
- `status_changed`
- `day_advanced`
- `task_executed`
- `task_skipped`
- `paused`
- `resumed`
- `circuit_breaker_triggered`
- `completed`
- `failed`

Validation:
- Payload must not contain secrets, session material, API hashes, proxy credentials, phone numbers in raw form, or raw runtime paths.

## Preparation Task Run

Durable idempotency record for worker steps.

Fields:
- `id`
- `workspace_id`
- `session_id`
- `day`
- `task_type`
- `status`: started, completed, skipped, failed
- `worker_id`
- `error_code`
- `error_message`
- `metadata_json`
- `started_at`
- `completed_at`

Relationships:
- Belongs to one session.
- Belongs to one workspace.

Validation:
- Unique `(session_id, day, task_type)`.
- Day is 0..14.
- Metadata must be sanitized.

## Readiness Check Result

Transient response object, not necessarily stored as a table.

Fields:
- `key`
- `label`
- `passed`
- `severity`: error or warning
- `detail`

Rules:
- Error severity affects `is_ready`.
- Warning severity is displayed but does not block creation.

