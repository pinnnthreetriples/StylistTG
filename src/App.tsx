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
import { normalizeError } from '@/lib/appErrors'
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
import {
  useAccountSafetyQuery,
  useAccountValidityChecksQuery,
  useCreateAccountSafetyOverrideMutation,
  useAccountOperationLogsQuery,
  useAccountProxyQuery,
  useCheckAccountProxyMutation,
  useDeleteAccountProxyMutation,
  useRunAccountValidityCheckMutation,
  useSaveAccountProxyMutation,
} from '@/hooks/queries/useAccountsQueries'
import { operationSafetyLabel, validityCheckSummary, type AccountValidityCheck, type OperationSafety } from '@/lib/accountSafety'
import { compactOperationLogLabel, type OperationLog } from '@/lib/operationLogs'
import {
  proxyErrorLabel,
  proxyStatusLabel,
  validateProxyInput,
  type AccountProxy,
  type AccountProxyInput,
} from '@/lib/proxy'
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
  const validityCheckMutation = useRunAccountValidityCheckMutation()
  const safetyOverrideMutation = useCreateAccountSafetyOverrideMutation()
  const accountSafetyQuery = useAccountSafetyQuery(activeAccountId)
  const validityChecksQuery = useAccountValidityChecksQuery(activeAccountId)
  const accountProxyQuery = useAccountProxyQuery(activeAccountId)
  const accountLogsQuery = useAccountOperationLogsQuery(activeAccountId)
  const saveProxyMutation = useSaveAccountProxyMutation()
  const checkProxyMutation = useCheckAccountProxyMutation()
  const deleteProxyMutation = useDeleteAccountProxyMutation()

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

  const handleCheckValidity = useCallback(async () => {
    if (!activeAccountId) return
    try {
      await validityCheckMutation.mutateAsync(activeAccountId)
      notify({ tone: 'success', title: 'Проверка аккаунта завершена' })
    } catch {
      notify({ tone: 'error', title: 'Не удалось проверить аккаунт' })
    }
  }, [activeAccountId, notify, validityCheckMutation])

  const handleCreateSafetyOverride = useCallback(
    async (item: OperationSafety, reason: string) => {
      if (!activeAccountId) return
      try {
        await safetyOverrideMutation.mutateAsync({
          accountId: activeAccountId,
          operation: String(item.operation),
          reason,
          requestedBlockers: item.blockers,
        })
        notify({ tone: 'success', title: 'Ручной разбор сохранён', description: operationSafetyLabel(item) })
      } catch {
        notify({ tone: 'error', title: 'Не удалось сохранить ручной разбор' })
      }
    },
    [activeAccountId, notify, safetyOverrideMutation],
  )

  const handleSaveProxy = useCallback(
    async (payload: AccountProxyInput) => {
      if (!activeAccountId) return
      const validationError = validateProxyInput(payload)
      if (validationError) {
        notify({ tone: 'error', title: validationError })
        return
      }
      try {
        await saveProxyMutation.mutateAsync({ accountId: activeAccountId, payload })
        notify({ tone: 'success', title: 'Proxy сохранён' })
      } catch (error) {
        const apiError = normalizeError(error)
        notify({
          tone: 'error',
          title: proxyErrorLabel(apiError.error_code) || 'Не удалось сохранить proxy',
        })
      }
    },
    [activeAccountId, notify, saveProxyMutation],
  )

  const handleCheckProxy = useCallback(async () => {
    if (!activeAccountId) return
    try {
      await checkProxyMutation.mutateAsync(activeAccountId)
      notify({ tone: 'success', title: 'Проверка proxy завершена' })
    } catch {
      notify({ tone: 'error', title: 'Не удалось проверить proxy' })
    }
  }, [activeAccountId, checkProxyMutation, notify])

  const handleDeleteProxy = useCallback(async () => {
    if (!activeAccountId) return
    try {
      await deleteProxyMutation.mutateAsync(activeAccountId)
      notify({ tone: 'success', title: 'Proxy удалён' })
    } catch {
      notify({ tone: 'error', title: 'Не удалось удалить proxy' })
    }
  }, [activeAccountId, deleteProxyMutation, notify])

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
        isCheckingValidity={validityCheckMutation.isPending}
        safety={accountSafetyQuery.data ?? null}
        proxy={accountProxyQuery.data ?? null}
        onBack={handleDashboardBackToAccounts}
        onRefresh={handleRefreshRuntime}
        onCheckValidity={handleCheckValidity}
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
        {route.section === 'debug' ? (
          <>
            <SafetyHistoryPanel checks={validityChecksQuery.data ?? []} />
            <OperationLogsPanel logs={accountLogsQuery.data?.items ?? []} title="История операций аккаунта" />
          </>
        ) : null}

        <div className="space-y-4">
          <ProxyPanel
            key={accountProxyQuery.data ? `${accountProxyQuery.data.proxy_type}:${accountProxyQuery.data.host}:${accountProxyQuery.data.port}:${accountProxyQuery.data.username ?? ''}:${accountProxyQuery.data.has_password}` : 'proxy-empty'}
            isChecking={checkProxyMutation.isPending}
            isDeleting={deleteProxyMutation.isPending}
            isSaving={saveProxyMutation.isPending}
            onCheck={handleCheckProxy}
            onDelete={handleDeleteProxy}
            onSave={handleSaveProxy}
            proxy={accountProxyQuery.data ?? null}
          />
          {route.section !== 'debug' ? (
            <OperationLogsPanel logs={(accountLogsQuery.data?.items ?? []).slice(0, 5)} title="История операций" />
          ) : null}
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
        onCreateSafetyOverride={handleCreateSafetyOverride}
      />

      {shouldShowJobPanel ? (
        <div id="account-workspace-jobs">
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

function SafetyHistoryPanel({ checks }: { checks: AccountValidityCheck[] }) {
  return (
    <section className="mb-4 rounded-xl border border-gray-200 bg-white p-4 shadow-soft" id="account-workspace-debug">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-gray-900">История проверок безопасности</h2>
        <span className="text-[11px] text-gray-400">{checks.length > 0 ? `Последние ${Math.min(checks.length, 5)}` : 'Нет проверок'}</span>
      </div>
      {checks.length === 0 ? (
        <p className="text-xs text-gray-500">Проверка ещё не запускалась. Кнопка “Проверить” не меняет аккаунт, а только проверяет сессию.</p>
      ) : (
        <div className="space-y-1.5">
          {checks.slice(0, 5).map((check) => (
            <details className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600" key={check.id}>
              <summary className="cursor-pointer font-semibold text-gray-800">{validityCheckSummary(check)}</summary>
              <pre className="mt-2 max-h-40 overflow-auto rounded bg-white p-2 text-[11px] text-gray-500">
                {JSON.stringify({ status: check.status, error_code: check.error_code, details: check.details, result: check.result }, null, 2)}
              </pre>
            </details>
          ))}
        </div>
      )}
    </section>
  )
}

function ProxyPanel({
  proxy,
  isSaving,
  isChecking,
  isDeleting,
  onSave,
  onCheck,
  onDelete,
}: {
  proxy: AccountProxy | null
  isSaving: boolean
  isChecking: boolean
  isDeleting: boolean
  onSave: (payload: AccountProxyInput) => void
  onCheck: () => void
  onDelete: () => void
}) {
  const [proxyType, setProxyType] = useState<AccountProxyInput['proxy_type']>(proxy?.proxy_type === 'http' ? 'http' : 'socks5')
  const [host, setHost] = useState(proxy?.host ?? '')
  const [port, setPort] = useState(proxy?.port ?? 1080)
  const [username, setUsername] = useState(proxy?.username ?? '')
  const [password, setPassword] = useState('')

  const errorLabel = proxyErrorLabel(proxy?.last_error_code)

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-gray-900">Сеть и Proxy</h2>
          <p className="mt-0.5 text-xs text-gray-500">
            Proxy используется для сетевой маршрутизации аккаунта и диагностики подключения.
          </p>
        </div>
        <span className="rounded-lg bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600">
          {proxyStatusLabel(proxy?.status)}
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-[110px_1fr_90px]">
        <select
          className="rounded-lg border border-gray-200 bg-white px-2.5 py-2 text-sm"
          onChange={(event) => setProxyType(event.currentTarget.value as AccountProxyInput['proxy_type'])}
          value={proxyType}
        >
          <option value="socks5">SOCKS5</option>
          <option value="http">HTTP</option>
        </select>
        <input
          className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm"
          onChange={(event) => setHost(event.currentTarget.value)}
          placeholder="host"
          value={host}
        />
        <input
          className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm"
          onChange={(event) => setPort(Number(event.currentTarget.value))}
          placeholder="port"
          type="number"
          value={port}
        />
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <input
          className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm"
          onChange={(event) => setUsername(event.currentTarget.value)}
          placeholder="username"
          value={username}
        />
        <input
          className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm"
          onChange={(event) => setPassword(event.currentTarget.value)}
          placeholder={proxy?.has_password ? 'пароль сохранён, новый ввод заменит его' : 'password'}
          type="password"
          value={password}
        />
      </div>
      {proxy?.last_checked_at || errorLabel ? (
        <p className="mt-2 text-xs text-gray-500">
          {proxy?.last_checked_at ? `Последняя проверка: ${new Date(proxy.last_checked_at).toLocaleString('ru-RU')}` : null}
          {errorLabel ? ` · ${errorLabel}` : null}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="rounded-lg bg-navy-500 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          disabled={isSaving}
          onClick={() =>
            onSave({
              proxy_type: proxyType,
              host,
              port,
              username: username || null,
              password: password || null,
            })
          }
          type="button"
        >
          {isSaving ? 'Сохраняем…' : 'Сохранить'}
        </button>
        <button className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 disabled:opacity-50" disabled={!proxy || isChecking} onClick={onCheck} type="button">
          {isChecking ? 'Проверяем…' : 'Проверить proxy'}
        </button>
        <button className="rounded-lg border border-red-100 px-3 py-1.5 text-xs font-semibold text-red-500 disabled:opacity-50" disabled={!proxy || isDeleting} onClick={onDelete} type="button">
          {isDeleting ? 'Удаляем…' : 'Удалить'}
        </button>
      </div>
    </section>
  )
}

function OperationLogsPanel({ logs, title }: { logs: OperationLog[]; title: string }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-soft">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-gray-900">{title}</h2>
        <span className="text-[11px] text-gray-400">{logs.length ? `Событий: ${logs.length}` : 'Нет событий'}</span>
      </div>
      {logs.length === 0 ? (
        <p className="text-xs text-gray-500">Пока нет записей. Новые проверки и операции будут появляться здесь.</p>
      ) : (
        <div className="space-y-1.5">
          {logs.map((log) => (
            <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600" key={log.id}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold text-gray-800">{compactOperationLogLabel(log)}</span>
                <span className="text-[11px] text-gray-400">{new Date(log.created_at).toLocaleString('ru-RU')}</span>
              </div>
              <p className="mt-0.5 text-gray-500">{log.message}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

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
