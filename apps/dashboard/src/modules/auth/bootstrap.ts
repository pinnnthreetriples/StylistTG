import type { QueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import type React from 'react'

import { normalizeError } from '@/lib/appErrors'
import {
  buildAuthErrorMessage,
  nextAuthPhaseFromState,
  shouldClearStoredAccountForAuthState,
  shouldRunAuthBootstrap,
  type AuthPhase,
  type AuthStateResponse,
  type AuthErrorMessage,
} from './api'
import type { ApiError } from '@/lib/http'
import type { FormState } from '@/modules/account-editing'
import { authStateQueryOptions } from '@/lib/queries'

export function useAuthBootstrap({
  accountId,
  applyAuthStateResponse,
  authPhase,
  clearAccountContext,
  dashboardReadyRef,
  formBaselineRef,
  formInitializedRef,
  formRef,
  loadDashboardState,
  queryClient,
  setApiError,
  setAuthError,
  setAuthErrorCode,
  setAuthPhase,
  setAuthStep,
  setForm,
  setIsBootRefreshing,
  setPhoneNumber,
  skipNextAuthBootstrapRef,
}: {
  accountId: string | null
  applyAuthStateResponse: (state: AuthStateResponse) => void
  authPhase: AuthPhase
  clearAccountContext: () => void
  dashboardReadyRef: React.MutableRefObject<boolean>
  formBaselineRef: React.MutableRefObject<FormState | null>
  formInitializedRef: React.MutableRefObject<boolean>
  formRef: React.MutableRefObject<FormState>
  loadDashboardState: (
    accountId: string,
    formRef: React.MutableRefObject<FormState>,
    formBaselineRef: React.MutableRefObject<FormState | null>,
    formInitializedRef: React.MutableRefObject<boolean>,
    setForm: (next: FormState) => void,
    options?: { resetForm?: boolean; quiet?: boolean; forceRefresh?: boolean },
  ) => Promise<boolean>
  queryClient: QueryClient
  setApiError: React.Dispatch<React.SetStateAction<ApiError | null>>
  setAuthError: React.Dispatch<React.SetStateAction<AuthErrorMessage | null>>
  setAuthErrorCode: React.Dispatch<React.SetStateAction<string | null>>
  setAuthPhase: React.Dispatch<React.SetStateAction<AuthPhase>>
  setAuthStep: React.Dispatch<React.SetStateAction<'phone' | 'code' | 'password'>>
  setForm: (next: FormState) => void
  setIsBootRefreshing: React.Dispatch<React.SetStateAction<boolean>>
  setPhoneNumber: (value: string) => void
  skipNextAuthBootstrapRef: React.MutableRefObject<boolean>
}) {
  useEffect(() => {
    if (!shouldRunAuthBootstrap(accountId, authPhase)) return
    const bootstrapAccountId = accountId
    if (!bootstrapAccountId) return
    if (skipNextAuthBootstrapRef.current) {
      skipNextAuthBootstrapRef.current = false
      return
    }

    let active = true
    const visualStateTimeout = window.setTimeout(() => {
      if (!active) return
      if (!dashboardReadyRef.current) {
        setAuthPhase('auth-loading')
      } else {
        setIsBootRefreshing(true)
      }
    }, 0)

    void (async () => {
      try {
        const authState = await queryClient.fetchQuery(authStateQueryOptions(bootstrapAccountId))
        if (!active) return

        if (shouldClearStoredAccountForAuthState(authState)) {
          clearAccountContext()
          setPhoneNumber(authState.external_ref)
          setAuthPhase('auth-phone')
          return
        }

        if (nextAuthPhaseFromState(authState) === 'dashboard') {
          setPhoneNumber(authState.external_ref)
          const loaded = await loadDashboardState(
            bootstrapAccountId,
            formRef,
            formBaselineRef,
            formInitializedRef,
            setForm,
          )
          if (loaded) {
            setApiError(null)
            if (active) setAuthPhase('dashboard')
          }
          return
        }

        applyAuthStateResponse(authState)
      } catch (error) {
        if (!active) return
        const normalized = normalizeError(error)
        setAuthError(buildAuthErrorMessage(normalized))
        setAuthErrorCode(normalized.error_code)
        setAuthStep('phone')
        setAuthPhase('auth-error')
      } finally {
        if (active) setIsBootRefreshing(false)
      }
    })()

    return () => {
      active = false
      window.clearTimeout(visualStateTimeout)
    }
  }, [
    accountId,
    applyAuthStateResponse,
    authPhase,
    clearAccountContext,
    dashboardReadyRef,
    formBaselineRef,
    formInitializedRef,
    formRef,
    loadDashboardState,
    queryClient,
    setApiError,
    setAuthError,
    setAuthErrorCode,
    setAuthPhase,
    setAuthStep,
    setForm,
    setIsBootRefreshing,
    setPhoneNumber,
    skipNextAuthBootstrapRef,
  ])
}
