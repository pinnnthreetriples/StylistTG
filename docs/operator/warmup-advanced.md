<!-- markdownlint-disable MD013 -->

# Advanced Warmup Operator Runbook

This runbook is for operators of the `Прогрев аккаунтов` module. It explains how to start, monitor, pause, and recover warmup without touching live TDLib or Telegram unless explicit operator approval and feature flags are present.

## 1. Обзор

### Что делает модуль

Advanced Warmup prepares imported Telegram accounts through staged, auditable sessions. It schedules quiet periods, micro-sessions, action simulation or gated TDLib actions, channel health updates, proxy-adaptive presets, lifecycle transitions, live logs, and survival metrics.

### Что модуль не обещает

Warmup is not an anti-ban or restriction-bypass system. It is an operational safety, scheduling, audit, and readiness workflow. Treat every warning as a safety signal, not as something to work around.

### Жизненный цикл аккаунта

Canonical lifecycle:

```text
imported -> cold_soak -> warming -> pre_production -> active -> idle -> retired
```

The operator-facing stages in this runbook are `COLD_SOAK`, `WARMING`, `PRE_PRODUCTION`, `ACTIVE`, and `IDLE`.

### Связи с другими модулями

Warmup coordinates with:

- `account_lifecycle` for lifecycle transitions.
- `account_survival` for survival and flood-wait metrics.
- `account_safety` for safety-gate and quarantine decisions.
- `account_editing` for profile uniqueness and AI bio/avatar generation.
- `warmup/bootstrap_pool` for safe public channel targets.
- `warmup/channel_state` for channel health and selector context.
- RQ queues `warmup_jobs` and `warmup_dispatch_jobs` for execution.

### Источник правды

`warmup_session` is the operational source of truth. `warmup_event` is the audit trail. Dashboard live logs read `/api/warmup-events` and `/api/warmup-events/stream`; session detail reads `/api/warmup/sessions/{session_id}` and session events.

## 2. Quick Start

### Pre-flight

Check these before creating sessions:

- Account is imported and workspace-scoped.
- Proxy status is known or intentionally absent.
- Bootstrap channels exist when strategy has no explicit targets.
- Workers/Redis are healthy if execution is expected.
- Live flags remain off unless approved.

### Import -> warmup -> monitor

1. Import or select accounts.
2. Open `/modules/warmup`.
3. Select account(s) and a strategy.
4. Run readiness validation.
5. Optional: enable cyclic mode, for example `15:00 -> 18:00`, `7` days.
6. Create the session.
7. Watch summary cards, status pill, timer, session table, and live logs.

### Safe default

Default local mode is dry-run: the module records plans and simulated actions without Telegram network calls. Do not change this default in production-like environments without explicit approval.

### Manual pause

Use manual pause when an account, proxy, profile, or workspace policy looks suspicious. Add a short reason. Resume only after the incident checklist is complete.

## 3. Каталог Стадий

### COLD_SOAK

Meaning: silence after import/session creation. No warmup actions should run. Default duration is controlled by `WARMUP_COLD_SOAK_MIN_HOURS` and `WARMUP_COLD_SOAK_MAX_HOURS` (12-24h by default).

Normal signals: `cold_soak_started`, periodic `cold_soak_in_progress`, then `cold_soak_completed`.

If stuck: verify `cold_soak_until`, worker state, scheduler flags, and current time. Do not manually force warmup unless the timestamp and queue state prove the session is overdue.

### WARMING

Meaning: scheduled warmup is active. The selector chooses actions from the strategy snapshot, disabled-actions list, channel health, proxy adaptation, personality seed, and daily counters.

Normal signals: `micro_session_window_opened`, `session_plan_announced`, action events, `micro_session_window_closed`, `day_advanced`.

If noisy: inspect `task_skipped.reason` and disabled actions before changing strategy limits.

### PRE_PRODUCTION

Meaning: short dry-run probe before active production. It requires an empty profile: no bio, no avatar, no pinned profile link. It plans dry-run neuro-commenting and mass reaction work, then completes into `ACTIVE` or returns to `COLD_SOAK` on flood-wait/failure.

Normal signals: `pre_production_started` and lifecycle transition to `active`.

