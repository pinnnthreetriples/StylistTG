---
status: planned
implemented: partial
last_updated: 2026-06-08
---

# Advanced Warmup v1 File Map

This document stores the large planned file map, action catalog, and lifecycle notes for Advanced Warmup v1. The compact procedural pattern lives in `.mex/patterns/warmup-advanced.md`; current milestone state lives in `.mex/context/warmup-advanced-state.md`.

## Existing Anchors

- `backend/app/model_defs/warmup.py` owns `WarmupStrategy`, `WarmupSession`, `WarmupEvent`, `WarmupTaskRun`, and warmup enums.
- `backend/app/modules/warmup/commands.py` owns create/pause/resume/delete session use cases.
- `backend/app/modules/warmup/dispatch_processor.py` owns one dispatch tick.
- `backend/app/modules/warmup/dispatch_schedule.py` owns day plan and window scheduling helpers.
- `backend/app/modules/warmup/dispatch_context.py` owns per-action context resolution.
- `backend/app/modules/warmup/dispatch_results.py` owns success/failure event recording and counters.
- `backend/app/adapters/warmup_tdlib_real.py` and `backend/app/adapters/warmup_tdlib_mock.py` own action execution.
- `backend/app/adapters/warmup_tdlib_contracts.py` owns supported action lists and `WRITE_ACTION_TYPES`.
- `apps/dashboard/src/modules/warmup/` owns dashboard warmup UI.

## Planned Stage 1 Backend Structure

- `backend/migrations/versions/YYYYMMDD_XXXX_warmup_channel_state.py`
- `backend/migrations/versions/YYYYMMDD_XXXX_warmup_cold_soak_status.py`
- `backend/migrations/versions/YYYYMMDD_XXXX_warmup_personality_disabled.py`
- `backend/app/model_defs/warmup_channel_state.py`
- `backend/app/modules/warmup/channel_state/__init__.py`
- `backend/app/modules/warmup/channel_state/contracts.py`
- `backend/app/modules/warmup/channel_state/repository.py`
- `backend/app/modules/warmup/channel_state/service.py`
- `backend/app/modules/warmup/channel_state/selector.py`
- `backend/app/modules/warmup/cold_soak.py`
- `backend/app/modules/account_survival/module.py`
- `backend/app/modules/account_survival/repository.py`
- `backend/app/modules/account_survival/queries.py`
- `backend/app/modules/account_survival/events.py`
- `backend/app/modules/account_survival/router.py`
- `backend/app/model_defs/account_survival.py`

## Planned Stages 2-3 Warmup Extensions

- `backend/app/modules/warmup/action_metadata.py`
- `backend/app/modules/warmup/action_presets.py`
- `backend/app/modules/warmup/channel_state/health.py`
- `backend/app/modules/warmup/adaptive_plan.py`
- `backend/app/modules/warmup/typing.py`
- `backend/app/model_defs/warmup_p2p_friend_link.py`
- `backend/app/modules/warmup/p2p/graph.py`
- `backend/app/modules/warmup/p2p/peer_selection.py`

## Planned Stages 4-6 Lifecycle, Realism, Content

- `backend/app/modules/account_lifecycle/state_machine.py`
- `backend/app/modules/account_lifecycle/transitions.py`
- `backend/app/modules/account_lifecycle/idle_detector.py`
- `backend/app/modules/warmup/idle_session.py`
- `backend/app/modules/warmup/pre_production.py`
- `backend/app/modules/warmup/cyclic.py`
- `backend/app/modules/warmup/circadian/__init__.py`
- `backend/app/modules/warmup/circadian/windows.py`
- `backend/app/modules/warmup/circadian/personality.py`
- `backend/app/modules/warmup/proxy_adaptation.py`
- `backend/app/modules/warmup/bootstrap_pool/__init__.py`
- `backend/app/modules/warmup/bootstrap_pool/repository.py`
- `backend/app/modules/warmup/bootstrap_pool/service.py`
- `backend/app/scripts/seed_bootstrap_channels.py`
- `backend/app/modules/account_editing/uniqueness_check.py`
- `backend/app/adapters/ai_profile_provider/__init__.py`
- `backend/app/adapters/ai_profile_provider/contracts.py`
- `backend/app/adapters/ai_profile_provider/fake.py`
- `backend/app/adapters/ai_profile_provider/openai.py`
- `backend/app/modules/account_editing/ai_generation.py`
- `backend/app/modules/account_editing/invite_links.py`

## Planned Stage 7 UI Structure

- `apps/dashboard/src/modules/warmup/components/WarmupAccountSelector.tsx`
- `apps/dashboard/src/modules/warmup/components/WarmupLiveLogs.tsx`
- `apps/dashboard/src/modules/warmup/components/WarmupSessionTimer.tsx`
- `apps/dashboard/src/modules/warmup/components/WarmupSummaryCards.tsx`
- `apps/dashboard/src/modules/warmup/components/WarmupStatusPill.tsx`
- `apps/dashboard/src/modules/warmup/components/WarmupCyclicConfig.tsx`
- `apps/dashboard/src/modules/warmup/components/WarmupCyclicStatus.tsx`
- `apps/dashboard/src/modules/warmup/components/ActionPresetButtons.tsx`
- `apps/dashboard/src/modules/warmup/components/ActionCategoryHeader.tsx`
- `apps/dashboard/src/modules/warmup/labels.ts`
- `apps/dashboard/src/modules/warmup/types.ts`
- `apps/dashboard/src/modules/warmup/api.ts`

