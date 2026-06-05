---
name: Warmup divergence from GramGPT
description: Intentional Advanced Warmup v1 divergences from the GramGPT reference.
last_updated: 2026-06-05
related:
  - .mex/patterns/warmup-advanced.md
  - docs/design/warmup-ux-blueprint.md
---

# Where StylistTG Diverges From GramGPT

Advanced Warmup v1 follows the GramGPT auto-warm reference for operator workflow and broad feature parity, but not as a blind clone. This document records intentional differences so later issues do not drift back by accident.

Source basis: GramGPT reference screenshots and transcript reviewed in the 2026-06-05 architecture session. This document does not quote private material and does not rely on unsupported external claims about Telegram internals.

## Summary Table

| Aspect | GramGPT reference behavior | StylistTG behavior | Reason |
| --- | --- | --- | --- |
| Reactions | Presented as a normal warmup action | Write action behind safety gate | Public trace needs stricter guard |
| P2P graph | Farm-style engagement can become dense | Sparse friend graph, 2-3 outgoing peers | Avoid uniform all-to-all patterns |
| Channel memory | Action choice mostly target-list driven | Per-account channel state | Prevent repeats and impossible actions |
| Plan | Mostly fixed configured plan | Adaptive plan optional | Respond to flood waits and clean days |
| Cold soak | Operator guidance/reference flow | Formal `cold_soak` state | Enforce silence before activity |
| Strategy changes | Mutable settings can affect later runs | Session strategy snapshot | Protect in-flight sessions |
| Personality | Shared presets dominate behavior | Per-account personality seed | Reduce same-pattern accounts |
| Traffic-heavy actions | Operator toggles | Metadata plus proxy adaptation | Make proxy cost visible and enforceable |
| Logs | UI log stream | Typed `warmup_event` first | Audit, filtering, tests |
| Pre-production | Warmup then production setup | Empty-profile probe before profile setup | Risk exposure before template profile |
| DRY_RUN | Not core to operator flow | First-class end-to-end mode | CI and safe development |
| Safety policy | Reference UI mostly action-centric | Workspace thresholds plus per-account behavior | Separate policy from personality |

### Reactions — write action, not safe-for-all

**What GramGPT does:** The reference treats channel reactions as a selectable warmup action in the same action catalog as read-like activity. Source: GramGPT action tooltip area in the 2026-06-05 reference packet.

**What StylistTG does:** `react_to_post` is classified as write and must be added to `WRITE_ACTION_TYPES` in `backend/app/adapters/warmup_tdlib_contracts.py`. It also requires safety gate, channel capability discovery, and profile readiness.

**Rationale:** A reaction leaves account-visible activity. Treating it as write keeps public traces behind the same safety posture as joins and p2p sends.

**Условие пересмотра:** Reconsider only if production metrics show reactions have read-like risk and write gating materially prevents successful warmup without improving survival.

### P2P — sparse friend graph, not dense farm graph

**What GramGPT does:** The reference emphasizes p2p-style trust activity between accounts. Source: GramGPT p2p/trust action area in the 2026-06-05 reference packet.

**What StylistTG does:** #369 creates a sparse directed friend graph: each account gets about 2-3 outgoing friends, with about half of links reciprocal when peer degree allows.

**Rationale:** Dense all-to-all engagement is too uniform. A sparse graph is easier to audit, test, and reason about.

**Условие пересмотра:** Reconsider if sparse graph leaves too few eligible p2p actions and survival metrics do not improve versus simpler peer selection.

### Channel State — remember channel history per account

**What GramGPT does:** The reference centers target channel selection and action toggles. Source: target/action setup screens in the 2026-06-05 reference packet.

**What StylistTG does:** #355 introduces `warmup_channel_state` and #359 makes selector use it to know subscription, stories, reactions, last action times, and failures.

**Rationale:** Without per-account channel memory, the system can retry joins, react where reactions are unavailable, or overuse the same channel.

**Условие пересмотра:** Reconsider only if channel state creates operational cost without reducing skips, failures, or repeated actions.

### Adaptive Plan — optional runtime adjustment

**What GramGPT does:** The reference flow presents a configured warmup plan and duration. Source: schedule/intensity controls in the 2026-06-05 reference packet.

**What StylistTG does:** #373 adds optional adaptive multipliers that slow down on recent failures or flood waits and speed up after clean days.

**Rationale:** A fixed plan cannot react to account condition. Adaptation lets the system preserve safety while still moving healthy accounts forward.

