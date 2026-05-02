import { apiRequest } from '@/lib/http'
import type { ApiError } from '@/lib/http'
import { labelIssue } from '@/lib/uiLabels'

const RUNTIME_REFRESH_TIMEOUT_MS = 45000
const ACCOUNT_STORAGE_KEY = 'stylisttg.account_id'

export type AuthPhase =
  | 'auth-loading'
  | 'auth-phone'
  | 'auth-code'
  | 'auth-password'
  | 'auth-refreshing'
  | 'dashboard'
  | 'auth-error'

export type AuthStateResponse = {
  account_id: string
  external_ref: string
  telegram_user_id: string | null
  orchestration_state: string
  auth_step_status: string
  needs_code: boolean
  needs_password: boolean
  password_hint: string | null
  session_present: boolean
  runtime_health: string
  reauth_required: boolean
  recovery_marker: string | null
  authorized_last_confirmed_at: string | null
  error: string | null
}

export type AuthErrorMessage = {
  title: string
  description: string
}

export type AuthRuntimeMode = {
  tdlib_use_test_dc: boolean
  tdlib_production_auth_enabled: boolean
}

export function readStoredAccountId(storage: Pick<Storage, 'getItem'> | null): string | null {
  return storage?.getItem(ACCOUNT_STORAGE_KEY) ?? null
}

export function persistAccountId(
  storage: Pick<Storage, 'setItem'> | null,
  accountId: string,
): void {
  storage?.setItem(ACCOUNT_STORAGE_KEY, accountId)
}

export function clearStoredAccountId(storage: Pick<Storage, 'removeItem'> | null): void {
  storage?.removeItem(ACCOUNT_STORAGE_KEY)
}

export function shouldRunAuthBootstrap(accountId: string | null, phase: AuthPhase): boolean {
  if (!accountId) return false
  return ['auth-loading', 'auth-code', 'auth-password', 'auth-error', 'auth-refreshing'].includes(phase)
}

export function nextAuthPhaseFromState(state: AuthStateResponse): AuthPhase {
  if (state.orchestration_state === 'execution_usable' || state.orchestration_state === 'authorized_ready') {
    return 'dashboard'
  }

  if (state.orchestration_state === 'awaiting_password' || state.needs_password) {
    return 'auth-password'
  }

  if (state.orchestration_state === 'awaiting_code' || state.needs_code) {
    return 'auth-code'
  }

  return 'auth-phone'
}

export function shouldClearStoredAccountForAuthState(state: AuthStateResponse): boolean {
  return (
    state.orchestration_state === 'runtime_broken' &&
    !state.needs_code &&
    !state.needs_password &&
    !state.session_present
  )
}

export function buildAuthErrorMessage(error: ApiError): AuthErrorMessage {
  if (
    error.error_code === 'REQUEST_VALIDATION_ERROR' &&
    error.field_errors.some((fieldError) => fieldError.field === 'phone_number')
  ) {
    return {
      title: 'Проверьте номер телефона',
      description:
        error.field_errors.find((fieldError) => fieldError.field === 'phone_number')?.message ?? error.message,
    }
  }

  if (
    error.error_code === 'REQUEST_VALIDATION_ERROR' &&
    error.field_errors.some((fieldError) => fieldError.field === 'code')
  ) {
    return {
      title: 'Проверьте код подтверждения',
      description:
        error.field_errors.find((fieldError) => fieldError.field === 'code')?.message ?? error.message,
    }
  }

  if (error.error_code === 'ACCOUNT_NOT_FOUND') {
    return {
      title: 'Аккаунт не найден',
      description: 'Сессия не найдена. Начните вход заново.',
    }
  }

  if (error.error_code === 'UNSUPPORTED_AUTH_BRANCH') {
    return {
      title: 'Этот способ входа пока не поддерживается',
      description: 'Продолжить можно только через OTP-код.',
    }
  }

  if (error.error_code === 'NETWORK_ERROR') {
    return {
      title: 'Не удалось связаться с сервером',
      description: 'Проверьте подключение и попробуйте ещё раз.',
    }
  }

  return {
    title: labelIssue(error.error_code),
    description: error.message,
  }
}

export async function startOtp(phoneNumber: string): Promise<AuthStateResponse> {
  return apiRequest<AuthStateResponse>('/api/auth/otp/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      phone_number: phoneNumber,
    }),
  })
}

export async function confirmOtp(accountId: string, code: string): Promise<AuthStateResponse> {
  return apiRequest<AuthStateResponse>('/api/auth/otp/confirm', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      account_id: accountId,
      code,
    }),
  })
}

export async function submitPassword(accountId: string, password: string): Promise<AuthStateResponse> {
  return apiRequest<AuthStateResponse>('/api/auth/password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      account_id: accountId,
      password,
    }),
  })
}

export async function fetchAuthState(accountId: string): Promise<AuthStateResponse> {
  return apiRequest<AuthStateResponse>('/api/accounts/auth-state', {
    headers: { 'X-Account-Id': accountId },
  })
}

export async function fetchAuthRuntimeMode(): Promise<AuthRuntimeMode> {
  return apiRequest<AuthRuntimeMode>('/api/auth/runtime-mode')
}

export async function updateAuthRuntimeMode(tdlibUseTestDc: boolean): Promise<AuthRuntimeMode> {
  return apiRequest<AuthRuntimeMode>('/api/auth/runtime-mode', {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      tdlib_use_test_dc: tdlibUseTestDc,
    }),
  })
}

export async function refreshAuthRuntime(accountId: string): Promise<{
  account_id: string
  account_state: string
  is_execution_usable: boolean
}> {
  return apiRequest('/api/accounts/refresh-runtime', {
    method: 'POST',
    headers: { 'X-Account-Id': accountId },
    timeoutMs: RUNTIME_REFRESH_TIMEOUT_MS,
  })
}
