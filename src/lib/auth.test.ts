import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  buildAuthErrorMessage,
  nextAuthPhaseFromState,
  resolveInitialAccountId,
  shouldClearStoredAccountForAuthState,
  shouldRunAuthBootstrap,
  type AuthStateResponse,
} from '@/lib/auth'
import type { ApiError } from '@/lib/dashboard'

describe('resolveInitialAccountId', () => {
  it('prefers query parameter over local storage and env fallback', () => {
    expect(resolveInitialAccountId('?account_id=query-id', 'stored-id', 'env-id')).toBe('query-id')
  })

  it('uses local storage when query parameter is absent', () => {
    expect(resolveInitialAccountId('', 'stored-id', 'env-id')).toBe('stored-id')
  })

  it('falls back to env when query and local storage are empty', () => {
    expect(resolveInitialAccountId('', null, 'env-id')).toBe('env-id')
  })
})

describe('syncAccountIdQueryParam', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('removes account_id from the visible url after bootstrap', async () => {
    const { syncAccountIdQueryParam } = await import('@/lib/auth')
    let href = 'http://localhost:5173/?account_id=legacy-id&tab=profile'
    vi.stubGlobal('window', {
      get location() {
        return new URL(href)
      },
      history: {
        replaceState: (_state: unknown, _title: string, url: URL) => {
          href = url.toString()
        },
      },
    })

    syncAccountIdQueryParam('account-1')

    expect(window.location.search).toBe('?tab=profile')
  })
})

describe('shouldRunAuthBootstrap', () => {
  it('does not bootstrap without an account id', () => {
    expect(shouldRunAuthBootstrap(null, 'dashboard')).toBe(false)
  })

  it('does not interrupt account list, phone auth, or batch auth screens', () => {
    expect(shouldRunAuthBootstrap('acc-1', 'account-list')).toBe(false)
    expect(shouldRunAuthBootstrap('acc-1', 'auth-phone')).toBe(false)
    expect(shouldRunAuthBootstrap('acc-1', 'auth-batch')).toBe(false)
  })

  it('runs bootstrap for transitional auth phases only', () => {
    expect(shouldRunAuthBootstrap('acc-1', 'auth-loading')).toBe(true)
    expect(shouldRunAuthBootstrap('acc-1', 'auth-code')).toBe(true)
    expect(shouldRunAuthBootstrap('acc-1', 'auth-password')).toBe(true)
    expect(shouldRunAuthBootstrap('acc-1', 'dashboard')).toBe(false)
  })
})

describe('nextAuthPhaseFromState', () => {
  it('routes awaiting_code accounts into the code step', () => {
    const state: AuthStateResponse = {
      account_id: 'acc-1',
      external_ref: '+15550102000',
      telegram_user_id: null,
      orchestration_state: 'awaiting_code',
      auth_step_status: 'wait_code',
      needs_code: true,
      needs_password: false,
      password_hint: null,
      session_present: true,
      runtime_health: 'awaiting_code',
      reauth_required: false,
      recovery_marker: 'wait-code',
      authorized_last_confirmed_at: null,
      error: null,
    }

    expect(nextAuthPhaseFromState(state)).toBe('auth-code')
  })

  it('routes awaiting_password accounts into the password step', () => {
    const state: AuthStateResponse = {
      account_id: 'acc-1',
      external_ref: '+15550102000',
      telegram_user_id: null,
      orchestration_state: 'awaiting_password',
      auth_step_status: 'wait_password',
      needs_code: false,
      needs_password: true,
      password_hint: 'my hint',
      session_present: true,
      runtime_health: 'awaiting_password',
      reauth_required: false,
      recovery_marker: 'wait-password',
      authorized_last_confirmed_at: null,
      error: null,
    }

    expect(nextAuthPhaseFromState(state)).toBe('auth-password')
  })

  it('routes authorized accounts into the dashboard', () => {
    const state: AuthStateResponse = {
      account_id: 'acc-1',
      external_ref: '+15550102000',
      telegram_user_id: 'tg-1',
      orchestration_state: 'authorized_ready',
      auth_step_status: 'ready',
      needs_code: false,
      needs_password: false,
      password_hint: null,
      session_present: true,
      runtime_health: 'ready',
      reauth_required: false,
      recovery_marker: 'ready',
      authorized_last_confirmed_at: '2026-04-23T12:00:00Z',
      error: null,
    }

    expect(nextAuthPhaseFromState(state)).toBe('dashboard')
  })

  it('routes unsupported or broken auth states back to the phone step', () => {
    const state: AuthStateResponse = {
      account_id: 'acc-1',
      external_ref: '+15550102000',
      telegram_user_id: null,
      orchestration_state: 'runtime_broken',
      auth_step_status: 'unsupported',
      needs_code: false,
      needs_password: false,
      password_hint: null,
      session_present: false,
      runtime_health: 'broken',
      reauth_required: true,
      recovery_marker: 'unsupported',
      authorized_last_confirmed_at: null,
      error: 'unsupported auth branch',
    }

    expect(nextAuthPhaseFromState(state)).toBe('auth-phone')
  })
})

describe('buildAuthErrorMessage', () => {
  it('formats validation errors for phone number input', () => {
    const error: ApiError = {
      error_code: 'REQUEST_VALIDATION_ERROR',
      error_class: 'validation',
      message: 'request validation failed',
      details: null,
      field_errors: [{ field: 'phone_number', message: 'invalid format' }],
      request_id: 'req-1',
    }

    expect(buildAuthErrorMessage(error)).toEqual({
      title: 'Проверьте номер телефона',
      description: 'invalid format',
    })
  })

  it('formats account not found and unsupported auth errors for users', () => {
    const notFound: ApiError = {
      error_code: 'ACCOUNT_NOT_FOUND',
      error_class: 'not_found',
      message: 'account not found',
      details: null,
      field_errors: [],
      request_id: 'req-2',
    }

    const unsupported: ApiError = {
      error_code: 'UNSUPPORTED_AUTH_BRANCH',
      error_class: 'runtime',
      message: 'unsupported auth branch',
      details: null,
      field_errors: [],
      request_id: 'req-3',
    }

    expect(buildAuthErrorMessage(notFound)).toEqual({
      title: 'Аккаунт не найден',
      description: 'Сессия не найдена. Начните вход заново.',
    })
    expect(buildAuthErrorMessage(unsupported)).toEqual({
      title: 'Этот способ входа пока не поддерживается',
      description: 'Продолжить можно только через OTP-код.',
    })
  })
})

describe('shouldClearStoredAccountForAuthState', () => {
  it('clears stale runtime-broken accounts that cannot continue auth', () => {
    expect(
      shouldClearStoredAccountForAuthState({
        account_id: 'acc-1',
        external_ref: '+15550102000',
        telegram_user_id: null,
        orchestration_state: 'runtime_broken',
        auth_step_status: 'runtime_broken',
        needs_code: false,
        needs_password: false,
        password_hint: null,
        session_present: false,
        runtime_health: 'unexpected_auth_state',
        reauth_required: false,
        recovery_marker: 'tdlib_unexpected:authorizationStateLoggingOut',
        authorized_last_confirmed_at: null,
        error: null,
      }),
    ).toBe(true)
  })
})
