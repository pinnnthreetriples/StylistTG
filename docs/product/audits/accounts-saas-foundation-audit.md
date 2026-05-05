# Accounts SaaS Foundation Audit

## Executive summary
failed.

StylistTG заметно продвинулся к Accounts-first SaaS: есть `/home`, `/accounts`, Account Workspace, Health Center, `packages/ui`, risk UI, motion foundation и русская навигация. Но текущий срез нельзя мержить: `npm run build` падает, основной пункт меню "Аккаунты" ведет не в Accounts, Browser QA не стартует, а часть primary flows остается смесью русскоязычного SaaS UI и англоязычных operator/foundation screens.

Были сделаны только мелкие obvious fixes, разрешенные задачей: удалены неиспользуемые props/imports, которые блокировали `npm run lint`:
- `apps/dashboard/src/components/dashboard/profile/ProfilePanels.tsx`
- `apps/dashboard/src/components/ui/AnimatedDialog.tsx`

## P0 Blockers

### Finding: P0 - dashboard build is broken
- severity: P0
- файл: `apps/dashboard/src/App.tsx`, `apps/dashboard/src/components/dashboard/profile/ProfilePanels.tsx`, `apps/dashboard/src/components/ui/AnimatedDialog.tsx`, `apps/dashboard/src/components/ui/AnimatedTabs.tsx`, `apps/dashboard/src/features/accounts/AccountsTableToolbar.tsx`, `apps/dashboard/src/features/home/HomePage.tsx`, `apps/dashboard/src/features/settings/SettingsPage.tsx`, `apps/dashboard/src/lib/motion.ts`
- что не так: `npm run build` падает на TypeScript errors: несовместимые props у animated components, неподдержанные `Button` variants/sizes, отсутствующие поля `SettingsBundle`, неверные motion easing types, ошибка `App.tsx(572,60)`.
- почему важно: acceptance criteria для SaaS UI не выполнены; Playwright QA и production build невозможны.
- конкретное исправление: привести usage к фактическим типам `@stylisttg/ui`, расширить primitives только если это реально нужно, починить `SettingsBundle` contract, убрать unsupported props `forceMount/asChild/delay/size/outline`, заменить unsafe motion easing cast.
- тест: существующий `npm run build` должен стать обязательным blocking test; новый тест не нужен, но текущий build должен проходить.

### Finding: P0 - primary Accounts navigation opens Home, not Accounts
- severity: P0
- файл: `apps/dashboard/src/lib/routes.ts:30`, `apps/dashboard/src/app/navigation.ts:21`, `apps/dashboard/src/router.tsx:44`, `apps/dashboard/src/router.tsx:61`, `apps/dashboard/src/lib/routes.test.ts:18`
- что не так: `router.tsx` определяет `/accounts`, но `appRoutes.accounts()` возвращает `/`; root `/` теперь redirect на `/home`, поэтому клик по "Аккаунты" в sidebar/top nav уводит на Home.
- почему важно: основной рабочий раздел Accounts недоступен из primary navigation. Это напрямую нарушает Accounts-first модель.
- конкретное исправление: изменить `accountListRoute()` и `appRoutes.accounts()` на `/accounts`; оставить `/` только как redirect на `/home`; обновить tests, которые сейчас закрепляют старое поведение.
- тест: обновить `routes.test.ts` и `navigation.test.ts`, чтобы проверять `primaryNavigation.find(label="Аккаунты").href === "/accounts"` и root redirect на `/home`.

### Finding: P0 - Browser QA cannot run
- severity: P0
- файл: `playwright.config.ts`, `apps/dashboard/e2e/saas-shell.spec.ts`
- что не так: `npm run qa:browser` и `npm run qa:screenshots` падают на старте webServer, потому что Playwright сначала запускает dashboard build, а build падает.
- почему важно: Browser QA не подтверждает новый SaaS shell, mobile shell, Accounts, Add Accounts, Account Workspace, Health.
- конкретное исправление: сначала исправить build; затем обновить e2e сценарии под новую русскую продуктовую структуру.
- тест: `npm run qa:browser` и `npm run qa:screenshots` должны проходить локально и в CI.