If rejected: clear profile fields or disable pre-production for that strategy only if the issue is intentional and documented.

### ACTIVE

Meaning: account is eligible for production work after warmup and safety gates. Warmup may release isolation. Workspace safety policy still applies where enabled.

Normal signals: `completed`, `isolation_released`, account lifecycle `active`.

If production jobs fail immediately: inspect account survival metrics, safety gate, proxy, and last warmup event before retrying production modules.

### IDLE

Meaning: account is active but not recently used by production jobs. The idle detector can create minimal read-only keepalive warmup when enabled.

Normal signals: idle keepalive session with write actions disabled, then `idle_session_stopped` when work resumes.

If idle loops: verify recent `Job` activity and `WARMUP_IDLE_THRESHOLD_MINUTES`.

## 4. Действия и Пресеты

### Execution modes

- `dry_run`: safe simulation and audit.
- `shadow`: dispatch path simulation without TDLib calls.
- `passive`: read-only TDLib actions, gated.
- `network`: passive plus cautious network actions such as `join_chat`, gated.
- `advanced`: full action catalog, gated and experimental.

### Economic preset

Use for young accounts, weak proxies, or recovery after warnings. Enables low-traffic actions: `feed_read`, `view_dialogs`, `mark_as_read`, `search_messages`, `saved_messages`, `check_settings`.

### Balanced preset

Use as normal default when account/proxy health is acceptable. In strategy terms this is the default planned mix; proxy adaptation may still disable traffic-heavy actions for mobile/residential proxies.

### Full preset

Use only when account age, proxy, channel health, and safety gate are clean. It restores the full advanced action catalog but does not bypass safety gates or live flags.

### Reading actions

| action_type | Operator meaning |
| --- | --- |
| `feed_read` | Read feed/chats without writes. |
| `channel_browse` | Browse safe target channel. |
| `view_dialogs` | Inspect dialog list. |
| `scroll_channels` | Scroll subscribed channel; traffic-heavy. |
| `mark_as_read` | Mark messages read. |
| `search_messages` | Search existing messages. |
| `view_story` | View channel story when available. |

### Activity actions

| action_type | Operator meaning |
| --- | --- |
| `vote_poll` | Vote/open poll flow; write-like risk. |
| `watch_video` | Watch candidate video; traffic-heavy. |
| `listen_voice` | Listen to voice/audio; traffic-heavy. |
| `react_to_post` | React to post; visible write action. |

### Entertainment actions

| action_type | Operator meaning |
| --- | --- |
| `search_gif` | Search GIF/animation; traffic-heavy. |
| `view_stickers` | View sticker data; traffic-heavy. |
| `inline_bot` | Read-only approved inline bot interaction. |
| `link_preview` | Generate/check link preview; traffic-heavy. |

### Social actions

| action_type | Operator meaning |
| --- | --- |
| `p2p_send` | Send P2P message to trusted/friend peer. |
| `forward_message` | Forward safe source message. |
| `saved_messages` | Write to Saved Messages. |
| `sync_contacts` | Sync contacts from approved pool. |

### Group actions

| action_type | Operator meaning |
| --- | --- |
| `join_chat` | Join safe target chat/channel. |
| `archive_chat` | Local archive action. |
| `mute_chat` | Local mute action. |

### Profile and settings actions

| action_type | Operator meaning |
| --- | --- |
| `simulate_typing` | Ephemeral typing indicator before chat action. |
| `view_profile` | Read profile/contact info. |
| `check_settings` | Read TDLib option/settings. |
| `emoji_status` | Premium-only emoji status. |
| `drafts` | Local draft create/clear. |
| `scheduled_messages` | Saved Messages scheduling flow. |
| `update_profile_gradual` | Profile update through safety/uniqueness guards. |
| `notification_settings` | Local notification settings change. |
| `ping_proxy` | Proxy reachability probe. |
| `get_me` | Read own account identity. |

### Traffic-heavy actions

Traffic-heavy actions are `scroll_channels`, `watch_video`, `listen_voice`, `search_gif`, `view_stickers`, and `link_preview`. Mobile/residential proxy adaptation may disable them automatically.

### Write actions

