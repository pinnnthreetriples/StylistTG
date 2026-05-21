/**
 * AccountDashboardView – the main dashboard view for an active account workspace.
 *
 * Renders: AccountHeader, WarmupIsolationBanner, animated tab layout, action bar,
 * floating job panel, and the real-execution confirmation modal.
 */

import { Check } from 'lucide-react'
import { useCallback } from 'react'

import { AccountHeader } from '@/components/dashboard/accountWorkspace/AccountHeader'
import { ProfileCompletenessBar } from '@/modules/shared/ProfileCompletenessBar'
import { SafetyGateBanner } from '@/modules/shared/SafetyGateBanner'
import { WarmupIsolationBanner } from '@/modules/warmup'
import { DashboardActionBar } from '@/components/dashboard/DashboardActionBar'
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
import { useFileInputs } from '@/providers/FileInputsProvider'
import { buildJobMetrics } from '@/lib/dashboard'
import type {
  ChangeItem,
  CurrentProfile,
  FormState,
  PhotoPreviewState,
  RuntimeBanner,
} from '@/lib/dashboard'
import type { JobDetail, JobSummary, ProfilePreview, StoryCapabilities, StoryDraftPayload, StoryPost } from '@/lib/api'
import type { AccountOperationCooldown, AccountSafety, AccountValidityCheck, OperationSafety } from '@/lib/accountSafety'
import type { AccountProxy, AccountProxyInput } from '@/lib/proxy'
import type { AccountWorkspaceSection, AppRouteState } from '@/lib/routes'
import { accountWorkspaceRoute } from '@/lib/routes'
import type { AccountRisk } from '@/features/accounts/accountRisk'
import type { JobDisplayItem, JobProgressSummary, JobResultSummary } from '@/lib/jobs'
import type { OperationLogPage } from '@/lib/operationLogs'
import type { DashboardBundle } from '@/lib/queries'

type AccountRouteState = Extract<AppRouteState, { screen: 'account' }>

export type AccountDashboardViewProps = {
  route: AccountRouteState
  accountId: string

  // Dashboard data
  dashboard: DashboardBundle['dashboard'] | null
  jobs: JobSummary[]
  currentJob: JobDetail | null
  storyCapabilities: StoryCapabilities | null

  // Form + draft
  form: FormState
  changeItems: ChangeItem[]
  changedItems: ChangeItem[]
  currentProfile: CurrentProfile
  photoPreview: PhotoPreviewState
  isUploadingPhoto: boolean
  isUploadingAudio: boolean
  isUploadingStory: boolean
  selectedPhotoName: string | null
  selectedAudioName: string | null
  preview: ProfilePreview | null
  isSubmittingJob: boolean
  isRefreshingRuntime: boolean
  isBootRefreshing: boolean
  isLoading: boolean
  deletingStoryPostId: string | null

  // Presentation
  visibleBanner: RuntimeBanner | null
  shouldShowJobPanel: boolean
  jobDisplayItems: JobDisplayItem[]
  jobPanelKey: string | null
  jobProgressSummary: JobProgressSummary
  jobResultSummary: JobResultSummary

  // Account queries
  accountProxyData: AccountProxy | null
  accountSafetyData: AccountSafety | null
  accountRiskData: AccountRisk | null
  accountCooldownsData: AccountOperationCooldown[]
  validityChecksData: AccountValidityCheck[]
  accountLogsData: OperationLogPage | null

  // Mutation states
  isCheckingValidity: boolean
  isCheckingProxy: boolean
  isDeletingProxy: boolean
  isSavingProxy: boolean
  isRealExecutionConfirmOpen: boolean

  // Navigation
  navigateToRoute: (href: string) => void

  // Handlers
  onBack: () => void
  onSync: () => void
  onCheckValidity: () => void
  onClearPhoto: () => void
  onKeepAudio: () => void
  onRemoveAudio: () => void
  onUpdateStory: (clientId: string, patch: Partial<StoryDraftPayload>) => void
  onRemoveStory: (clientId: string) => void
  onDeleteStoryPost: (post: StoryPost) => void
  onReset: () => void
  onCreateJob: () => void
  onCreateSafetyOverride: (item: OperationSafety, reason: string) => void
  onSaveProxy: (payload: AccountProxyInput) => void
  onCheckProxy: () => void
  onDeleteProxy: () => void
  onHideJobPanel: (key: string) => void
  onCancelRealExecution: () => void
  onConfirmRealExecution: () => void
  onFormChange: (next: FormState | ((previous: FormState) => FormState)) => void
}

