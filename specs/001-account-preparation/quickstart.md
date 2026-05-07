# Quickstart: Account Preparation Module

## Local Backend Checks

```powershell
cd backend
python -m alembic upgrade head
python -m pytest tests/test_warmup_migration_contract.py -q
python -m ruff check .
```

## Run Local Services

Preferred:

```powershell
.\scripts\start-dev.ps1
```

Manual backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Manual worker after worker slice:

```powershell
cd backend
python -m app.workers.run_worker --queues warmup_jobs
```

## Frontend Checks

```powershell
npm run generate:api
npm run check:api
npm run lint
npm run test
npm run build
```

## Operator Flow

1. Open the dashboard.
2. Navigate to `Прогрев аккаунтов`.
3. Confirm the dry-run/readiness banner.
4. Start creation wizard.
5. Select account.
6. Select strategy.
7. Run readiness check.
8. Fix blocking errors if any.
9. Create the preparation session.
10. Monitor status, current day, next step time, and events.
11. Pause/resume when needed.

## Safety Expectations

- Worker does not call Telegram live APIs.
- No Telethon is introduced.
- No automatic channel joins, reactions, online-status imitation, synthetic P2P, or LLM message rewriting.
- Proxy geo/risk checks are warnings unless combined with other blocking system/account issues.