Write actions require live gates, adapter support, and safety checks. Examples: `join_chat`, `react_to_post`, `p2p_send`, `forward_message`, `saved_messages`, `sync_contacts`, `archive_chat`, `mute_chat`, `simulate_typing`, `emoji_status`, `drafts`, `scheduled_messages`, `update_profile_gradual`, `notification_settings`.

## 5. Каталог Событий Лога

### Severity guide

- `info`: normal planning, state, and scheduler messages.
- `success`: completed useful action or milestone.
- `warning`: skip, risk, degraded dependency, or recoverable issue.
- `error`: failed action, queue failure, or circuit-breaker problem.
- `debug`: diagnostic-only events; use for support, not daily decisions.

### Top event checklist

| event_type | Meaning | Operator action |
| --- | --- | --- |
| `session_created` | Session row created. | Confirm strategy/mode/duration. |
| `proxy_adaptation_applied` | Proxy preset changed action mix. | Check disabled actions; avoid overriding on weak proxy. |
| `cold_soak_started` | Silence window opened. | Wait; no action unless timestamp wrong. |
| `cold_soak_in_progress` | Still inside silence window. | Verify `until` if repeated after expected end. |
| `cold_soak_completed` | Silence ended. | Expect scheduled/dispatch work soon. |
| `micro_session_window_opened` | Micro-session started. | Read planned action targets. |
| `session_plan_announced` | Human-readable per-account plan. | Check stage, account age, session length, action count. |
| `session_action_simulated` | Dry-run action recorded. | Safe; no Telegram call. |
| `session_action_executed` | Live action completed. | Confirm mode was approved. |
| `micro_session_window_closed` | Micro-session ended. | Review counters and failed actions. |
| `task_skipped` | Step skipped with reason. | Read `reason`, then follow reason-specific recovery. |
| `task_failed` | Action failed. | Check `error_code`, retry timing, flood-wait status. |
| `day_advanced` | Daily plan advanced. | Confirm current day/progress. |
| `completed` | Warmup completed. | Confirm lifecycle/pre-production/active transition. |
| `paused` | Manual pause. | Keep reason clear; avoid blind resume. |
| `resumed` | Manual/system resume. | Watch next event. |
| `disabled_actions_updated` | Escape hatch changed. | Confirm operator intent and action list. |
| `queue_enqueue_failed` | RQ enqueue failed. | Check Redis/RQ worker before retry. |
| `circuit_breaker_triggered` | Consecutive failures paused session. | Investigate root cause before resume. |
| `circuit_breaker_tripped` | Legacy name for same breaker. | Same as triggered. |
| `p2p_contact_recorded` | Friend graph contact recorded. | Normal after successful live P2P send. |
| `p2p_contact_recording_failed` | Friend graph update failed. | Check workspace graph constraints. |
| `isolation_claimed` | Warmup owns account lock. | Other modules should not mutate account. |
| `isolation_released` | Warmup released lock. | Account available again. |
| `cyclic.started` | Cyclic schedule created. | Check start/end/days. |
| `cyclic.completed` | Cyclic run reached end. | Confirm session completed. |
| `pre_production_started` | Dry-run pre-production probe started. | Verify profile remains empty. |
| `idle_session_stopped` | Idle keepalive stopped. | Normal when production work resumes. |
| `plan_adjusted` | Adaptive plan changed pace. | Check reason/multiplier. |

### Common skip reasons

Important `task_skipped.reason` values:

- `quiet_hours`: wait until quiet hours end.
- `cyclic_inactive_window`: wait for configured cyclic window.
- `passive_disabled`: adapter unavailable or live gate disabled.
- `disabled_by_operator`: action disabled in session escape hatch.
- `write_action_not_enabled`: mode does not allow write action.
- `safety_gate_blocked`: account safety gate blocked action.
- `no_eligible_trusted_peers`: P2P graph has no safe peer.
- `text_provider_unavailable` or `text_provider_empty_render`: check text provider setup.

## 6. Инциденты и Recovery

### Account got `flood_wait`

1. Do not retry immediately.
2. Check `task_failed.error_code` and `retry_after_seconds`.
3. Confirm whether session moved to `paused_risk` or back to `cold_soak`.
4. Keep write actions disabled until account/proxy is reviewed.
5. Resume only after the retry time and safety gate are clean.