export function AccountDashboardView({
  route,
  accountId,
  dashboard,
  jobs,
  currentJob,
  storyCapabilities,
  form,
  changeItems,
  changedItems,
  currentProfile,
  photoPreview,
  isUploadingPhoto,
  isUploadingAudio,
  isUploadingStory,
  selectedPhotoName,
  selectedAudioName,
  preview,
  isSubmittingJob,
  isRefreshingRuntime,
  isBootRefreshing,
  isLoading,
  deletingStoryPostId,
  visibleBanner,
  shouldShowJobPanel,
  jobDisplayItems,
  jobPanelKey,
  jobProgressSummary,
  jobResultSummary,
  accountProxyData,
  accountSafetyData,
  accountRiskData,
  accountCooldownsData,
  validityChecksData,
  accountLogsData,
  isCheckingValidity,
  isCheckingProxy,
  isDeletingProxy,
  isSavingProxy,
  isRealExecutionConfirmOpen,
  navigateToRoute,
  onBack,
  onSync,
  onCheckValidity,
  onClearPhoto,
  onKeepAudio,
  onRemoveAudio,
  onUpdateStory,
  onRemoveStory,
  onDeleteStoryPost,
  onReset,
  onCreateJob,
  onCreateSafetyOverride,
  onSaveProxy,
  onCheckProxy,
  onDeleteProxy,
  onHideJobPanel,
  onCancelRealExecution,
  onConfirmRealExecution,
  onFormChange,
}: AccountDashboardViewProps) {
  const { triggerPhotoInput, triggerAudioInput, triggerStoryInput } = useFileInputs()

  const handleTabChange = useCallback(
    (section: string) => {
      navigateToRoute(accountWorkspaceRoute(accountId, section as AccountWorkspaceSection))
    },
    [accountId, navigateToRoute],
  )

  return (
    <div className="min-h-screen bg-cream">
      {dashboard?.account ? (
        <AccountHeader
          account={dashboard.account}
          isChecking={isCheckingValidity}
          isSyncing={isRefreshingRuntime || isBootRefreshing || isLoading}
          proxyStatus={accountProxyData?.status ?? accountSafetyData?.proxy_status}
          risk={accountRiskData ?? null}
          onCheck={onCheckValidity}
          onBack={onBack}
          onSync={onSync}
        />
      ) : (
        <div className="border-b border-gray-200/70 bg-white px-4 py-3 sm:px-6">
          <div className="mx-auto max-w-6xl text-sm text-gray-500">Загружаем аккаунт...</div>
        </div>
      )}

      {accountId ? (
        <div className="mx-auto grid max-w-6xl gap-3 px-4 pt-3 sm:px-6">
          <SafetyGateBanner accountId={accountId} intent="commenting" />
          <ProfileCompletenessBar accountId={accountId} />
          <WarmupIsolationBanner accountId={accountId} />
        </div>
      ) : null}

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-4 pb-24">
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
            <SafetyHistoryPanel checks={validityChecksData} />
            <OperationLogsPanel logs={accountLogsData?.items ?? []} title="История операций аккаунта" />
          </>
        ) : null}

        <div className="mb-4">
          <AnimatedTabs
            value={route.section}
            onValueChange={handleTabChange}
            tabs={[
              {
                value: 'profile',
                label: 'Профиль',
                content: (
                  <ProfileEditor
                    changeItems={changeItems}
                    hasSelectedPhoto={Boolean(form.profilePhotoAssetId)}
                    photoPreviewUrl={photoPreview.imageUrl}
                    onClearPhoto={onClearPhoto}
                    onChoosePhoto={triggerPhotoInput}
                    isUploadingPhoto={isUploadingPhoto}
                    selectedPhotoName={selectedPhotoName}
                    profileAudio={dashboard?.profile_audio ?? null}
                    profileAudioAction={form.profileAudioAction}
                    selectedAudioName={selectedAudioName}
                    isUploadingAudio={isUploadingAudio}
                    onChooseAudio={triggerAudioInput}
                    onKeepAudio={onKeepAudio}
                    onRemoveAudio={onRemoveAudio}
                    stories={form.stories}
                    isUploadingStory={isUploadingStory}
                    deletingStoryPostId={deletingStoryPostId}
                    onChooseStoryImage={triggerStoryInput}
                    onUpdateStory={onUpdateStory}
                    onRemoveStory={onRemoveStory}
                    onDeleteStoryPost={onDeleteStoryPost}
                    storyPosts={dashboard?.story_posts ?? []}
                    storyCapabilities={storyCapabilities}
                    currentProfile={currentProfile}
                    form={form}
                    onChange={onFormChange}
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
                      onChooseStoryImage={triggerStoryInput}
                      onUpdateStory={onUpdateStory}
                      onRemoveStory={onRemoveStory}
                      onDeleteStoryPost={onDeleteStoryPost}
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
                      onChooseAudio={triggerAudioInput}
                      onKeepAudio={onKeepAudio}
                      onRemoveAudio={onRemoveAudio}
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
                      key={accountProxyData ? `${accountProxyData.proxy_type}:${accountProxyData.host}:${accountProxyData.port}:${accountProxyData.username ?? ''}:${accountProxyData.has_password}` : 'proxy-empty'}
                      isChecking={isCheckingProxy}
                      isDeleting={isDeletingProxy}
                      isSaving={isSavingProxy}
                      onCheck={onCheckProxy}
                      onDelete={onDeleteProxy}
                      onSave={onSaveProxy}
                      proxy={accountProxyData ?? null}
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
                        onHide={jobPanelKey ? () => onHideJobPanel(jobPanelKey) : undefined}
                        progressSummary={jobProgressSummary}
                        resultSummary={jobResultSummary}
                      />
                    ) : (
                      <div className="text-sm text-gray-500">Нет активных задач.</div>
                    )}
                    <OperationLogsPanel logs={(accountLogsData?.items ?? []).slice(0, 10)} title="История задач" />
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
                      cooldowns={(accountCooldownsData ?? []).map((cooldown) => ({
                        operation: cooldown.operation,
                        expires_at: cooldown.retry_after_at,
                      }))}
                      proxyStatus={accountProxyData?.status ?? accountSafetyData?.proxy_status}
                      risk={accountRiskData ?? null}
                      runtimeHealth={dashboard?.account.runtime_health ?? accountSafetyData?.health_status}
                      validityChecks={validityChecksData}
                    />
                    <OperationLogsPanel logs={accountLogsData?.items ?? []} title="Полный журнал аудита" />
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
        onReset={onReset}
        onCreateJob={onCreateJob}
        onCreateSafetyOverride={onCreateSafetyOverride}
      />

      {shouldShowJobPanel ? (
        <div id="account-workspace-jobs">
          <JobStepPanel
            currentJob={currentJob}
            items={jobDisplayItems}
            onHide={jobPanelKey ? () => onHideJobPanel(jobPanelKey) : undefined}
            progressSummary={jobProgressSummary}
            resultSummary={jobResultSummary}
          />
        </div>
      ) : null}

      {isRealExecutionConfirmOpen ? (
        <RealTelegramExecutionModal
          changedItems={changedItems}
          isSubmitting={isSubmittingJob}
          onCancel={onCancelRealExecution}
          onConfirm={onConfirmRealExecution}
        />
      ) : null}
    </div>
  )
}
