/**
 * App – root application controller.
 *
 * Responsibilities:
 *  - Rendering the screen selected by TanStack Router
 *  - Managing auth/dashboard phases inside account workspace routes
 *  - Composing the three custom hooks: useAuthFlow, useDashboard, useProfileDraft
 *  - Wiring hidden file inputs for photo / audio / story upload
 */

import { AlertTriangle, Check, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState, useTransition } from 'react'

import { AuthScreen } from '@/components/auth/AuthScreen'
import { DashboardActionBar } from '@/components/dashboard/DashboardActionBar'
import { DashboardHeader } from '@/components/dashboard/DashboardHeader'
import { DashboardSkeleton } from '@/components/dashboard/DashboardSkeleton'
import { ErrorBanner } from '@/components/dashboard/ErrorBanner'
import { JobStepPanel } from '@/components/dashboard/jobs/JobPanels'
import { ProfileEditor } from '@/components/dashboard/profile/ProfilePanels'
import { ToastViewport, type ToastItem } from '@/components/ui/toast'
import { getPollingIntervalMs } from '@/lib/config'
import {
  type ProfilePreview,
} from '@/lib/api'
import {
  buildJobMetrics,
  formatChangeOperationLabel,
  groupRealExecutionChanges,
  type ApiError,
  type ChangeItem,
} from '@/lib/dashboard'
import { useDashboardInitialState } from '@/hooks/useDashboardInitialState'
import { useAuthBootstrap } from '@/hooks/useAuthBootstrap'
import { useAuthFlow } from '@/hooks/useAuthFlow'
import { useDashboardActions } from '@/hooks/useDashboardActions'
import { useDashboard } from '@/hooks/useDashboard'
import { useDashboardPresentation } from '@/hooks/useDashboardPresentation'
import { useProfileDraft } from '@/hooks/useProfileDraft'
import { useTerminalJobRefresh } from '@/hooks/useTerminalJobRefresh'
import {
  useDeleteStoryPostMutation,
  useRefreshRuntimeMutation,
} from '@/hooks/queries/useDashboardMutations'
import type { AuthPhase } from '@/lib/auth'
import { appRoutes, type AppRouteState } from '@/lib/routes'

const JOB_POLLING_INTERVAL_MS = getPollingIntervalMs()
type AccountRouteState = Extract<AppRouteState, { screen: 'account' }>

function initialAuthPhaseForRoute(hasInitialDashboard: boolean): AuthPhase {
  return hasInitialDashboard ? 'dashboard' : 'auth-loading'
}

function workspaceSectionId(route: AccountRouteState): string | null {
  if (route.section === 'profile') return null
  if (route.section === 'jobs') return 'account-workspace-jobs'
  if (route.section === 'debug') return 'account-workspace-debug'
  return `account-workspace-${route.section}`
}

function toVisibleAuthPhase(
  phase: AuthPhase,
): 'auth-loading' | 'auth-phone' | 'auth-code' | 'auth-password' | 'auth-refreshing' | 'auth-error' {
  if (phase === 'dashboard') return 'auth-loading'
  return phase
}

