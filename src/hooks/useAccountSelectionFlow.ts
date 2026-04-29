import type { QueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import type React from 'react'

import { normalizeError } from '@/lib/appErrors'
import type { ProfilePreview } from '@/lib/api'
import { writeAccountListView } from '@/lib/appView'
import {
  nextAuthPhaseFromState,
  type AuthPhase,
  type AuthStateResponse,
} from '@/lib/auth'
import type { ApiError, FormState } from '@/lib/dashboard'
import { readCachedDashboardHydration } from '@/lib/dashboardNavigation'
import { authStateQueryOptions, type DashboardBundle } from '@/lib/queries'

export function useAccountSelectionFlow({
  applyAccountContext,
  applyAuthStateResponse,
  formBaselineRef,
  formInitializedRef,
  formRef,
  loadDashboardState,
  queryClient,
  setApiError,
  setDashboard,
  setForm,
  setHiddenJobPanelKey,
  setIsBootRefreshing,
  setSubmittedPreview,
  skipNextAuthBootstrapRef,
  transitionToPhase,
}: {
  applyAccountContext: (accountId: string) => void
  applyAuthStateResponse: (state: AuthStateResponse) => boolean
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
  setDashboard: React.Dispatch<React.SetStateAction<DashboardBundle['dashboard'] | null>>
  setForm: (next: FormState) => void
  setHiddenJobPanelKey: React.Dispatch<React.SetStateAction<string | null>>
  setIsBootRefreshing: React.Dispatch<React.SetStateAction<boolean>>
  setSubmittedPreview: React.Dispatch<React.SetStateAction<ProfilePreview | null>>
  skipNextAuthBootstrapRef: React.MutableRefObject<boolean>
  transitionToPhase: (phase: AuthPhase) => void
}) {
  const hydrateCachedDashboard = useCallback(
    (accountId: string): boolean => {
      const cached = readCachedDashboardHydration(window.localStorage, accountId)
      if (!cached) return false

      setDashboard(cached.dashboard)
      formBaselineRef.current = cached.baselineForm
      formInitializedRef.current = true
      formRef.current = cached.nextForm
      setForm(cached.nextForm)
      setApiError(null)
      setSubmittedPreview(null)
      setHiddenJobPanelKey(null)
      return true
    },
    [
      formBaselineRef,
      formInitializedRef,
      formRef,
      setApiError,
      setDashboard,
      setForm,
      setHiddenJobPanelKey,
      setSubmittedPreview,
    ],
  )

  const selectAccount = useCallback(
    (accountId: string) => {
      writeAccountListView('accounts', 'replace')
      skipNextAuthBootstrapRef.current = false
      const hydrated = hydrateCachedDashboard(accountId)
      applyAccountContext(accountId)
      transitionToPhase(hydrated ? 'dashboard' : 'auth-loading')
      if (!hydrated) return

      setIsBootRefreshing(true)
      void (async () => {
        try {
          const authState = await queryClient.fetchQuery(authStateQueryOptions(accountId))
          if (nextAuthPhaseFromState(authState) !== 'dashboard') {
            applyAuthStateResponse(authState)
            return
          }
          const loaded = await loadDashboardState(
            accountId,
            formRef,
            formBaselineRef,
            formInitializedRef,
            setForm,
            { quiet: true },
          )
          if (loaded) setApiError(null)
        } catch (error) {
          const normalized = normalizeError(error)
          setApiError(normalized)
        } finally {
          setIsBootRefreshing(false)
        }
      })()
    },
    [
      applyAccountContext,
      applyAuthStateResponse,
      formBaselineRef,
      formInitializedRef,
      formRef,
      hydrateCachedDashboard,
      loadDashboardState,
      queryClient,
      setApiError,
      setForm,
      setIsBootRefreshing,
      skipNextAuthBootstrapRef,
      transitionToPhase,
    ],
  )

  return { selectAccount }
}
