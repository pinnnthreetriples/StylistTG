/**
 * App – root application controller.
 *
 * Responsibilities:
 *  - Phase-based routing (account-list → auth → dashboard)
 *  - Composing the three custom hooks: useAuthFlow, useDashboard, useProfileDraft
 *  - Rendering the matching screen for the current phase
 *  - Wiring hidden file inputs for photo / audio / story upload
 */

import { Check } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { AuthScreen } from '@/components/auth/AuthScreen'
import { BulkAuthScreen } from '@/components/auth/BulkAuthScreen'
import { AccountList } from '@/components/dashboard/accounts/AccountList'
import { DashboardActionBar } from '@/components/dashboard/DashboardActionBar'
import { DashboardHeader } from '@/components/dashboard/DashboardHeader'
import { DashboardSkeleton } from '@/components/dashboard/DashboardSkeleton'
import { ErrorBanner } from '@/components/dashboard/ErrorBanner'
import { JobStepPanel } from '@/components/dashboard/jobs/JobPanels'
import { ProfileEditor } from '@/components/dashboard/profile/ProfilePanels'
import { ToastViewport, type ToastItem } from '@/components/ui/toast'
import { getPollingIntervalMs } from '@/lib/config'
import {
  deleteStoryPost,
  refreshRuntime,
  type JobSummary,
  type ProfilePreview,
  type StoryPost,
} from '@/lib/api'
import { normalizeError } from '@/lib/appErrors'
import {
  buildJobDisplayItems,
  buildJobProgressSummary,
  buildJobResultSummary,
  buildJobStepItems,
  shouldResetDraftAfterJobState,
} from '@/lib/jobs'
import { buildJobMetrics, buildRuntimeBanner, type ApiError } from '@/lib/dashboard'
import { emptyDashboardForm, useDashboardInitialState } from '@/hooks/useDashboardInitialState'
import { useAuthFlow } from '@/hooks/useAuthFlow'
import { useDashboard } from '@/hooks/useDashboard'
import { useProfileDraft } from '@/hooks/useProfileDraft'
import { labelIssue, labelJobState } from '@/lib/uiLabels'
import { readAccountListView, writeAccountListView, type AccountListView } from '@/lib/appView'
import {
  buildAuthErrorMessage,
  fetchAuthState,
  shouldClearStoredAccountForAuthState,
  shouldRunAuthBootstrap,
  nextAuthPhaseFromState,
} from '@/lib/auth'

const JOB_POLLING_INTERVAL_MS = getPollingIntervalMs()

