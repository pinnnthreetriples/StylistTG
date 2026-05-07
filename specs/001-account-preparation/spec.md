# Feature Specification: Account Preparation Module

**Feature Branch**: `001-account-preparation`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "Профессиональный модуль подготовки аккаунтов: стратегии, readiness, 14-дневные сессии, dry-run/RQ execution, аудит, UI и безопасная интеграция без имитации поведения и без обхода антиспам-систем"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check Account Readiness (Priority: P1)

An operator checks whether a Telegram account is safe and ready to enter preparation before creating a session.

**Why this priority**: The module must prevent unsafe or invalid starts before any scheduling or worker execution happens.

**Independent Test**: Can be tested by selecting an account and strategy, running readiness checks, and verifying that blocking errors and warnings are shown separately.

**Acceptance Scenarios**:

1. **Given** an account that is authorized, has no active preparation session, and has no blocking cooldown, **When** the operator runs readiness, **Then** the system marks it ready and shows any non-blocking warnings separately.
2. **Given** an account that already has an active preparation session, **When** the operator runs readiness, **Then** the system blocks creation and explains that an active session already exists.
3. **Given** an account with proxy geo mismatch or elevated proxy risk score, **When** the operator runs readiness, **Then** the system shows warnings but does not block creation only because of those warnings.

---

### User Story 2 - Create a 14-Day Preparation Session (Priority: P1)

An operator creates a preparation session for one account using a selected strategy.

**Why this priority**: Session creation is the core business action of the module.

**Independent Test**: Can be tested by creating a session after successful readiness and confirming status, day, cadence, next step time, and audit event.

**Acceptance Scenarios**:

1. **Given** readiness passes without blocking errors, **When** the operator creates a session, **Then** the system creates a scheduled 14-day session with day 0, cadence policy, next step time, and a session-created audit event.
2. **Given** readiness has blocking errors, **When** the operator attempts to create a session, **Then** the system refuses creation and returns the blocking reasons.
3. **Given** a completed or failed previous session for the account, **When** the operator creates a new session, **Then** the system allows a new session if no active session exists.

---

### User Story 3 - Monitor Progress and Events (Priority: P1)

An operator monitors all preparation sessions and inspects a single session's history.

**Why this priority**: The module must be observable and auditable from day one.

**Independent Test**: Can be tested by opening the module page, viewing session rows, opening details, and checking that event history matches session state changes.

**Acceptance Scenarios**:

1. **Given** there are preparation sessions in different states, **When** the operator opens the module dashboard, **Then** the system shows account, strategy, status, current day, next step time, and last update time.
2. **Given** a session has events, **When** the operator opens the session details, **Then** the system shows the event log in reverse chronological order.
3. **Given** a session is completed or failed, **When** the dashboard refreshes, **Then** the session remains visible but is not polled as an active execution.

---

### User Story 4 - Pause and Resume Safely (Priority: P2)

An operator pauses or resumes a preparation session without losing audit history or violating schedule rules.

**Why this priority**: Operational control is required when risks, mistakes, or maintenance appear.

**Independent Test**: Can be tested by pausing an active session, verifying state and audit event, then resuming only when retry/cadence rules allow it.

**Acceptance Scenarios**:

1. **Given** a session is scheduled or active, **When** the operator pauses it with a reason, **Then** the system changes status to manual pause and records the reason in events.
2. **Given** a session has a future retry time, **When** the operator attempts to resume it, **Then** the system refuses resume and shows when retry becomes available.
3. **Given** a manually paused session has no future retry block, **When** the operator resumes it, **Then** the system returns it to scheduled state and records a resume event.

---

### User Story 5 - Execute Dry-Run Daily Steps (Priority: P2)

The system advances due sessions through a 14-day dry-run plan without calling Telegram live APIs.

**Why this priority**: Professional execution requires a worker model, idempotency, cadence, and circuit breaker even before any live actions are allowed.

**Independent Test**: Can be tested by creating due sessions, running the worker, and verifying day advancement, task-run records, events, and next step scheduling.

**Acceptance Scenarios**:

1. **Given** a scheduled session whose next step time has arrived, **When** the worker runs, **Then** it records one completed dry-run step, advances the current day by one, and schedules the next step according to cadence.
2. **Given** a session has already recorded a task run for the same day and task type, **When** the worker sees the same session again, **Then** it skips duplicate execution and records no duplicate task run.
3. **Given** a worker step fails repeatedly, **When** failures reach the configured threshold, **Then** the system fails or risk-pauses the session and records a circuit-breaker event.

---

### User Story 6 - Use Preset Strategies (Priority: P3)

An operator selects from curated preparation strategies instead of configuring low-level rules manually.

**Why this priority**: Presets reduce mistakes and make the feature usable without exposing unsafe automation controls.

**Independent Test**: Can be tested by loading strategy list and creating sessions with each preset.

**Acceptance Scenarios**:

1. **Given** the module is installed, **When** the operator opens strategy selection, **Then** the system shows preset strategies with Russian names and descriptions.
2. **Given** a preset exists, **When** a session is created from it, **Then** the session stores the selected strategy and uses its cadence/risk policy for future worker steps.

### Edge Cases