### Warmup stuck in COLD_SOAK

1. Compare `cold_soak_until` with current UTC/local time.
2. Verify `WARMUP_WORKERS_ENABLED`, `WARMUP_SCHEDULER_ENABLED`, Redis, and RQ workers.
3. Check for repeated `cold_soak_in_progress`.
4. If timestamp is overdue and workers are healthy, re-enqueue due sessions.
5. Do not manually set status unless there is an audited operator decision.

### All accounts quarantined at once

1. Pause warmup workers.
2. Check workspace safety policy and recent global setting changes.
3. Inspect account-safety events for common reason.
4. Avoid mass resume; sample a few accounts first.
5. Record incident notes before changing policy or thresholds.

### Channel health score below threshold

1. Treat channel as unsafe for selection.
2. Check recent `task_failed`, skip reasons, and channel-state rows.
3. Do not force it back into target pools until health recovers.
4. Prefer bootstrap pool replacement or operator-curated channel update.

### Queue enqueue failure

1. Check Redis availability.
2. Check `warmup_jobs` and `warmup_dispatch_jobs` workers.
3. Verify queue names in worker-plane config.
4. Recreate/retry session only after enqueue path is healthy.

### Live adapter unavailable

1. Confirm live mode was actually approved.
2. Check `WARMUP_LIVE_ENABLED` plus mode flag.
3. Confirm TDLib adapter availability without reading TDLib storage.
4. In normal dry-run/shadow operations, keep adapter unavailable and treat as expected.

### Bad strategy or disabled action mix

1. Inspect strategy snapshot and `disabled_actions_json`.
2. Check `proxy_adaptation_applied`.
3. Apply action preset only if account/proxy health supports it.
4. Use per-session disabled actions for emergency escape hatches.

## 7. Конфигурация

### Environment settings

| Setting | Default | Operator meaning |
| --- | --- | --- |
| `WARMUP_WORKERS_ENABLED` | `false` | Allows worker execution when true. |
| `WARMUP_DRY_RUN` | `true` | Keeps default behavior safe. |
| `WARMUP_DEFAULT_CADENCE_HOURS` | `24` | Legacy dry-run cadence. |
| `WARMUP_COLD_SOAK_MIN_HOURS` | `12` | Minimum silence window. |
| `WARMUP_COLD_SOAK_MAX_HOURS` | `24` | Maximum silence window. |
| `WARMUP_MAX_CONSECUTIVE_FAILURES` | `3` | Circuit-breaker threshold. |
| `WARMUP_BATCH_LIMIT` | `50` | Batch processing cap. |
| `WARMUP_LIVE_ENABLED` | `false` | Global live warmup gate. |
| `WARMUP_PASSIVE_ENABLED` | `false` | Passive live gate. |
| `WARMUP_NETWORK_ENABLED` | `false` | Network live gate. |
| `WARMUP_ADVANCED_ENABLED` | `false` | Advanced live gate. |
| `WARMUP_HARD_DISABLE` | `false` | Kill switch. |
| `WARMUP_SCHEDULER_ENABLED` | `false` | API scheduler loop gate. |
| `WARMUP_SCHEDULER_TICK_SECONDS` | `60` | Scheduler interval. |
| `WARMUP_CONNECTION_STAGGER_MIN_SECONDS` | `15` | Min live connect stagger. |
| `WARMUP_CONNECTION_STAGGER_MAX_SECONDS` | `30` | Max live connect stagger. |
| `WARMUP_DEFAULT_DURATION_DAYS` | `14` | Default session length. |
| `WARMUP_IDLE_DETECTION_ENABLED` | `false` | Idle keepalive gate. |
| `WARMUP_IDLE_THRESHOLD_MINUTES` | `60` | Idle detector threshold. |
| `WARMUP_PRE_PRODUCTION_ENABLED` | `false` | Pre-production gate. |
| `WARMUP_PRE_PRODUCTION_DURATION_HOURS` | `2` | Pre-production dry-run duration. |
| `WARMUP_CIRCADIAN_ENABLED` | `true` | Human-hour scheduling weights. |
| `WARMUP_LAZY_DAY_PROBABILITY` | `0.10` | Deterministic lazy-day rate. |
| `WARMUP_MICRO_SESSION_MIN_MINUTES` | `2` | Minimum micro-session duration. |
| `WARMUP_MICRO_SESSION_MAX_MINUTES` | `7` | Maximum micro-session duration. |
| `WARMUP_DAILY_SESSION_MIN_COUNT` | `3` | Minimum sessions per day. |
| `WARMUP_DAILY_SESSION_MAX_COUNT` | `6` | Maximum sessions per day. |
| `WARMUP_QUIET_HOURS_LOCAL_START` | `23` | Quiet hours start. |
| `WARMUP_QUIET_HOURS_LOCAL_END` | `8` | Quiet hours end. |
| `WARMUP_PEER_ELIGIBILITY_DELAY_HOURS` | `24` | P2P friend eligibility delay. |
| `WARMUP_DATACENTER_PROXY_POLICY` | `warn` | Datacenter proxy policy signal. |
| `WARMUP_SPAM_BOT_RECOVERY_ENABLED` | `false` | Spam-bot recovery gate. |