function App() {
  const { initialAccountId, initialDashboard, initialForm } = useDashboardInitialState()
  const initialAccountListView = readAccountListView(window.location.search)

  // ── File input refs (wiring hidden <input type="file"> elements) ─────────────
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const audioInputRef = useRef<HTMLInputElement | null>(null)
  const storyImageInputRef = useRef<HTMLInputElement | null>(null)

  // ── Toast notifications ───────────────────────────────────────────────────────
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const toastTimeoutsRef = useRef<number[]>([])
  const [submittedPreview, setSubmittedPreview] = useState<ProfilePreview | null>(null)
  const [deletingStoryPostId, setDeletingStoryPostId] = useState<string | null>(null)

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const notify = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = crypto.randomUUID()
    setToasts((prev) => [...prev.slice(-3), { ...toast, id }])
    const tid = window.setTimeout(
      () => setToasts((prev) => prev.filter((t) => t.id !== id)),
      toast.tone === 'error' ? 6000 : 3600,
    )
    toastTimeoutsRef.current.push(tid)
  }, [])

  // ── Auth flow ─────────────────────────────────────────────────────────────────
  const initialPhase = initialDashboard
    ? 'dashboard'
    : initialAccountId
      ? 'auth-loading'
      : initialAccountListView === 'auth-batch'
        ? 'auth-batch'
        : 'account-list'
  const [accountListView, setAccountListView] = useState<AccountListView>(
    initialAccountListView === 'auth-batch' ? 'accounts' : initialAccountListView,
  )

  const auth = useAuthFlow({ initialAccountId, initialPhase } as Parameters<typeof useAuthFlow>[0])
  const {
    authPhase,
    authStep,
    accountId,
    phoneNumber,
    otpCode,
    twoFaPassword,
    passwordHint,
    authError,
    authErrorCode,
    testDcEnabled,
    isUpdatingTestDc,
    setAuthPhase,
    setOtpCode,
    setTwoFaPassword,
    setPhoneNumber,
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
    _skipNextBootstrapRef: skipNextAuthBootstrapRef,
  } = auth as typeof auth & { _skipNextBootstrapRef: React.MutableRefObject<boolean> }

  useEffect(() => {
    function handlePopState() {
      const nextView = readAccountListView(window.location.search)
      if (!accountId && nextView === 'auth-batch') {
        skipNextAuthBootstrapRef.current = true
        setAuthPhase('auth-batch')
        setAccountListView('accounts')
        return
      }
      if (!accountId) {
        setAuthPhase('account-list')
        setAccountListView(nextView === 'auth-batch' ? 'accounts' : nextView)
      }
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [accountId, setAuthPhase, skipNextAuthBootstrapRef])

  function showAccountListView(view: AccountListView, mode: 'push' | 'replace' = 'push') {
    skipNextAuthBootstrapRef.current = true
    writeAccountListView(view, mode)
    if (view === 'auth-batch') {
      setAuthPhase('auth-batch')
      setAccountListView('accounts')
      return
    }
    setAuthPhase('account-list')
    setAccountListView(view)
  }

  // ── Dashboard data + job polling ──────────────────────────────────────────────
  const dashboardHook = useDashboard({
    accountId,
    authPhase,
    pollingIntervalMs: JOB_POLLING_INTERVAL_MS,
  })
  const {
    dashboard,
    jobs,
    currentJob,
    currentSteps,
    storyCapabilities,
    terminalJobRefreshSeq,
    isLoading,
    isBootRefreshing,
    setIsBootRefreshing,
    loadJobState,
    loadDashboardState,
    resetDashboard,
    patchDashboardPipeline,
    terminalJobStates,
  } = dashboardHook

  // ── Profile draft (form + uploads + job creation) ─────────────────────────────
  const draft = useProfileDraft({
    accountId,
    dashboard,
    initialForm,
    initialDashboard,
    notify,
  })
  const {
    form,
    preview,
    isFormInitialized,
    isSubmittingJob,
    isRefreshingRuntime,
    setIsRefreshingRuntime,
    isUploadingPhoto,
    isUploadingAudio,
    isUploadingStory,
    selectedPhotoName,
    selectedAudioName,
    photoPreview,
    currentProfile,
    changeItems,
    changedItems,
    setForm,
    formRef,
    formBaselineRef,
    formInitializedRef,
    clearSelectedPhotoPreview,
    handlePhotoUpload,
    handleClearProfilePhoto,
    handleAudioUpload,
    handleKeepProfileAudio,
    handleRemoveProfileAudio,
    handleStoryUpload,
    handleUpdateStory,
    handleRemoveStory,
    handleReset,
  } = draft

  // ── Derived dashboard readiness ───────────────────────────────────────────────
  const dashboardReady = Boolean(
    accountId && dashboard?.account.account_id === accountId && isFormInitialized,
  )
  const dashboardReadyRef = useRef(dashboardReady)

  useEffect(() => {
    dashboardReadyRef.current = dashboardReady
  }, [dashboardReady])

  // ── API error state (passed from dashboard loads) ─────────────────────────────
  const [apiError, setApiError] = useState<ApiError | null>(null)
  const runtimeBanner = useMemo(() => buildRuntimeBanner({ apiError }), [apiError])
  const visibleBanner = runtimeBanner
  const latestJobPlan = useMemo(() => {
    if (!currentJob) return null
    const latest = jobs.find((job) => job.job_id === currentJob.job_id)
    if (!latest?.plan_summary.length) return null
    return {
      steps: latest.plan_summary.map((step_key) => ({ step_key })),
    }
  }, [currentJob, jobs])
  const jobPlan = submittedPreview ?? preview ?? latestJobPlan
  const jobStepItems = useMemo(
    () => buildJobStepItems(currentSteps, jobPlan, currentJob?.job_state),
    [currentJob?.job_state, currentSteps, jobPlan],
  )
  const jobResultSummary = useMemo(
    () => buildJobResultSummary(currentJob, currentSteps),
    [currentJob, currentSteps],
  )
  const jobProgressSummary = useMemo(() => buildJobProgressSummary(jobStepItems), [jobStepItems])
  const jobDisplayItems = useMemo(() => buildJobDisplayItems(jobStepItems), [jobStepItems])
  const shouldShowJobPanel = Boolean(currentJob || preview || jobStepItems.length > 0)

  // ── Auth bootstrap: fetch auth state whenever accountId changes ───────────────
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
        const authState = await fetchAuthState(bootstrapAccountId)
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
    loadDashboardState,
    formRef,
    formBaselineRef,
    formInitializedRef,
    setForm,
    dashboardReadyRef,
    setAuthPhase,
    setPhoneNumber,
    setIsBootRefreshing,
    skipNextAuthBootstrapRef,
    setAuthError,
    setAuthErrorCode,
    setAuthStep,
  ])

  // ── If dashboard phase but form not ready, trigger load ───────────────────────
  useEffect(() => {
    if (!accountId || authPhase !== 'dashboard' || dashboardReady) return
    const id = window.setTimeout(
      () =>
        void loadDashboardState(accountId, formRef, formBaselineRef, formInitializedRef, setForm),
      0,
    )
    return () => window.clearTimeout(id)
  }, [accountId, authPhase, dashboardReady, loadDashboardState, formRef, formBaselineRef, formInitializedRef, setForm])

  useEffect(() => {
    if (!accountId || terminalJobRefreshSeq === 0) return
    const shouldResetDraft = shouldResetDraftAfterJobState(currentJob?.job_state)
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
    currentJob?.job_state,
    formBaselineRef,
    formInitializedRef,
    formRef,
    loadDashboardState,
    setForm,
    terminalJobRefreshSeq,
  ])

  // ── Cleanup toast timers ──────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      toastTimeoutsRef.current.forEach((id) => window.clearTimeout(id))
      toastTimeoutsRef.current = []
    }
  }, [])

  // ── Handlers ──────────────────────────────────────────────────────────────────

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
    setIsRefreshingRuntime(false)
    setPhoneNumber('')
    setOtpCode('')
    setTwoFaPassword('')
    setAuthPhase('account-list')
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
        { quiet: true, resetForm: true },
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

  async function handleCreateJob() {
    const planForCreatedJob = preview
    await draft.handleCreateJob(
      async (job: JobSummary) => {
        setSubmittedPreview(planForCreatedJob)
        patchDashboardPipeline(job)
        if (job.job_state === 'dedup_blocked') return
        const jobDetail = await loadJobState(accountId!, job.job_id)
        if (jobDetail && terminalJobStates.has(jobDetail.job_state)) {
          const loaded = await loadDashboardState(
            accountId!,
            formRef,
            formBaselineRef,
            formInitializedRef,
            setForm,
            { resetForm: shouldResetDraftAfterJobState(jobDetail.job_state) },
          )
          if (loaded) setApiError(null)
        }
        notify({ tone: 'success', title: 'Задача создана', description: labelJobState(job.job_state) })
      },
      (err) => setApiError(err),
    )
  }

  async function handleDeleteStoryPost(post: StoryPost) {
    if (!accountId) return

    setDeletingStoryPostId(post.id)
    try {
      await deleteStoryPost(accountId, post.id)
      const loaded = await loadDashboardState(
        accountId,
        formRef,
        formBaselineRef,
        formInitializedRef,
        setForm,
        { quiet: true },
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

  // ── Render routing ────────────────────────────────────────────────────────────

  if (authPhase === 'auth-loading' && accountId) {
    return <DashboardSkeleton />
  }

  if (authPhase === 'dashboard' && !dashboardReady) {
    return <DashboardSkeleton />
  }

  if (authPhase === 'account-list') {
    return (
      <AccountList
        activeTab={accountListView === 'settings' ? 'settings' : 'accounts'}
        onAddBatch={() => showAccountListView('auth-batch')}
        onSelectAccount={(nextAccountId) => {
          writeAccountListView('accounts', 'replace')
          applyAccountContext(nextAccountId)
          setAuthPhase('auth-loading')
        }}
        onTabChange={(tab) => showAccountListView(tab)}
      />
    )
  }

  if (authPhase === 'auth-batch') {
    return (
      <BulkAuthScreen
        onBack={() => showAccountListView('accounts')}
        onTestDcChange={handleBatchTestDcChange}
        testDcEnabled={testDcEnabled}
        testDcPending={isUpdatingTestDc}
      />
    )
  }

  if (authPhase !== 'dashboard') {
    return (
      <AuthScreen
        code={otpCode}
        password={twoFaPassword}
        passwordHint={passwordHint}
        errorCode={authErrorCode}
        errorMessage={authError}
        testDcEnabled={testDcEnabled}
        testDcPending={isUpdatingTestDc}
        onCodeChange={setOtpCode}
        onPasswordChange={setTwoFaPassword}
        onConfirm={handleConfirmOtp}
        onSubmitPassword={handleSubmitPassword}
        onPhoneNumberChange={setPhoneNumber}
        onResetPhone={handleResetAuthPhone}
        onStart={handleStartOtp}
        onTestDcChange={handleTestDcChange}
        phase={authPhase}
        phoneNumber={phoneNumber}
        step={authStep}
      />
    )
  }

  // ── Dashboard view ────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-cream">
      <DashboardHeader
        displayName={dashboard?.account.display_name}
        username={dashboard?.account.username}
        isExecutionUsable={Boolean(dashboard?.account.is_execution_usable)}
        isBootRefreshing={isBootRefreshing}
        isLoading={isLoading}
        isRefreshingRuntime={isRefreshingRuntime}
        onBack={handleBackToAccounts}
        onRefresh={handleRefreshRuntime}
      />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-4 pb-24">
        {/* Page title + job metrics */}
        <div className="flex items-center justify-between mb-4 fade-in">
          <div className="flex items-center gap-3">
            <h1 className="font-display font-bold text-lg tracking-tight text-gray-900">
              Редактирование профиля
            </h1>
          </div>
          <div className="hidden sm:flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-50 border border-emerald-100 rounded-md text-[11px] font-medium text-emerald-700">
              <Check className="size-3 text-emerald-500" />
              {buildJobMetrics(jobs).success} успешно
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-50 border border-gray-200 rounded-md text-[11px] font-medium text-gray-500">
              {buildJobMetrics(jobs).total} задач
            </span>
          </div>
        </div>

        {visibleBanner ? <ErrorBanner banner={visibleBanner} /> : null}

        <div className="space-y-4">
          <ProfileEditor
            changeItems={changeItems}
            hasSelectedPhoto={Boolean(form.profilePhotoAssetId)}
            photoPreviewUrl={photoPreview.imageUrl}
            onClearPhoto={handleClearProfilePhoto}
            onChoosePhoto={() => fileInputRef.current?.click()}
            isUploadingPhoto={isUploadingPhoto}
            selectedPhotoName={selectedPhotoName}
            profileAudio={dashboard?.profile_audio ?? null}
            profileAudioAction={form.profileAudioAction}
            selectedAudioName={selectedAudioName}
            isUploadingAudio={isUploadingAudio}
            onChooseAudio={() => audioInputRef.current?.click()}
            onKeepAudio={handleKeepProfileAudio}
            onRemoveAudio={handleRemoveProfileAudio}
            stories={form.stories}
            isUploadingStory={isUploadingStory}
            deletingStoryPostId={deletingStoryPostId}
            onChooseStoryImage={() => storyImageInputRef.current?.click()}
            onUpdateStory={handleUpdateStory}
            onRemoveStory={handleRemoveStory}
            onDeleteStoryPost={handleDeleteStoryPost}
            storyPosts={dashboard?.story_posts ?? []}
            storyCapabilities={storyCapabilities}
            currentProfile={currentProfile}
            form={form}
            onChange={draft.updateForm}
          />
        </div>
      </main>

      <DashboardActionBar
        changedItems={changedItems}
        preview={preview}
        isSubmittingJob={isSubmittingJob}
        onReset={handleReset}
        onCreateJob={handleCreateJob}
      />

      {shouldShowJobPanel ? (
        <JobStepPanel
          currentJob={currentJob}
          items={jobDisplayItems}
          progressSummary={jobProgressSummary}
          resultSummary={jobResultSummary}
        />
      ) : null}

      {/* Hidden file inputs */}
      <input
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => void handlePhotoUpload(e.target.files?.[0] ?? null)}
        ref={fileInputRef}
        type="file"
      />
      <input
        accept="image/png,image/jpeg,image/webp,video/mp4,video/quicktime,video/webm"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0] ?? null
          if (!file) return
          const kind = file.type.startsWith('video/') ? 'video' : 'image'
          void handleStoryUpload(file, kind)
        }}
        ref={storyImageInputRef}
        type="file"
      />
      <input
        accept="audio/mpeg,audio/mp4,.mp3,.m4a"
        className="hidden"
        onChange={(e) => void handleAudioUpload(e.target.files?.[0] ?? null)}
        ref={audioInputRef}
        type="file"
      />

      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default App
