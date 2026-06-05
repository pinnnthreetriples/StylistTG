# Advanced Warmup Rollout

## Stage 1 Rollout

### Before Deploy

- Verify all Stage 1 migrations apply cleanly in staging.
- Run migration replay and warmup regression tests.
- Confirm operators know that live TDLib warmup remains disabled unless explicitly approved.

### Deploy

- Deploy backend and let normal migration automation apply additive schema changes.
- Do not recreate or manually mutate active `WarmupSession` rows.
- Existing in-flight sessions continue on their current status and action plan.
- New sessions created after deploy start with `cold_soak`.

### 24 Hour Monitoring

- Existing in-flight sessions should continue to `completed` without entering `cold_soak`.
- New sessions should move from `cold_soak` to scheduled dispatch after the configured silence window.
- Watch logs for missing-field regressions such as `personality_seed_json`, `disabled_actions_json`, `lifecycle_state`, or `cold_soak_until`.
- Check warmup events for unexpected `view_story` or `react_to_post` actions on strategies that do not include them.

## In-Flight Migration Rules

### Existing Sessions

- Keep the current action plan until completion.
- Do not apply `cold_soak` retroactively.
- Keep `personality_seed_json` as an empty object unless a later explicit opt-in migration is added.
- Keep `disabled_actions_json` as an empty list unless an operator changes it.
- Treat missing `warmup_channel_state` rows as a compatibility case: legacy actions continue, and channel state is populated only by actions that actually run.
- If `strategy_snapshot_json` is missing, dispatch uses the read-only strategy relationship fallback for the lifetime of that session.

### New Sessions

- Start in `cold_soak`.
- Receive the additive defaults from current schema.
- Build `warmup_channel_state` naturally as channel actions run.

### Manual Migration

- Do not mass-backfill or mutate active warmup sessions during Stage 1 rollout.
- If a future opt-in upgrade endpoint is added, use it only with operator approval and a rollback note.
- Avoid destructive SQL, bulk rewrites, or forced status transitions for active sessions.

## Rollback Notes

- Stage 1 migrations are additive; rollback should prefer code rollback over data mutation.
- If dispatch errors spike, pause warmup workers before changing data.
- Keep in-flight session rows intact for post-incident inspection.
