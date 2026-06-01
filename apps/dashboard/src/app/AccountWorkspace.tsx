// fallow-ignore-file complexity
// fallow-ignore-reason: Transitional workspace composition shell; route effect semantics are covered by accountWorkspaceRouteEffects.test.ts.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { QueryClient } from '@tanstack/react-query'

import {
  shouldResetWorkspaceSectionState,
  workspaceSectionIdForSection,
  type AccountRouteState,
} from '@/app/accountWorkspaceRouteEffects'
import { AccountDashboardView } from '@/components/workspace/AccountDashboardView'
import { DashboardSkeleton } from '@/components/dashboard/DashboardSkeleton'
import { FileInputsProvider } from '@/providers/FileInputsProvider'
import type { ToastItem } from '@/components/ui/toast'
import { normalizeError } from '@/lib/appErrors'
import type { ProfilePreview } from '@/lib/api'
import type { ApiError } from '@/lib/dashboard'
import { operationSafetyLabel, type OperationSafety } from '@/lib/accountSafety'
import { proxyErrorLabel, validateProxyInput, type AccountProxyInput } from '@/lib/proxy'
import { appRoutes } from '@/lib/routes'
import type { AuthErrorMessage, AuthPhase } from '@/modules/auth'
import { useAuthBootstrap } from '@/modules/auth'
import { useProfileDraft } from '@/modules/account-editing'
import type { FormState } from '@/modules/account-editing'
import { useDashboard } from '@/hooks/useDashboard'
import { useDashboardActions } from '@/hooks/useDashboardActions'
import { useDashboardPresentation } from '@/hooks/useDashboardPresentation'
import { useTerminalJobRefresh } from '@/hooks/useTerminalJobRefresh'
import {
  useDeleteStoryPostMutation,
  useRefreshRuntimeMutation,
} from '@/hooks/queries/useDashboardMutations'
import {
  useAccountCooldownsQuery,
  useAccountOperationLogsQuery,
  useAccountProxyQuery,
  useAccountRiskQuery,
  useAccountSafetyQuery,
  useAccountValidityChecksQuery,
  useCheckAccountProxyMutation,
  useCreateAccountSafetyOverrideMutation,
  useDeleteAccountProxyMutation,
  useRunAccountValidityCheckMutation,
  useSaveAccountProxyMutation,
} from '@/hooks/queries/useAccountsQueries'

type Notify = (toast: Omit<ToastItem, 'id'>) => void
type AuthBridge = {
  accountId: string | null
  applyAccountContext: (accountId: string) => void
  applyAuthStateResponse: Parameters<typeof useAuthBootstrap>[0]['applyAuthStateResponse']
  clearAccountContext: () => void
  setAuthError: React.Dispatch<React.SetStateAction<AuthErrorMessage | null>>
  setAuthErrorCode: React.Dispatch<React.SetStateAction<string | null>>
  setAuthPhase: React.Dispatch<React.SetStateAction<AuthPhase>>
  setAuthStep: Parameters<typeof useAuthBootstrap>[0]['setAuthStep']
  setOtpCode: (code: string) => void
  setPhoneNumber: (phone: string) => void
  setTwoFaPassword: (password: string) => void
  skipNextAuthBootstrapRef: React.MutableRefObject<boolean>
}
type WorkspaceRouteParams = {
  route: AccountRouteState
  setApiError: React.Dispatch<React.SetStateAction<ApiError | null>>
  setHiddenJobPanelKey: (key: string | null) => void
  setIsRealExecutionConfirmOpen: (value: boolean) => void
  setSubmittedPreview: (preview: ProfilePreview | null) => void
  transitionToPhase: (phase: AuthPhase) => void
  workspace: ReturnType<typeof useDashboard>
}

type RouteEffectsParams = WorkspaceRouteParams & {
  activeAccountId: string | null
  auth: AuthBridge
  authPhase: AuthPhase
  dashboardReady: boolean
  draft: ReturnType<typeof useProfileDraft>
}

