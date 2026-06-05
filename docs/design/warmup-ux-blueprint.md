---
name: Advanced Warmup UX blueprint
description: Screen-by-screen UI blueprint for Advanced Warmup v1.
last_updated: 2026-06-05
related:
  - .mex/patterns/warmup-advanced.md
  - docs/design/warmup-divergence-from-gramgpt.md
---

# Advanced Warmup UX Blueprint

Source of truth for Stage 7 UI issues #387 through #392. This is a product UI blueprint, not frontend implementation. Use existing `@stylisttg/ui` primitives and keep the surface dense, calm, and operational.

Reference basis: the GramGPT auto-warm reference packet reviewed in the 2026-06-05 architecture session. When the reference conflicts with StylistTG safety or architecture, follow `.mex/patterns/warmup-advanced.md` and the divergences listed below.

## Screen Rules

- First viewport is the usable warmup tool, not a landing page.
- Live TDLib actions must look gated and intentional.
- Keep selections, safety limits, action toggles, targets, launch, and logs in one continuous workflow.
- Use compact panels, rows, tabs, badges, toggles, inputs, and lists. Do not nest cards.
- Russian UI copy is canonical for this module.
- Avoid decorative visuals; state, risk, and progress carry visual weight.

### Экран 1 — Шапка модуля

Purpose: orient operator before setup.

UI texts:

- `Прогрев аккаунтов`
- `Настройте безопасный прогрев, действия, цели и мониторинг сессии.`
- `О модуле`
- `Статьи`

Components:

- `@stylisttg/ui` `PageHeader` or existing page heading pattern.
- `@stylisttg/ui` `Button` for secondary links.
- `lucide-react` info/book icons where current dashboard uses icons.

States:

- Normal: title, description, two secondary actions.
- Loading: header visible; downstream sections skeleton.
- Error: header remains; readiness or account fetch errors appear in relevant section, not here.
- Empty: header remains; selector empty state explains no eligible accounts.

Implementation notes:

- Keep copy compact. No marketing hero.
- Buttons open docs/help only; they must not start warmup.

### Экран 2 — Выбор аккаунтов (Dual-list)

Purpose: choose accounts for a warmup run with filters.

Left column texts:

- `Доступные`
- `Отфильтровано: {filtered} / Всего: {total}`
- `Поиск`
- `Страна`
- `Роль`
- `Добавить все`
- `Рабочие прокси`
- `Скрыть в работе`
- `Нет аккаунтов, соответствующих фильтрам`

Right column texts:

- `Выбрано для прогрева`
- `Выбрано: {count}`
- `Удалить все`
- `Вернуть`
- country headers: ISO code plus count, for example `RU · 12`

Components:

- `@stylisttg/ui` `Input`, `Select`, `Checkbox`, `Button`, `Badge`, `StatusPill`.
- Two responsive list panels. Desktop: 2 columns. Narrow width: stacked with selected list first after at least one account is selected.
- Per-row compact account item: display name, internal ID, username, validity badge, proxy badge, lifecycle/warmup phase badge.

States:

- Loading: skeleton rows in both lists.
- Empty: left list has filter-aware empty text; right list has `Аккаунты ещё не выбраны`.
- Error: inline alert above left list with retry.
- Normal: bulk add/remove and per-row move buttons.

Acceptance mapping:

- #387 owns `apps/dashboard/src/modules/warmup/components/WarmupAccountSelector.tsx`.
- API must debounce search by 300 ms and avoid loading more than 500 accounts at once.

### Экран 3 — Настройки прогрева

Purpose: set activity window and intensity.

Left panel texts:

- `Расписание активности`
- `С`
- `До`
- `Часовой пояс`
- `Случайные перерывы`

Right panel texts:

- `Интенсивность прогрева`
- `Осторожный`
- `Нормальный`
- `Агрессивный`
- `Для новых аккаунтов`
- `Для стабильных аккаунтов`

Components:

