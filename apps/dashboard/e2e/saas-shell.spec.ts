import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('stylisttg:e2e-auth-bypass', 'true')
  })
  await mockApi(page)
})

test('SaaS shell loads and captures the primary pages', async ({ page, isMobile }, testInfo) => {
  test.skip(isMobile, 'desktop navigation is covered by the chromium project')
  await page.goto('/')
  await expect(page.getByText('StylistTG').first()).toBeVisible()
  await expect(page).toHaveURL(/\/home$/)
  await expect(page.getByRole('heading', { name: 'Контрольная панель' })).toBeVisible()
  await expect(page.getByText('Отключён безопасно').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('saas-shell-dashboard.png'), fullPage: true })

  await page.goto('/accounts')
  await expect(page.locator('tbody tr', { hasText: 'Demo Account' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Обновить риск/ })).toBeDisabled()
  await page.screenshot({ path: testInfo.outputPath('accounts-page.png'), fullPage: true })

  await page.goto('/accounts/add')
  await expect(page.getByRole('heading', { name: 'Добавление аккаунтов' })).toBeVisible()
  await expect(page.getByText('Способ')).toBeVisible()
  await expect(page.getByText('Номера', { exact: true })).toBeVisible()
  await expect(page.getByText('JSON', { exact: true })).toBeVisible()
  await expect(page.getByText('TDLib', { exact: true })).toBeVisible()
  await expect(page.getByText('tdata', { exact: true })).toBeVisible()
  await expect(page.getByText('Session', { exact: true })).toBeVisible()
  await expect(page.getByText('Ввод или загрузка')).toBeVisible()
  await expect(page.getByRole('button', { name: /Preview/ })).toBeDisabled()

  await page.goto('/accounts/acc_1/profile')
  await expect(page.getByText('Demo Account').first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Редактирование профиля' })).toBeVisible()
  await expect(page.getByText('Профиль').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('account-profile.png'), fullPage: true })

  await page.goto('/accounts/acc_1/proxy')
  await expect(page.getByText('Сеть и прокси')).toBeVisible()
  await expect(page.getByText('Оставьте пустым, чтобы не менять пароль')).toBeVisible()

  await page.goto('/accounts/acc_1/risk')
  await expect(page.getByText('Причины риска')).toBeVisible()
  await expect(page.getByText('Готовность аккаунта')).toBeVisible()

  await page.goto('/health')
  await expect(page.getByRole('heading', { name: 'Состояние системы' })).toBeVisible()
  await expect(page.getByText('Готовность аккаунтов')).toBeVisible()
  await expect(page.getByText(/TDLib, планировщик/)).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('health-center.png'), fullPage: true })

  await page.goto('/jobs')
  await expect(page.getByRole('heading', { name: 'Задачи' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('jobs-page.png'), fullPage: true })

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'Настройки рабочей области' })).toBeVisible()
  await expect(page.getByText('Биллинг')).toBeVisible()
})