function useWorkspaceLocalState(activeAccountId: string | null) {
  const [submittedPreview, setSubmittedPreview] = useState<ProfilePreview | null>(null)
  const [deletingStoryPostId, setDeletingStoryPostId] = useState<string | null>(null)
  const [isRealExecutionConfirmOpen, setIsRealExecutionConfirmOpen] = useState(false)
  const [hiddenJobPanelKey, setHiddenJobPanelKey] = useState<string | null>(null)
  return {
    accountCooldownsQuery: useAccountCooldownsQuery(activeAccountId),
    accountLogsQuery: useAccountOperationLogsQuery(activeAccountId),
    accountProxyQuery: useAccountProxyQuery(activeAccountId),
    accountRiskQuery: useAccountRiskQuery(activeAccountId),
    accountSafetyQuery: useAccountSafetyQuery(activeAccountId),
    checkProxyMutation: useCheckAccountProxyMutation(),
    deleteProxyMutation: useDeleteAccountProxyMutation(),
    deleteStoryPostMutation: useDeleteStoryPostMutation(),
    deletingStoryPostId,
    hiddenJobPanelKey,
    isRealExecutionConfirmOpen,
    refreshRuntimeMutation: useRefreshRuntimeMutation(),
    safetyOverrideMutation: useCreateAccountSafetyOverrideMutation(),
    saveProxyMutation: useSaveAccountProxyMutation(),
    setDeletingStoryPostId,
    setHiddenJobPanelKey,
    setIsRealExecutionConfirmOpen,
    setSubmittedPreview,
    submittedPreview,
    validityCheckMutation: useRunAccountValidityCheckMutation(),
    validityChecksQuery: useAccountValidityChecksQuery(activeAccountId),
  }
}

function useDashboardReady(activeAccountId: string | null, dashboard: ReturnType<typeof useDashboard>['dashboard'], isFormInitialized: boolean) {
  const dashboardReady = Boolean(activeAccountId && dashboard?.account.account_id === activeAccountId && isFormInitialized)
  const dashboardReadyRef = useRef(dashboardReady)
  useEffect(() => {
    dashboardReadyRef.current = dashboardReady
  }, [dashboardReady])
  return { dashboardReady, dashboardReadyRef }
}

function useBootstrapRefreshAndRouteEffects({
  activeAccountId,
  auth,
  authPhase,
  dashboardReady,
  dashboardReadyRef,
  draft,
  queryClient,
  route,
  setApiError,
  setHiddenJobPanelKey,
  setIsRealExecutionConfirmOpen,
  setSubmittedPreview,
  transitionToPhase,
  workspace,
}: WorkspaceRouteParams & {
  activeAccountId: string | null
  auth: AuthBridge
  authPhase: AuthPhase
  dashboardReady: boolean
  dashboardReadyRef: React.MutableRefObject<boolean>
  draft: ReturnType<typeof useProfileDraft>
  queryClient: QueryClient
}) {
  useAuthBootstrap({
    accountId: activeAccountId,
    applyAuthStateResponse: auth.applyAuthStateResponse,
    authPhase,
    clearAccountContext: auth.clearAccountContext,
    dashboardReadyRef,
    queryClient,
    loadDashboardState: workspace.loadDashboardState,
    formRef: draft.formRef,
    formBaselineRef: draft.formBaselineRef,
    formInitializedRef: draft.formInitializedRef,
    setForm: draft.setForm,
    setApiError,
    setAuthPhase: auth.setAuthPhase,
    setPhoneNumber: auth.setPhoneNumber,
    setIsBootRefreshing: workspace.setIsBootRefreshing,
    skipNextAuthBootstrapRef: auth.skipNextAuthBootstrapRef,
    setAuthError: auth.setAuthError,
    setAuthErrorCode: auth.setAuthErrorCode,
    setAuthStep: auth.setAuthStep,
  })
  useTerminalJobRefresh({
    accountId: activeAccountId,
    currentJobState: workspace.currentJob?.job_state,
    formBaselineRef: draft.formBaselineRef,
    formInitializedRef: draft.formInitializedRef,
    formRef: draft.formRef,
    loadDashboardState: workspace.loadDashboardState,
    setApiError,
    setForm: draft.setForm,
    terminalJobRefreshSeq: workspace.terminalJobRefreshSeq,
  })
  const routeEffects: RouteEffectsParams = {
    activeAccountId,
    auth,
    authPhase,
    dashboardReady,
    draft,
    route,
    setApiError,
    setHiddenJobPanelKey,
    setIsRealExecutionConfirmOpen,
    setSubmittedPreview,
    transitionToPhase,
    workspace,
  }
  useRouteEffects(routeEffects)
}