- `@stylisttg/ui` `Select`, `Input`, `Switch`, `RadioGroup` or segmented cards.
- Intensity options use compact selectable rows, not large marketing cards.

States:

- Loading: strategy defaults skeleton.
- Empty: defaults still shown; no account-specific proxy adaptation yet.
- Error: inline validation on invalid hours/timezone.
- Normal: selected intensity changes the summary preview.

Architecture notes:

- Strategy values become session snapshot at creation time.
- Any later proxy adaptation or personality adjustment must show in logs/events, not silently mutate the UI values.

### Экран 4 — Лимиты безопасности

Purpose: define operator-visible safety caps before launch.

UI texts:

- `Лимиты безопасности`
- `Использовать лимиты`
- `Действий в час`
- `Действий в день`
- `Вступлений в день`
- `Сообщений в день`
- `Прогрессивное увеличение`
- `День 1: 30%, день 7: 100%`

Components:

- `@stylisttg/ui` `Switch`, `Input`, `Tooltip`, `Alert`.
- Numeric inputs with min/max hints and inline validation.

States:

- Loading: disabled inputs until strategy loaded.
- Empty: defaults from selected preset.
- Error: invalid values inline, submit disabled.
- Normal: summary preview updates immediately.

Safety notes:

- This section configures limits; it must not imply live safety gates are disabled.
- Existing workspace policy remains a separate settings surface until #396.

### Экран 5 — Длительность сеанса

Purpose: choose one warmup duration.

UI texts:

- `Длительность сеанса`
- `30мин`
- `1ч`
- `2ч`
- `8ч`
- `1д`
- `3д`
- `7д`
- `Своё значение`
- `Минуты`
- `Часы`
- `Дни`

Components:

- `@stylisttg/ui` segmented buttons or compact `Button` group.
- `Input` plus `Select` for custom duration.

States:

- Loading: preset chips disabled.
- Empty: default preset selected.
- Error: custom value out of bounds.
- Normal: selection reflected in summary card and timer preview.

Validation:

- Keep backend constraints authoritative.
- If cyclic mode is enabled later, duration summary must show active time, not calendar time only.

### Экран 6 — Действия прогрева

Purpose: expose six high-level action groups.

UI texts:

- `Действия прогрева`
- `Реакции`
- `Читать каналы`
- `Рандомные`
- `Диалоги`
- `Сторис`
- `Группы`
- `Повышение доверия`

Tooltip texts:

- `Реакции: публичный след, применяются только после safety gate.`
- `Читать каналы: открывает каналы и просматривает историю.`
- `Диалоги: имитирует чтение списка чатов.`
- `Сторис: просматривает доступные сторис у выбранных каналов.`
- `Группы: локальные действия с чатами, например mute или archive.`
- `Повышение доверия: p2p и профильные действия по безопасному плану.`

Components:

- `@stylisttg/ui` `Switch`, `Tooltip`, `Select`, `Badge`.
- Use toggles for binary enable/disable.

States:

- Loading: toggles disabled.
- Empty: all groups follow selected preset.
- Error: impossible combination shows inline alert.
- Normal: toggles update fine-tuning section.

Architecture notes:

- These groups map to action categories, not direct dispatch choices.
- Final dispatch choices come from `channel_state.selector.choose_actions`.

### Экран 7 — Тонкая настройка

Purpose: configure 27+ micro-actions by category.

UI texts:

- `Тонкая настройка`
- `Экономный режим`
- `Включить всё`
- `Выключить всё`
- `Чтение`
- `Активность`
- `Развлечения`
- `Социальные`
- `Группы`
- `Профиль и настройки`
- `трафик`

Action labels:

