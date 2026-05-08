/**
 * App – root application controller for account workspace.
 *
 * Responsibilities:
 *  - Composing hooks (useAuthFlow, useDashboard, useProfileDraft, useDashboardActions)
 *  - Managing auth/dashboard phase transitions
 *  - Delegating rendering to AuthScreen or AccountDashboardView
 */

import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState, useTransition } from 'react'

import { AuthScreen } from '@/components/auth/AuthScreen'
import { DashboardSkeleton } from '@/components/dashboard/DashboardSkeleton'
import { AccountDashboardView } from '@/components/workspace/AccountDashboardView'
import { ToastProvider, useToast } from '@/providers/ToastProvider'
import { FileInputsProvider } from '@/providers/FileInputsProvider'
import { getPollingIntervalMs } from '@/lib/config'
import { normalizeError } from '@/lib/appErrors'
import type { ProfilePreview } from '@/lib/api'
import type { ApiError } from '@/lib/dashboard'
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

function AppInner({ route }: { route: AccountRouteState }) {
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [, startNavigationTransition] = useTransition()
  const activeAccountId = route.accountId
  const { initialAccountId, initialBundle, initialDashboard, initialForm } = useDashboardInitialState(route.accountId, queryClient)

  // ── State ─────────────────────────────────────────────────────────────────────
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

  // ── Profile draft ─────────────────────────────────────────────────────────────
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

  // ── Dashboard readiness ───────────────────────────────────────────────────────
  const dashboardReady = Boolean(
    activeAccountId && dashboard?.account.account_id === activeAccountId && isFormInitialized,
  )
  const dashboardReadyRef = useRef(dashboardReady)

  useEffect(() => {
    dashboardReadyRef.current = dashboardReady
  }, [dashboardReady])

  // ── Presentation ──────────────────────────────────────────────────────────────
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

  // ── Actions ───────────────────────────────────────────────────────────────────
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
        const apiErr = normalizeError(error)
        notify({
          tone: 'error',
          title: proxyErrorLabel(apiErr.error_code) || 'Не удалось сохранить proxy',
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

  // ── Account switch effect ─────────────────────────────────────────────────────
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

  // ── Section scroll effect ─────────────────────────────────────────────────────
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
    <FileInputsProvider
      onPhotoChange={(file) => void handlePhotoUpload(file)}
      onAudioChange={(file) => void handleAudioUpload(file)}
      onStoryChange={(file, kind) => void handleStoryUpload(file, kind)}
    >
      <AccountDashboardView
        route={route}
        accountId={activeAccountId!}
        dashboard={dashboard}
        jobs={jobs}
        currentJob={currentJob}
        storyCapabilities={storyCapabilities}
        form={form}
        changeItems={changeItems}
        changedItems={changedItems}
        currentProfile={currentProfile}
        photoPreview={photoPreview}
        isUploadingPhoto={isUploadingPhoto}
        isUploadingAudio={isUploadingAudio}
        isUploadingStory={isUploadingStory}
        selectedPhotoName={selectedPhotoName}
        selectedAudioName={selectedAudioName}
        preview={preview}
        isSubmittingJob={isSubmittingJob}
        isRefreshingRuntime={isRefreshingRuntime}
        isBootRefreshing={isBootRefreshing}
        isLoading={isLoading}
        deletingStoryPostId={deletingStoryPostId}
        visibleBanner={visibleBanner}
        shouldShowJobPanel={shouldShowJobPanel}
        jobDisplayItems={jobDisplayItems}
        jobPanelKey={jobPanelKey}
        jobProgressSummary={jobProgressSummary}
        jobResultSummary={jobResultSummary}
        accountProxyData={accountProxyQuery.data ?? null}
        accountSafetyData={accountSafetyQuery.data ?? null}
        accountRiskData={accountRiskQuery.data ?? null}
        accountCooldownsData={accountCooldownsQuery.data ?? []}
        validityChecksData={validityChecksQuery.data ?? []}
        accountLogsData={accountLogsQuery.data ?? null}
        isCheckingValidity={validityCheckMutation.isPending}
        isCheckingProxy={checkProxyMutation.isPending}
        isDeletingProxy={deleteProxyMutation.isPending}
        isSavingProxy={saveProxyMutation.isPending}
        isRealExecutionConfirmOpen={isRealExecutionConfirmOpen}
        navigateToRoute={navigateToRoute}
        onBack={handleDashboardBackToAccounts}
        onSync={handleRefreshRuntime}
        onCheckValidity={handleCheckValidity}
        onClearPhoto={handleClearProfilePhoto}
        onKeepAudio={handleKeepProfileAudio}
        onRemoveAudio={handleRemoveProfileAudio}
        onUpdateStory={handleUpdateStory}
        onRemoveStory={handleRemoveStory}
        onDeleteStoryPost={handleDeleteStoryPost}
        onReset={handleReset}
        onCreateJob={handleCreateJob}
        onCreateSafetyOverride={handleCreateSafetyOverride}
        onSaveProxy={handleSaveProxy}
        onCheckProxy={handleCheckProxy}
        onDeleteProxy={handleDeleteProxy}
        onHideJobPanel={(key) => setHiddenJobPanelKey(key)}
        onCancelRealExecution={() => setIsRealExecutionConfirmOpen(false)}
        onConfirmRealExecution={() => void confirmRealExecution()}
        onFormChange={draft.updateForm}
      />
    </FileInputsProvider>
  )
}

function App({ route }: { route: AccountRouteState }) {
  return (
    <ToastProvider>
      <AppInner route={route} />
    </ToastProvider>
  )
}

export default App