function useRouteEffects(params: RouteEffectsParams) {
  useAccountRouteSwitchEffect(params)
  useWorkspaceSectionRouteEffect(params)
  useDashboardLazyLoadEffect(params)
}

function useAccountRouteSwitchEffect({
  auth,
  draft,
  route,
  setApiError,
  setHiddenJobPanelKey,
  setIsRealExecutionConfirmOpen,
  setSubmittedPreview,
  transitionToPhase,
}: RouteEffectsParams) {
  const authAccountId = auth.accountId
  const applyAccountContext = auth.applyAccountContext
  const clearSelectedPhotoPreview = draft.clearSelectedPhotoPreview
  const routeAccountId = route.accountId
  const setIsRefreshingRuntime = draft.setIsRefreshingRuntime

  useEffect(() => {
    if (authAccountId === routeAccountId) return
    const id = window.setTimeout(() => {
      clearSelectedPhotoPreview()
      setSubmittedPreview(null)
      setApiError(null)
      setHiddenJobPanelKey(null)
      setIsRealExecutionConfirmOpen(false)
      setIsRefreshingRuntime(false)
      applyAccountContext(routeAccountId)
      transitionToPhase('auth-loading')
    }, 0)
    return () => window.clearTimeout(id)
  }, [
    applyAccountContext,
    authAccountId,
    clearSelectedPhotoPreview,
    routeAccountId,
    setApiError,
    setHiddenJobPanelKey,
    setIsRealExecutionConfirmOpen,
    setIsRefreshingRuntime,
    setSubmittedPreview,
    transitionToPhase,
  ])
}

function useWorkspaceSectionRouteEffect({
  dashboardReady,
  route,
  setHiddenJobPanelKey,
}: RouteEffectsParams) {
  const lastSectionRouteRef = useRef<AccountRouteState | null>(null)
  const routeAccountId = route.accountId
  const routeSection = route.section

  useEffect(() => {
    const nextRoute = {
      screen: 'account',
      accountId: routeAccountId,
      section: routeSection,
    } satisfies AccountRouteState
    if (!shouldResetWorkspaceSectionState(lastSectionRouteRef.current, nextRoute)) return
    lastSectionRouteRef.current = nextRoute
    setHiddenJobPanelKey(null)
  }, [routeAccountId, routeSection, setHiddenJobPanelKey])

  useEffect(() => {
    if (!dashboardReady) return
    const targetId = workspaceSectionIdForSection(routeSection)
    if (!targetId) return
    const id = window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }, 0)
    return () => window.clearTimeout(id)
  }, [dashboardReady, routeAccountId, routeSection])
}

function useDashboardLazyLoadEffect({
  activeAccountId,
  authPhase,
  dashboardReady,
  draft,
  workspace,
}: RouteEffectsParams) {
  const formBaselineRef = draft.formBaselineRef
  const formInitializedRef = draft.formInitializedRef
  const formRef = draft.formRef
  const loadDashboardState = workspace.loadDashboardState
  const setForm = draft.setForm

  useEffect(() => {
    if (!activeAccountId || authPhase !== 'dashboard' || dashboardReady) return
    const id = window.setTimeout(
      () =>
        void loadDashboardState(
          activeAccountId,
          formRef,
          formBaselineRef,
          formInitializedRef,
          setForm,
        ),
      0,
    )
    return () => window.clearTimeout(id)
  }, [
    activeAccountId,
    authPhase,
    dashboardReady,
    formBaselineRef,
    formInitializedRef,
    formRef,
    loadDashboardState,
    setForm,
  ])
}