test('mobile shell renders without a blank screen', async ({ page, isMobile }, testInfo) => {
  test.skip(!isMobile, 'mobile screenshot is covered by the mobile project')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Контрольная панель' })).toBeVisible()
  await page.goto('/health')
  await expect(page.getByRole('heading', { name: 'Состояние системы' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('mobile-shell.png'), fullPage: true })
})

test('account jobs keeps hidden job panel hidden across same-route browser rerenders', async ({ page, isMobile }) => {
  test.skip(isMobile, 'desktop job panel interaction is covered by the chromium project')
  await page.addInitScript(() => {
    const testWindow = window as typeof window & { __scrollIntoViewCalls?: number }
    const originalScrollIntoView = Element.prototype.scrollIntoView
    testWindow.__scrollIntoViewCalls = 0
    Element.prototype.scrollIntoView = function scrollIntoView(...args) {
      testWindow.__scrollIntoViewCalls = (testWindow.__scrollIntoViewCalls ?? 0) + 1
      return originalScrollIntoView.apply(this, args)
    }
  })

  await page.goto('/accounts/acc_1/jobs?e2e_active_job=1')
  await expect(page.getByRole('heading', { name: 'План и выполнение' }).first()).toBeVisible()
  const scrollCallsAfterRoute = await scrollIntoViewCalls(page)

  await page.getByRole('button', { name: 'Убрать панель задачи' }).last().click()
  await expect(page.getByRole('heading', { name: 'План и выполнение' })).toHaveCount(0)
  const scrollCallsAfterHide = await scrollIntoViewCalls(page)

  await triggerSameRouteBrowserRerender(page)
  await expect(page).toHaveURL(/route_render_nonce=1/)
  await expect(page.getByRole('heading', { name: 'План и выполнение' })).toHaveCount(0)
  expect(await scrollIntoViewCalls(page)).toBe(scrollCallsAfterHide)
  expect(scrollCallsAfterHide).toBeGreaterThanOrEqual(scrollCallsAfterRoute)
})

async function scrollIntoViewCalls(page: Page): Promise<number> {
  return page.evaluate(() => {
    const testWindow = window as typeof window & { __scrollIntoViewCalls?: number }
    return testWindow.__scrollIntoViewCalls ?? 0
  })
}

async function triggerSameRouteBrowserRerender(page: Page): Promise<void> {
  await page.evaluate(() => {
    const nextUrl = new URL(window.location.href)
    nextUrl.searchParams.set('route_render_nonce', '1')
    window.history.pushState({}, '', nextUrl)
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
}

async function mockApi(page: Page) {
  const activeJobSummary = {
    job_id: 'job_active',
    job_state: 'running',
    execution_intent_hash: 'job-active-hash',
    plan_summary: ['set_name'],
    created_at: '2026-05-03T00:00:00Z',
    message: null,
  }
  const activeJobDetail = {
    job_id: 'job_active',
    job_state: 'running',
    account_id: 'acc_1',
    execution_intent_hash: 'job-active-hash',
    started_at: '2026-05-03T00:00:00Z',
    finished_at: null,
    failure_reason: null,
    can_retry: false,
    can_refresh_runtime: true,
    step_counts: { running: 1 },
  }
  const activeJobSteps = [
    {
      step_key: 'set_name',
      step_type: 'set_name',
      status: 'running',
      verification_attempted: false,
      verification_result: null,
      uncertain_reason: null,
      error_code: null,
      error_class: null,
      result_payload_json: null,
      started_at: '2026-05-03T00:00:00Z',
      finished_at: null,
    },
  ]
  const hasActiveJob = () => page.url().includes('e2e_active_job=1')
  const accounts = [
    {
      account_id: 'acc_1',
      display_name: 'Demo Account',
      username: 'demo',
      phone_number: '+15550102000',
      telegram_user_id: '777000',
      account_state: 'execution_usable',
      runtime_health: 'ready',
      is_execution_usable: true,
      is_test_dc: false,
      profile_photo_asset_id: null,
      updated_at: '2026-05-02T00:00:00Z',
    },
  ]
  const safety = [
    {
      account_id: 'acc_1',
      health_status: 'ready',
      overall_risk_level: 'low',
      validity_status: 'valid',
      proxy_status: 'none',
      capability_summary: {},
      cooldown_summary: [],
      top_reasons: [],
      last_checked_at: '2026-05-02T00:00:00Z',
      source: 'browser_qa_mock',
    },
  ]

  await page.route('**/health', (route) =>
    route.request().resourceType() === 'document'
      ? route.fulfill({ path: 'dist/index.html', contentType: 'text/html' })
      : route.fulfill({ json: { status: 'ok' } }),
  )
  await page.route('**/ready', (route) =>
    route.request().resourceType() === 'document'
      ? route.continue()
      : route.fulfill({ json: { database: 'ok', redis: 'ok', tdlib: 'not_configured' } }),
  )
  await page.route('**/diagnostics/runtime', (route) =>
    route.fulfill({ json: { database: 'ok', redis: 'ok', tdlib: 'not_configured' } }),
  )
  await page.route('**/diagnostics/live-preflight', (route) =>
    route.fulfill({
      json: {
        tdjson_present: false,
        tdlib_credentials_present: false,
        postgres_reachable: true,
        redis_reachable: true,
        storage_writable: true,
        rq_worker_expected: true,
        rq_worker_status: 'ready',
        profile_worker_status: 'ready',
        auth_worker_status: 'ready',
        overall_status: 'ok',
      },
    }),
  )
  await page.route('**/diagnostics/frontend-summary', (route) =>
    route.fulfill({
      json: {
        app_env: 'staging',
        auth_mode: 'supabase_jwt',
        db: { status: 'ok', mode: 'neon' },
        redis: { status: 'ok', configured: true },
        storage: {
          backend: 's3',
          bucket_configured: true,
          signed_url_enabled: true,
          public_base_url_configured: false,
        },
        tdlib: {
          status: 'not_configured',
          profile_execution_adapter: 'mock',
          live_enabled: false,
          runtime_mode: 'mock',
          library_configured: false,
          library_loadable: false,
          api_id_configured: false,
          api_hash_configured: false,
          auth_worker_ready: true,
          readonly_smoke_available: false,
          execution_plane_ready: false,
        },
        workers: { queues: ['profile_jobs', 'auth_jobs'], mode: 'redis_rq' },
        generated_at: '2026-05-03T00:00:00Z',
      },
    }),
  )
  await page.route('**/api/workers/diagnostics', (route) =>
    route.fulfill({
      json: {
        queues: [
          { name: 'auth_jobs', purpose: 'Telegram auth jobs', live_enabled_by_default: false },
          { name: 'profile_jobs', purpose: 'Profile jobs', live_enabled_by_default: false },
        ],
        rate_limits: { enabled: true, backend: 'redis' },
        scheduler: { enabled: false, mode: 'disabled' },
        reaper: { enabled: false, mode: 'dry_run' },
        tdlib: { live_enabled: false, adapter: 'mock', execution_plane_ready: false },
      },
    }),
  )
  await page.route('**/api/jobs/policies', (route) => route.fulfill({ json: { validation_error: { retry: false } } }))
  await page.route('**/api/tdlib/runtime', (route) =>
    route.fulfill({
      json: {
        configured: false,
        library_loadable: false,
        live_enabled: false,
        runtime_mode: 'mock',
        api_id_configured: false,
        api_hash_configured: false,
        error_code: null,
      },
    }),
  )
  await page.route('**/api/accounts/risk-summary', (route) =>
    route.fulfill({
      json: {
        total: 1,
        low: 1,
        medium: 0,
        high: 0,
        critical: 0,
        reauth_required: 0,
        missing_session: 0,
        runtime_unhealthy: 0,
        proxy_problem: 0,
        items: [
          {
            account_id: 'acc_1',
            score: 10,
            level: 'low',
            reasons: [{ code: 'ready', severity: 'info', message: 'Account is ready based on stored app signals.' }],
            recommended_action: null,
            computed_at: '2026-05-03T00:00:00Z',
          },
        ],
        computed_at: '2026-05-03T00:00:00Z',
      },
    }),
  )
  await page.route('**/api/accounts', (route) => route.fulfill({ json: accounts }))
  await page.route('**/api/accounts/acc_1/auth-state', (route) =>
    route.fulfill({
      json: {
        account_id: 'acc_1',
        authorized: true,
        branch: 'authorized',
        can_submit_code: false,
        can_submit_password: false,
        cooldown_until: null,
        display_message: 'Готов',
        last_error_code: null,
        phone_number: '+15550102000',
      },
    }),
  )
  await page.route('**/api/dashboard/profile/acc_1', (route) =>
    route.fulfill({
      json: {
        account: accounts[0],
        current_profile: {
          first_name: 'Demo',
          last_name: 'Account',
          bio: '',
          username: 'demo',
          profile_photo_asset_id: null,
        },
        diagnostics: {
          authorized_last_confirmed_at: '2026-05-03T00:00:00Z',
          last_error_class: null,
          last_error_code: null,
          real_execution_enabled: false,
          stories_live_execution_enabled: false,
        },
        editable_fields: {
          bio: '',
          name: 'Demo Account',
          profile_photo: null,
          username: 'demo',
        },
        pipeline: {
          has_active_job: hasActiveJob(),
          latest_job: hasActiveJob() ? activeJobSummary : null,
          latest_job_finished_at: null,
          latest_job_id: hasActiveJob() ? activeJobSummary.job_id : null,
          latest_job_state: hasActiveJob() ? activeJobSummary.job_state : null,
          unsaved_changes_supported: true,
        },
        profile_audio: null,
        story_posts: [],
      },
    }),
  )
  await page.route('**/api/accounts/acc_1/jobs**', (route) =>
    route.request().url().endsWith('/latest')
      ? route.fulfill({ json: hasActiveJob() ? activeJobSummary : null })
      : route.fulfill({ json: hasActiveJob() ? [activeJobSummary] : [] }),
  )
  await page.route('**/api/jobs/job_active', (route) => route.fulfill({ json: activeJobDetail }))
  await page.route('**/api/jobs/job_active/steps', (route) => route.fulfill({ json: activeJobSteps }))
  await page.route('**/api/story-drafts/acc_1', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/story-capabilities/acc_1', (route) =>
    route.fulfill({ json: { can_post: false, reason_code: 'stories_live_disabled', warnings: [] } }),
  )
  await page.route('**/api/accounts/acc_1/risk', (route) =>
    route.fulfill({
      json: {
        account_id: 'acc_1',
        score: 10,
        level: 'low',
        reasons: [],
        recommended_action: 'Аккаунт готов к работе.',
        computed_at: '2026-05-03T00:00:00Z',
      },
    }),
  )
  await page.route('**/api/accounts/acc_1/validity-checks**', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/accounts/acc_1/cooldowns', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/accounts/acc_1/proxy', (route) =>
    route.fulfill({
      json: {
        account_id: 'acc_1',
        created_at: '2026-05-03T00:00:00Z',
        has_password: true,
        host: 'proxy.example.com',
        last_check_scope: null,
        last_checked_at: null,
        last_error_code: null,
        last_error_message: null,
        port: 1080,
        proxy_type: 'socks5',
        status: 'configured',
        tdlib_last_error_code: null,
        tdlib_last_error_message: null,
        tdlib_verified_at: null,
        updated_at: '2026-05-03T00:00:00Z',
        username: 'operator',
      },
    }),
  )
  await page.route('**/api/accounts/safety-summary', (route) => route.fulfill({ json: safety }))
  await page.route('**/api/accounts/proxy-summary', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/accounts/safety-batch-preview', (route) =>
    route.fulfill({
      json: {
        operation: 'batch_operation',
        can_start: true,
        counts: { ready: 1, needs_login: 0, paused: 0, limited: 0, blocked: 0, unknown: 0 },
        blocking_account_ids: [],
        warning_account_ids: [],
        items: [],
      },
    }),
  )
  await page.route('**/api/settings/execution-policy', (route) =>
    route.fulfill({
      json: {
        profile_job_cooldown_seconds: 300,
        profile_job_cooldown_enabled: true,
        allowed_profile_job_cooldown_seconds: [60, 300],
        profile_update_cooldown_seconds: 300,
        username_cooldown_seconds: 86400,
        profile_photo_cooldown_seconds: 300,
        profile_music_cooldown_seconds: 300,
        story_post_cooldown_seconds: 300,
        story_delete_cooldown_seconds: 300,
        unknown_capability_policy: 'block_live_execution',
        recent_failure_policy: 'cooldown',
        fresh_validity_required: 'if_stale',
        fresh_validity_max_age_minutes: 30,
        manual_hard_blocker_override_enabled: false,
        non_overridable_blockers: [],
      },
    }),
  )
  await page.route('**/api/auth/runtime-mode', (route) =>
    route.fulfill({ json: { tdlib_use_test_dc: false, tdlib_production_auth_enabled: false } }),
  )
  await page.route('**/api/operation-logs?**', (route) =>
    route.fulfill({ json: { items: [], total: 0, limit: 100, offset: 0 } }),
  )
  for (const path of ['/accounts/add', '/auth/batch', '/jobs', '/settings']) {
    await page.route(`**${path}`, (route) =>
      route.request().resourceType() === 'document'
        ? route.fulfill({ path: 'dist/index.html', contentType: 'text/html' })
        : route.continue(),
    )
  }
}
