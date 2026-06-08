---
name: advanced warmup
description: Architecture rules and file map for Advanced Warmup v1.
edges:
  - .mex/ROUTER.md
  - .mex/context/warmup.md
  - .mex/patterns/warmup-change.md
  - docs/runbooks/account-preparation.md
  - docs/design/warmup-ux-blueprint.md
  - docs/design/warmup-divergence-from-gramgpt.md
last_updated: 2026-06-05
---

# Advanced Warmup v1 Pattern

Canonical pattern for milestone `Advanced Warmup v1`. Use this before implementing issues #354 onward. Stage 0 companion docs: `docs/design/warmup-ux-blueprint.md` and `docs/design/warmup-divergence-from-gramgpt.md`.

## 1. Seven Architecture Rules

1. **One action handler pattern.** Each new TDLib action is implemented as `_action_<action_type>` in `backend/app/adapters/warmup_tdlib_real.py`, a matching deterministic branch in `backend/app/adapters/warmup_tdlib_mock.py`, and a handler entry in `execute_action`. Do not branch on `action_type` in `backend/app/modules/warmup/dispatch_processor.py`.
2. **Strategy snapshot is sacred.** New session-affecting strategy fields are copied into `WarmupSession.strategy_snapshot_json` when the session is created. Dispatch code reads the snapshot, not mutable `WarmupStrategy` rows. In-flight sessions with `strategy_snapshot_json is None` use a read-only fallback built from their current strategy.
3. **Event log first.** Every scheduler, selector, lifecycle, safety, and action decision writes to `warmup_event` through `write_warmup_event`. Sanitize event payloads; never store secrets, TDLib paths, invite tokens, phone numbers, or raw generated assets.
4. **Mock parity.** Every real action has a mock result with deterministic metadata. `DRY_RUN` and mock-backed tests must exercise the full dispatch path end to end without live TDLib.
5. **Additive migrations only.** New migrations add tables/columns/enums/defaults. No destructive `DROP`, `RENAME`, or `NOT NULL` without a safe default. Old `WarmupSession` rows must keep dispatching.
6. **Selector is the only decision point.** `<backend/app/modules/warmup/channel_state/selector.py::choose_actions>` returns action/target pairs. Dispatch code resolves context, executes, and records results; it does not decide what should happen next.
7. **Cross-cutting concerns live outside warmup.** Survival analytics, lifecycle state machine, profile uniqueness, AI profile generation, and invite links are separate modules. Warmup calls their public APIs but does not own their models or policy.

## 2. File Map

### Existing anchors

- `backend/app/model_defs/warmup.py` owns `WarmupStrategy`, `WarmupSession`, `WarmupEvent`, `WarmupTaskRun`, and warmup enums.
- `backend/app/modules/warmup/commands.py` owns create/pause/resume/delete session use cases.
- `backend/app/modules/warmup/dispatch_processor.py` owns one dispatch tick.
- `backend/app/modules/warmup/dispatch_schedule.py` owns day plan and window scheduling helpers.
- `backend/app/modules/warmup/dispatch_context.py` owns per-action context resolution.
- `backend/app/modules/warmup/dispatch_results.py` owns success/failure event recording and counters.
- `backend/app/adapters/warmup_tdlib_real.py` and `backend/app/adapters/warmup_tdlib_mock.py` own action execution.
- `backend/app/adapters/warmup_tdlib_contracts.py` owns supported action lists and `WRITE_ACTION_TYPES`.
- `apps/dashboard/src/modules/warmup/` owns dashboard warmup UI.

### Stage 1 backend structure

- `<backend/migrations/versions/YYYYMMDD_XXXX_warmup_channel_state.py>`
- `<backend/migrations/versions/YYYYMMDD_XXXX_warmup_cold_soak_status.py>`
- `<backend/migrations/versions/YYYYMMDD_XXXX_warmup_personality_disabled.py>`
- `<backend/app/model_defs/warmup_channel_state.py>`
- `<backend/app/modules/warmup/channel_state/__init__.py>`
- `<backend/app/modules/warmup/channel_state/contracts.py>`
- `<backend/app/modules/warmup/channel_state/repository.py>`
- `<backend/app/modules/warmup/channel_state/service.py>`
- `<backend/app/modules/warmup/channel_state/selector.py>`
- `<backend/app/modules/warmup/cold_soak.py>`
- `<backend/app/modules/account_survival/module.py>`
- `<backend/app/modules/account_survival/repository.py>`
- `<backend/app/modules/account_survival/queries.py>`
- `<backend/app/modules/account_survival/events.py>`
- `<backend/app/modules/account_survival/router.py>`
- `<backend/app/model_defs/account_survival.py>`

### Stages 2-3 warmup extensions