**Условие пересмотра:** Reconsider if adaptive plan increases variance without improving completion rate, flood-wait rate, or survival.

### Cold Soak — formal lifecycle state

**What GramGPT does:** The reference uses a warmup flow that implies waiting and gradual ramp-up. Source: duration and safety setup in the 2026-06-05 reference packet.

**What StylistTG does:** #356 adds `cold_soak` as a real warmup status with `cold_soak_until`, skip events, and automatic transition after 12-24 hours.

**Rationale:** Silence after import should be enforceable, observable, and testable, not only remembered by operators.

**Условие пересмотра:** Reconsider only if cold-soak creates unacceptable operator delay and survival metrics show no benefit.

### Strategy Snapshot — freeze session inputs

**What GramGPT does:** The reference is settings-driven from the current UI plan. Source: warmup settings flow in the 2026-06-05 reference packet.

**What StylistTG does:** #354/#360 introduce session snapshot behavior. New sessions copy action limits, windows, targets, and related strategy values into `WarmupSession.strategy_snapshot_json`.

**Rationale:** Operators can edit strategies while sessions run. In-flight sessions need stable inputs for reproducibility and safe rollback.

**Условие пересмотра:** Reconsider only if product requirements demand live strategy edits for active sessions, with explicit versioning and audit.

### Personality Seed — per-account behavioral variance

**What GramGPT does:** The reference exposes presets and action toggles. Source: intensity and action configuration screens in the 2026-06-05 reference packet.

**What StylistTG does:** #379 generates deterministic per-account personality: preferred hours, typing speed, favorite reactions, action preferences, and session-length bias.

**Rationale:** Shared presets alone make many accounts behave too similarly. Personality keeps behavior deterministic for tests while varying accounts.

**Условие пересмотра:** Reconsider if personality makes support/debug harder and does not improve survival or reduce repeated behavior patterns.

### Traffic Metadata — explicit proxy cost signal

**What GramGPT does:** The reference groups actions and exposes toggles. Source: fine-tuning action catalog in the 2026-06-05 reference packet.

**What StylistTG does:** #368 adds traffic-heavy metadata and #380 consumes it for proxy-adaptive presets.

**Rationale:** Video, voice, GIF, stickers, and inline previews can consume proxy traffic. Operators need the signal before automation disables or enables them.

**Условие пересмотра:** Reconsider if measured traffic impact is negligible or if proxy providers change pricing/limits enough that the tag loses value.

### Event Log First — typed backend events before UI strings

**What GramGPT does:** The reference has operator-facing logs. Source: launch/log screen in the 2026-06-05 reference packet.

**What StylistTG does:** Warmup records typed `warmup_event` rows through `write_warmup_event`; UI logs render from structured events and severity.

**Rationale:** Typed events enable tests, filters, audit, migration checks, and later metrics without scraping UI text.

**Условие пересмотра:** Reconsider only if event volume becomes a storage problem that cannot be solved by retention or pagination.

### Pre-production — empty-profile probe

**What GramGPT does:** The reference aims to prepare accounts for later work through warmup actions. Source: warmup launch flow in the 2026-06-05 reference packet.

**What StylistTG does:** #376 adds a short pre-production run with an intentionally empty profile before profile setup and production work.

**Rationale:** If the account hits a risk signal during early production-like behavior, a blank profile exposes less repeated template data.

**Условие пересмотра:** Reconsider if empty-profile probes reduce activation success or if operators need profile setup before any production-like test.

### DRY_RUN — first-class execution mode

**What GramGPT does:** The reference is operator-facing, with emphasis on running warmup. Source: launch and action setup screens in the 2026-06-05 reference packet.

**What StylistTG does:** DRY_RUN and mock TDLib remain first-class. Every action must run through mock parity and emit deterministic metadata.

**Rationale:** This project needs CI coverage, no-live-TDLib verification, and safe agent development across many issues.

**Условие пересмотра:** Reconsider only for a separate live-validation environment, never for unit/integration CI.

### Workspace Safety Policy — thresholds, not behavior personality

**What GramGPT does:** The reference appears action/preset oriented. Source: settings and safety control areas in the 2026-06-05 reference packet.

**What StylistTG does:** #396 re-enables workspace safety policy as protective thresholds while behavior shape moves to per-account personality.

**Rationale:** Policy answers what is allowed; personality answers how an account behaves. Mixing them makes both harder to reason about.

**Условие пересмотра:** Reconsider if operators need workspace-wide behavior defaults that cannot be represented as personality templates.