### Finding: P0 - route/test coverage still encodes the old route model
- severity: P0
- файл: `apps/dashboard/src/lib/routes.test.ts:18`, `apps/dashboard/e2e/saas-shell.spec.ts:11`, `apps/dashboard/e2e/saas-shell.spec.ts:26`, `apps/dashboard/e2e/saas-shell.spec.ts:33`, `apps/dashboard/e2e/saas-shell.spec.ts:236`
- что не так: unit test ожидает `accountListRoute() === "/"`, а Browser QA все еще проверяет old/operator labels: `Workspace: Staging Ops`, `TDLib live-disabled`, `Real authorization`, `Preview account packages`, `Worker Activity`, `/proxy`.
- почему важно: тесты не защищают новую архитектуру `/home` + `/accounts`; они могут пропустить regressions или падать после правильной русификации.
- конкретное исправление: переписать tests под expected routes: `/`, `/home`, `/accounts`, `/accounts/add`, `/accounts/:accountId/profile`, `/health`, `/jobs`, `/settings`, `/billing`; убрать primary `/proxy` e2e из main flow.
- тест: добавить route restructure tests, raw enum protection tests и browser QA для Home/Accounts/Add Accounts/Account Workspace/Health/Settings/Billing.

## P1 Issues

### Finding: P1 - canonical `/accounts/add` route is missing
- severity: P1
- файл: `apps/dashboard/src/router.tsx:75`, `apps/dashboard/src/features/accounts/AccountsPage.tsx:37`, `apps/dashboard/src/features/home/HomePage.tsx:17`, `apps/dashboard/src/lib/routes.ts:69`
- что не так: добавление аккаунтов живет на legacy route `/auth/batch`; ожидаемый SaaS route `/accounts/add` отсутствует.
- почему важно: IA остается legacy/operator-oriented; Home и Accounts ведут пользователя не в новую Accounts Platform модель.
- конкретное исправление: добавить `/accounts/add` как canonical route для Add Accounts 2.0; оставить `/auth/batch` как legacy redirect/deep link.
- тест: route test для `/accounts/add`; browser QA для Add Accounts page.

### Finding: P1 - Add Accounts/auth/import primary flows are still English and show raw source/status values
- severity: P1
- файл: `apps/dashboard/src/features/auth/AuthSessionStatusCard.tsx:12`, `apps/dashboard/src/features/auth/AuthSessionWizard.tsx:41`, `apps/dashboard/src/features/auth/StartAuthForm.tsx:17`, `apps/dashboard/src/features/auth/SubmitCodeForm.tsx:14`, `apps/dashboard/src/features/auth/SubmitPasswordForm.tsx:14`, `apps/dashboard/src/features/account-import/ImportBatchPage.tsx:52`, `apps/dashboard/src/features/account-import/ImportUploadForm.tsx:47`, `apps/dashboard/src/features/account-import/ImportPreviewTable.tsx:45`
- что не так: primary UI показывает `TDLib auth foundation`, `Submit Telegram code`, `2FA required`, `cooldown active`, `Preview account packages`, `tdlib-directory`, `session-file`, `unknown`, `pending`.
- почему важно: пользовательский SaaS flow должен быть на русском и не показывать raw enum/source values.
- конкретное исправление: добавить русские label maps для auth/import statuses/source types; перевести headings, descriptions, placeholders, buttons, errors.
- тест: component/unit test на отсутствие raw enum/source values в Add Accounts DOM.

### Finding: P1 - Account Risk tab exposes raw backend state/details in primary UI
- severity: P1
- файл: `apps/dashboard/src/components/dashboard/accountWorkspace/AccountRiskTab.tsx:37`, `apps/dashboard/src/components/dashboard/accountWorkspace/AccountRiskTab.tsx:38`, `apps/dashboard/src/components/dashboard/accountWorkspace/AccountRiskTab.tsx:39`, `apps/dashboard/src/components/dashboard/accountWorkspace/AccountRiskTab.tsx:106`
- что не так: readiness details напрямую показывают `accountState`, `runtimeHealth`, `proxyStatus`, а также JSON с `status`, `error_code`, `details`, `result`.
- почему важно: primary Risk & Audit flow должен объяснять риск по-русски и давать next action, а не показывать raw enums/debug payload.
- конкретное исправление: использовать `labelAccountState`, `labelRuntimeHealth`, `labelProxyStatus`; raw JSON перенести в явно свернутый блок "Расширенная диагностика".
- тест: unit test на отсутствие `execution_usable`, `ready`, `failed`, `unknown` в primary render.

