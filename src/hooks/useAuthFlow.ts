/**
 * useAuthFlow – manages the full Telegram OTP/password authentication lifecycle.
 *
 * Extracted from App.tsx to keep auth state isolated and testable.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type React from 'react'

import { normalizeError } from '@/lib/appErrors'
import {
  buildAuthErrorMessage,
  clearStoredAccountId,
  confirmOtp,
  fetchAuthRuntimeMode,
  fetchAuthState,
  nextAuthPhaseFromState,
  persistAccountId,
  refreshAuthRuntime,
  startOtp,
  submitPassword,
  updateAuthRuntimeMode,
  type AuthErrorMessage,
  type AuthPhase,
  type AuthStateResponse,
} from '@/lib/auth'

export type { AuthPhase, AuthErrorMessage, AuthStateResponse }

export interface AuthFlowResult {
  // ── State ──────────────────────────────────────────────────────────────────
  authPhase: AuthPhase
  authStep: 'phone' | 'code' | 'password'
  phoneNumber: string
  otpCode: string
  twoFaPassword: string
  passwordHint: string | null
  authError: AuthErrorMessage | null
  authErrorCode: string | null
  testDcEnabled: boolean
  isUpdatingTestDc: boolean
  accountId: string | null

  // ── Setters (for controlled inputs) ───────────────────────────────────────
  setPhoneNumber: (v: string) => void
  setOtpCode: (v: string) => void
  setTwoFaPassword: (v: string) => void
  setAuthPhase: React.Dispatch<React.SetStateAction<AuthPhase>>
  setAccountId: React.Dispatch<React.SetStateAction<string | null>>
  setAuthError: React.Dispatch<React.SetStateAction<AuthErrorMessage | null>>
  setAuthErrorCode: React.Dispatch<React.SetStateAction<string | null>>
  setAuthStep: React.Dispatch<React.SetStateAction<'phone' | 'code' | 'password'>>

  // ── Actions ────────────────────────────────────────────────────────────────
  handleStartOtp: () => Promise<void>
  handleConfirmOtp: () => Promise<void>
  handleSubmitPassword: () => Promise<void>
  handleResetAuthPhone: () => void
  handleTestDcChange: (enabled: boolean) => Promise<void>
  handleBatchTestDcChange: (enabled: boolean) => Promise<void>
  applyAuthStateResponse: (state: AuthStateResponse) => boolean
  applyAccountContext: (nextAccountId: string) => void
  clearAccountContext: () => void
}

export function useAuthFlow({
  initialAccountId,
  initialPhase,
}: {
  initialAccountId: string | null
  initialPhase: AuthPhase
}): AuthFlowResult {
  const [accountId, setAccountId] = useState<string | null>(initialAccountId)
  const [authPhase, setAuthPhase] = useState<AuthPhase>(initialPhase)
  const [authStep, setAuthStep] = useState<'phone' | 'code' | 'password'>('phone')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [twoFaPassword, setTwoFaPassword] = useState('')
  const [passwordHint, setPasswordHint] = useState<string | null>(null)
  const [authError, setAuthError] = useState<AuthErrorMessage | null>(null)
  const [authErrorCode, setAuthErrorCode] = useState<string | null>(null)
  const [testDcEnabled, setTestDcEnabled] = useState(false)
  const [isUpdatingTestDc, setIsUpdatingTestDc] = useState(false)

  // ── Fetch runtime-mode on mount (only when not already on dashboard) ────────
  useEffect(() => {
    if (authPhase === 'dashboard') return
    let cancelled = false
    fetchAuthRuntimeMode()
      .then((mode) => { if (!cancelled) setTestDcEnabled(mode.tdlib_use_test_dc) })
      .catch(() => { if (!cancelled) setTestDcEnabled(false) })
    return () => { cancelled = true }
  }, [authPhase])

  // ── Helpers ──────────────────────────────────────────────────────────────────

  const applyAccountContext = useCallback((nextAccountId: string) => {
    persistAccountId(window.localStorage, nextAccountId)
    setAccountId(nextAccountId)
  }, [])

  const clearAccountContext = useCallback(() => {
    if (accountId) clearStoredAccountId(window.localStorage)
    setAccountId(null)
  }, [accountId])

  /** Apply a raw AuthStateResponse; returns true if the user has reached the dashboard. */
  const applyAuthStateResponse = useCallback((authState: AuthStateResponse): boolean => {
    setPhoneNumber(authState.external_ref)

    if (authState.password_hint) {
      setPasswordHint(authState.password_hint)
    }

    if (
      authState.auth_step_status === 'unsupported' ||
      authState.error ||
      authState.orchestration_state === 'runtime_broken'
    ) {
      const syntheticError = {
        error_code:
          authState.auth_step_status === 'unsupported' ? 'UNSUPPORTED_AUTH_BRANCH' : 'RUNTIME_UNUSABLE',
        error_class: 'runtime',
        message: authState.error ?? 'Аккаунт пока не готов к работе.',
        details: null,
        field_errors: [],
        request_id: 'frontend-auth-state',
      }
      setAuthError(buildAuthErrorMessage(syntheticError))
      setAuthErrorCode(syntheticError.error_code)
      setAuthStep(authState.needs_password ? 'password' : authState.needs_code ? 'code' : 'phone')
      setAuthPhase('auth-error')
      return false
    }

    setAuthError(null)
    setAuthErrorCode(null)

    const nextPhase = nextAuthPhaseFromState(authState)
    if (nextPhase === 'dashboard') {
      setAuthPhase('dashboard')
      return true
    }

    if (nextPhase === 'auth-password') {
      setAuthStep('password')
    } else {
      setAuthStep(nextPhase === 'auth-code' ? 'code' : 'phone')
    }
    setAuthPhase(nextPhase)
    return false
  }, [])

  // ── Auth actions ─────────────────────────────────────────────────────────────

  const handleStartOtp = useCallback(async () => {
    setAuthPhase('auth-loading')
    try {
      const authState = await startOtp(phoneNumber)
      applyAccountContext(authState.account_id)
      setOtpCode('')
      applyAuthStateResponse(authState)
    } catch (error) {
      const normalized = normalizeError(error)
      setAuthError(buildAuthErrorMessage(normalized))
      setAuthErrorCode(normalized.error_code)
      setAuthStep('phone')
      setAuthPhase('auth-error')
    }
  }, [phoneNumber, applyAccountContext, applyAuthStateResponse])

  const handleConfirmOtp = useCallback(async () => {
    if (!accountId) return
    setAuthPhase('auth-loading')
    try {
      const result = await confirmOtp(accountId, otpCode)
      if (result.needs_password) {
        if (result.password_hint) setPasswordHint(result.password_hint)
        setAuthStep('password')
        setAuthPhase('auth-password')
        return
      }
      setAuthPhase('auth-refreshing')
      const refresh = await refreshAuthRuntime(accountId)
      if (refresh.is_execution_usable) {
        setAuthError(null)
        setAuthErrorCode(null)
        setAuthPhase('dashboard')
        return
      }
      const authState = await fetchAuthState(accountId)
      if (applyAuthStateResponse(authState)) return
      setAuthError({
        title: 'Аккаунт ещё не готов к работе',
        description: `Текущее состояние: ${authState.orchestration_state}. Повторите попытку или обновите runtime позже.`,
      })
      setAuthErrorCode('RUNTIME_UNUSABLE')
      setAuthPhase('auth-error')
    } catch (error) {
      const normalized = normalizeError(error)
      setAuthError(buildAuthErrorMessage(normalized))
      setAuthErrorCode(normalized.error_code)
      setAuthStep('code')
      setAuthPhase('auth-error')
    }
  }, [accountId, otpCode, applyAuthStateResponse])

  const handleSubmitPassword = useCallback(async () => {
    if (!accountId) return
    setAuthPhase('auth-loading')
    try {
      const authState = await submitPassword(accountId, twoFaPassword)
      if (authState.needs_password && authState.error) {
        setAuthError(buildAuthErrorMessage({
          error_code: 'WRONG_PASSWORD',
          error_class: 'auth',
          message: authState.error,
          details: null,
          field_errors: [],
          request_id: 'frontend-password',
        }))
        setAuthErrorCode('WRONG_PASSWORD')
        setAuthStep('password')
        setAuthPhase('auth-error')
        return
      }
      setAuthPhase('auth-refreshing')
      const refresh = await refreshAuthRuntime(accountId)
      if (refresh.is_execution_usable) {
        setAuthError(null)
        setAuthErrorCode(null)
        setAuthPhase('dashboard')
        return
      }
      const finalState = await fetchAuthState(accountId)
      if (applyAuthStateResponse(finalState)) return
      setAuthError({
        title: 'Аккаунт ещё не готов к работе',
        description: `Текущее состояние: ${finalState.orchestration_state}`,
      })
      setAuthErrorCode('RUNTIME_UNUSABLE')
      setAuthPhase('auth-error')
    } catch (error) {
      const normalized = normalizeError(error)
      setAuthError(buildAuthErrorMessage(normalized))
      setAuthErrorCode(normalized.error_code)
      setAuthStep('password')
      setAuthPhase('auth-error')
    }
  }, [accountId, twoFaPassword, applyAuthStateResponse])

  const handleResetAuthPhone = useCallback(() => {
    setOtpCode('')
    setTwoFaPassword('')
    setPasswordHint(null)
    setAuthError(null)
    setAuthErrorCode(null)
    setAuthStep('phone')
    setAuthPhase('auth-phone')
  }, [])

  const handleTestDcChange = useCallback(async (enabled: boolean) => {
    setIsUpdatingTestDc(true)
    setAuthError(null)
    setAuthErrorCode(null)
    try {
      const mode = await updateAuthRuntimeMode(enabled)
      setTestDcEnabled(mode.tdlib_use_test_dc)
      clearAccountContext()
      setAuthStep('phone')
      setAuthPhase('auth-phone')
      setOtpCode('')
      setTwoFaPassword('')
      setPasswordHint(null)
    } catch (error) {
      const normalized = normalizeError(error)
      setAuthError(buildAuthErrorMessage(normalized))
      setAuthErrorCode(normalized.error_code)
      setAuthPhase('auth-error')
    } finally {
      setIsUpdatingTestDc(false)
    }
  }, [clearAccountContext])

  const handleBatchTestDcChange = useCallback(async (enabled: boolean) => {
    setIsUpdatingTestDc(true)
    setAuthError(null)
    setAuthErrorCode(null)
    try {
      const mode = await updateAuthRuntimeMode(enabled)
      setTestDcEnabled(mode.tdlib_use_test_dc)
    } catch (error) {
      const normalized = normalizeError(error)
      setAuthError(buildAuthErrorMessage(normalized))
      setAuthErrorCode(normalized.error_code)
    } finally {
      setIsUpdatingTestDc(false)
    }
  }, [])

  // ── Auth bootstrap: fetch state whenever accountId changes ───────────────────

  const skipNextBootstrapRef = useRef<boolean>(false)

  return {
    authPhase,
    authStep,
    phoneNumber,
    otpCode,
    twoFaPassword,
    passwordHint,
    authError,
    authErrorCode,
    testDcEnabled,
    isUpdatingTestDc,
    accountId,
    setPhoneNumber,
    setOtpCode,
    setTwoFaPassword,
    setAuthPhase,
    setAccountId,
    setAuthError,
    setAuthErrorCode,
    setAuthStep,
    handleStartOtp,
    handleConfirmOtp,
    handleSubmitPassword,
    handleResetAuthPhone,
    handleTestDcChange,
    handleBatchTestDcChange,
    applyAuthStateResponse,
    applyAccountContext,
    clearAccountContext,
    // expose ref so App can suppress the bootstrap on first login
    _skipNextBootstrapRef: skipNextBootstrapRef,
  } as AuthFlowResult & { _skipNextBootstrapRef: React.MutableRefObject<boolean> }
}
