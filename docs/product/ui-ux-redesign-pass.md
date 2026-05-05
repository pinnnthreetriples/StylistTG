# Premium SaaS UI/UX Redesign Pass

## Primary UI

Primary UI is the user-facing product layer: Home, Accounts, Add Accounts, Account Workspace, Health, Jobs, Settings and Billing placeholder.

It must answer:

- Что происходит?
- Что требует внимания?
- Почему это важно?
- Что сделать дальше?

## Advanced UI

Technical details belong only in explicitly named advanced areas:

- `Здоровье -> Расширенная диагностика`
- `Настройки -> Расширенные`
- `Аккаунт -> Риск и аудит -> Расширенная диагностика`

Primary screens must not show raw enum values, internal queue names, heartbeat logs, foundation language or technical English.

## Safe Defaults

Live TDLib remains disabled by default. The UI may explain readiness, but it must not imply that live Telegram mutations are enabled.
