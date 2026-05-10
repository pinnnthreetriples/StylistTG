# Account Preparation Runbook

Модуль `Прогрев аккаунтов` в текущей реализации работает как безопасная подготовка аккаунтов:

- ведёт 14-дневную сессию;
- выполняет только dry-run шаги;
- поддерживает shadow-режим без TDLib-вызовов;
- live-уровни `passive`, `network`, `advanced` существуют только за отдельными флагами и требуют явного операторского разрешения перед работой с реальными Telegram-аккаунтами;
- не использует Telethon;
- не выполняет имитацию онлайн-статуса и не обещает антибан/обход ограничений;
- пишет события и task-run записи для аудита и идемпотентности.

## Local Setup

```powershell
.\scripts\start-dev.ps1
```

Отдельный worker после включения очереди:

```powershell
cd backend
python -m app.workers.run_worker --queues warmup_jobs
python -m app.workers.run_worker --queues warmup_dispatch_jobs
```

## Feature Flags

```env
WARMUP_WORKERS_ENABLED=false
WARMUP_DRY_RUN=true
WARMUP_DEFAULT_CADENCE_HOURS=24
WARMUP_MAX_CONSECUTIVE_FAILURES=3
WARMUP_BATCH_LIMIT=50
WARMUP_LIVE_ENABLED=false
WARMUP_PASSIVE_ENABLED=false
WARMUP_NETWORK_ENABLED=false
WARMUP_ADVANCED_ENABLED=false
WARMUP_SCHEDULER_ENABLED=false
WARMUP_HARD_DISABLE=false
```

`WARMUP_WORKERS_ENABLED=false` означает, что сессии можно создавать и проверять, но worker execution должен оставаться выключенным.

`WARMUP_LIVE_ENABLED=false` означает, что live dispatch не должен выполнять TDLib-действия. `shadow` остаётся симуляцией; `passive`, `network` и `advanced` дополнительно требуют соответствующие level-флаги.

## Verification

```powershell
cd backend
python -m pytest tests/test_warmup_foundation.py tests/test_warmup_readiness.py tests/test_warmup_sessions_api.py tests/test_warmup_worker.py tests/test_warmup_strategies.py tests/test_warmup_account_integration.py -q
python -m pytest tests/test_warmup_dispatch.py tests/test_warmup_passive.py tests/test_warmup_network_advanced.py tests/test_warmup_isolation.py -q
python -m ruff check .
```

Frontend:

```powershell
npm --workspace @stylisttg/dashboard run typecheck
npm --workspace @stylisttg/dashboard run lint
```

## Safety Notes

Не описывать модуль как антибан, обход ограничений или защиту от теневого бана. Это инструмент контроля подготовки, расписания, аудита и операционной безопасности.