### Finding: P1 - runtime health readiness checks mismatch backend values
- severity: P1
- файл: `apps/dashboard/src/components/dashboard/accountWorkspace/AccountHeader.tsx:52`, `apps/dashboard/src/components/dashboard/accountWorkspace/AccountRiskTab.tsx:38`
- что не так: UI считает healthy только `runtime_health === "ready"`, хотя backend/local data использует `ok` в health/diagnostics contexts.
- почему важно: здоровый аккаунт может отображаться как neutral/not ready, что ломает trust в Risk & Safety UX.
- конкретное исправление: нормализовать runtime health в одном mapper/helper: `ok` и `ready` должны попадать в один пользовательский статус "Готов".
- тест: unit test для `labelRuntimeHealth` и AccountHeader tone для `ok`.

### Finding: P1 - Proxy form still looks like raw/debug UI
- severity: P1
- файл: `apps/dashboard/src/components/dashboard/accountWorkspace/WorkspacePanels.tsx:81`, `apps/dashboard/src/components/dashboard/accountWorkspace/WorkspacePanels.tsx:89`, `apps/dashboard/src/components/dashboard/accountWorkspace/WorkspacePanels.tsx:93`, `apps/dashboard/src/components/dashboard/accountWorkspace/WorkspacePanels.tsx:97`
- что не так: форма использует raw `<select>/<input>`, placeholders `host`, `username`, `password`, текст "Сеть и Proxy"; нет обязательной подсказки "Оставьте пустым, чтобы не менять пароль".
- почему важно: Proxy внутри аккаунта - sensitive flow; сырой UI повышает риск неверного ввода и недоверия.
- конкретное исправление: перейти на `@stylisttg/ui` `Select/Input/FormField/FieldHint`; русифицировать labels/placeholders; явно объяснить поведение пароля.
- тест: component test: password не отображается обратно, password не сохраняется в storage, helper text виден.

### Finding: P1 - bulk account toolbar exposes actions that appear enabled but do nothing
- severity: P1
- файл: `apps/dashboard/src/features/accounts/AccountsTableToolbar.tsx:48`, `apps/dashboard/src/features/accounts/AccountsTableToolbar.tsx:52`, `apps/dashboard/src/features/accounts/AccountsTableToolbar.tsx:56`
- что не так: bulk buttons "Обновить риск", "Запустить аудит", "Проверить готовность" включаются при selection, но не имеют handlers.
- почему важно: UI выглядит как production action, но пользователь нажимает пустую кнопку. Для risk/safety flows это особенно плохо.
- конкретное исправление: либо подключить безопасные backend-backed actions, либо оставить disabled с русским reason/tooltip "Скоро".
- тест: component test: bulk actions disabled when unsupported and show reason.

### Finding: P1 - Accounts saved view localStorage key is not scoped
- severity: P1
- файл: `apps/dashboard/src/features/accounts/AccountsTable.tsx:38`, `apps/dashboard/src/features/accounts/AccountsTable.tsx:46`
- что не так: view хранится в `stylisttg_accounts_view` без workspace/user scope.
- почему важно: настройки одного workspace/user могут протечь в другой контекст на том же браузере.
- конкретное исправление: включить workspace id/user id/app env в key или хранить через scoped preferences layer.
- тест: unit test для key builder и reset behavior.

### Finding: P1 - Accounts lacks a mobile card-list implementation
- severity: P1
- файл: `apps/dashboard/src/features/accounts/AccountsTable.tsx:113`
- что не так: компонент рендерит table layout; отдельного mobile card-list flow не найдено.
- почему важно: Accounts Platform должна быть usable на mobile; таблица с множеством колонок деградирует.
- конкретное исправление: добавить responsive card list для small screens или скрытые колонки + карточки.
- тест: Browser QA mobile Accounts screenshot.

