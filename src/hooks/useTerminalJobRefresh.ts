import { useEffect } from 'react'
import type React from 'react'

import type { JobDetail } from '@/lib/api'
import type { ApiError, FormState } from '@/lib/dashboard'
import { shouldResetDraftAfterJobState } from '@/lib/jobs'

export function useTerminalJobRefresh({
  accountId,
  currentJobState,
  formBaselineRef,
  formInitializedRef,
  formRef,
  loadDashboardState,
  setApiError,
  setForm,
  terminalJobRefreshSeq,
}: {
  accountId: string | null
  currentJobState: JobDetail['job_state'] | undefined
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
  setApiError: React.Dispatch<React.SetStateAction<ApiError | null>>
  setForm: (next: FormState) => void
  terminalJobRefreshSeq: number
}) {
  useEffect(() => {
    if (!accountId || terminalJobRefreshSeq === 0) return
    const shouldResetDraft = shouldResetDraftAfterJobState(currentJobState)
    void (async () => {
      const loaded = await loadDashboardState(
        accountId,
        formRef,
        formBaselineRef,
        formInitializedRef,
        setForm,
        { resetForm: shouldResetDraft },
      )
      if (loaded) setApiError(null)
    })()
  }, [
    accountId,
    currentJobState,
    formBaselineRef,
    formInitializedRef,
    formRef,
    loadDashboardState,
    setApiError,
    setForm,
    terminalJobRefreshSeq,
  ])
}
