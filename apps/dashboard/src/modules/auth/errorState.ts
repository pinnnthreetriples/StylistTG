import { normalizeError } from '@/lib/appErrors'

import { buildAuthErrorMessage, type AuthErrorMessage, type AuthPhase } from './api'

type StateSetter<T> = (value: T | ((previous: T) => T)) => void
type AuthStep = 'phone' | 'code' | 'password'

export type AuthErrorSetters = {
  setAuthError: StateSetter<AuthErrorMessage | null>
  setAuthErrorCode: StateSetter<string | null>
  setAuthStep: StateSetter<AuthStep>
  setAuthPhase: StateSetter<AuthPhase>
}

export function applyNormalizedAuthError(
  error: unknown,
  step: AuthStep,
  setters: AuthErrorSetters,
) {
  const normalized = normalizeError(error)
  setters.setAuthError(buildAuthErrorMessage(normalized))
  setters.setAuthErrorCode(normalized.error_code)
  setters.setAuthStep(step)
  setters.setAuthPhase('auth-error')
}