### Finding: P1 - Home uses static/foundation values instead of backend-backed overview
- severity: P1
- файл: `apps/dashboard/src/features/home/HomePage.tsx:31`, `apps/dashboard/src/features/home/HomePage.tsx:46`, `apps/dashboard/src/features/home/HomePage.tsx:58`, `apps/dashboard/src/features/home/HomePage.tsx:94`
- что не так: cards показывают `--`, "Работает", "Подключено", future modules; risk/system/active work не backend-backed.
- почему важно: Home должен говорить "что делать дальше", а не быть декоративной заглушкой.
- конкретное исправление: подключить safe diagnostics/risk/jobs summary endpoints; для отсутствующих данных показывать честный empty/degraded state.
- тест: Home component/browser tests для empty workspace, degraded health, risk summary.

### Finding: P1 - legacy auth/bulk flow can retain sensitive values longer than necessary
- severity: P1
- файл: `apps/dashboard/src/components/auth/BulkAuthScreen.tsx:482`, `apps/dashboard/src/components/auth/BulkAuthScreen.tsx:270`, `apps/dashboard/src/components/auth/BulkAuthScreen.tsx:69`
- что не так: credential row держит OTP/2FA input in React state до component lifecycle; bulk draft сохраняет raw phone list в localStorage.
- почему важно: OTP/2FA/password/session-sensitive data должны очищаться сразу после submit и не попадать в persistent browser storage. Phone list не OTP, но это все равно sensitive account data.
- конкретное исправление: после submit очищать input value; не сохранять raw phone list в localStorage или хранить только user-confirmed draft с явным warning/expiry.
- тест: unit/component test: submit clears credential input; localStorage не содержит OTP/2FA/password.

### Finding: P1 - Settings exposes technical mode labels in primary UI
- severity: P1
- файл: `apps/dashboard/src/features/settings/SettingsPage.tsx:65`, `apps/dashboard/src/features/settings/SettingsPage.tsx:105`
- что не так: primary Settings показывает `mock` и англоязычный "TDLib live execution".
- почему важно: обычный SaaS user не должен видеть raw runtime enum вне advanced/diagnostics.
- конкретное исправление: заменить на "Безопасный mock-режим" / "Live-режим выключен"; raw fields только внутри advanced block.
- тест: Russian UI test for Settings primary render.

### Finding: P1 - Design system exists but primary app still bypasses primitives
- severity: P1
- файл: `packages/ui/src/index.ts`, `apps/dashboard/src/components/dashboard/accountWorkspace/WorkspacePanels.tsx:81`, `apps/dashboard/src/features/accounts/accountColumns.tsx:19`, `apps/dashboard/src/components/dashboard/profile/StoriesBlock.tsx:278`
- что не так: `packages/ui` экспортирует нужные primitives, но core forms/table controls продолжают использовать raw inputs/selects/buttons.
- почему важно: из-за этого accessibility, states, density и visual language расходятся между страницами.
- конкретное исправление: мигрировать primary forms/tables на `Input`, `Select`, `Checkbox`, `Button`, `FormField`, `FieldHint`, `TableToolbar`.
- тест: smoke/component tests для disabled/loading/error states и aria labels.

### Finding: P1 - Browser QA scenarios are still old/operator-oriented
- severity: P1
- файл: `apps/dashboard/e2e/saas-shell.spec.ts:11`, `apps/dashboard/e2e/saas-shell.spec.ts:26`, `apps/dashboard/e2e/saas-shell.spec.ts:33`, `apps/dashboard/e2e/saas-shell.spec.ts:236`
- что не так: e2e ожидает English/operator labels and `/proxy` primary page.
- почему важно: даже после build fix QA будет валидировать старую модель, а не новый Accounts-first SaaS.
- конкретное исправление: обновить QA на Home desktop/mobile, Accounts filters, Add Accounts, Account Profile, Proxy tab inside account, Risk tab, Health, Settings, Billing placeholder.
- тест: сам обновленный Playwright suite.

## P2 Improvements

### Finding: P2 - Billing nav is hidden on mobile
- severity: P2
- файл: `apps/dashboard/src/app/AppShell.tsx`
- что не так: desktop показывает disabled "Биллинг", mobile navigation фильтрует disabled items.
- почему важно: desktop/mobile IA расходятся.
- конкретное исправление: показывать disabled Billing и на mobile или осознанно документировать отличие.
- тест: AppShell mobile nav test.

