# Beta Ready Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move StylistTG beyond v0 by making the profile edit flow safer, clearer, and easier to operate locally.

**Architecture:** Keep the backend API contract stable where possible and improve the frontend around the contracts that already exist. The next work should be incremental: pure mappers first, focused UI components second, backend changes only where UI needs missing state.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, FastAPI, SQLAlchemy, RQ/Redis, TDLib.

---

## Scope

This plan covers the next beta-ready slice:

1. Preview flow visibility.
2. Job result UX.
3. Safety/runtime dashboard.
4. Asset/photo draft UX.
5. Frontend structure cleanup.

It intentionally does not include WebSocket/SSE, multi-account management, cloud deploy, billing, or mass automation.

---

## Task 1: Preview Flow UI

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/lib/jobs.ts`
- Modify: `src/lib/jobs.test.ts`
- Optional create: `src/lib/preview.ts`
- Optional create: `src/lib/preview.test.ts`

**Goal:** Make preview state explicit before job creation.

- [ ] Write a pure mapper test for preview status.

Expected behavior:
- `blocking_errors.length > 0` maps to status `blocked`.
- `dedup_would_block === true` maps to status `dedup`.
- `warnings.length > 0` maps to status `warning`.
- otherwise status `ready`.

Run:

```bash
npm test -- src/lib/preview.test.ts
```

Expected first run: fail because the mapper does not exist.

- [ ] Implement the mapper.

Suggested type:

```ts
export type PreviewStatus =
  | { kind: 'empty'; title: string; description: string }
  | { kind: 'ready'; title: string; description: string }
  | { kind: 'warning'; title: string; description: string; items: string[] }
  | { kind: 'blocked'; title: string; description: string; items: string[] }
  | { kind: 'dedup'; title: string; description: string; blockedByJobId: string | null }
```

- [ ] Add a compact preview status block near the `Создать задачу` button.

Display:
- `Готово к запуску`
- `Есть предупреждения`
- `Запуск заблокирован`
- `Такая задача уже есть`

- [ ] Make disabled create button explain why.

Use existing data:
- `preview.can_create_job`
- `preview.blocking_errors`
- `preview.warnings`
- `preview.dedup_would_block`

- [ ] Verify.

Run:

```bash
npm test
npm run build
```

Browser check:
- edit name or bio;
- confirm preview appears;
- force duplicate job if available;
- confirm disabled state is explained.

---

## Task 2: Job Result UX

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/lib/jobs.ts`
- Modify: `src/lib/jobs.test.ts`

**Goal:** Make completed, failed, partial, dedup, and manual-intervention job outcomes understandable.

- [ ] Extend `src/lib/jobs.ts` with `buildJobResultSummary(job, steps)`.

Expected statuses:
- `completed` -> success summary.
- `partially_completed` -> partial summary with uncertain/failed steps.
- `failed` -> failure summary.
- `manual_intervention_needed` -> manual check summary.
- `dedup_blocked` -> duplicate summary.
- `queued/running/waiting_lock` -> active summary.

- [ ] Add tests for each state in `src/lib/jobs.test.ts`.

Run:

```bash
npm test -- src/lib/jobs.test.ts
```

Expected first run: fail until mapper is implemented.

- [ ] Add `JobResultSummary` UI inside the `План и выполнение` panel.

Display:
- final outcome title;
- short instruction;
- error code or uncertain reason when available.

- [ ] Add a contextual action area.

Initial safe actions only:
- `Синхронизировать профиль` after terminal job;
- no automatic retry until backend exposes safe retry policy.

- [ ] Verify.

Run:

```bash
npm test
npm run build
```

Browser check:
- no job state;
- preview-only state;
- existing latest job state;
- failed/manual state using seeded backend test data if needed.

---