### Per-strategy settings

Strategies define duration, execution mode, daily action limits, session windows, quiet hours, target channels, and optional pre-production flag. Dispatch must read the session snapshot when available.

### Per-session escape hatches

Operators can disable action types for a single session. Use this for incident response, weak proxy recovery, or stopping write actions without changing the shared strategy.

### Cyclic mode

Cyclic sessions run only inside configured active hours, for example `15:00-18:00` for 7 days. Outside the window, expect `task_skipped.reason=cyclic_inactive_window`.

## 8. Метрики

### Prometheus export

Scrape `/metrics` with `X-Internal-Scrape: true`; public scrapes are rejected unless `METRICS_ALLOW_PUBLIC=true`. The Advanced Warmup dashboard lives at `infra/grafana/dashboards/warmup-advanced.json`.

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `account_survival_total` | Counter | `state`, `workspace_id` | Cumulative survival observations for `alive`, `banned`, and `deleted`. |
| `account_survival_current` | Gauge | `state`, `workspace_id` | Current counts used by the survival-rate panel. |
| `account_survival_days` | Gauge | `percentile`, `workspace_id` | Mean, p50, and p90 survival days. |
| `warmup_session_completed_total` | Counter | `preset`, `workspace_id` | Completed warmup sessions by preset. |
| `warmup_action_executed_total` | Counter | `action_type`, `result`, `workspace_id` | Warmup action outcomes, including dry-run simulations. |
| `warmup_flood_wait_total` | Counter | `action_type`, `workspace_id` | Flood-wait incidents from warmup dispatch failures. |
| `warmup_channel_health_total` | Gauge | `bucket`, `workspace_id` | Channel health distribution: `healthy`, `warning`, `blacklisted`. |

The hourly workflow `account_survival.metrics.update` refreshes gauge metrics from PostgreSQL. Counter metrics are written from account-survival and warmup event hooks.

### Survival rate

Use account survival metrics to compare accounts that completed warmup against accounts that hit flood-wait, quarantine, ban, or early production failure.

### Average warmup days to active

Track time from `warmup_started_at` to `warmup_completed_at` and lifecycle `active`. Spikes usually mean cold-soak queues, cyclic windows, failures, or pre-production delays.

### Failure rate per action

Group `task_failed` by `action_type`, `error_code`, proxy category, strategy, and account age. Watch write actions and traffic-heavy actions separately.

### Flood-wait count

Count `task_failed` where `error_code` starts with `flood_wait`. Treat repeated flood-wait as a hard stop until account/proxy health is reviewed.

### Channel health trend

Monitor channel-state health scores and skip reasons. Replace channels that repeatedly cause `no_*_available`, failed browsing, or unsafe reactions.

### Queue health

Monitor `warmup_jobs`, `warmup_dispatch_jobs`, Redis availability, enqueue latency, and `queue_enqueue_failed`.

### Operator review cadence

Daily: summary cards, paused sessions, flood-wait, queue failures, survival rate. Weekly: strategy presets, disabled action usage, bootstrap channel health, and accounts stuck in non-terminal states.