- `<backend/app/modules/warmup/action_metadata.py>`
- `<backend/app/modules/warmup/action_presets.py>`
- `<backend/app/modules/warmup/channel_state/health.py>`
- `<backend/app/modules/warmup/adaptive_plan.py>`
- `<backend/app/modules/warmup/typing.py>`
- `<backend/app/model_defs/warmup_p2p_friend_link.py>`
- `<backend/app/modules/warmup/p2p/graph.py>`
- `<backend/app/modules/warmup/p2p/peer_selection.py>`

### Stages 4-6 lifecycle, realism, content

- `<backend/app/modules/account_lifecycle/state_machine.py>`
- `<backend/app/modules/account_lifecycle/transitions.py>`
- `<backend/app/modules/account_lifecycle/idle_detector.py>`
- `<backend/app/modules/warmup/idle_session.py>`
- `<backend/app/modules/warmup/pre_production.py>`
- `<backend/app/modules/warmup/cyclic.py>`
- `<backend/app/modules/warmup/circadian/__init__.py>`
- `<backend/app/modules/warmup/circadian/windows.py>`
- `<backend/app/modules/warmup/circadian/personality.py>`
- `<backend/app/modules/warmup/proxy_adaptation.py>`
- `<backend/app/modules/warmup/bootstrap_pool/__init__.py>`
- `<backend/app/modules/warmup/bootstrap_pool/repository.py>`
- `<backend/app/modules/warmup/bootstrap_pool/service.py>`
- `<backend/app/scripts/seed_bootstrap_channels.py>`
- `<backend/app/modules/account_editing/uniqueness_check.py>`
- `<backend/app/adapters/ai_profile_provider/__init__.py>`
- `<backend/app/adapters/ai_profile_provider/contracts.py>`
- `<backend/app/adapters/ai_profile_provider/fake.py>`
- `<backend/app/adapters/ai_profile_provider/openai.py>`
- `<backend/app/modules/account_editing/ai_generation.py>`
- `<backend/app/modules/account_editing/invite_links.py>`

### Stage 7 UI structure

- `<apps/dashboard/src/modules/warmup/components/WarmupAccountSelector.tsx>`
- `<apps/dashboard/src/modules/warmup/components/WarmupLiveLogs.tsx>`
- `<apps/dashboard/src/modules/warmup/components/WarmupSessionTimer.tsx>`
- `<apps/dashboard/src/modules/warmup/components/WarmupSummaryCards.tsx>`
- `<apps/dashboard/src/modules/warmup/components/WarmupStatusPill.tsx>`
- `<apps/dashboard/src/modules/warmup/components/WarmupCyclicConfig.tsx>`
- `<apps/dashboard/src/modules/warmup/components/WarmupCyclicStatus.tsx>`
- `<apps/dashboard/src/modules/warmup/components/ActionPresetButtons.tsx>`
- `<apps/dashboard/src/modules/warmup/components/ActionCategoryHeader.tsx>`
- `apps/dashboard/src/modules/warmup/labels.ts`
- `apps/dashboard/src/modules/warmup/types.ts`
- `apps/dashboard/src/modules/warmup/api.ts`

### Docs and operations

- `<docs/design/warmup-ux-blueprint.md>`
- `<docs/design/warmup-divergence-from-gramgpt.md>`
- `<docs/runbooks/warmup-rollout.md>`
- `<docs/operator/warmup-advanced.md>`
- `<infra/grafana/dashboards/warmup-advanced.json>`

## 3. Action Type Catalog

| action_type | Category | Class | Dependencies | Traffic |
| --- | --- | --- | --- | --- |
| action_type `feed_read` | base | read | TDLib available | normal |
| action_type `channel_browse` | base | read | `channel_ref`, `channel_state` | normal |
| action_type `view_story` | base | read | `channel_ref`, `has_stories=true` | normal |
| action_type `react_to_post` | base | write | `WRITE_ACTION_TYPES`, safety gate, `has_reactions=true`, profile required | normal |
| action_type `join_chat` | base | write | safety gate, target channel | normal |
| action_type `p2p_send` | base | write | safety gate, trusted/friend peer, text provider | normal |
| action_type `view_dialogs` | reading | read | TDLib chats | normal |
| action_type `scroll_channels` | reading | read | `channel_ref`, subscribed channel | heavy |
| action_type `mark_as_read` | reading | read | TDLib chats | normal |
| action_type `search_messages` | reading | read | query seed | normal |
| action_type `vote_poll` | activity | write | open poll, safety hint for young accounts | normal |
| action_type `watch_video` | activity | read | video message candidate | heavy |
| action_type `listen_voice` | activity | read | voice/audio candidate | heavy |
| action_type `search_gif` | entertainment | read | query seed, animation search | heavy |
| action_type `view_stickers` | entertainment | read | sticker sets/recent stickers | heavy |
| action_type `inline_bot` | entertainment | read | approved popular bot only, no send | heavy |
| action_type `link_preview` | entertainment | read | safe URL pool | heavy |
| action_type `forward_message` | social | write | source message, Saved Messages or friend peer | normal |
| action_type `saved_messages` | social | write-self | Saved Messages chat | normal |
| action_type `sync_contacts` | social | write | contacts pool; skip when pool absent | normal |
| action_type `archive_chat` | groups | write-local | non-protected chat | normal |
| action_type `mute_chat` | groups | write-local | non-protected chat | normal |
| action_type `simulate_typing` | profile/settings | write-ephemeral | chat target | normal |
| action_type `view_profile` | profile/settings | read | contact or recent user | normal |
| action_type `check_settings` | profile/settings | read | TDLib option name | normal |
| action_type `update_profile_gradual` | profile/settings | write | profile safety, uniqueness guard where relevant | normal |
| action_type `emoji_status` | profile/settings | write | Premium capability; skip otherwise | normal |
| action_type `drafts` | profile/settings | write-local | chat target; reversible clear | normal |
| action_type `notification_settings` | profile/settings | write-local | scope notification settings | normal |
| action_type `scheduled_messages` | profile/settings | write-self | Saved Messages; reversible/cancellable | normal |