### Finding: P2 - clickable account table rows are not keyboard-friendly
- severity: P2
- файл: `apps/dashboard/src/features/accounts/AccountsTable.tsx:122`
- что не так: `<tr onClick>` открывает аккаунт, но нет role/tabIndex/keyboard handler или явной link cell.
- почему важно: accessibility и keyboard navigation.
- конкретное исправление: сделать имя аккаунта ссылкой на account profile или добавить keyboard-supported row action.
- тест: component test for Enter/Space navigation.

### Finding: P2 - motion components live in app layer, not the shared UI package
- severity: P2
- файл: `apps/dashboard/src/components/ui/MotionProvider.tsx`, `apps/dashboard/src/components/ui/AnimatedPage.tsx`, `apps/dashboard/src/components/ui/AnimatedDialog.tsx`, `apps/dashboard/src/lib/motion.ts`
- что не так: motion foundation есть, но находится внутри dashboard, а не `packages/ui`.
- почему важно: если это часть design system, другие apps/packages не смогут переиспользовать presets consistently.
- конкретное исправление: после стабилизации build перенести generic animated primitives/presets в `packages/ui` или задокументировать их app-local статус.
- тест: build/type tests for exported motion primitives if moved.

### Finding: P2 - Future module labels on Home are English
- severity: P2
- файл: `apps/dashboard/src/features/home/HomePage.tsx:94`
- что не так: "Campaigns & Warmup", "AI Replies", "Billing & Analytics" в русскоязычном primary UI.
- почему важно: нарушает единый tone, хотя модули пока locked/future.
- конкретное исправление: заменить на "Кампании и прогрев", "AI-ответы", "Биллинг и аналитика".
- тест: Russian UI snapshot/string test.

## Route audit
Expected model partially exists:
- `/` redirects to `/home` in `apps/dashboard/src/router.tsx`.
- `/home` exists.
- `/accounts` exists.
- `/accounts/:accountId/profile`, `/stories`, `/music`, `/proxy`, `/jobs`, `/risk` exist.
- `/health`, `/jobs`, `/settings` exist.
- Operations and Proxy Center are removed from `primaryNavigation`.

Failed items:
- `appRoutes.accounts()` still returns `/`, so main navigation breaks Accounts.
- `/accounts/add` is missing; current flow is `/auth/batch`.
- Browser QA still treats `/proxy` as a primary route.

## Russian UI audit
Passed in main shell navigation and many account labels. Failed in Add Accounts/auth/import, Settings runtime labels, Home future modules, and Risk raw detail rendering.

Raw enum/source leakage found in primary or near-primary flows:
- `tdlib-directory`, `session-file`, `unknown`, `pending`
- `mock`
- `accountState`, `runtimeHealth`, `proxyStatus` raw details in Risk tab
- JSON diagnostic snippets inside Account Workspace panels

## Design system audit
`packages/ui/src/index.ts` exports the expected primitives: Input, Textarea, Select, Checkbox, Switch, Tabs, Dialog, DropdownMenu, Tooltip, Alert, Skeleton, MetricCard, PageShell, SidebarNav, TopBar, TableToolbar, FormField, FieldError, FieldHint, StickyActionBar, Risk components.

The boundary is not yet clean enough: primary app screens still use one-off raw controls and classes in account workspace, stories/music blocks and accounts table controls. No generic primitive with product-specific Russian text was found in the inspected `packages/ui/src/index.ts` export surface.

## Motion audit
Good:
- `motion` package is used.
- imports are from `motion/react`.
- `MotionProvider` uses `MotionConfig reducedMotion="user"`.
- durations are intended to be 150-300ms.

Issues:
- build currently fails in motion-related files (`AnimatedDialog`, `AnimatedTabs`, `lib/motion.ts`).
- motion primitives are app-local, not shared design system.
- `lib/motion.ts` contains an unsafe easing cast that TypeScript rejects.

## Accounts Platform audit
Good:
- `/accounts` page exists.
- TanStack Table is used.
- Search/filter/view foundations exist.
- Checkbox click stops row navigation.
- Risk/proxy/runtime/job columns exist.

Failed:
- Primary nav does not open `/accounts`.
- bulk buttons appear actionable but do nothing.
- saved view key is not workspace scoped.
- mobile card-list implementation was not found.
- row navigation lacks keyboard path.

## Account Workspace audit
Good:
- Account Workspace route exists.
- First section is Profile.
- Tabs include Профиль, Истории, Музыка, Прокси, Задачи, Риск и аудит.
- Proxy is inside account workspace.
- Profile uses TanStack Form foundation.

