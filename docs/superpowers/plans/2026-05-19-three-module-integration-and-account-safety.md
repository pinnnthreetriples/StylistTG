# StylistTG: интеграция модулей `account-editing` + `warmup` + `neuro-commenting` + слой Account Safety (паритет с GramGPT)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (рекомендовано) или `superpowers:executing-plans`. Шаги — чекбоксы `- [ ]`. Все Task'и пронумерованы; внутренние ссылки идут по номеру задачи (например, `Task 11`).

**Версия:** 2.0 (объединяет три предыдущих итерации обсуждения).
**Дата:** 2026-05-19.
**Авторы:** StylistTG core team, аналог feature-set GramGPT (`gramgpt.io`).

---

## Содержание

1. [Goal, scope, non-goals](#1-goal-scope-non-goals)
2. [Контекст: что копируем у GramGPT](#2-контекст-что-копируем-у-gramgpt)
3. [Architecture overview](#3-architecture-overview)
4. [File structure](#4-file-structure)
5. [Phase 0 — MVP-блокеры](#5-phase-0--mvp-блокеры)
6. [Phase 1 — Glue между модулями](#6-phase-1--glue-между-модулями)
7. [Phase 2 — Account Safety Pipeline (центральный слой)](#7-phase-2--account-safety-pipeline-центральный-слой)
8. [Phase 2.5 — Production Hardening](#8-phase-25--production-hardening)
9. [Phase 3 — End-to-end verification & documentation](#9-phase-3--end-to-end-verification--documentation)
10. [Verification gates](#10-verification-gates)
11. [Risks & mitigations](#11-risks--mitigations)
12. [Out of scope](#12-out-of-scope)
13. [Effort estimate](#13-effort-estimate)

---

## 1. Goal, scope, non-goals

### 1.1 Goal
Привести три модуля (`account-editing`, `warmup`, `neuro-commenting`) к production-ready состоянию, объединить их через **Account Safety Pipeline** уровня GramGPT с шестью защитными слоями:

1. Workspace-level Safety Policy (conservative / balanced / aggressive).
2. GGR (GramGPT-Rating-equivalent): композитный 1.0–10.0 скоринг живучести аккаунта.
3. Account Safety Gate: per-intent verdict (editing / warmup / commenting).
4. Human Behavior Emulator: реалистичная имитация (typing speed, опечатки, view профилей, scroll, удаление, рандомизация порядка).
5. Quarantine engine: жёсткий 24h-карантин при FloodWait + recovery flow.
6. Account Status Monitor + Cross-Module Load Tracker (фоновое наблюдение, auto-pause).

### 1.2 Scope
- 3 backend модуля (`account-editing`, `warmup`, `neuro-commenting`).
- 6 новых сервисов safety pipeline.
- 11 новых миграций (`0033`–`0043`).
- Wizard-based UI для `neuro-commenting` (паритет UX с warmup).
- Production hardening: idempotency, observability, feature-flags, performance SLO.

### 1.3 Non-goals (явно отрезаны, оформляются отдельными спеками)
- Semantic match через pgvector / embeddings.
- A/B тестирование промптов.
- DM lead-handoff (модуль `neuro-chatting`).
- Channel discovery / TG keyword search.
- Replacement timer (двушаговая отправка эмодзи→текст).
- View boosting / реакции на пост.
- Public API + webhooks для внешних интеграций.
- AI cost tracking (тоже отдельный спек).
- Workspace plan limits (Free/Pro/Enterprise — billing-задача).
- i18n английский интерфейс.
- GDPR-аудит (compliance, не код).

### 1.4 Tech stack
FastAPI, Pydantic v2, SQLAlchemy, Alembic, PostgreSQL, Redis (RQ + rate limiter + cache), TDLib, React 18, Vitest, pytest, Hypothesis, Prometheus client.

---

## 2. Контекст: что копируем у GramGPT

GramGPT safety — **отдельный модуль**, который работает параллельно с автоматизацией (нейрокомментинг, нейрочаттинг, парсинг, реакции, рассылки). Его задача — снижать риск SpamBlock, заморозки, бана, ограничений.

### 2.1 Три режима AI-защиты с точными параметрами

| Параметр | Conservative | Balanced | Aggressive |
|---|---|---|---|
| Delay multiplier | x1.5 | x1.0 | x0.7 |
| Typing speed (chars/min) | 40–60 | 100–150 | disabled |
| Profile view probability | 0.90 | 0.70 | 0.30 |
| Scroll probability | 0.50 | 0.30 | 0.00 |
| Typo probability | 0.08 | 0.05 | 0.02 |
| Message deletion probability | 0.03 | 0.02 | 0.01 |
| Sleep window (local time) | 01:00–07:00 | 02:00–06:00 | none |
| Require warmup before commenting | required | required | optional |
| Min warmup days | 7 | 3 | 1 |
| Min account age (hours) | 72 | 24 | 0 |
| Auto-pause on FloodWait streak | ≥1 | ≥3 | ≥5 |
| Auto-pause on deleted-comments streak | ≥2 | ≥5 | ≥10 |

### 2.2 GGR (GramGPT Rating)
Композитный скоринг 1.0–10.0:
- **7.0–10.0** — сильный аккаунт, любые задачи.
- **4.0–6.99** — средний, только аккуратный прогрев / низкая нагрузка.
- **1.0–3.99** — высокий риск, BLOCKED для commenting.

Входные сигналы:
- account_age_hours;
- account_origin (imported / bought / created);
- spamblock_history_count;
- recent_flood_wait_count_30d;
- proxy_quality_score (sticky / rotating / datacenter / residential / mobile);
- fingerprint_stability (изменялся ли device_model);
- ip_change_frequency_24h;
- session_anomalies_count_7d;
- warmup_completion_score (если есть);
- profile_completeness (0..1).

### 2.3 Жёсткий 24h-карантин при FloodWait
Любой FloodWait → авто-карантин 24h независимо от длительности самого FW (короткий FW = ранний сигнал риска; если продолжать давить, ограничение растёт).

### 2.4 Стабильность сессий и прокси
GramGPT-причины разлогина:
- одна сессия с разных IP;
- резкая смена прокси без sticky-IP;
- ротационные прокси;
- параллельные действия с одного аккаунта;
- некачественные tdata;
- подозрительные device_model;
- активные действия сразу после смены IP.

Принцип: **одна сессия — одно стабильное окружение — один стабильный IP**.

### 2.5 Купленные аккаунты
Recovery flow:
- включить 2FA (cloud password);
- авторизация на новом устройстве;
- через 24h terminate other sessions;
- 5–7 дней rest period (карантин);
- GGR pre-check перед выпуском.

### 2.6 Age-based progression
- 0–7 дней → forced conservative.
- 7–30 дней → balanced default; aggressive с явным warning.
- 30+ дней → любой preset.

---

## 3. Architecture overview

### 3.1 Six-layer safety pipeline

```
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: WorkspaceSafetyPolicy (mode + thresholds, per workspace)     │
└──────────────────┬─────────────────────────────────────────────────────┘
                   │ provides defaults
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: GGR Calculator (account-level composite score, 1.0..10.0)    │
│  recalculated every 6h + on-demand triggers                            │
└──────────────────┬─────────────────────────────────────────────────────┘
                   │ feeds verdict
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: AccountSafetyGate.evaluate(account_id, intent)               │
│  Inputs: GGR, proxy_check, warmup_state, quarantine, profile_complete, │
│          cross-module load, status snapshot, fraud_score               │
│  Output: SafetyGateVerdict(eligible, severity, reasons[])              │
└──────────────────┬─────────────────────────────────────────────────────┘
                   │ used by all three modules + sender preflight
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: HumanBehaviorEmulator                                        │
│  Wraps every TDLib action with typing/scroll/view/typo/delete sim      │
│  Uses per-account stable BehaviorProfile baseline                      │
└──────────────────┬─────────────────────────────────────────────────────┘
                   │ executes
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 5: Quarantine Engine                                            │
│  Hard 24h on any FloodWait; manual release endpoint                    │
│  Integrates with TerminalStatus enum (banned/restricted/frozen/deleted)│
└──────────────────┬─────────────────────────────────────────────────────┘
                   │ feeds back into gate as BLOCKED
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 6: AccountStatusMonitor + CrossModuleLoadTracker                │
│  Periodic scan, IP-change detector, sticky-IP enforcement,             │
│  auto-pause on degraded signals, total load aggregation                │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Account lifecycle

```
imported
   │
   ▼
bought-account-flow (if origin=bought)
   ├── enable_2fa
   ├── terminate_other_sessions (T+24h)
   └── rest_period (5-7d, quarantined)
   │
   ▼
profile_completeness (account-editing module sets name/bio/photo/pinned_channel)
   │
   ▼
warmup (mandatory unless aggressive mode)
   │
   ▼
ggr_calculator (must be ≥ 4.0 for any commenting)
   │
   ▼
neuro_commenting eligible
   │
   ▼
status_monitor watches → degraded → cooldown / quarantine → recovery (manual)
```

### 3.3 Каждый sender preflight = gate-check
Даже свежий cached verdict (≤60s) **перепроверяется атомарно через Redis Lua** перед каждой отправкой. Fail-closed.

---

## 4. File structure

### 4.1 Новые backend файлы

```
backend/app/services/
  workspace_safety_policy.py
  account_safety_gate.py
  account_status_monitor.py
  ggr_calculator.py
  account_quarantine.py
  account_profile_completeness.py
  cross_module_load_tracker.py
  human_behavior/
    __init__.py
    behavior_profile.py
    typing_emulator.py
    action_sequencer.py
    typo_generator.py
    decoy_actions.py
  neuro_commenting/
    approval_expirer.py
    prompt_presets.py
    behavior_aware_sender.py     # wraps tdlib_comment_sender with emulator
  bought_account_onboarding.py
  reconcile_stuck_attempts.py

backend/app/api/
  safety_policy.py
  account_safety_routes.py        # GGR, quarantine, gate verdict endpoints
  human_behavior_routes.py        # behavior profile read/update (admin only)

backend/app/contracts/
  safety_gate.py
  ggr.py
  human_behavior.py
  quarantine.py

backend/migrations/versions/
  20260520_0033_workspace_safety_policy.py
  20260520_0034_account_status_observations.py
  20260520_0035_pinned_channel_step.py
  20260520_0036_ggr_scores.py
  20260520_0037_account_quarantine.py
  20260520_0038_account_behavior_profile.py
  20260520_0039_account_terminal_status.py
  20260520_0040_cross_module_load_buckets.py
  20260520_0041_rate_limit_persistent_counters.py
  20260520_0042_attempt_idempotency_keys.py
  20260520_0043_safety_pipeline_feature_flags.py

backend/tests/
  test_account_safety_gate.py
  test_workspace_safety_policy.py
  test_account_status_monitor.py
  test_ggr_calculator.py
  test_account_quarantine.py
  test_account_profile_completeness.py
  test_cross_module_load_tracker.py
  test_bought_account_onboarding.py
  test_human_behavior_emulator.py
  test_human_behavior_property.py   # Hypothesis-based
  test_attempt_idempotency.py
  test_reconcile_stuck_attempts.py
  integration/
    test_three_module_pipeline.py
    test_safety_pipeline_e2e.py
  _fakes/
    fake_tdlib_runtime.py
    fake_proxy_checker.py
```

### 4.2 Новые frontend файлы

```
apps/dashboard/src/
  modules/shared/
    safetyGate.ts
    SafetyGateBanner.tsx
    GGRBadge.tsx
    QuarantineStateBanner.tsx
  modules/neuro-commenting/components/
    CampaignWizard.tsx
    ApprovalInbox.tsx
    SafetyPresetSelector.tsx
    PromptPresetDropdown.tsx
    BulkTargetsImporter.tsx
  modules/account-editing/components/
    BoughtAccountOnboardingWizard.tsx
    PinnedChannelField.tsx
  features/settings/
    SafetyPolicyPanel.tsx
    BehaviorProfileViewer.tsx
  routes/
    NeuroCommentingCampaignsRoute.tsx
    NeuroCommentingCampaignDetailRoute.tsx
    NeuroCommentingApprovalRoute.tsx
    NeuroCommentingAnalyticsRoute.tsx
    AccountSafetyRoute.tsx
```

### 4.3 Модифицируемые файлы
- `backend/app/contracts/neuro_commenting.py` — удалить shelfware enums, добавить `safety_preset`, `pinned_channel_ref`, `prompt_preset_id`.
- `backend/app/api/neuro_commenting.py` — bulk-targets, prompt-presets endpoint, hide shelfware.
- `backend/app/services/neuro_commenting/live_readiness_service.py` — интеграция gate.
- `backend/app/services/neuro_commenting/sender_service.py` → переименовать в `behavior_aware_sender.py`; preflight всегда повторяет gate-check.
- `backend/app/services/warmup_readiness.py` — gate + proxy + GGR + quarantine checks.
- `backend/app/services/warmup_dispatch.py` — gate preflight; новые action types через emulator.
- `backend/app/services/step_registry.py` — регистрация `set_pinned_channel`, `enable_2fa`, `terminate_other_sessions`.
- `backend/app/api/account_update.py` — preview интегрирует gate(intent=editing).
- `backend/app/services/scheduler.py` — джобы tick-функций (status monitor, ggr recalc, approval expirer, reconcile stuck).
- `backend/app/config.py` — ENV-валидация AI provider, новые тумблеры + feature flag.
- `backend/app/services/tenant_scope.py` — добавить scope для всех новых таблиц.
- `apps/dashboard/src/modules/neuro-commenting/NeuroCommentingPage.tsx` — стать layout с `<Outlet />`.
- `apps/dashboard/src/routes/NeuroCommentingRoute.tsx` — child routes.
- `apps/dashboard/src/routes/SettingsRoute.tsx` — добавить SafetyPolicyPanel.
- `apps/dashboard/src/modules/account-editing/types.ts` — расширить `FormPayload` (`pinnedChannelRef`).

---

## 5. Phase 0 — MVP-блокеры

**Goal:** убрать contract shelfware, поднять минимальный E2E pipeline, разбить перегруженный UI.
**Duration:** 1 sprint.

### Task 1: Удалить enum-shelfware

**Files:**
- Modify: `backend/app/contracts/neuro_commenting.py`
- Modify: `backend/app/api/neuro_commenting.py`
- Test: `backend/tests/test_neuro_commenting_config.py`

- [ ] **1.1** Удалить или пометить deprecated с возвратом 422 (`feature_not_available`):
  - `NeuroCampaignMode.SEMANTIC_MATCH`
  - `NeuroWorkMode.SCHEDULED`
  - `NeuroSendStrategy.EMOJI_THEN_EDIT`
  - `NeuroSendMode.AUTO`
  - `ChannelRuleType.auto_blacklist_suggested|auto_whitelist_suggested`
- [ ] **1.2** Сохранить значения в Python enum (для будущего), но `Create`/`Update` validators отвергают.
- [ ] **1.3** Тесты: каждое shelfware значение → 422 с `error_code=feature_not_available`.
- [ ] **1.4** Регенерировать `packages/api-client` OpenAPI клиент.

### Task 2: ENV-валидация AI provider в production

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_neuro_commenting_config.py`

- [ ] **2.1** `@model_validator(mode="after")` в `Settings`:
  ```python
  if self.environment == "production" and self.neuro_comment_ai_provider == "fake":
      raise ValueError("neuro_comment_ai_provider=fake запрещён в production")
  ```
- [ ] **2.2** Тест: env=production + provider=fake → ValueError.

### Task 3: Approval expirer worker

**Files:**
- New: `backend/app/services/neuro_commenting/approval_expirer.py`
- Modify: `backend/app/services/scheduler.py`
- Test: `backend/tests/test_neuro_commenting_approval_expirer.py`

- [ ] **3.1** `expire_stale_approvals(now, ttl_seconds)`: PENDING + `created_at < now - ttl` → EXPIRED + `NeuroCommentEvent(event_type='approval_expired', event_level='warning')`.
- [ ] **3.2** Регистрация в scheduler с интервалом 15 минут.
- [ ] **3.3** Config `neuro_comment_approval_ttl_seconds` (default 14400).
- [ ] **3.4** Тест: pending старше TTL → expired; моложе → не тронуты.

### Task 4: Split UI на роуты + Wizard

**Files:**
- Refactor: `apps/dashboard/src/modules/neuro-commenting/NeuroCommentingPage.tsx` → layout
- New: 4 route файла + `CampaignWizard.tsx` + `ApprovalInbox.tsx`
- Test: `apps/dashboard/src/modules/neuro-commenting/neuroCommentingRoute.test.tsx`

- [ ] **4.1** Wizard шаги: (1) Аккаунты с фильтром «прогретые + GGR ≥ 4», (2) Каналы (bulk + single), (3) Промпт+режим, (4) Лимиты+SafetyPreset, (5) Подтверждение + inline live-readiness.
- [ ] **4.2** ApprovalInbox: keyboard shortcuts (`a`=approve, `r`=reject, `e`=edit, `j`/`k`=navigate, `s`=skip).
- [ ] **4.3** AnalyticsRoute собирает все stats секции.
- [ ] **4.4** Переиспользовать существующие компоненты (`CampaignListSection`, `GeneratedCommentsSection`).
- [ ] **4.5** Vitest smoke-tests на каждый роут.

### Task 5: E2E smoke pipeline-тест + fake TDLib

**Files:**
- New: `backend/tests/_fakes/fake_tdlib_runtime.py`
- New: `backend/tests/integration/test_three_module_pipeline.py`
- Config: переключатель `TDLIB_RUNTIME_PROVIDER=fake`

- [ ] **5.1** `FakeTdlibRuntime`: контракт совместим с production TDLib runtime; in-memory chats/messages, configurable error injection (FloodWait, NetworkError, AuthError).
- [ ] **5.2** Сценарий: workspace → 1 импорт аккаунта → profile editing (dry_run) → warmup dry_run → completion → создание campaign → observe (fake post) → generate → approve → send (dry_run) → assert `attempt.status=SENT`.
- [ ] **5.3** Команда:
  ```powershell
  cd backend
  python -m pytest tests/integration/test_three_module_pipeline.py -q -s
  ```

---

## 6. Phase 1 — Glue между модулями

**Goal:** связать модули через общие операции и пресеты, реализовать pinned-channel, bulk-targets, prompt presets.
**Duration:** 1–2 sprints.

### Task 6: Pinned channel операция в `account-editing`

**Files:**
- Modify: `backend/app/services/step_registry.py`, `backend/app/api/account_update.py`
- Migration: `20260520_0035_pinned_channel_step.py` (колонка `accounts.pinned_channel_ref` nullable text)
- Modify: `apps/dashboard/src/modules/account-editing/types.ts`
- New UI: `PinnedChannelField.tsx`
- Test: `backend/tests/test_account_update_pinned_channel.py`

- [ ] **6.1** Step `set_pinned_channel` с payload `{channel_ref}`, idempotency_class `account_profile`.
- [ ] **6.2** TDLib вызов `setPersonalChat` (через `tdlib_client`).
- [ ] **6.3** `FormPayload.pinnedChannelRef`, `ChangeItem.operation += 'set_pinned_channel'`.
- [ ] **6.4** Preview validation: канал должен принадлежать workspace или быть public; запрет на cross-workspace ref.
- [ ] **6.5** Тест: cross-workspace ref → preview blocking_error.

### Task 7: Bulk-import targets

**Files:**
- Modify: `backend/app/api/neuro_commenting.py`, `backend/app/contracts/neuro_commenting.py`
- New UI: `BulkTargetsImporter.tsx`
- Test: `backend/tests/test_neuro_commenting_bulk_targets.py`

- [ ] **7.1** `POST /api/neuro-commenting/campaigns/{id}/targets:bulk` — body `{items: [{channel_ref, keywords?, exclude_keywords?}]}`, max 200 items.
- [ ] **7.2** Response `{created: [...], skipped: [{channel_ref, reason}]}` с reasons: `duplicate`, `blacklisted_workspace`, `invalid_ref`, `limit_exceeded`.
- [ ] **7.3** UI textarea: 1 channel per line, валидация в реальном времени.
- [ ] **7.4** Тест: дубль внутри батча skipped с `duplicate`; валидная запись добавлена.

### Task 8: Prompt presets

**Files:**
- New: `backend/app/services/neuro_commenting/prompt_presets.py`
- Modify: `backend/app/api/neuro_commenting.py` (`GET /prompt-presets`)
- Migration: добавить `prompt_preset_id` (nullable FK) в `neuro_comment_campaigns` (в `0033` или новой).
- New UI: `PromptPresetDropdown.tsx`
- Test: `backend/tests/test_neuro_commenting_prompt_presets.py`

- [ ] **8.1** 5 пресетов в коде: `short_native_ru`, `expert_opinion_ru`, `question_to_author_ru`, `emoji_reaction_ru`, `short_native_en`.
- [ ] **8.2** UI: при выборе подставляет в textarea, можно редактировать.
- [ ] **8.3** Hash самой текущей версии promptа → `prompt_version` (уже есть в БД).

### Task 9: Safety preset на campaign + автопресеты лимитов

**Files:**
- Modify: `backend/app/contracts/neuro_commenting.py`, campaign service
- Test: расширить `test_neuro_commenting_runtime_api.py`

- [ ] **9.1** Поле `safety_preset: Literal["conservative","balanced","aggressive"]`, default `balanced`.
- [ ] **9.2** При старте кампании без существующих лимитов — авто-создать набор по таблице:
  | preset | per_hour | per_day | min_delay_s | max_parallel |
  |---|---|---|---|---|
  | conservative | 3 | 20 | 600 | 1 |
  | balanced | 8 | 50 | 180 | 2 |
  | aggressive | 20 | 150 | 60 | 4 |
- [ ] **9.3** **Age-based forced mode** (вместо multiplier):
  - account_age < 7d → forced `conservative` (UI блокирует выбор других).
  - account_age 7–30d → default `balanced`; `aggressive` доступен с warning баннером.
  - account_age ≥ 30d → любой preset.
- [ ] **9.4** Тест: попытка установить `aggressive` для аккаунта 5d → 422 с `error_code=age_forces_conservative`.

---

## 7. Phase 2 — Account Safety Pipeline (центральный слой)

**Goal:** шесть слоёв safety pipeline.
**Duration:** 3–4 sprints (самый плотный кусок).

### Task 10: WorkspaceSafetyPolicy

**Files:**
- New: `backend/app/models.py` → `class WorkspaceSafetyPolicy(Base)`
- New: `backend/app/services/workspace_safety_policy.py`, `backend/app/api/safety_policy.py`, `backend/app/contracts/safety_gate.py`
- Migration: `20260520_0033_workspace_safety_policy.py`
- New UI: `SafetyPolicyPanel.tsx` (в SettingsRoute)
- Test: `backend/tests/test_workspace_safety_policy.py`

- [ ] **10.1** Таблица `workspace_safety_policy`:
  - PK `id`, FK `workspace_id` (unique);
  - `mode` (`conservative|balanced|aggressive`);
  - `require_warmup_before_commenting` (bool);
  - `min_warmup_days` (int);
  - `require_healthy_proxy` (bool);
  - `min_account_age_hours` (int);
  - `auto_pause_on_flood_wait_count` (int);
  - `auto_pause_on_deleted_comments_count` (int);
  - **Behavioral params (Section 2.1):** `delay_multiplier` (float), `typing_chars_per_minute_min/max` (int), `profile_view_probability` (float), `scroll_probability` (float), `typo_probability` (float), `message_deletion_probability` (float), `quiet_hours_local_start/end` (int);
  - `quarantine_hours_on_flood_wait` (int, default 24);
  - `created_at`, `updated_at`.
- [ ] **10.2** Endpoints:
  - `GET /api/safety-policy` (lazy-create default=balanced если нет).
  - `PATCH /api/safety-policy` (admin only; sensitive_audit лог).
- [ ] **10.3** Пресеты применяют defaults по таблице из Section 2.1.
- [ ] **10.4** UI: `SafetyPolicyPanel` с режимом + раскрытый список параметров (read-only для не-admin).
- [ ] **10.5** Тест: PATCH mode=conservative → defaults применены; non-admin → 403; sensitive_audit запись создана.

### Task 11: GGR Calculator

**Files:**
- New: `backend/app/services/ggr_calculator.py`, `backend/app/contracts/ggr.py`
- Migration: `20260520_0036_ggr_scores.py`
- New UI: `GGRBadge.tsx` (в AccountsTable, NeuroCommenting wizard)
- Test: `backend/tests/test_ggr_calculator.py`

- [ ] **11.1** Таблица `account_ggr_scores`:
  - PK `id`, FK `workspace_id`, FK `account_id` (unique);
  - `score` (numeric(3,1), 1.0–10.0);
  - `bucket` (`strong|medium|weak`);
  - `breakdown_json` (jsonb: age_score, origin_score, history_score, proxy_score, fingerprint_score, ip_change_score, session_anomaly_score, warmup_score, profile_score);
  - `last_calculated_at`, `next_calculation_at`.
- [ ] **11.2** Algorithm (weighted average 0..1 → scaled to 1..10):
  ```
  weights = {age: 0.20, origin: 0.10, history: 0.15, proxy: 0.15,
             fingerprint: 0.10, ip_change: 0.10, session_anomaly: 0.10,
             warmup: 0.05, profile: 0.05}
  total = sum(weights[k] * components[k])  # 0..1
  score = round(1.0 + 9.0 * total, 1)
  bucket = 'strong' if score >= 7 else 'medium' if score >= 4 else 'weak'
  ```
- [ ] **11.3** Tick-функция: пересчёт раз в 6h + on-demand триггеры (post-warmup, post-flood_wait, post-proxy-change).
- [ ] **11.4** Endpoint `GET /api/accounts/{id}/ggr` → `{score, bucket, breakdown, last_calculated_at}`.
- [ ] **11.5** Тесты: каждый component scoring isolated; total computation; bucket boundaries; backfill для existing accounts (default score=5.0, bucket=medium, force-recalc сразу).

### Task 12: AccountQuarantine engine

**Files:**
- New: `backend/app/services/account_quarantine.py`
- Migration: `20260520_0037_account_quarantine.py`
- New UI: `QuarantineStateBanner.tsx`, endpoint в AccountSafetyRoute
- Test: `backend/tests/test_account_quarantine.py`

- [ ] **12.1** Таблица `account_quarantines`:
  - PK `id`, FK `workspace_id`, FK `account_id`;
  - `reason` (`flood_wait|status_degraded|manual|bought_rest_period|fraud_high`);
  - `started_at`, `until` (timestamp);
  - `released_at` (nullable), `released_by_user_id` (nullable);
  - `metadata_json` (jsonb: original flood_wait_seconds, source_attempt_id, etc.);
  - Index `(workspace_id, account_id, until)`.
- [ ] **12.2** API:
  - `GET /api/accounts/{id}/quarantine` → текущий активный или null.
  - `POST /api/accounts/{id}/quarantine/release` (admin only, требует `reason` text) → sensitive_audit.
- [ ] **12.3** Trigger handler: при `attempt.status=FLOOD_WAIT` → создать quarantine с `until=now+quarantine_hours_on_flood_wait*3600`.
- [ ] **12.4** Gate hard-block если активный quarantine.
- [ ] **12.5** Тест: FloodWait 60s → quarantine 24h; manual release → released_at + audit.

### Task 13: AccountSafetyGate (центральный сервис)

**Files:**
- New: `backend/app/services/account_safety_gate.py`
- New: `backend/app/contracts/safety_gate.py`
- New: `backend/app/api/account_safety_routes.py`
- New UI: `SafetyGateBanner.tsx`
- Test: `backend/tests/test_account_safety_gate.py`

- [ ] **13.1** Contracts:
  ```python
  class SafetyGateReason(BaseModel):
      code: Literal[
          "proxy_unhealthy", "no_warmup", "warmup_incomplete",
          "age_too_low", "flood_wait_streak", "fraud_score_high",
          "ggr_too_low", "status_degraded", "profile_incomplete",
          "active_quarantine", "cross_module_overload",
          "terminal_status", "ip_change_cooldown"
      ]
      severity: Literal["warning", "blocked"]
      message: str
      metadata: dict

  class SafetyGateVerdict(BaseModel):
      account_id: UUID
      intent: Literal["editing", "warmup", "commenting"]
      eligible: bool
      severity: Literal["ok", "warning", "blocked"]
      reasons: list[SafetyGateReason]
      ggr_score: float | None
      checked_at: datetime
      cache_ttl_seconds: int
  ```
- [ ] **13.2** Чек-листы per intent:
  - **commenting**: proxy_healthy (policy-aware), warmup_completed (policy-aware), age ≥ min, GGR ≥ 4.0, fraud_score < 0.7, recent_flood_waits < auto_pause_count, profile_completeness ≥ 0.8, no_active_quarantine, no_terminal_status, no_ip_change_cooldown, cross_module_load_under_threshold.
  - **warmup**: proxy_healthy, no_active_quarantine, no_terminal_status, no_warmup_isolation_conflict.
  - **editing**: proxy_check != failed (warning ok), no_critical_status, no_terminal_status.
- [ ] **13.3** Кеш в Redis 60s, ключ `safety:gate:{account_id}:{intent}:{policy_version}`. Policy version меняется при PATCH /safety-policy.
- [ ] **13.4** Endpoint `GET /api/accounts/{id}/safety-gate?intent=...` (lazy compute если кеш пуст).
- [ ] **13.5** **Атомарность для sender preflight (Task 27)** — не просто read-cache, а Lua-скрипт reserve+verdict.
- [ ] **13.6** Тесты: 12 кейсов (по reason_code × intent), кеш-hit/miss, тенант изоляция.

### Task 14: HumanBehaviorEmulator + BehaviorProfile

**Files:**
- New: `backend/app/services/human_behavior/` (5 файлов: behavior_profile, typing_emulator, action_sequencer, typo_generator, decoy_actions)
- Migration: `20260520_0038_account_behavior_profile.py`
- Modify: `tdlib_comment_sender` → `behavior_aware_sender`
- Modify: `warmup_dispatch.py` (новые action types через emulator)
- New UI: `BehaviorProfileViewer.tsx` (admin only, in SettingsRoute)
- Test: `backend/tests/test_human_behavior_emulator.py`, `backend/tests/test_human_behavior_property.py` (Hypothesis)

- [ ] **14.1** Таблица `account_behavior_profile` (per-account stable baseline):
  - PK `id`, FK `workspace_id`, FK `account_id` (unique);
  - `typing_speed_baseline_cpm` (int): рандом из preset range при первом use, потом стабильный per-account;
  - `typo_rate_baseline` (float);
  - `profile_view_probability_baseline` (float);
  - `scroll_probability_baseline` (float);
  - `message_deletion_probability_baseline` (float);
  - `action_sequence_seed` (int): сид для шафла последовательности действий;
  - `last_randomization_at`, `created_at`, `updated_at`.
- [ ] **14.2** Per-session randomization: всегда `baseline ± 10%`, чтобы выглядеть живым, но **узнаваемым**.
- [ ] **14.3** `TypingEmulator.emit_typing(account, text)`:
  - вычислить duration: `len(text) / (cpm/60)` секунд;
  - разбить на 5–15 фрагментов с микропаузами;
  - вызвать TDLib `sendChatAction(typing)` периодически.
- [ ] **14.4** `TypoGenerator.maybe_typo(text, probability)`: с вероятностью `p` вставляет typo, шлёт первый вариант, ждёт 200–800ms, шлёт edit с правильным текстом.
- [ ] **14.5** `DecoyActions.run_before_send(account)`: с вероятностью `profile_view_probability` сделать `getUser` / `getChat` / `getMessages` без побочных эффектов перед основным действием.
- [ ] **14.6** `ActionSequencer.shuffle(actions, seed)`: смешать порядок планируемых действий внутри сессии (не нарушая зависимостей).
- [ ] **14.7** Warmup новые action types: `view_profile`, `scroll_chat`, `view_story`, `react_to_post`, `delete_own_message`. Добавить в `daily_action_limits` json-схему.
- [ ] **14.8** Property-based tests (Hypothesis):
  - typing duration ≈ len/cpm * 60 ± 15%;
  - typo rate over 10000 runs ≈ baseline ± 0.5%;
  - sequence shuffle deterministic с тем же сидом.
- [ ] **14.9** UI BehaviorProfileViewer: показывает baseline + last 10 session randomizations.

### Task 15: AccountStatusMonitor + IP-change/sticky-IP enforcement

**Files:**
- New: `backend/app/services/account_status_monitor.py`
- Migration: `20260520_0034_account_status_observations.py`
- Modify: `backend/app/services/scheduler.py`
- Test: `backend/tests/test_account_status_monitor.py`

- [ ] **15.1** Таблица `account_status_observations`:
  - PK `id`, FK `workspace_id`, FK `account_id`;
  - `observed_at`;
  - `proxy_healthy` (bool), `proxy_ip_hash` (text);
  - `tdlib_authorized` (bool);
  - `device_model_hash` (text);
  - `consecutive_failures` (int);
  - `auto_action_taken` (nullable: `paused|quarantine|cooldown|none`);
  - `details_json` (jsonb).
- [ ] **15.2** Tick (default every 10 min):
  - Для каждого активного аккаунта: TDLib auth check + proxy check + IP hash.
  - **IP-change detection:** `proxy_ip_hash` ≠ предыдущего → soft cooldown 30 min (`SafetyGateReason: ip_change_cooldown`).
  - **Sticky-IP enforcement:** если аккаунт «прыгает» между IP >3 раз в час → quarantine reason=`status_degraded`.
  - **Device fingerprint change:** `device_model_hash` ≠ предыдущего → audit-log + warning (не block).
- [ ] **15.3** Auto-actions: `consecutive_failures ≥ threshold` или `fraud_score ≥ 0.7` → auto-pause всех активных warmup/neuro-commenting + `NeuroCommentEvent(event_type='account_auto_paused')`.
- [ ] **15.4** Endpoint `GET /api/accounts/{id}/status-observations?limit=50`.
- [ ] **15.5** Тесты: симуляция IP change → cooldown reason; sticky-IP violation → quarantine; recovery NOT auto-resume (требует manual).

### Task 16: Profile completeness check

**Files:**
- New: `backend/app/services/account_profile_completeness.py`
- Test: `backend/tests/test_account_profile_completeness.py`

- [ ] **16.1** `evaluate(account_id) → ProfileCompletenessReport`:
  - `first_name` set, len ≥ 2 (required, 0.3 вес);
  - `bio` set, len ≥ 10 (required, 0.3 вес);
  - `profile_photo_asset_id` set (required, 0.2 вес);
  - `username` set (recommended, 0.1 вес);
  - `pinned_channel_ref` set (recommended, 0.1 вес);
  - completeness score 0..1.
- [ ] **16.2** Используется в Gate (Task 13) для `intent=commenting`.
- [ ] **16.3** UI progress bar 0–100% в AccountWorkspaceRoute.

### Task 17: CrossModuleLoadTracker

**Files:**
- New: `backend/app/services/cross_module_load_tracker.py`
- Migration: `20260520_0040_cross_module_load_buckets.py`
- Test: `backend/tests/test_cross_module_load_tracker.py`

- [ ] **17.1** Таблица `cross_module_load_buckets` (rolling counter per hour):
  - PK `id`, FK `workspace_id`, FK `account_id`;
  - `bucket_start` (timestamp, truncated to hour);
  - `warmup_actions` (int), `commenting_actions` (int), `editing_actions` (int), `other_actions` (int);
  - `total_actions` (int generated col);
  - Index `(account_id, bucket_start)`.
- [ ] **17.2** `track(account, module, count=1)` — incr current-hour bucket.
- [ ] **17.3** `current_load(account) → CrossModuleLoad{last_hour, last_24h, breakdown}`.
- [ ] **17.4** Thresholds per safety mode:
  - conservative: 12/h, 80/24h;
  - balanced: 25/h, 200/24h;
  - aggressive: 60/h, 500/24h.
- [ ] **17.5** Gate проверяет: total_load > threshold → `cross_module_overload` reason (severity=warning при 0.8×threshold, blocked при ≥threshold).
- [ ] **17.6** Тесты: warmup-only под порогом → ok; warmup+commenting сумма выше порога → blocked.

### Task 18: Bought-account onboarding wizard

**Files:**
- New: `backend/app/services/bought_account_onboarding.py`
- Modify: `backend/app/services/step_registry.py` (steps `enable_2fa`, `terminate_other_sessions`)
- New UI: `BoughtAccountOnboardingWizard.tsx`
- Test: `backend/tests/test_bought_account_onboarding.py`

- [ ] **18.1** Новое поле `accounts.origin` (`imported|bought|created`) + миграция.
- [ ] **18.2** Wizard steps (UI):
  1. **Enable 2FA** — обязательно (TDLib `setPassword`); без 2FA нельзя продолжить.
  2. **Terminate other sessions** — scheduled на T+24h (через scheduler).
  3. **Rest period** — авто-карантин 5–7 дней (`reason=bought_rest_period`).
  4. **GGR pre-check** — после rest auto-trigger GGR recalc; если bucket=weak → продлить rest +3d, иначе release.
- [ ] **18.3** Backend endpoints:
  - `POST /api/accounts/{id}/bought-onboarding/start` (создаёт quarantine + scheduled job).
  - `GET /api/accounts/{id}/bought-onboarding/status` (текущий шаг).
- [ ] **18.4** Тест: bought account → forced wizard → 5d quarantine → GGR check → release.

### Task 19: Интеграция Gate во все три модуля

**Files:**
- Modify: `live_readiness_service.py`, `warmup_readiness.py`, `account_update.py` (preview), `behavior_aware_sender.py`, `warmup_dispatch.py`
- Test: `backend/tests/test_account_safety_gate_integration.py`

- [ ] **19.1** Live-readiness (neuro-commenting): для каждого аккаунта вызвать `gate.evaluate(intent=commenting)`; любой blocked → ready=False с check_code=`account_safety_blocked` и `referenced_account_id`.
- [ ] **19.2** Sender preflight: атомарный gate-check через Lua-скрипт перед каждой отправкой (см. Task 27).
- [ ] **19.3** Warmup dispatch: gate(intent=warmup) перед каждой micro-session; blocked → session status `paused_risk`.
- [ ] **19.4** Account update preview: gate(intent=editing); blocked → `blocking_errors.append("safety_gate_blocked: ...")`.
- [ ] **19.5** UI `<SafetyGateBanner accountId intent />` — переиспользуемый компонент с reasons + кнопка «See details».
- [ ] **19.6** Тесты: 4 integration scenarios:
  - не прогретый аккаунт → live-readiness blocks commenting.
  - unhealthy proxy → warmup blocks.
  - critical safety snapshot → editing blocks.
  - active quarantine → все три intents blocked.

---

## 8. Phase 2.5 — Production Hardening

**Goal:** добиться prod-deployability. Без этой фазы Phase 2 нельзя катить.
**Duration:** 1.5–2 sprints.

### Task 20: Per-workspace feature flag для safety pipeline v2

**Files:**
- Migration: `20260520_0043_safety_pipeline_feature_flags.py`
- New: helper `backend/app/services/feature_flags.py`
- Test: `backend/tests/test_safety_pipeline_feature_flags.py`

- [ ] **20.1** Колонка `workspaces.safety_pipeline_v2_enabled` (bool, default False).
- [ ] **20.2** `gate.evaluate()` если flag=False → возвращает старый verdict-shim (только основные блокеры из существующего pipeline).
- [ ] **20.3** Admin-endpoint для toggle (sensitive_audit).
- [ ] **20.4** Rollout strategy: документировать в `docs/runbooks/safety-rollout.md` — staged enablement (canary workspace → 10% → 50% → 100% за 2 недели).

### Task 21: Idempotency на attempts

**Files:**
- Migration: `20260520_0042_attempt_idempotency_keys.py` (добавить `idempotency_key` UUID unique, `external_message_id_provisional` nullable)
- Modify: `behavior_aware_sender.py`
- New: `backend/app/services/idempotency_keys.py`
- Test: `backend/tests/test_attempt_idempotency.py`

- [ ] **21.1** Перед TDLib `sendMessage`:
  1. Сгенерировать `idempotency_key = uuid4()`.
  2. `SET attempt:idem:{key} = attempt_id NX EX 3600` в Redis.
  3. TDLib `sendMessage(..., random_id=hash(idempotency_key))`.
  4. После ответа TDLib: транзакционно записать `attempt.telegram_message_id` + `attempt.status=SENT`.
  5. Если шаг 4 упал — reconcile-job по `idempotency_key` найдёт сообщение (TDLib гарантирует idempotency через `random_id`).
- [ ] **21.2** Transactional outbox для post-send events.
- [ ] **21.3** Тест: симулировать падение между шагами 3 и 4 → reconcile восстанавливает SENT без дубля.

### Task 22: Concurrency-safe gate через Lua

**Files:**
- New: Redis Lua script `backend/redis_scripts/safety_gate_reserve.lua`
- Modify: `account_safety_gate.py`
- Test: `backend/tests/test_account_safety_gate.py`

- [ ] **22.1** Lua script атомарно:
  ```
  local verdict_key = KEYS[1]
  local rate_keys = KEYS[2..N]
  if not redis.call('EXISTS', verdict_key) then return 'STALE' end
  local v = redis.call('GET', verdict_key)
  if v ~= 'ELIGIBLE' then return v end
  -- check + decrement rate counters atomically
  for i, k in ipairs(rate_keys) do
    local cur = tonumber(redis.call('INCR', k)) or 0
    local lim = tonumber(ARGV[i]) or 0
    if cur > lim then
      for j, rk in ipairs(rate_keys) do if j <= i then redis.call('DECR', rk) end end
      return 'RATE_BLOCKED:' .. k
    end
  end
  return 'RESERVED'
  ```
- [ ] **22.2** Sender preflight использует этот Lua-скрипт; verdict=STALE → форсированный refresh + retry.
- [ ] **22.3** Тест: два параллельных attempt на лимит=1 → один RESERVED, второй RATE_BLOCKED.

### Task 23: Persistent rate limiter fallback

**Files:**
- Migration: `20260520_0041_rate_limit_persistent_counters.py`
- Modify: `backend/app/services/neuro_commenting/rate_limiter.py`
- Test: `backend/tests/test_rate_limiter_persistent.py`

- [ ] **23.1** Таблица `rate_limit_persistent_counters`: (workspace_id, account_id, scope_key, window_start, count, updated_at) + index.
- [ ] **23.2** Каждые 60s rq-job flush Redis counters → Postgres.
- [ ] **23.3** На старте rate-limiter: hot-load из Postgres → Redis (если Redis пустой).
- [ ] **23.4** Тест: симулировать `FLUSHALL` Redis → counters восстановлены из Postgres.

### Task 24: Reconcile stuck attempts

**Files:**
- New: `backend/app/services/reconcile_stuck_attempts.py`
- Modify: `backend/app/services/scheduler.py`
- Test: `backend/tests/test_reconcile_stuck_attempts.py`

- [ ] **24.1** Tick every 2 min: find attempts `status IN (SENDING, RESERVED)` AND `updated_at < now - 5min`.
- [ ] **24.2** Для каждого:
  - TDLib `searchChatMessages` по `random_id=hash(idempotency_key)`.
  - Найдено → `status=SENT`, `telegram_message_id=found.id`.
  - Не найдено → `status=FAILED`, `error_code=stuck_attempt_lost`.
- [ ] **24.3** Тест: симулировать stuck → reconcile resolves.

### Task 25: Tenant scope на всех новых таблицах

**Files:**
- Modify: `backend/app/services/tenant_scope.py`
- Audit: каждая query на новые таблицы должна включать `workspace_id` фильтр.
- New: `backend/tests/test_tenant_isolation_safety_pipeline.py`

- [ ] **25.1** Все 11 новых таблиц должны иметь `workspace_id` FK (где применимо).
- [ ] **25.2** Тест: создать 2 workspaces, у каждого по аккаунту/quarantine/ggr; запрос workspace_1 не должен видеть workspace_2 данных.
- [ ] **25.3** Static-analysis: добавить linter-rule (semgrep правило) что любой query на `account_ggr_scores|account_quarantines|account_status_observations|...` обязан фильтровать по `workspace_id`. Положить в `.semgrep/tenant_scope.yml`.

### Task 26: Sensitive audit на изменения safety policy

**Files:**
- Modify: `backend/app/services/sensitive_audit.py`
- Test: `backend/tests/test_sensitive_audit_safety.py`

- [ ] **26.1** Любой PATCH safety-policy, quarantine release, manual gate override → audit запись `category=safety_policy_change` с before/after diff, user_id, IP, user-agent.
- [ ] **26.2** UI отдельная вкладка «Safety Audit Log» в SettingsRoute.

### Task 27: Performance budget на gate

**Files:**
- Modify: `account_safety_gate.py`
- New benchmark: `backend/tests/benchmarks/test_safety_gate_perf.py`

- [ ] **27.1** SLO: gate.evaluate p95 < 50ms cache-hit, < 200ms cold.
- [ ] **27.2** Cold-call rate budget: ≤ 1 per account per minute.
- [ ] **27.3** Benchmark с pytest-benchmark, fail если регрессия > 20%.
- [ ] **27.4** Add to nightly CI workflow.

### Task 28: Backfill стратегия для existing data

**Files:**
- New script: `backend/scripts/backfill_safety_pipeline.py`
- Docs: `docs/runbooks/backfill-safety-pipeline.md`

- [ ] **28.1** Для каждого existing аккаунта:
  - Создать `account_ggr_scores` с initial score=5.0, force-recalc enqueued.
  - Создать `account_behavior_profile` с baseline по balanced preset.
  - Set `accounts.origin='imported'` (default).
- [ ] **28.2** Grace period: existing аккаунты считаются `balanced` 30 дней с момента миграции.
- [ ] **28.3** Idempotent: повторный запуск не создаёт дубли.
- [ ] **28.4** Прогон в staging до prod миграции.

### Task 29: Migration safety на больших БД

**Files:**
- Каждая alembic-миграция Phase 2/2.5

- [ ] **29.1** Все `ADD COLUMN ... NOT NULL DEFAULT` → разбить на 3 миграции: ADD COLUMN NULL → backfill batch (1000 rows / commit) → ALTER SET NOT NULL.
- [ ] **29.2** Все `CREATE INDEX` → `CREATE INDEX CONCURRENTLY` (вне транзакции).
- [ ] **29.3** Документировать ожидаемое время + lock-impact в комментарии миграции.
- [ ] **29.4** Test: на dump prod-копии замерить время каждой миграции.

### Task 30: Observability (Prometheus + alerts)

**Files:**
- New: `backend/app/observability/safety_metrics.py`
- Modify: `backend/app/main.py` (регистрация metrics endpoint)
- New: `docs/runbooks/safety-alerts.md`

- [ ] **30.1** Метрики:
  - Counter `safety_gate_blocks_total{workspace, intent, reason}`.
  - Gauge `quarantine_active{workspace}`.
  - Histogram `ggr_score{workspace, bucket}`.
  - Counter `flood_wait_total{workspace, account}`.
  - Histogram `attempt_send_duration_seconds{strategy}`.
  - Histogram `safety_gate_evaluate_duration_seconds{intent, cache_hit}`.
  - Counter `human_behavior_typing_emit_total{outcome}`.
  - Counter `cross_module_overload_total{workspace}`.
- [ ] **30.2** Alertmanager rules (документировать в runbook):
  - `quarantine_active / total_accounts > 0.1` за 1h → warning.
  - `ggr_score{bucket=weak} growth rate > 5/h` → warning.
  - `safety_gate_blocks_total{reason=ggr_too_low} burst rate >50/min` → critical.
  - `attempt_send_duration_seconds p95 > 30s` → warning.
- [ ] **30.3** Грейфана dashboard JSON в `docs/grafana/safety-pipeline.json`.

### Task 31: Алерты для админа workspace

**Files:**
- New: `backend/app/services/admin_notifications.py`
- New: `backend/app/contracts/notifications.py`
- Test: `backend/tests/test_admin_notifications.py`

- [ ] **31.1** Triggers:
  - >10% аккаунтов workspace в quarantine за 1h.
  - GGR drop >2 points у любого аккаунта за 24h.
  - Sustained gate-block rate (>30% sends blocked за 30 min).
  - Workspace-wide proxy provider outage.
- [ ] **31.2** Каналы: email + (опционально) Telegram bot (через user-provided webhook URL).
- [ ] **31.3** Deduplication: один и тот же alert не чаще 1/час per workspace.

### Task 32: Manual quarantine release + admin overrides

**Files:**
- Modify: `backend/app/api/account_safety_routes.py`
- New UI: button в `QuarantineStateBanner.tsx`
- Test: `backend/tests/test_account_quarantine.py` (extend)

- [ ] **32.1** `POST /api/accounts/{id}/quarantine/release` (admin only):
  - Body `{reason: str, override_gate_block: bool=false}`.
  - Записать `released_at`, `released_by_user_id`.
  - Sensitive_audit.
  - Если `override_gate_block=true` → создать `safety_gate_override` запись на 24h (не блочит даже при weak GGR).
- [ ] **32.2** UI: кнопка с modal «Reason for early release» + checkbox «Override safety gate».

### Task 33: Terminal status enum

**Files:**
- Migration: `20260520_0039_account_terminal_status.py`
- Modify: `accounts` модель
- Test: `backend/tests/test_account_terminal_status.py`

- [ ] **33.1** Новая колонка `accounts.terminal_status` (nullable enum: `banned|restricted|frozen|deleted_by_user`).
- [ ] **33.2** Detect via TDLib (различные error_code типа `USER_DEACTIVATED_BAN`, `USER_RESTRICTED`).
- [ ] **33.3** Gate: terminal_status set → blocked для всех intents (нет recovery).
- [ ] **33.4** UI: банер «Аккаунт в terminal state, замените».

### Task 34: Disaster mode UI

**Files:**
- New: `apps/dashboard/src/features/home/DisasterModeBanner.tsx`
- New: endpoint `GET /api/dashboard/disaster-state`
- Test: `apps/dashboard/src/features/home/DisasterModeBanner.test.tsx`

- [ ] **34.1** Backend computes:
  - `quarantined_fraction = quarantine_active / total_accounts`.
  - `disaster_mode = quarantined_fraction > 0.5 за last 1h`.
- [ ] **34.2** UI красный баннер сверху Dashboard с кнопкой «Escalate to support».

### Task 35: Edit-diff audit on approval

**Files:**
- Modify: `backend/app/services/neuro_commenting/approval_service.py`
- Test: `backend/tests/test_neuro_commenting_runtime_api.py` (extend)

- [ ] **35.1** На approve если `edited_text` ≠ `generated_text` — записать `NeuroCommentEvent(event_type='comment_edited_on_approve', data_json={diff: unified_diff(generated_text, edited_text), user_id})`.

### Task 36: Retention для events и observations

**Files:**
- New: `backend/app/services/retention_worker.py`
- Modify: `scheduler.py`

- [ ] **36.1** Default retention 90 дней для `neuro_comment_events`, `account_status_observations`, `cross_module_load_buckets`.
- [ ] **36.2** Configurable per workspace (`workspace.event_retention_days`).
- [ ] **36.3** Tick daily, batch delete 10k rows per iteration.

### Task 37: Property-based tests на behavior emulator

**Files:**
- New: `backend/tests/test_human_behavior_property.py` (упомянут в Task 14, выделить отдельно)

- [ ] **37.1** Hypothesis strategies:
  - `typing_duration ≈ len * 60 / cpm ± 15%` over 1000 runs.
  - `typo_count / total_runs ≈ probability ± 0.5%` over 10000 runs.
  - `action_sequence_shuffle` deterministic с одним сидом, разный с разными.
- [ ] **37.2** Запуск в nightly CI (не на PR из-за времени).

---

## 9. Phase 3 — End-to-end verification & documentation

**Duration:** 0.5–1 sprint.

### Task 38: Расширенный E2E pipeline

**Files:**
- Modify: `backend/tests/integration/test_three_module_pipeline.py`
- New: `backend/tests/integration/test_safety_pipeline_e2e.py`

- [ ] **38.1** Сценарии:
  1. Не прогретый аккаунт → live-readiness blocked.
  2. Account_status_monitor detects degraded → active campaign auto-paused.
  3. Bought-account flow → 5d rest → GGR check → release → eligible.
  4. FloodWait → 24h quarantine → manual release → eligible.
  5. Cross-module overload → soft warning at 0.8×threshold, blocked at ≥threshold.
  6. IP-change cooldown 30 min → blocked → expires → eligible.
- [ ] **38.2** Coverage assertion: pipeline проходит через `safety_gate.evaluate` минимум 5 раз.

### Task 39: Документация

**Files:**
- New: `docs/modules/account-safety-pipeline.md`
- New: `docs/runbooks/safety-rollout.md`
- New: `docs/runbooks/safety-alerts.md`
- New: `docs/runbooks/backfill-safety-pipeline.md`
- Update: `README.md` (1 абзац + ссылка)

- [ ] **39.1** `account-safety-pipeline.md`:
  - Архитектурная диаграмма (Section 3.1).
  - Каждый layer: входы, выходы, конфигурация.
  - GGR formula с весами.
  - Quarantine reasons matrix.
  - Recovery procedures.
- [ ] **39.2** `safety-rollout.md`: канареечный план staged enablement Phase 2.5 Task 20.
- [ ] **39.3** `safety-alerts.md`: каждый Prometheus alert → severity, runbook link, recovery steps.
- [ ] **39.4** `backfill-safety-pipeline.md`: пошагово запуск Task 28 в prod.

### Task 40: Pre-flight в продакшен

**Files:**
- New: `docs/runbooks/safety-pipeline-preflight-checklist.md`

- [ ] **40.1** Checklist (вручную пройти):
  - [ ] Все миграции протестированы на копии prod БД (Task 29).
  - [ ] Backfill script отработал в staging (Task 28).
  - [ ] Feature flag для canary workspace включён (Task 20).
  - [ ] Grafana dashboard развёрнут (Task 30).
  - [ ] Alertmanager rules задеплоены (Task 30, 31).
  - [ ] On-call runbooks готовы (Task 39).
  - [ ] Load test gate.evaluate под 500 qps пройден (Task 27).
  - [ ] E2E scenarios зелёные (Task 38).

---

## 10. Verification gates

### Phase 0 done when:
- [ ] `pytest backend/tests/test_neuro_commenting_*` зелёный.
- [ ] `pytest backend/tests/integration/test_three_module_pipeline.py` зелёный (basic scenario).
- [ ] Все 5 shelfware enum-значений возвращают 422 с `feature_not_available`.
- [ ] `npm test --workspace=apps/dashboard` зелёный.
- [ ] Manual smoke в dev: создать campaign через wizard → пройти 5 шагов → start в dry_run.

### Phase 1 done when:
- [ ] `pytest backend/tests/test_account_update_pinned_channel.py` зелёный.
- [ ] `pytest backend/tests/test_neuro_commenting_bulk_targets.py` зелёный.
- [ ] Bulk-import 100 каналов работает < 2s в dev.
- [ ] Prompt preset подставляется в UI без перезагрузки.
- [ ] Safety preset `conservative` → лимиты per_hour=3.
- [ ] Age-forced mode: 5d account → попытка `aggressive` → 422.

### Phase 2 done when:
- [ ] Все backend safety тесты зелёные.
- [ ] Gate срабатывает в 4 местах: live_readiness, sender preflight, warmup dispatch, editing preview.
- [ ] Auto-pause при моделируемом FloodWait streak.
- [ ] GGR пересчитывается в течение 30s после симулированного proxy degradation.
- [ ] Bought-account flow: 5d quarantine → GGR check → release.
- [ ] Behavior emulator: typing duration распределение matches preset ±15%.
- [ ] Settings UI: SafetyPolicyPanel отображает + admin может PATCH.
- [ ] Незрогретый аккаунт в campaign → live-readiness blocked с reason=`no_warmup`.

### Phase 2.5 done when:
- [ ] Feature flag toggleable per workspace.
- [ ] Idempotency test: симулированный crash между TDLib send и DB commit → reconcile восстанавливает без дубля.
- [ ] Concurrency test: 100 параллельных attempts на лимит=10 → ровно 10 RESERVED, остальные RATE_BLOCKED.
- [ ] Persistent rate limiter test: `FLUSHALL` Redis → counters восстановлены.
- [ ] Tenant isolation: 2 workspaces, ни один запрос не возвращает чужие safety-данные.
- [ ] Performance bench: gate p95 cache-hit < 50ms, cold < 200ms.
- [ ] Prometheus `/metrics` отдаёт все 8 серий.
- [ ] Grafana dashboard рисует quarantine_active по времени.
- [ ] Backfill script idempotent (двойной прогон не ломает).

### Phase 3 done when:
- [ ] Все 6 E2E сценариев из Task 38 проходят.
- [ ] 4 runbook документа написаны и слинкованы из README.
- [ ] Pre-flight checklist (Task 40) пройден полностью.
- [ ] Canary workspace на feature flag отработал 1 неделю без P1-инцидентов.

---

## 11. Risks & mitigations

| Риск | Mitigation |
|---|---|
| Adaptive limits сломают существующие лимиты юзеров | Применять только к auto-created defaults; ручные limits не трогать. |
| Gate-кеш 60s даст stale verdict | Sender preflight через Lua атомарно; cache invalidation on policy change. |
| Account status monitor нагрузит TDLib | Batched check; не более N accounts/tick; exponential backoff. |
| Workspace без safety policy записи | Lazy-create при первом GET с `mode=balanced`. |
| Auto-pause массово при сетевой проблеме провайдера | Distinguish `proxy_provider_outage` (workspace-wide warning) от per-account fail. |
| Behavior emulator замедляет sender в 3-5 раз | SLO `attempt_send_duration_seconds p95 < 30s`; aggressive preset отключает typing для скорости. |
| GGR scores могут резко падать при ошибке в формуле | Smoothing: max delta 1.0 point per 6h cycle. |
| 24h quarantine кажется юзеру слишком строгим | Manual release endpoint (Task 32) с reason + audit. |
| Backfill 100k+ аккаунтов залочит БД | Batch 1000 rows + sleep 100ms между batches (Task 28, 29). |
| Феноменальный flood алертов в первые дни prod | Alert deduplication + warmup-period: первые 7 дней warn-only. |
| Cross-tenant leak через новые таблицы | Semgrep static rule + integration test (Task 25). |
| Feature flag race: половина workspaces v2, половина v1 | Все codepaths через `gate.evaluate` который сам разбирается. |

---

## 12. Out of scope

Явно отрезаны, оформляются отдельными спеками:

- **Semantic match** (pgvector / embeddings) → Phase 4+.
- **A/B prompt testing** (используя существующий `prompt_version`) → Phase 4+.
- **DM lead-handoff** (модуль `neuro-chatting`) → отдельный спек после Phase 3.
- **Channel discovery** (TG keyword search) → отдельный спек.
- **Replacement timer** (двушаговый emoji→edit text) → Phase 4+.
- **View boosting / reactions на пост** → отдельный спек.
- **Public API + webhooks** → отдельный спек.
- **AI cost tracking + budget cap** → отдельный спек.
- **Workspace plan limits** (Free/Pro/Enterprise) → billing-задача.
- **i18n английский** → отдельная задача.
- **GDPR / privacy review** → compliance-аудит, не код.

---

## 13. Effort estimate

| Phase | Tasks | Sprints |
|---|---|---|
| Phase 0 — MVP-блокеры | 1–5 | 1 |
| Phase 1 — Glue | 6–9 | 1.5–2 |
| Phase 2 — Safety pipeline | 10–19 | 3–4 |
| Phase 2.5 — Production hardening | 20–37 | 1.5–2 |
| Phase 3 — E2E + docs | 38–40 | 0.5–1 |
| **Total** | **40 tasks** | **7.5–10 sprints** |

При параллельной работе двух разработчиков (один backend, один frontend) — **5–6 sprints** реальных.

---

## Приложение A: Pre-Phase 0 проверка («Task 0»)

Перед стартом Phase 0 запустить локально existing-код и подтвердить:

- [ ] `tdlib_observer_enabled=True` end-to-end парсит channel посты на 1 тестовом канале.
- [ ] `tdlib_send_enabled=True` отправляет комментарий через 1 тестовый аккаунт.
- [ ] Warmup `network` execution_mode реально вызывает TDLib (не shadow).
- [ ] Warmup `p2p_send` работает с двумя реальными аккаунтами одновременно.
- [ ] `proxy_checks.py` корректно детектит unhealthy proxy.

Если что-либо из этого не работает — приоритет **выше Phase 0**, потому что вся остальная архитектура опирается на эти примитивы.

---

## Приложение B: Mapping существующих сервисов

| GramGPT-эквивалент | StylistTG (существующий или новый) |
|---|---|
| Лимит-контроль | `rate_limits.py` + Task 23 (persistent fallback) |
| Темпоральное распределение | `delay_min/max` в campaign + Task 14 (behavior emulator) |
| Прокси-изоляция | `proxy_accounts.py`, `proxy_checks.py` + Task 15 (sticky-IP) |
| Status monitoring | `account_safety_snapshot` + Task 15 (status monitor) |
| Intelligent warmup | модуль `warmup` (существует) + Task 19 (gate integration) |
| Adaptive limits (consvtv/blncd/aggr) | Task 9 + Task 10 |
| Behavioral imitation | Task 14 (новое) |
| GGR rating | Task 11 (новое) |
| FloodWait 24h quarantine | Task 12 (новое) |
| Sticky-IP / device fingerprint | Task 15 (расширение) |
| Bought-account onboarding | Task 18 (новое) |
| Cross-module load tracking | Task 17 (новое) |

---

**END OF SPEC v2.0.**