function useAccountOperationHandlers({
  activeAccountId,
  localState,
  notify,
}: {
  activeAccountId: string | null
  localState: ReturnType<typeof useWorkspaceLocalState>
  notify: Notify
}) {
  const handleCheckValidity = useCallback(async () => {
    if (!activeAccountId) return
    try {
      await localState.validityCheckMutation.mutateAsync(activeAccountId)
      notify({ tone: 'success', title: 'Проверка аккаунта завершена' })
    } catch {
      notify({ tone: 'error', title: 'Не удалось проверить аккаунт' })
    }
  }, [activeAccountId, localState.validityCheckMutation, notify])
  const handleCreateSafetyOverride = useCallback(async (item: OperationSafety, reason: string) => {
    if (!activeAccountId) return
    try {
      await localState.safetyOverrideMutation.mutateAsync({
        accountId: activeAccountId,
        operation: String(item.operation),
        reason,
        requestedBlockers: item.blockers,
      })
      notify({ tone: 'success', title: 'Ручной разбор сохранён', description: operationSafetyLabel(item) })
    } catch {
      notify({ tone: 'error', title: 'Не удалось сохранить ручной разбор' })
    }
  }, [activeAccountId, localState.safetyOverrideMutation, notify])
  const handleSaveProxy = useCallback(async (payload: AccountProxyInput) => {
    if (!activeAccountId) return
    const validationError = validateProxyInput(payload)
    if (validationError) return notify({ tone: 'error', title: validationError })
    try {
      await localState.saveProxyMutation.mutateAsync({ accountId: activeAccountId, payload })
      notify({ tone: 'success', title: 'Proxy сохранён' })
    } catch (error) {
      const apiErr = normalizeError(error)
      notify({ tone: 'error', title: proxyErrorLabel(apiErr.error_code) || 'Не удалось сохранить proxy' })
    }
  }, [activeAccountId, localState.saveProxyMutation, notify])
  return {
    handleCheckProxy: useMutationToastHandler(activeAccountId, localState.checkProxyMutation.mutateAsync, notify, 'Проверка proxy завершена', 'Не удалось проверить proxy'),
    handleCheckValidity,
    handleCreateSafetyOverride,
    handleDeleteProxy: useMutationToastHandler(activeAccountId, localState.deleteProxyMutation.mutateAsync, notify, 'Proxy удалён', 'Не удалось удалить proxy'),
    handleSaveProxy,
  }
}

function useMutationToastHandler(
  activeAccountId: string | null,
  mutateAsync: (accountId: string) => Promise<unknown>,
  notify: Notify,
  successTitle: string,
  errorTitle: string,
) {
  return useCallback(async () => {
    if (!activeAccountId) return
    try {
      await mutateAsync(activeAccountId)
      notify({ tone: 'success', title: successTitle })
    } catch {
      notify({ tone: 'error', title: errorTitle })
    }
  }, [activeAccountId, errorTitle, mutateAsync, notify, successTitle])
}

