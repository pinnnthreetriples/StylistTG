import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('SaaS shell loads and captures the primary pages', async ({ page, isMobile }, testInfo) => {
  test.skip(isMobile, 'desktop navigation is covered by the chromium project')
  await page.goto('/')
  await expect(page.getByText('StylistTG').first()).toBeVisible()
  await expect(page.getByText('Workspace: Staging Ops')).toBeVisible()
  await expect(page.getByText('TDLib live-disabled')).toBeVisible()
  await expect(page.getByText('Account Risk')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('saas-shell-dashboard.png'), fullPage: true })

  await expect(page.getByText('Demo Account').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('accounts-page.png'), fullPage: true })

  await page.goto('/health')
  await expect(page.getByRole('heading', { name: 'Runtime Readiness' })).toBeVisible()
  await expect(page.getByText('Account risk summary')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('health-center.png'), fullPage: true })

  await page.goto('/jobs')
  await expect(page.getByRole('heading', { name: 'Worker Activity' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('jobs-page.png'), fullPage: true })

  await page.goto('/proxy')
  await expect(page.getByRole('heading', { name: 'Proxy Inventory' })).toBeVisible()

  await page.goto('/settings')
  await expect(page.getByRole('button', { name: 'Настройки', exact: true })).toBeVisible()
})

test('mobile shell renders without a blank screen', async ({ page, isMobile }, testInfo) => {
  test.skip(!isMobile, 'mobile screenshot is covered by the mobile project')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.goto('/health')
  await expect(page.getByRole('heading', { name: 'Runtime Readiness' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('mobile-shell.png'), fullPage: true })
})

async function mockApi(page: Page) {
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
        tdlib: { status: 'not_configured', profile_execution_adapter: 'mock', live_enabled: false },
        workers: { queues: ['profile_jobs', 'auth_jobs'], mode: 'redis_rq' },
        generated_at: '2026-05-03T00:00:00Z',
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
  for (const path of ['/jobs', '/proxy', '/settings']) {
    await page.route(`**${path}`, (route) =>
      route.request().resourceType() === 'document'
        ? route.fulfill({ path: 'dist/index.html', contentType: 'text/html' })
        : route.continue(),
    )
  }
}
