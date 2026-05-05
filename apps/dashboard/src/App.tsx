/**
 * App – root application controller.
 *
 * Responsibilities:
 *  - Rendering the screen selected by TanStack Router
 *  - Managing auth/dashboard phases inside account workspace routes
 *  - Composing the three custom hooks: useAuthFlow, useDashboard, useProfileDraft
 *  - Wiring hidden file inputs for photo / audio / story upload
 */

import { Check } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState, useTransition } from 'react'

import { AuthScreen } from '@/components/auth/AuthScreen'
import { DashboardActionBar } from '@/components/dashboard/DashboardActionBar'
import { AccountHeader } from '@/components/dashboard/accountWorkspace/AccountHeader'
import { DashboardSkeleton } from '@/components/dashboard/DashboardSkeleton'
import { ErrorBanner } from '@/components/dashboard/ErrorBanner'
import { JobStepPanel } from '@/components/dashboard/jobs/JobPanels'
import { ProfileEditor } from '@/components/dashboard/profile/ProfilePanels'
import { StoriesBlock } from '@/components/dashboard/profile/StoriesBlock'
import { MusicBlock } from '@/components/dashboard/profile/MusicBlock'
import { AnimatedTabs } from '@/components/ui/AnimatedTabs'
import { AccountRiskTab } from '@/components/dashboard/accountWorkspace/AccountRiskTab'
import {
  OperationLogsPanel,
  ProxyPanel,
  RealTelegramExecutionModal,
  SafetyHistoryPanel,
} from '@/components/dashboard/accountWorkspace/WorkspacePanels'
import { ToastViewport, type ToastItem } from '@/components/ui/toast'
import { getPollingIntervalMs } from '@/lib/config'
import { normalizeError } from '@/lib/appErrors'
import {
  type ProfilePreview,
} from '@/lib/api'
import {
  buildJobMetrics,
  type ApiError,
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
  useAccountRiskQuery,
  useAccountCooldownsQuery,
  useAccountProxyQuery,
  useCheckAccountProxyMutation,
  useDeleteAccountProxyMutation,
  useRunAccountValidityCheckMutation,
  useSaveAccountProxyMutation,
} from '@/hooks/queries/useAccountsQueries'
import { operationSafetyLabel, type OperationSafety } from '@/lib/accountSafety'
import {
  proxyErrorLabel,
  validateProxyInput,
  type AccountProxyInput,
} from '@/lib/proxy'
import type { AuthPhase } from '@/lib/auth'
import { accountWorkspaceRoute, appRoutes, type AccountWorkspaceSection, type AppRouteState } from '@/lib/routes'

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
  const accountRiskQuery = useAccountRiskQuery(activeAccountId)
  const accountCooldownsQuery = useAccountCooldownsQuery(activeAccountId)
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
      {dashboard?.account ? (
        <AccountHeader
          account={dashboard.account}
          isChecking={validityCheckMutation.isPending}
          isSyncing={isRefreshingRuntime || isBootRefreshing || isLoading}
          proxyStatus={accountProxyQuery.data?.status ?? accountSafetyQuery.data?.proxy_status}
          risk={accountRiskQuery.data ?? null}
          onCheck={handleCheckValidity}
          onBack={handleDashboardBackToAccounts}
          onSync={handleRefreshRuntime}
        />
      ) : (
        <div className="border-b border-gray-200/70 bg-white px-4 py-3 sm:px-6">
          <div className="mx-auto max-w-6xl text-sm text-gray-500">Загружаем аккаунт...</div>
        </div>
      )}

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-4 pb-24">
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

        <div className="mb-4">
          <AnimatedTabs
            value={route.section}
            onValueChange={(section) => {
              navigateToRoute(accountWorkspaceRoute(accountId, section as AccountWorkspaceSection))
            }}
            tabs={[
              {
                value: 'profile',
                label: 'Профиль',
                content: (
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
                ),
              },
              {
                value: 'stories',
                label: 'Истории',
                content: (
                  <div className="py-4">
                    <StoriesBlock
                      stories={form.stories}
                      storyPosts={dashboard?.story_posts ?? []}
                      storyCapabilities={storyCapabilities}
                      isUploadingStory={isUploadingStory}
                      deletingStoryPostId={deletingStoryPostId}
                      onChooseStoryImage={() => storyImageInputRef.current?.click()}
                      onUpdateStory={handleUpdateStory}
                      onRemoveStory={handleRemoveStory}
                      onDeleteStoryPost={handleDeleteStoryPost}
                    />
                  </div>
                ),
              },
              {
                value: 'music',
                label: 'Музыка',
                content: (
                  <div className="py-4">
                    <MusicBlock
                      profileAudio={dashboard?.profile_audio ?? null}
                      profileAudioAction={form.profileAudioAction}
                      selectedAudioName={selectedAudioName}
                      isUploadingAudio={isUploadingAudio}
                      onChooseAudio={() => audioInputRef.current?.click()}
                      onKeepAudio={handleKeepProfileAudio}
                      onRemoveAudio={handleRemoveProfileAudio}
                    />
                  </div>
                ),
              },
              {
                value: 'proxy',
                label: 'Прокси',
                content: (
                  <div className="py-4">
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
                  </div>
                ),
              },
              {
                value: 'jobs',
                label: 'Задачи',
                content: (
                  <div className="py-4 space-y-4">
                    {shouldShowJobPanel ? (
                      <JobStepPanel
                        currentJob={currentJob}
                        items={jobDisplayItems}
                        onHide={jobPanelKey ? () => setHiddenJobPanelKey(jobPanelKey) : undefined}
                        progressSummary={jobProgressSummary}
                        resultSummary={jobResultSummary}
                      />
                    ) : (
                      <div className="text-sm text-gray-500">Нет активных задач.</div>
                    )}
                    <OperationLogsPanel logs={(accountLogsQuery.data?.items ?? []).slice(0, 10)} title="История задач" />
                  </div>
                ),
              },
              {
                value: 'risk',
                label: 'Риск и аудит',
                content: (
                  <div className="space-y-4">
                    <AccountRiskTab
                      accountState={dashboard?.account.account_state}
                      cooldowns={(accountCooldownsQuery.data ?? []).map((cooldown) => ({
                        operation: cooldown.operation,
                        expires_at: cooldown.retry_after_at,
                      }))}
                      proxyStatus={accountProxyQuery.data?.status ?? accountSafetyQuery.data?.proxy_status}
                      risk={accountRiskQuery.data ?? null}
                      runtimeHealth={dashboard?.account.runtime_health ?? accountSafetyQuery.data?.health_status}
                      validityChecks={validityChecksQuery.data ?? []}
                    />
                    <OperationLogsPanel logs={accountLogsQuery.data?.items ?? []} title="Полный журнал аудита" />
                  </div>
                ),
              },
            ]}
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