- Account is deleted, deauthorized, or runtime state becomes unavailable during an active session.
- Redis or workers are unavailable while the web application is running.
- Database already contains a historical completed or failed session for the same account.
- Two operators try to create or resume sessions for the same account at the same time.
- A paused-risk session has a future retry time and an operator attempts to resume it early.
- A worker receives the same due session multiple times.
- A session reaches day 14 and must become completed without scheduling another step.
- Proxy diagnostics are unavailable or external proxy scoring fails.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a dedicated account preparation module for operators.
- **FR-002**: System MUST support preparation strategies with name, description, day/cadence policy, risk policy, preset flag, and workspace scope.
- **FR-003**: System MUST support creating one preparation session per account when no active session already exists for that account in the same workspace.
- **FR-004**: System MUST model session statuses at minimum as draft, validating, scheduled, active, paused by risk, paused manually, completed, and failed.
- **FR-005**: System MUST track current day, next step time, last step time, cadence interval, retry time, failure count, and worker identity for each session.
- **FR-006**: System MUST run server-side readiness checks before session creation and MUST NOT trust client-side readiness results.
- **FR-007**: Readiness checks MUST distinguish blocking errors from non-blocking warnings.
- **FR-008**: Proxy geo mismatch and elevated proxy risk score MUST be warnings, not sole blocking reasons.
- **FR-009**: Blocking checks MUST include at least account existence, account workspace ownership, runtime readiness, active-session uniqueness, active cooldowns, and system readiness for queue/database dependencies.
- **FR-010**: System MUST reject session creation when blocking readiness errors exist and return human-readable Russian reasons.
- **FR-011**: System MUST expose session list, session detail, session status, session events, strategy list, readiness status, pause, and resume capabilities.
- **FR-012**: System MUST record every meaningful state transition and operator action in preparation events.
- **FR-013**: Worker execution MUST be dry-run by default and MUST NOT call Telegram live APIs unless an explicit future live capability is approved separately.
- **FR-014**: Worker execution MUST respect next step time and cadence interval; it MUST NOT advance multiple preparation days in one scheduler tick.
- **FR-015**: Worker execution MUST record idempotent task runs so the same session/day/task type cannot execute twice.
- **FR-016**: Worker execution MUST use account-level locking so only one worker can process a given account at a time.
- **FR-017**: System MUST pause or fail sessions after repeated worker failures according to a circuit-breaker threshold.
- **FR-018**: System MUST allow manual pause for scheduled or active sessions with a required reason.
- **FR-019**: System MUST allow resume only when retry and cadence constraints allow it.
- **FR-020**: System MUST mark sessions completed when the preparation plan reaches the final day.
- **FR-021**: System MUST expose a Russian-language UI for dashboard, session creation, status, events, pause, and resume.
- **FR-022**: UI MUST show dry-run/readiness state clearly when execution workers or live execution are disabled.
- **FR-023**: UI MUST poll active sessions and avoid unnecessary polling for terminal sessions.
- **FR-024**: UI MUST show warnings separately from blockers during readiness.
- **FR-025**: System MUST never return Telegram session material, auth secrets, API hashes, proxy credentials, or raw TDLib paths to the client.
- **FR-026**: System MUST integrate with account views by exposing current preparation state as derived account information, not as a denormalized account status column.
- **FR-027**: System MUST block or warn on conflicting account actions while a preparation session is active, according to a clear operation policy.
- **FR-028**: System MUST provide preset strategies suitable for safe account preparation without P2P messaging, automatic channel joins, automatic reactions, online-status imitation, LLM message rewriting, or behavior designed to bypass anti-spam systems.

### Key Entities

- **Preparation Strategy**: A reusable strategy that defines the preparation cadence, day ranges, limits, and operator-facing description.
- **Preparation Session**: A 14-day account preparation lifecycle for a single account and strategy.
- **Preparation Event**: An immutable audit record for session creation, status changes, readiness results, worker steps, pauses, resumes, skips, failures, and completion.
- **Preparation Task Run**: An idempotency record for a specific session/day/task type execution attempt.
- **Readiness Check Result**: A single pre-flight check result with key, label, severity, pass/fail state, and optional detail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can create a valid preparation session from the UI in under 2 minutes after selecting an eligible account and strategy.
- **SC-002**: 100% of attempted duplicate active sessions for the same account are rejected or safely deduplicated.
- **SC-003**: 100% of session state changes create an audit event visible from the session detail view.
- **SC-004**: A due dry-run worker step advances at most one preparation day per session per run.
- **SC-005**: Replaying the same worker step for the same session/day/task type does not create a duplicate completed task run.
- **SC-006**: Terminal sessions are no longer actively polled by the UI within one refresh interval after reaching completed or failed status.
- **SC-007**: No client response includes Telegram session material, auth secrets, proxy passwords, API hashes, or raw runtime paths.
- **SC-008**: A session with repeated worker failures reaches a safe terminal or paused state within the configured failure threshold.

## Assumptions

- The module name in product UI may be "Прогрев аккаунтов", but the internal safety framing is account preparation.
- The project remains polling-first; no WebSocket or SSE is required.
- Existing workspace/account ownership rules apply to every preparation object.
- Existing worker, queue, lock, cooldown, audit, and diagnostics patterns are reused instead of introducing a second Telegram runtime.
- Live Telegram actions are out of scope until a separate product decision defines allowed actions and risk controls.
- Proxy geo and fraud score are diagnostics and warnings, not guarantees of account safety.
- Russian is the primary UI language for all operator-facing text.