## Task 3: Safety And Runtime Dashboard

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services/runtime_diagnostics.py`
- Modify: `backend/app/api/accounts.py`
- Modify: `backend/tests/test_runtime_diagnostics_api.py`
- Modify: `src/lib/diagnostics.ts`
- Modify: `src/lib/diagnostics.test.ts`
- Modify: `src/App.tsx`

**Goal:** Surface safety conditions that already exist in backend policy.

- [ ] Extend account runtime diagnostics with safety fields.

Candidate response additions:

```py
auth_reauth_required: bool
manual_intervention_required: bool
recovery_marker: str | None
lock_owner: str | None
lock_epoch: int
```

Do not expose secrets or TDLib credentials.

- [ ] Add backend contract test.

Run:

```bash
cd backend
python -m pytest tests/test_runtime_diagnostics_api.py -q
```

- [ ] Update frontend diagnostics mapper.

Show:
- `Runtime ready`
- `Нужен повторный вход`
- `Нужно ручное вмешательство`
- `Задача держит lock`

- [ ] Add safety section in dashboard.

Recommended placement:
- under `Система` in sidebar;
- compact, not another large dashboard card.

- [ ] Verify.

Run:

```bash
cd backend && python -m pytest tests/test_runtime_diagnostics_api.py -q
npm test
npm run build
```

---

## Task 4: Asset And Photo Draft UX

**Files:**
- Modify: `backend/app/api/assets.py`
- Modify: `backend/tests/test_api_contracts.py`
- Modify: `src/lib/api.ts`
- Modify: `src/lib/dashboard.ts`
- Modify: `src/lib/dashboard.test.ts`
- Modify: `src/App.tsx`

**Goal:** Make selected profile photos behave like real draft data across reloads.

Current state:
- `profilePhotoAssetId` persists in draft.
- visual preview now falls back to `/api/assets/{asset_id}/content`.

Next improvements:

- [ ] Show selected asset state after reload.

UI copy:
- `Фото выбрано`
- `Готово к применению`

- [ ] Add button to clear selected photo draft.

Expected behavior:
- clears `form.profilePhotoAssetId`;
- clears local object URL;
- updates preview;
- removes photo operation from unsaved changes if it matches current profile.

- [ ] Add test for clearing photo draft.

Preferred pure test:
- mapper/action helper in `src/lib/dashboard.ts`;
- avoid UI-only testing if the logic can be pure.

- [ ] Handle missing asset content.

If `/api/assets/{asset_id}/content` returns 404:
- show placeholder;
- keep draft;
- show small warning `Фото выбрано, но файл недоступен`.

- [ ] Verify.

Run:

```bash
npm test
npm run build
cd backend && python -m pytest tests/test_api_contracts.py::test_api_contract_creates_account_asset_and_profile_job -q
```

Browser check:
- upload photo;
- reload page;
- preview remains visible;
- clear selected photo;
- reload again.

---

## Task 5: Frontend Structure Cleanup

**Files:**
- Modify: `src/App.tsx`
- Create: `src/components/dashboard/Sidebar.tsx`
- Create: `src/components/dashboard/DiagnosticsPanel.tsx`
- Create: `src/components/dashboard/ProfilePreviewPane.tsx`
- Create: `src/components/dashboard/ProfileFormPane.tsx`
- Create: `src/components/dashboard/PlanExecutionPanel.tsx`
- Optional create: `src/hooks/useDashboardState.ts`
- Optional create: `src/hooks/useProfileDraft.ts`
- Optional create: `src/hooks/useJobPolling.ts`

**Goal:** Reduce `App.tsx` risk before more UI work.

- [ ] Move presentational dashboard components out of `App.tsx`.

Start with components that do not own state:
- `Sidebar`
- `DiagnosticsPanel`
- `ProfilePreviewPane`
- `ProfileFormPane`
- `JobStepPanel`
- `AccountCard`
- `PipelineCard`

- [ ] Keep state orchestration in `App.tsx` during first pass.

Do not extract hooks until component movement is green.

- [ ] Run build after each component extraction.

Run:

```bash
npm run build
```

- [ ] Extract hooks only after components are stable.

Suggested order:
1. `useProfileDraft`
2. `useJobPolling`
3. `useDashboardState`

- [ ] Verify no behavior changes.

Run:

```bash
npm test
npm run build
```

Browser check:
- reload does not flash auth screen;
- draft text remains;
- photo draft remains;
- diagnostics still loads;
- create job still calls preview/create flow.

---

## Recommended Execution Order

1. Task 1: Preview Flow UI.
2. Task 2: Job Result UX.
3. Task 4: Asset And Photo Draft UX.
4. Task 3: Safety And Runtime Dashboard.
5. Task 5: Frontend Structure Cleanup.

Reasoning:
- Preview and job UX directly improve the daily workflow.
- Photo UX is fresh and user-visible.
- Safety dashboard benefits from clearer diagnostics state.
- Structure cleanup should happen after the UI behavior is settled enough to avoid moving unstable code twice.

---

## Final Verification

Before calling this beta-ready slice complete:

```bash
npm test
npm run build
cd backend && python -m pytest -q
```

Manual browser checks:
- auth test account loads dashboard;
- profile draft survives reload;
- photo draft survives reload;
- preview explains blocked/dedup states;
- job panel explains current/terminal states;
- diagnostics shows DB/Redis/TDLib/runtime;
- no auth-screen flash during dashboard reload.
