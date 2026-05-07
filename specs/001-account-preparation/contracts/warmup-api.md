# Contract: Account Preparation API

Base path: `/api/warmup`

All responses must be workspace-scoped by the authenticated context and must not expose secrets, Telegram session material, API hashes, proxy credentials, or raw runtime paths.

## GET /readiness

Returns module/system readiness.

Response:

```json
{
  "workers_enabled": false,
  "dry_run": true,
  "redis_connected": true,
  "database_connected": true,
  "active_sessions": 3,
  "strategies_available": 3
}
```

## POST /validate

Runs server-side readiness for an account and strategy.

Request:

```json
{
  "account_id": "uuid",
  "strategy_id": "uuid"
}
```

Response:

```json
{
  "is_ready": true,
  "checks": [
    {
      "key": "no_active_session",
      "label": "Нет активной подготовки",
      "passed": true,
      "severity": "error",
      "detail": null
    },
    {
      "key": "proxy_geo_match",
      "label": "Гео proxy совпадает с номером",
      "passed": false,
      "severity": "warning",
      "detail": "Гео отличается; это предупреждение, не блокировка"
    }
  ],
  "blocking_reasons": [],
  "warnings": ["Гео proxy отличается от номера"]
}
```

## GET /strategies

Returns available preset and workspace strategies.

Response:

```json
[
  {
    "id": "uuid",
    "name": "Мягкая подготовка",
    "description": "Минимальная активность и строгий контроль пауз",
    "is_preset": true
  }
]
```

## POST /sessions

Creates a session after repeating readiness server-side.

Request:

```json
{
  "account_id": "uuid",
  "strategy_id": "uuid"
}
```

Success response:

```json
{
  "id": "uuid",
  "account_id": "uuid",
  "strategy_id": "uuid",
  "strategy_name": "Мягкая подготовка",
  "status": "scheduled",
  "current_day": 0,
  "cadence_hours": 24,
  "next_step_at": "2026-05-05T12:00:00Z",
  "last_step_at": null,
  "next_attempt_at": null,
  "consecutive_failures": 0,
  "created_at": "2026-05-05T12:00:00Z",
  "updated_at": "2026-05-05T12:00:00Z"
}
```

Failure:
- `422` when readiness has blocking errors.
- `409` when a concurrent active session already exists.

## GET /sessions

Query:
- `status`: optional repeated status filter
- `page`: default 1
- `limit`: default 20

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "account_id": "uuid",
      "account_label": "Аккаунт 1",
      "strategy_name": "Мягкая подготовка",
      "status": "active",
      "current_day": 4,
      "cadence_hours": 24,
      "next_step_at": "2026-05-06T12:00:00Z",
      "updated_at": "2026-05-05T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20
}
```

## GET /sessions/{session_id}

Returns full session detail.

## GET /sessions/{session_id}/status

Returns compact polling status.

Response:

```json
{
  "status": "active",
  "current_day": 4,
  "next_step_at": "2026-05-06T12:00:00Z",
  "next_attempt_at": null
}
```

## PUT /sessions/{session_id}/pause

Request:

```json
{
  "reason": "Проверка proxy"
}
```

Response: session detail.

Failure:
- `409` when session is terminal or already paused.

## PUT /sessions/{session_id}/resume

Response: session detail.

Failure:
- `409` with retry timestamp when `next_attempt_at` is in the future.

```json
{
  "error": "retry_not_ready",
  "retry_after": "2026-05-06T12:00:00Z"
}
```

## GET /sessions/{session_id}/events

Query:
- `page`: default 1
- `limit`: default 50

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "event_type": "session_created",
      "payload": {
        "status": "scheduled"
      },
      "created_at": "2026-05-05T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 50
}
```

## Account API Extension

Account detail/list responses should include derived preparation state:

```json
{
  "warmup": {
    "session_id": "uuid",
    "status": "active",
    "current_day": 4,
    "is_locked": true
  }
}
```

This is derived from active preparation sessions and must not be stored as `account.warmup_status`.