function useWorkspaceActions({
  activeAccountId,
  auth,
  draft,
  localState,
  navigateToRoute,
  notify,
  setApiError,
  workspace,
}: {
  activeAccountId: string | null
  auth: AuthBridge
  draft: ReturnType<typeof useProfileDraft>
  localState: ReturnType<typeof useWorkspaceLocalState>
  navigateToRoute: (href: string) => void
  notify: Notify
  setApiError: React.Dispatch<React.SetStateAction<ApiError | null>>
  workspace: ReturnType<typeof useDashboard>
}) {
  const actions = useDashboardActions({
    accountId: activeAccountId,
    changedItems: draft.changedItems,
    clearAccountContext: auth.clearAccountContext,
    clearSelectedPhotoPreview: draft.clearSelectedPhotoPreview,
    confirmDiagnostics: workspace.dashboard?.diagnostics,
    createProfileJob: draft.handleCreateJob,
    deleteStoryPost: (post) => localState.deleteStoryPostMutation.mutateAsync({ accountId: activeAccountId!, postId: post.id }),
    formBaselineRef: draft.formBaselineRef,
    formInitializedRef: draft.formInitializedRef,
    formRef: draft.formRef,
    loadDashboardState: workspace.loadDashboardState,
    loadJobState: workspace.loadJobState,
    notify,
    patchDashboardPipeline: workspace.patchDashboardPipeline,
    preview: draft.preview,
    refreshRuntime: localState.refreshRuntimeMutation.mutateAsync,
    resetDashboard: workspace.resetDashboard,
    setApiError,
    setDeletingStoryPostId: localState.setDeletingStoryPostId,
    setForm: draft.setForm,
    setHiddenJobPanelKey: localState.setHiddenJobPanelKey,
    setIsRealExecutionConfirmOpen: localState.setIsRealExecutionConfirmOpen,
    setIsRefreshingRuntime: draft.setIsRefreshingRuntime,
    setOtpCode: auth.setOtpCode,
    setPhoneNumber: auth.setPhoneNumber,
    setSubmittedPreview: localState.setSubmittedPreview,
    setTwoFaPassword: auth.setTwoFaPassword,
    terminalJobStates: workspace.terminalJobStates,
  })
  const handleDashboardBackToAccounts = useCallback(() => {
    actions.handleBackToAccounts()
    navigateToRoute(appRoutes.accounts())
  }, [actions, navigateToRoute])
  return { ...actions, handleDashboardBackToAccounts }
}

