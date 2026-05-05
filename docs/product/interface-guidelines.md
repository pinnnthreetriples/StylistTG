# Product Interface Guidelines

StylistTG is an Accounts-first SaaS interface, not an operator console. Primary screens must answer:

- what is happening;
- what needs attention;
- why it matters;
- what the user should do next.

## Primary vs Advanced UI

Primary UI includes Home, Accounts, Add Accounts, Account Workspace, Health, Jobs, Settings and Billing placeholder.

Technical details belong only in clearly named advanced areas:

- `Здоровье -> Расширенная диагностика`
- `Настройки -> Расширенные`
- `Аккаунт -> Риск и аудит -> Расширенная диагностика`

Primary screens must not show raw enum values, internal queue names, heartbeat logs, foundation language or technical English.

## Russian Product Language

All primary flows use Russian labels, descriptions, buttons, empty states and errors.

Use product labels instead of raw backend values:

- `ready` / `ok` -> `Готов`
- `unknown` -> `Неизвестно`
- `failed` / `error` / `broken` -> `Проблема`
- `low` -> `Низкий`
- `medium` -> `Средний`
- `high` -> `Высокий`
- `critical` -> `Критический`
- `mock` -> `Безопасный mock-режим`

Technical terms are allowed only when the user intentionally opens advanced diagnostics. Sensitive values must never be shown.

## Status And Risk Language

Risk is a user-facing readiness signal, not a Telegram ban guarantee.

Status tones:

- green: ready, safe, successful;
- amber: needs attention, waiting, safety pause;
- red: critical risk, error, blocker;
- blue: information or synchronization;
- gray: disabled, unknown, inactive.

Do not use green for live readiness when live mode is disabled. Use:

> Инфраструктура готова, live-режим выключен.

or:

> Live-режим отключён безопасно.

## Empty States

Every empty state must include a clear headline, short explanation, and next action when useful.

Standard copy:

- No accounts: `Добавьте первый Telegram-аккаунт`
- No jobs: `Задач пока нет`
- No stories: `Историй пока нет`
- Degraded system: `Данные временно недоступны`

## Account Workspace

Account Workspace is the main working surface for one Telegram account.

Tabs:

- `Профиль`
- `Истории`
- `Музыка`
- `Прокси`
- `Задачи`
- `Риск и аудит`

The header should show identity, readiness, risk, auth/runtime/proxy posture and safe actions. Risk and audit must explain what to do next before any task is created.

## Jobs Page

The Jobs page is a product page, not a raw worker log.

Primary view:

- summary counts;
- clear empty state;
- user-facing task history.

Advanced view:

- service worker events;
- internal diagnostics;
- queue details.

Heartbeat-style logs must not be the primary experience.

## Motion

Motion is polish, not decoration.

Allowed:

- page fade or slide, 150-220ms;
- card entrance, 150-200ms;
- tab content fade;
- dialog scale from 0.98 to 1;
- empty state fade.

Avoid:

- pulsing errors;
- infinite status animation;
- dense table animation;
- log animation;
- aggressive critical-risk transforms;
- layout shift.

The app uses reduced-motion-aware primitives where motion is applied. Live TDLib remains disabled by default; UI may explain readiness, but must not imply that live Telegram mutations are enabled.
