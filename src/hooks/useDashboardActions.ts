import type React from 'react'

import type { JobDetail, JobSummary, ProfilePreview, StoryPost } from '@/lib/api'
import { normalizeError } from '@/lib/appErrors'
import type { AuthPhase } from '@/lib/auth'
import {
  shouldConfirmRealTelegramExecution,
  type ApiError,
  type ChangeItem,
  type FormState,
} from '@/lib/dashboard'
import { emptyDashboardForm } from '@/hooks/useDashboardInitialState'
import { shouldResetDraftAfterJobState } from '@/lib/jobs'
import { labelIssue, labelJobState } from '@/lib/uiLabels'
import type { ToastItem } from '@/components/ui/toast'

export function useDashboardActions({
  accountId,
  changedItems,
  clearAccountContext,
  clearSelectedPhotoPreview,
  confirmDiagnostics,
  createProfileJob,
  deleteStoryPost,
  formBaselineRef,
  formInitializedRef,
  formRef,
  loadDashboardState,
  loadJobState,
  notify,
  patchDashboardPipeline,
  preview,
  refreshRuntime,
  resetDashboard,
  setApiError,
  setDeletingStoryPostId,
  setForm,
  setHiddenJobPanelKey,
  setIsRealExecutionConfirmOpen,
  setIsRefreshingRuntime,
  setOtpCode,
  setPhoneNumber,
  setSubmittedPreview,
  setTwoFaPassword,
  terminalJobStates,
  transitionToPhase,
}: {
  accountId: string | null
  changedItems: ChangeItem[]
  clearAccountContext: () => void
  clearSelectedPhotoPreview: () => void
  confirmDiagnostics: Parameters<typeof shouldConfirmRealTelegramExecution>[0]
  createProfileJob: (
    onJobCreated: (job: JobSummary) => void | Promise<void>,
    onError: (err: ApiError) => void,
  ) => Promise<void>
  deleteStoryPost: (post: StoryPost) => Promise<void>
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
  loadJobState: (accountId: string, jobId: string) => Promise<JobDetail | null>
  notify: (toast: Omit<ToastItem, 'id'>) => void
  patchDashboardPipeline: (job: JobSummary) => void
  preview: ProfilePreview | null
  refreshRuntime: (accountId: string) => Promise<unknown>
  resetDashboard: () => void
  setApiError: React.Dispatch<React.SetStateAction<ApiError | null>>
  setDeletingStoryPostId: React.Dispatch<React.SetStateAction<string | null>>
  setForm: (next: FormState) => void
  setHiddenJobPanelKey: React.Dispatch<React.SetStateAction<string | null>>
  setIsRealExecutionConfirmOpen: React.Dispatch<React.SetStateAction<boolean>>
  setIsRefreshingRuntime: React.Dispatch<React.SetStateAction<boolean>>
  setOtpCode: (value: string) => void
  setPhoneNumber: (value: string) => void
  setSubmittedPreview: React.Dispatch<React.SetStateAction<ProfilePreview | null>>
  setTwoFaPassword: (value: string) => void
  terminalJobStates: ReadonlySet<string>
  transitionToPhase: (phase: AuthPhase) => void
}) {
  function handleBackToAccounts() {
    clearSelectedPhotoPreview()
    clearAccountContext()
    formInitializedRef.current = false
    formBaselineRef.current = null
    formRef.current = emptyDashboardForm
    setForm(emptyDashboardForm)
    resetDashboard()
    setSubmittedPreview(null)
    setApiError(null)
    setHiddenJobPanelKey(null)
    setIsRealExecutionConfirmOpen(false)
    setIsRefreshingRuntime(false)
    setPhoneNumber('')
    setOtpCode('')
    setTwoFaPassword('')
    transitionToPhase('account-list')
  }

  async function handleRefreshRuntime() {
    if (!accountId) return
    setIsRefreshingRuntime(true)
    try {
      await refreshRuntime(accountId)
      const loaded = await loadDashboardState(
        accountId,
        formRef,
        formBaselineRef,
        formInitializedRef,
        setForm,
        { quiet: true, resetForm: true, forceRefresh: true },
      )
      if (loaded) setApiError(null)
      notify({ tone: 'success', title: 'Профиль синхронизирован' })
    } catch (error) {
      const normalized = normalizeError(error)
      setApiError(normalized)
      notify({ tone: 'error', title: 'Не удалось синхронизировать профиль', description: labelIssue(normalized.error_code) })
    } finally {
      setIsRefreshingRuntime(false)
    }
  }

  async function submitCreateJob() {
    const planForCreatedJob = preview
    await createProfileJob(
      async (job: JobSummary) => {
        setSubmittedPreview(planForCreatedJob)
        patchDashboardPipeline(job)
        if (!accountId || job.job_state === 'dedup_blocked') return
        const jobDetail = await loadJobState(accountId, job.job_id)
        if (jobDetail && terminalJobStates.has(jobDetail.job_state)) {
          const loaded = await loadDashboardState(
            accountId,
            formRef,
            formBaselineRef,
            formInitializedRef,
            setForm,
            { resetForm: shouldResetDraftAfterJobState(jobDetail.job_state), forceRefresh: true },
          )
          if (loaded) setApiError(null)
        }
        notify({ tone: 'success', title: 'Задача создана', description: labelJobState(job.job_state) })
      },
      (err) => setApiError(err),
    )
  }

  async function handleCreateJob() {
    if (shouldConfirmRealTelegramExecution(confirmDiagnostics, changedItems)) {
      setIsRealExecutionConfirmOpen(true)
      return
    }
    await submitCreateJob()
  }

  async function confirmRealExecution() {
    setIsRealExecutionConfirmOpen(false)
    await submitCreateJob()
  }

  async function handleDeleteStoryPost(post: StoryPost) {
    if (!accountId) return

    setDeletingStoryPostId(post.id)
    try {
      await deleteStoryPost(post)
      const loaded = await loadDashboardState(
        accountId,
        formRef,
        formBaselineRef,
        formInitializedRef,
        setForm,
        { quiet: true, forceRefresh: true },
      )
      if (loaded) setApiError(null)
      notify({ tone: 'success', title: 'История удалена' })
    } catch (error) {
      const normalized = normalizeError(error)
      setApiError(normalized)
      notify({ tone: 'error', title: 'Не удалось удалить историю', description: labelIssue(normalized.error_code) })
    } finally {
      setDeletingStoryPostId(null)
    }
  }

  return {
    confirmRealExecution,
    handleBackToAccounts,
    handleCreateJob,
    handleDeleteStoryPost,
    handleRefreshRuntime,
  }
}