export function AccountWorkspace({
  activeAccountId,
  auth,
  authPhase,
  initialBundle,
  initialDashboard,
  initialForm,
  navigateToRoute,
  notify,
  pollingIntervalMs,
  queryClient,
  route,
  transitionToPhase,
}: {
  activeAccountId: string
  auth: AuthBridge
  authPhase: AuthPhase
  initialBundle: Parameters<typeof useDashboard>[0]['initialBundle']
  initialDashboard: Parameters<typeof useProfileDraft>[0]['initialDashboard']
  initialForm: FormState
  navigateToRoute: (href: string) => void
  notify: Notify
  pollingIntervalMs: number
  queryClient: QueryClient
  route: AccountRouteState
  transitionToPhase: (phase: AuthPhase) => void
}) {
  const localState = useWorkspaceLocalState(activeAccountId)
  const workspace = useDashboard({ accountId: activeAccountId, authPhase, initialBundle, pollingIntervalMs })
  const draft = useProfileDraft({ accountId: activeAccountId, dashboard: workspace.dashboard, initialForm, initialDashboard, notify })
  const { dashboardReady, dashboardReadyRef } = useDashboardReady(activeAccountId, workspace.dashboard, draft.isFormInitialized)
  const [apiError, setApiError] = useState<ApiError | null>(null)
  const presentation = useDashboardPresentation({
    apiError,
    currentJob: workspace.currentJob,
    currentSteps: workspace.currentSteps,
    hiddenJobPanelKey: localState.hiddenJobPanelKey,
    jobs: workspace.jobs,
    preview: draft.preview,
    submittedPreview: localState.submittedPreview,
    terminalJobStates: workspace.terminalJobStates,
  })
  useBootstrapRefreshAndRouteEffects({ activeAccountId, auth, authPhase, dashboardReady, dashboardReadyRef, draft, queryClient, route, setApiError, setHiddenJobPanelKey: localState.setHiddenJobPanelKey, setIsRealExecutionConfirmOpen: localState.setIsRealExecutionConfirmOpen, setSubmittedPreview: localState.setSubmittedPreview, transitionToPhase, workspace })
  const accountHandlers = useAccountOperationHandlers({ activeAccountId, localState, notify })
  const actions = useWorkspaceActions({ activeAccountId, auth, draft, localState, navigateToRoute, notify, setApiError, workspace })

  if (!dashboardReady) return <DashboardSkeleton />
  return (
    <FileInputsProvider onPhotoChange={(file) => void draft.handlePhotoUpload(file)} onAudioChange={(file) => void draft.handleAudioUpload(file)} onStoryChange={(file, kind) => void draft.handleStoryUpload(file, kind)}>
      <AccountDashboardView
        route={route}
        accountId={activeAccountId}
        dashboard={workspace.dashboard}
        jobs={workspace.jobs}
        currentJob={workspace.currentJob}
        storyCapabilities={workspace.storyCapabilities}
        form={draft.form}
        changeItems={draft.changeItems}
        changedItems={draft.changedItems}
        currentProfile={draft.currentProfile}
        photoPreview={draft.photoPreview}
        isUploadingPhoto={draft.isUploadingPhoto}
        isUploadingAudio={draft.isUploadingAudio}
        isUploadingStory={draft.isUploadingStory}
        selectedPhotoName={draft.selectedPhotoName}
        selectedAudioName={draft.selectedAudioName}
        preview={draft.preview}
        isSubmittingJob={draft.isSubmittingJob}
        isRefreshingRuntime={draft.isRefreshingRuntime}
        isBootRefreshing={workspace.isBootRefreshing}
        isLoading={workspace.isLoading}
        deletingStoryPostId={localState.deletingStoryPostId}
        visibleBanner={presentation.runtimeBanner}
        shouldShowJobPanel={presentation.shouldShowJobPanel}
        jobDisplayItems={presentation.jobDisplayItems}
        jobPanelKey={presentation.jobPanelKey}
        jobProgressSummary={presentation.jobProgressSummary}
        jobResultSummary={presentation.jobResultSummary}
        accountProxyData={localState.accountProxyQuery.data ?? null}
        accountSafetyData={localState.accountSafetyQuery.data ?? null}
        accountRiskData={localState.accountRiskQuery.data ?? null}
        accountCooldownsData={localState.accountCooldownsQuery.data ?? []}
        validityChecksData={localState.validityChecksQuery.data ?? []}
        accountLogsData={localState.accountLogsQuery.data ?? null}
        isCheckingValidity={localState.validityCheckMutation.isPending}
        isCheckingProxy={localState.checkProxyMutation.isPending}
        isDeletingProxy={localState.deleteProxyMutation.isPending}
        isSavingProxy={localState.saveProxyMutation.isPending}
        isRealExecutionConfirmOpen={localState.isRealExecutionConfirmOpen}
        navigateToRoute={navigateToRoute}
        onBack={actions.handleDashboardBackToAccounts}
        onSync={actions.handleRefreshRuntime}
        onCheckValidity={accountHandlers.handleCheckValidity}
        onClearPhoto={draft.handleClearProfilePhoto}
        onKeepAudio={draft.handleKeepProfileAudio}
        onRemoveAudio={draft.handleRemoveProfileAudio}
        onUpdateStory={draft.handleUpdateStory}
        onRemoveStory={draft.handleRemoveStory}
        onDeleteStoryPost={actions.handleDeleteStoryPost}
        onReset={draft.handleReset}
        onCreateJob={actions.handleCreateJob}
        onCreateSafetyOverride={accountHandlers.handleCreateSafetyOverride}
        onSaveProxy={accountHandlers.handleSaveProxy}
        onCheckProxy={accountHandlers.handleCheckProxy}
        onDeleteProxy={accountHandlers.handleDeleteProxy}
        onHideJobPanel={(key) => localState.setHiddenJobPanelKey(key)}
        onCancelRealExecution={() => localState.setIsRealExecutionConfirmOpen(false)}
        onConfirmRealExecution={() => void actions.confirmRealExecution()}
        onFormChange={draft.updateForm}
      />
    </FileInputsProvider>
  )
}