function App({ route }: { route: AccountRouteState }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [, startNavigationTransition] = useTransition()
  const activeAccountId = route.accountId
  const { initialAccountId, initialBundle, initialDashboard, initialForm } = useDashboardInitialState(route.accountId, queryClient)

  // ── File input refs (wiring hidden <input type="file"> elements) ─────────────
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const audioInputRef = useRef<HTMLInputElement | null>(null)
  const storyImageInputRef = useRef<HTMLInputElement | null>(null)

  // ── Toast notifications ───────────────────────────────────────────────────────
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const toastTimeoutsRef = useRef<number[]>([])
  const [submittedPreview, setSubmittedPreview] = useState<ProfilePreview | null>(null)
  const [deletingStoryPostId, setDeletingStoryPostId] = useState<string | null>(null)
  const [isRealExecutionConfirmOpen, setIsRealExecutionConfirmOpen] = useState(false)
  const [hiddenJobPanelKey, setHiddenJobPanelKey] = useState<string | null>(null)
  const refreshRuntimeMutation = useRefreshRuntimeMutation()
  const deleteStoryPostMutation = useDeleteStoryPostMutation()

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
  const auth = useAuthFlow({
    initialAccountId,
    initialPhase: initialAuthPhaseForRoute(Boolean(initialDashboard)),
  } as Parameters<typeof useAuthFlow>[0])
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
    applyAuthStateResponse,
    applyAccountContext,
    clearAccountContext,
    _skipNextBootstrapRef: skipNextAuthBootstrapRef,
  } = auth as typeof auth & { _skipNextBootstrapRef: React.MutableRefObject<boolean> }

  const transitionToPhase = useCallback(
    (phase: AuthPhase) => {
      startNavigationTransition(() => setAuthPhase(phase))
    },
    [setAuthPhase],
  )

  const navigateToRoute = useCallback(
    (href: string) => {
      void navigate({ href })
    },
    [navigate],
  )

  // ── Dashboard data + job polling ──────────────────────────────────────────────
  const dashboardHook = useDashboard({
    accountId: activeAccountId,
    authPhase,
    initialBundle,
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
    accountId: activeAccountId,
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
    activeAccountId && dashboard?.account.account_id === activeAccountId && isFormInitialized,
  )
  const dashboardReadyRef = useRef(dashboardReady)

  useEffect(() => {
    dashboardReadyRef.current = dashboardReady
  }, [dashboardReady])

  // ── API error state (passed from dashboard loads) ─────────────────────────────
  const [apiError, setApiError] = useState<ApiError | null>(null)
  const {
    jobDisplayItems,
    jobPanelKey,
    jobProgressSummary,
    jobResultSummary,
    runtimeBanner: visibleBanner,
    shouldShowJobPanel,
  } = useDashboardPresentation({
    apiError,
    currentJob,
    currentSteps,
    hiddenJobPanelKey,
    jobs,
    preview,
    submittedPreview,
    terminalJobStates,
  })

  useAuthBootstrap({
    accountId: activeAccountId,
    applyAuthStateResponse,
    authPhase,
    clearAccountContext,
    dashboardReadyRef,
    queryClient,
    loadDashboardState,
    formRef,
    formBaselineRef,
    formInitializedRef,
    setForm,
    setApiError,
    setAuthPhase,
    setPhoneNumber,
    setIsBootRefreshing,
    skipNextAuthBootstrapRef,
    setAuthError,
    setAuthErrorCode,
    setAuthStep,
  })

  // ── If dashboard phase but form not ready, trigger load ───────────────────────
  useEffect(() => {
    if (!activeAccountId || authPhase !== 'dashboard' || dashboardReady) return
    const id = window.setTimeout(
      () =>
        void loadDashboardState(activeAccountId, formRef, formBaselineRef, formInitializedRef, setForm),
      0,
    )
    return () => window.clearTimeout(id)
  }, [activeAccountId, authPhase, dashboardReady, loadDashboardState, formRef, formBaselineRef, formInitializedRef, setForm])

  useTerminalJobRefresh({
    accountId: activeAccountId,
    currentJobState: currentJob?.job_state,
    formBaselineRef,
    formInitializedRef,
    formRef,
    loadDashboardState,
    setApiError,
    setForm,
    terminalJobRefreshSeq,
  })

  // ── Cleanup toast timers ──────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      toastTimeoutsRef.current.forEach((id) => window.clearTimeout(id))
      toastTimeoutsRef.current = []
    }
  }, [])

  const {
    confirmRealExecution,
    handleBackToAccounts,
    handleCreateJob,
    handleDeleteStoryPost,
    handleRefreshRuntime,
  } = useDashboardActions({
    accountId: activeAccountId,
    changedItems,
    clearAccountContext,
    clearSelectedPhotoPreview,
    confirmDiagnostics: dashboard?.diagnostics,
    createProfileJob: draft.handleCreateJob,
    deleteStoryPost: (post) => deleteStoryPostMutation.mutateAsync({ accountId: activeAccountId!, postId: post.id }),
    formBaselineRef,
    formInitializedRef,
    formRef,
    loadDashboardState,
    loadJobState,
    notify,
    patchDashboardPipeline,
    preview,
    refreshRuntime: refreshRuntimeMutation.mutateAsync,
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
  })

  const handleDashboardBackToAccounts = useCallback(() => {
    handleBackToAccounts()
    navigateToRoute(appRoutes.accounts())
  }, [handleBackToAccounts, navigateToRoute])

  useEffect(() => {
    if (accountId === route.accountId) return
    const id = window.setTimeout(() => {
      clearSelectedPhotoPreview()
      setSubmittedPreview(null)
      setApiError(null)
      setHiddenJobPanelKey(null)
      setIsRealExecutionConfirmOpen(false)
      setIsRefreshingRuntime(false)
      applyAccountContext(route.accountId)
      transitionToPhase('auth-loading')
    }, 0)
    return () => window.clearTimeout(id)
  }, [
    accountId,
    applyAccountContext,
    clearSelectedPhotoPreview,
    route,
    setIsRefreshingRuntime,
    transitionToPhase,
  ])

  useEffect(() => {
    if (!dashboardReady) return
    const targetId = workspaceSectionId(route)
    if (!targetId) return
    const id = window.setTimeout(() => {
      if (route.section === 'jobs' || route.section === 'debug') {
        setHiddenJobPanelKey(null)
      }
      document.getElementById(targetId)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }, 0)
    return () => window.clearTimeout(id)
  }, [dashboardReady, route])

  // ── Render routing ────────────────────────────────────────────────────────────

  if (accountId !== route.accountId) {
    return <DashboardSkeleton />
  }

  if (authPhase === 'auth-loading' && activeAccountId) {
    return <DashboardSkeleton />
  }

  if (authPhase === 'dashboard' && !dashboardReady) {
    return <DashboardSkeleton />
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
        phase={toVisibleAuthPhase(authPhase)}
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
        onBack={handleDashboardBackToAccounts}
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
        <div id={route.section === 'debug' ? 'account-workspace-debug' : 'account-workspace-jobs'}>
          <JobStepPanel
            currentJob={currentJob}
            items={jobDisplayItems}
            onHide={jobPanelKey ? () => setHiddenJobPanelKey(jobPanelKey) : undefined}
            progressSummary={jobProgressSummary}
            resultSummary={jobResultSummary}
          />
        </div>
      ) : null}

      {isRealExecutionConfirmOpen ? (
        <RealTelegramExecutionModal
          changedItems={changedItems}
          isSubmitting={isSubmittingJob}
          onCancel={() => setIsRealExecutionConfirmOpen(false)}
          onConfirm={() => void confirmRealExecution()}
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

function RealTelegramExecutionModal({
  changedItems,
  isSubmitting,
  onCancel,
  onConfirm,
}: {
  changedItems: ChangeItem[]
  isSubmitting: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const groups = groupRealExecutionChanges(changedItems)

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-navy-900/25 px-4 backdrop-blur-sm">
      <div className="modal-animate w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-gray-100 px-4 py-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <span className="mt-0.5 flex size-8 flex-shrink-0 items-center justify-center rounded-lg bg-honey-50 text-honey-700">
              <AlertTriangle className="size-4" />
            </span>
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-gray-900">Подтвердите изменение аккаунта</h2>
              <p className="mt-1 text-xs leading-relaxed text-gray-500">
                Это действие реально изменит Telegram-аккаунт.
              </p>
            </div>
          </div>
          <button
            aria-label="Закрыть подтверждение"
            className="flex size-8 flex-shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-50 hover:text-gray-700"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-3 px-4 py-3">
          <RealExecutionGroup title="Profile" items={groups.profile} />
          <RealExecutionGroup title="Music" items={groups.music} />
          <RealExecutionGroup title="Stories" items={groups.stories} />
        </div>

        <div className="flex justify-end gap-2 border-t border-gray-100 bg-gray-50 px-4 py-3">
          <button
            className="rounded-lg px-3 py-2 text-xs font-semibold text-gray-500 transition hover:bg-white hover:text-gray-700 disabled:opacity-50"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            Отмена
          </button>
          <button
            className="rounded-lg bg-navy-400 px-4 py-2 text-xs font-semibold text-white transition hover:bg-navy-500 disabled:opacity-50"
            disabled={isSubmitting}
            onClick={onConfirm}
            type="button"
          >
            Подтвердить и создать задачу
          </button>
        </div>
      </div>
    </div>
  )
}

function RealExecutionGroup({ title, items }: { title: string; items: ChangeItem[] }) {
  if (items.length === 0) return null
  return (
    <section>
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-gray-400">{title}</h3>
      <ul className="mt-1.5 space-y-1">
        {items.map((item) => (
          <li className="flex gap-2 text-xs text-gray-700" key={`${item.operation}:${item.value}`}>
            <span className="mt-1 size-1.5 flex-shrink-0 rounded-full bg-navy-300" />
            <span className="min-w-0">
              <span className="font-semibold">{formatChangeOperationLabel(item.operation)}</span>
              <span className="text-gray-400"> · {item.value}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
