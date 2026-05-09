import * as Sentry from '@sentry/react'
import { beforeEach, describe, expect, test, vi, type Mock } from 'vitest'
import { initObservability } from './observability'

vi.mock('@sentry/react', () => ({
  captureException: vi.fn(),
  flush: vi.fn().mockResolvedValue(true),
  init: vi.fn(),
}))

describe('dashboard observability', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  test('stays disabled without a Better Stack DSN', () => {
    vi.stubEnv('VITE_BETTER_STACK_DASHBOARD_DSN', '')

    expect(initObservability()).toBe(false)
    expect(Sentry.init).not.toHaveBeenCalled()
  })

  test('initializes Sentry client without tracing or replay', () => {
    vi.stubEnv('VITE_BETTER_STACK_DASHBOARD_DSN', 'https://token@example.com/1')
    vi.stubEnv('VITE_APP_ENV', 'staging')
    vi.stubEnv('VITE_SENTRY_RELEASE', 'test-release')

    expect(initObservability()).toBe(true)

    const init = Sentry.init as Mock
    expect(init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: 'https://token@example.com/1',
        environment: 'staging',
        release: 'test-release',
        replaysOnErrorSampleRate: 0,
        replaysSessionSampleRate: 0,
        sendDefaultPii: false,
        tracesSampleRate: 0,
      }),
    )
  })

  test('sanitizes dashboard events without redacting diagnostic status keys', () => {
    vi.stubEnv('VITE_BETTER_STACK_DASHBOARD_DSN', 'https://token@example.com/1')

    initObservability()

    const init = Sentry.init as Mock
    const options = init.mock.calls[0][0]
    const sanitized = options.beforeSend({
      extra: {
        statusCode: 503,
        errorCode: 'ECONNREFUSED',
        barcode: 'item-1',
        b2Bucket: 'assets',
        microphone: 'available',
        s3Bucket: 'assets',
        s3SecretAccessKey: 'secret',
        sessionId: 'secret-session',
        token: 'secret-token',
      },
    })

    expect(sanitized.extra.statusCode).toBe(503)
    expect(sanitized.extra.errorCode).toBe('ECONNREFUSED')
    expect(sanitized.extra.barcode).toBe('item-1')
    expect(sanitized.extra.b2Bucket).toBe('assets')
    expect(sanitized.extra.microphone).toBe('available')
    expect(sanitized.extra.s3Bucket).toBe('assets')
    expect(sanitized.extra.s3SecretAccessKey).toBe('[Filtered]')
    expect(sanitized.extra.sessionId).toBe('[Filtered]')
    expect(sanitized.extra.token).toBe('[Filtered]')
  })

  test('redacts sensitive text without treating generic error codes as auth codes', () => {
    vi.stubEnv('VITE_BETTER_STACK_DASHBOARD_DSN', 'https://token@example.com/1')

    initObservability()

    const init = Sentry.init as Mock
    const options = init.mock.calls[0][0]
    const sanitized = options.beforeSend({
      message: 'code: 200 error code=ECONNREFUSED auth_code: 12345 phone: +79990000001',
    })

    expect(sanitized.message).toContain('code: 200')
    expect(sanitized.message).toContain('code=ECONNREFUSED')
    expect(sanitized.message).toContain('auth_code: [Filtered]')
    expect(sanitized.message).toContain('phone: [Filtered]')
  })

  test('dev test command flushes the captured frontend error', async () => {
    vi.stubEnv('VITE_BETTER_STACK_DASHBOARD_DSN', 'https://token@example.com/1')
    vi.stubGlobal('window', {})

    initObservability()

    await window.__STYLISTTG_CAPTURE_TEST_ERROR__?.()

    expect(Sentry.captureException).toHaveBeenCalledWith(expect.any(Error))
    expect(Sentry.flush).toHaveBeenCalledWith(2000)
  })
})