Action catalog rules:

- Update `SUPPORTED_*_ACTIONS`, `WRITE_ACTION_TYPES`, frontend labels, action metadata, presets, and tests together.
- Write actions must pass safety gates. If an action leaves a public or account-visible trace, classify it as write.
- Traffic-heavy actions are metadata first. Proxy-adaptive behavior consumes metadata later; metadata alone does not disable actions.
- `DRY_RUN` still produces action events and deterministic mock metadata for every action_type.

## 4. Lifecycle States

Canonical account lifecycle:

```text
imported -> cold_soak -> warming -> pre_production -> active -> idle -> retired
```

State rules:

- `imported`: account exists, no advanced warmup has started.
- `cold_soak`: 12-24 hours of silence. No TDLib writes, no profile edits, no warmup actions.
- `warming`: normal warmup dispatch is active.
- `pre_production`: short empty-profile probe. Profile must remain empty; flood wait returns account to `cold_soak`.
- `active`: account is eligible for production work after safety gates.
- `idle`: non-production account runs minimal read-only keepalive warmup.
- `retired`: operator or lifecycle module stops future warmup.

Transition owners:

- `<backend/app/modules/account_lifecycle/state_machine.py>` is the only place that mutates lifecycle state.
- `<backend/app/modules/account_lifecycle/interfaces.py>` is the public facade other modules import.
- `<backend/app/modules/warmup/commands.py>` requests `imported -> cold_soak` when a new session starts.
- `<backend/app/modules/warmup/cold_soak.py>` requests `cold_soak -> warming` after the silence window expires.
- `<backend/app/modules/warmup/dispatch_results.py>` or completion flow requests `warming -> pre_production`.
- `<backend/app/modules/warmup/pre_production.py>` requests `pre_production -> active` on success or `pre_production -> cold_soak` on flood wait.
- `<backend/app/modules/account_safety/quarantine.py>` requests `active -> cold_soak` when quarantine opens or extends.
- `<backend/app/modules/account_lifecycle/idle_detector.py>` requests `active -> idle` and idle cleanup requests `idle -> active`.

Every transition writes an `account.lifecycle.transition` event with `from_state`,
`to_state`, `reason`, `actor_user_id`, and sanitized payload metadata. Terminal states
`retired`, `banned`, and `deleted`, plus manual rollback `warming -> cold_soak`, require
operator/manual lifecycle approval and must not be auto-assigned.

## 5. Forbidden

- Do not create a parallel warmup v2 module.
- Do not read mutable `WarmupStrategy` fields from dispatch paths when a `WarmupSession` snapshot can be used.
- Do not hardcode action selection in `dispatch_processor.py`.
- Do not add a real TDLib action without mock parity and `DRY_RUN` coverage.
- Do not enable live TDLib or live warmup without explicit operator approval.
- Do not store secrets, TDLib storage paths, raw logs, raw phone numbers, invite tokens, or generated asset blobs in `warmup_event.payload_json`.
- Do not remove or rename schema fields in this milestone. Use additive migrations and compatibility fallbacks.
- Do not put survival metrics, profile uniqueness, AI provider code, lifecycle state machine, or Grafana logic inside the warmup module.
- Do not let traffic-heavy metadata become an implicit runtime block. Runtime blocks belong to proxy adaptation or explicit operator escape hatches.
- Do not bypass `channel_state.selector.choose_actions` with ad hoc action decisions.

## 6. In-Flight Migration

- Existing `WarmupSession` rows continue with their current status and plan. Do not retroactively move them into `cold_soak`.
- Additive fields use compatibility defaults: `personality_seed_json={}`, `disabled_actions_json=[]`, `lifecycle_state="warming"`, and `cold_soak_until=None`.
- Missing `warmup_channel_state` rows are valid for legacy sessions; selector/context fallbacks must keep old action plans dispatching.
- Missing `strategy_snapshot_json` uses a read-only strategy relationship fallback for that session lifetime.
- Operational rollout steps live in `docs/runbooks/warmup-rollout.md`.