Issues:
- runtime readiness mismatch (`ready` vs `ok`).
- Proxy form still raw/debug-style.
- Risk tab exposes raw enum/details.
- Real execution group titles include English `Profile/Music/Stories`.
- Build failures affect ProfilePanels/animated UI.

## Add Accounts audit
Good:
- single auth wizard foundation exists.
- bulk auth screen exists.
- import preview foundation exists.
- new auth code/password forms clear their local state after submit.

Issues:
- canonical `/accounts/add` route missing.
- Add Accounts UI still has English copy.
- import source/status values are raw.
- legacy bulk/auth flow keeps phone batch draft in localStorage and credential inputs until component lifecycle.
- old `BatchImportForm` and new `ImportBatchPage` source-type language can confuse users.

## Risk & Safety audit
Good:
- risk is visible in Accounts table.
- risk is visible in AccountHeader.
- Health Center has account risk summary.
- Risk & Audit tab exists.
- `packages/ui` has Risk/Safety components.

Issues:
- Home risk summary is not backend-backed.
- AccountRiskTab exposes raw values and JSON.
- cooldown/action gate UX is not yet strong enough in bulk actions.
- high-risk bulk toolbar actions appear enabled without real gated behavior.

## Security audit
No tracked `.env.cloud.local`, `node_modules`, Playwright artifacts, storage files or TDLib session files were found via `git ls-files` scan.

Frontend risks:
- new auth forms clear code/password after submit, but legacy bulk credential row keeps value in component state until unmount.
- bulk phone list is persisted in localStorage under `AUTH_BATCH_DRAFT_STORAGE_KEY`.
- proxy password is not stored in localStorage/sessionStorage in inspected code, but Proxy UI lacks the required explicit "leave blank" copy and should clear password state after successful save.
- diagnostics reviewed here did not show DB/Redis/S3 URLs or API hash in primary Health Center, but raw diagnostic JSON in Account Workspace should remain advanced-only.

## Test coverage audit
Existing unit tests pass: 190 dashboard tests, 10 api-client tests, 1 ui test.

Coverage gaps/blockers:
- tests still expect Accounts route to be `/`.
- no route test catches primary nav href for Accounts.
- Browser QA is stale and cannot run while build is broken.
- raw enum protection exists at mapper level, but primary DOM tests do not cover Add Accounts/import/Risk tab leakage.
- missing tests for `/accounts/add`, Account Workspace profile-first route, mobile Accounts card-list, auth secret non-persistence in legacy bulk flow, and no Operations/Proxy Center in browser primary nav.

## Validation results
Frontend:
- `npm run lint`: pass after two obvious unused-code fixes.
- `npm test`: pass, 31 dashboard test files / 190 tests plus package tests.
- `npm run build`: fail, TypeScript errors in dashboard.
- `npm run qa:browser`: fail, Playwright webServer cannot start because build fails.
- `npm run qa:screenshots`: fail, Playwright webServer cannot start because build fails.
- `npm run check:api`: pass, OpenAPI generated artifacts are current.

Backend sanity:
- `python -m alembic heads`: pass, `20260503_0022 (head)`.
- `python -m ruff check .`: pass.
- `python -m pytest -q`: pass, `332 passed, 2 skipped`.
- `python -m compileall app`: pass.

## Recommended next PRs
1. Fix P0 Build + Route Contract PR: repair TypeScript build, set `appRoutes.accounts()` to `/accounts`, add `/accounts/add`, update unit/e2e route tests.
2. Russian Primary Flows PR: fully translate Add Accounts/auth/import/Settings/Home future modules and add DOM tests that block raw enum/source leakage.
3. Accounts Platform Interaction PR: wire or disable bulk actions, scope saved views, add mobile card-list and keyboard-accessible account row navigation.
4. Account Workspace Safety UX PR: normalize readiness statuses, harden Proxy form, move raw diagnostics under advanced blocks, improve risk/cooldown/action gate copy.
5. Browser QA 2.0 PR: rewrite Playwright coverage for Home, Accounts, Add Accounts, Account Profile/Proxy/Risk, Health, Settings, Billing placeholder and mobile shell.

Final decision: REQUEST CHANGES