- `Лента`, `Чтение каналов`, `Сторис`, `Реакции`, `Вступление в чат`, `P2P сообщение`
- `Диалоги`, `Скролл каналов`, `Отметить прочитанным`, `Поиск сообщений`
- `Голосование`, `Видео`, `Голосовые`
- `GIF`, `Стикеры`, `Inline-бот`, `Предпросмотр ссылок`
- `Переслать`, `Saved Messages`, `Контакты`
- `Архивировать чат`, `Отключить уведомления`
- `Печать`, `Профиль`, `Настройки`, `Плавное обновление профиля`, `Emoji status`, `Черновики`, `Настройки уведомлений`, `Отложенные сообщения`

Components:

- `@stylisttg/ui` `Button`, `Switch`, `Badge`, `Tooltip`, `Tabs` if categories need collapsing.
- `ActionPresetButtons` for presets.
- `ActionCategoryHeader` for category label and traffic badge.

States:

- Loading: category skeleton.
- Empty: selected strategy has no custom limits; show preset defaults.
- Error: save mutation failed, preserve local changes.
- Normal: per-action toggle, disabled reason where applicable.

Safety notes:

- Traffic tag is informational until proxy adaptation applies.
- `Выключить всё` must preserve at least one safe minimum action once backend rule #372 exists.

### Экран 8 — Целевые группы/каналы

Purpose: provide target channels/groups for warmup.

UI texts:

- `Целевые группы и каналы`
- `Добавьте username или ссылку`
- `+ Добавить`
- `Из спарсенных групп`
- `Из спарсенных каналов`
- `КАНАЛЫ`
- `ГРУППЫ`
- `Нет добавленных целей`

Placeholder:

- `@channel_username`
- `https://t.me/example`

Components:

- `@stylisttg/ui` `Textarea`, `Button`, `Badge`, `Alert`, `Tooltip`.
- Chips with remove buttons and accessible labels.

States:

- Loading: import buttons disabled while parser sources load.
- Empty: textarea plus guidance.
- Error: invalid target inline under textarea.
- Normal: targets grouped by type.

Architecture notes:

- Targets are copied into session strategy snapshot.
- Bootstrap pool can provide fallback targets when operator leaves list empty.

### Экран 9 — Запуск и логи

Purpose: launch, monitor, filter, and stop warmup.

UI texts:

- `Аккаунты`
- `Длительность`
- `Начать прогрев`
- `Остановить`
- `Остановлено`
- `Работает`
- `Не в сети`
- `В прямом эфире`
- `Прогресс по времени`
- `Все`
- `Инфо`
- `Успех`
- `Предупреждение`
- `Ошибка`
- `Дебаг`
- `Все аккаунты`

Log format:

- `{HH:MM:SS} · {account_label} · {phone_masked} · {message}`
- Per-account plan block: `Сессия {duration} мин · План {action_count} действий · ~{spacing} мин между`

Components:

- `@stylisttg/ui` `StatusCard`, `StatusPill`, `Button`, `Progress`, `Tabs`, `Select`, `Alert`, `ScrollArea`.
- `WarmupSummaryCards`, `WarmupStatusPill`, `WarmupSessionTimer`, `WarmupLiveLogs`.

States:

- Loading: summary skeleton and logs skeleton.
- Empty: `Логи появятся после запуска`.
- Error: SSE unavailable or polling fallback failed.
- Active: auto-scroll unless operator scrolled upward.
- Completed: timer full, launch button disabled or switches to repeat action.

Safety notes:

- `В прямом эфире` only when live gate is truly enabled.
- Live logs must not expose raw phone numbers, invite tokens, TDLib paths, or raw provider payloads.

## Divergences From GramGPT

- Reactions are treated as write actions behind safety gate.
- P2P uses a sparse friend graph, not all-to-all farm chatter.
- Strategy snapshot protects in-flight sessions from later strategy edits.
- Selector owns action choice through channel state.
- Cold-soak is a formal status, not only operator advice.
- Traffic-heavy actions are tagged and later proxy-adapted.
- DRY_RUN and mock parity are first-class.
- Logs are typed events first, UI text second.
- Personality seed drives per-account variability.
- Workspace safety policy returns as policy thresholds after personality lands.