## Docs and Operations

- `docs/design/warmup-ux-blueprint.md`
- `docs/design/warmup-divergence-from-gramgpt.md`
- `docs/runbooks/warmup-rollout.md`
- `docs/operator/warmup-advanced.md`
- `infra/grafana/dashboards/warmup-advanced.json`

## Action Type Catalog

| Action type | Category | Class | Dependencies | Traffic |
| --- | --- | --- | --- | --- |
| `feed_read` | base | read | TDLib available | normal |
| `channel_browse` | base | read | `channel_ref`, `channel_state` | normal |
| `view_story` | base | read | `channel_ref`, `has_stories=true` | normal |
| `react_to_post` | base | write | `WRITE_ACTION_TYPES`, safety gate, `has_reactions=true`, profile required | normal |
| `join_chat` | base | write | safety gate, target channel | normal |
| `p2p_send` | base | write | safety gate, trusted/friend peer, text provider | normal |
| `view_dialogs` | reading | read | TDLib chats | normal |
| `scroll_channels` | reading | read | `channel_ref`, subscribed channel | heavy |
| `mark_as_read` | reading | read | TDLib chats | normal |
| `search_messages` | reading | read | query seed | normal |
| `vote_poll` | activity | write | open poll, safety hint for young accounts | normal |
| `watch_video` | activity | read | video message candidate | heavy |
| `listen_voice` | activity | read | voice/audio candidate | heavy |
| `search_gif` | entertainment | read | query seed, animation search | heavy |
| `view_stickers` | entertainment | read | sticker sets/recent stickers | heavy |
| `inline_bot` | entertainment | read | approved popular bot only, no send | heavy |
| `link_preview` | entertainment | read | safe URL pool | heavy |
| `forward_message` | social | write | source message, Saved Messages or friend peer | normal |
| `saved_messages` | social | write-self | Saved Messages chat | normal |
| `sync_contacts` | social | write | contacts pool; skip when pool absent | normal |
| `archive_chat` | groups | write-local | non-protected chat | normal |
| `mute_chat` | groups | write-local | non-protected chat | normal |
| `simulate_typing` | profile/settings | write-ephemeral | chat target | normal |
| `view_profile` | profile/settings | read | contact or recent user | normal |
| `check_settings` | profile/settings | read | TDLib option name | normal |
| `update_profile_gradual` | profile/settings | write | profile safety, uniqueness guard where relevant | normal |
| `emoji_status` | profile/settings | write | Premium capability; skip otherwise | normal |
| `drafts` | profile/settings | write-local | chat target; reversible clear | normal |
| `notification_settings` | profile/settings | write-local | scope notification settings | normal |
| `scheduled_messages` | profile/settings | write-self | Saved Messages; reversible/cancellable | normal |

Action catalog rules:

- Update `SUPPORTED_*_ACTIONS`, `WRITE_ACTION_TYPES`, frontend labels, action metadata, presets, and tests together.
- Write actions must pass safety gates. If an action leaves a public or account-visible trace, classify it as write.
- Traffic-heavy actions are metadata first. Proxy-adaptive behavior consumes metadata later; metadata alone does not disable actions.
- `DRY_RUN` still produces action events and deterministic mock metadata for every action type.

## Lifecycle States

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

- `backend/app/modules/account_lifecycle/state_machine.py` is the only place that mutates lifecycle state.
- `backend/app/modules/warmup/commands.py` requests `imported -> cold_soak` when a new session starts.
- `backend/app/modules/warmup/cold_soak.py` requests `cold_soak -> warming` after the silence window expires.
- `backend/app/modules/warmup/dispatch_results.py` or completion flow requests `warming -> pre_production`.
- `backend/app/modules/warmup/pre_production.py` requests `pre_production -> active` on success or `pre_production -> cold_soak` on flood wait.
- `backend/app/modules/account_lifecycle/idle_detector.py` requests `active -> idle` and idle cleanup requests `idle -> active`.

Every transition writes an audit/lifecycle event. Terminal states are never auto-assigned without the explicit lifecycle rule for that state.

## In-Flight Migration Rules

- Existing `WarmupSession` rows continue with their current status and plan. Do not retroactively move them into `cold_soak`.
- Additive fields use compatibility defaults: `personality_seed_json={}`, `disabled_actions_json=[]`, `lifecycle_state="warming"`, and `cold_soak_until=None`.
- Missing `warmup_channel_state` rows are valid for legacy sessions; selector/context fallbacks must keep old action plans dispatching.
- Missing `strategy_snapshot_json` uses a read-only strategy relationship fallback for that session lifetime.
- Operational rollout steps live in `docs/runbooks/warmup-rollout.md`.
