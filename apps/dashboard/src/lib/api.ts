import {
  cancelJob as cancelTypedJob,
  checkAccountProxy as checkTypedAccountProxy,
  createAccountSafetyOverride as createTypedAccountSafetyOverride,
  createProfileJob as createTypedProfileJob,
  deleteAccount as deleteTypedAccount,
  deleteAccountProxy as deleteTypedAccountProxy,
  deleteJob as deleteTypedJob,
  deleteStoryPost as deleteTypedStoryPost,
  fetchAccountOperationLogs as fetchTypedAccountOperationLogs,
  fetchAccountProxy as fetchTypedAccountProxy,
  fetchProfileCompleteness as fetchTypedProfileCompleteness,
  fetchAccountRisk as fetchTypedAccountRisk,
  fetchAccountRiskSummary as fetchTypedAccountRiskSummary,
  fetchAccountDeletionPreview as fetchTypedAccountDeletionPreview,
  createAccountDeletionRequest as createTypedAccountDeletionRequest,
  fetchAccountDeletionRequests as fetchTypedAccountDeletionRequests,
  createAccountExportRequest as createTypedAccountExportRequest,
  fetchAccountExportRequests as fetchTypedAccountExportRequests,
  fetchAccountAuditEvents as fetchTypedAccountAuditEvents,
  fetchAuditEvents as fetchTypedAuditEvents,
  fetchAccountCooldowns as fetchTypedAccountCooldowns,
  fetchActionGate as fetchTypedActionGate,
  fetchWorkerDiagnostics as fetchTypedWorkerDiagnostics,
  fetchWorkerQueues as fetchTypedWorkerQueues,
  fetchJobPolicies as fetchTypedJobPolicies,
  fetchTdlibRuntimeStatus as fetchTypedTdlibRuntimeStatus,
  createTelegramAuthSession as createTypedTelegramAuthSession,
  fetchTelegramAuthSessions as fetchTypedTelegramAuthSessions,
  fetchTelegramAuthSession as fetchTypedTelegramAuthSession,
  submitTelegramAuthCode as submitTypedTelegramAuthCode,
  submitTelegramAuthPassword as submitTypedTelegramAuthPassword,
  cancelTelegramAuthSession as cancelTypedTelegramAuthSession,
  createReauthSession as createTypedReauthSession,
  createAccountImportBatch as createTypedAccountImportBatch,
  fetchAccountImportBatches as fetchTypedAccountImportBatches,
  fetchAccountImportBatch as fetchTypedAccountImportBatch,
  validateAccountImportBatch as validateTypedAccountImportBatch,
  confirmAccountImportBatch as confirmTypedAccountImportBatch,
  fetchAccountRuntimeDiagnostics as fetchTypedAccountRuntimeDiagnostics,
  fetchAccounts as fetchTypedAccounts,
  fetchAccountSafety as fetchTypedAccountSafety,
  fetchAccountSafetyGate as fetchTypedAccountSafetyGate,
  fetchAccountSafetySummary as fetchTypedAccountSafetySummary,
  fetchAccountValidityChecks as fetchTypedAccountValidityChecks,
  fetchDashboard as fetchTypedDashboard,
  fetchDisasterState as fetchTypedDisasterState,
  fetchExecutionPolicy as fetchTypedExecutionPolicy,
  fetchFrontendDiagnosticsSummary as fetchTypedFrontendDiagnosticsSummary,
  fetchGlobalOperationLogs as fetchTypedGlobalOperationLogs,
  fetchHealth as fetchTypedHealth,
  fetchCurrentUser as fetchTypedCurrentUser,
  fetchWorkspaceSafetyPolicy as fetchTypedWorkspaceSafetyPolicy,
  fetchJob as fetchTypedJob,
  fetchJobSteps as fetchTypedJobSteps,
  fetchLatestJob as fetchTypedLatestJob,
  fetchLatestJobs as fetchTypedLatestJobs,
  fetchLivePreflight as fetchTypedLivePreflight,
  fetchProxySummary as fetchTypedProxySummary,
  fetchReady as fetchTypedReady,
  fetchRuntimeDiagnostics as fetchTypedRuntimeDiagnostics,
  fetchStoryCapabilities as fetchTypedStoryCapabilities,
  fetchStoryDrafts as fetchTypedStoryDrafts,
  previewAccountBatchSafety as previewTypedAccountBatchSafety,
  previewProfileJob as previewTypedProfileJob,
  refreshRuntime as refreshTypedRuntime,
  runAccountValidityCheck as runTypedAccountValidityCheck,
  saveAccountProxy as saveTypedAccountProxy,
  updateExecutionPolicy as updateTypedExecutionPolicy,
  updateWorkspaceSafetyPolicy as updateTypedWorkspaceSafetyPolicy,
  type AccountListItem,
  type AccountReadinessRisk,
  type AccountReadinessRiskSummary,
  type AccountDeletionPreview,
  type AccountDeletionRequest,
  type AccountDeletionRequestCreate,
  type AccountExportRequest,
  type ActionGate,
  type SensitiveAuditEventPage,
  type WorkerDiagnostics,
  type QueueDescriptor,
  type RetryPolicy,
  type AccountSafetyOverride as SafetyOverride,
  type SafetyGateIntent,
  type SafetyGateVerdict,
  type ProfileCompletenessReport,
  type DashboardProfile as DashboardResponse,
  type DisasterState,
  type JobSummary,
  type RuntimeRefresh,
  type Readiness,
  type FrontendDiagnosticsSummary,
  type TdlibRuntimeStatus,
  type TelegramAuthSession,
  type TelegramAuthSessionCreate,
  type TelegramAuthCodeSubmit,
  type TelegramAuthPasswordSubmit,
  type AccountImportBatch,
  type AccountImportBatchCreate,
  type AccountImportBatchValidate,
  type AccountImportBatchConfirm,
  type CurrentUser,
  type WorkspaceSafetyPolicy,
  type WorkspaceSafetyPolicyUpdate,
  type StoryDraftRead,
} from '@stylisttg/api-client'

import type {
  AccountOperationCooldown,
  AccountSafety,
  AccountSafetySummary,
  AccountValidityCheck,
  SafetyOperation,
  FreshValidityPolicy,
  RecentFailurePolicy,
  UnknownCapabilityPolicy,
} from '@/lib/accountSafety'
import type { AccountRuntimeDiagnostics, RuntimeDiagnostics } from '@/lib/diagnostics'
import type { OperationLogPage } from '@/lib/operationLogs'
import type { AccountProxy, AccountProxyInput, AccountProxySummary } from '@/lib/proxy'
import type { LivePreflight } from '@/lib/settings'
import { dashboardApiClient } from '@/lib/apiClient'
export {
  buildAssetContentUrl,
  createAccountUpdateJob,
  createStoryDraft,
  deleteStoryDraft,
  previewAccountUpdateJob,
  updateStoryDraft,
  uploadProfileAudio,
  uploadProfilePhoto,
  uploadStoryImage,
  uploadStoryVideo,
} from '@/modules/account-editing'
import { composeDisplayName } from '@/modules/account-editing'
import type { FormPayload, ProfilePreview, StoryDraftPayload } from '@/modules/account-editing'
export type { FormPayload, ProfilePreview, StoryDraftPayload } from '@/modules/account-editing'

const RUNTIME_REFRESH_TIMEOUT_MS = 45000

export type {
  AccountListItem,
  AccountProxy,
  AccountProxyInput,
  AccountProxySummary,
  AccountRuntimeDiagnostics,
  AccountSafety,
  AccountSafetySummary,
  AccountValidityCheck,
  JobSummary,
  LivePreflight,
  OperationLogPage,
  RuntimeDiagnostics,
  RuntimeRefresh,
  Readiness,
  SafetyOverride,
  SafetyGateIntent,
  SafetyGateVerdict,
  ProfileCompletenessReport,
  DisasterState,
  StoryDraftRead,
  AccountReadinessRisk,
  AccountReadinessRiskSummary,
  AccountDeletionPreview,
  AccountDeletionRequest,
  AccountDeletionRequestCreate,
  AccountExportRequest,
  ActionGate,
  SensitiveAuditEventPage,
  WorkerDiagnostics,
  QueueDescriptor,
  RetryPolicy,
  FrontendDiagnosticsSummary,
  TdlibRuntimeStatus,
  TelegramAuthSession,
  TelegramAuthSessionCreate,
  TelegramAuthCodeSubmit,
  TelegramAuthPasswordSubmit,
  AccountImportBatch,
  AccountImportBatchCreate,
  AccountImportBatchValidate,
  AccountImportBatchConfirm,
  CurrentUser,
  WorkspaceSafetyPolicy,
  WorkspaceSafetyPolicyUpdate,
}

export type JobDetail = {
  job_id: string
  job_state: string
  account_id: string
  execution_intent_hash: string
  started_at: string | null
  finished_at: string | null
  failure_reason: string | null
  can_retry: boolean
  can_refresh_runtime: boolean
  step_counts: Record<string, number>
}

export type JobStep = {
  step_key: string
  step_type: string
  status: string
  verification_attempted: boolean
  verification_result: Record<string, unknown> | null
  uncertain_reason: string | null
  error_code: string | null
  error_class: string | null
  result_payload_json?: Record<string, unknown> | null
  started_at: string | null
  finished_at: string | null
}

export type ExecutionPolicy = {
  profile_job_cooldown_seconds: number
  profile_job_cooldown_enabled: boolean
  allowed_profile_job_cooldown_seconds: number[]
  profile_update_cooldown_seconds: number
  username_cooldown_seconds: number
  profile_photo_cooldown_seconds: number
  profile_music_cooldown_seconds: number
  story_post_cooldown_seconds: number
  story_delete_cooldown_seconds: number
  unknown_capability_policy: UnknownCapabilityPolicy
  recent_failure_policy: RecentFailurePolicy
  fresh_validity_required: FreshValidityPolicy
  fresh_validity_max_age_minutes: number
  manual_hard_blocker_override_enabled: boolean
  non_overridable_blockers: string[]
}

export type ExecutionPolicyUpdate = Partial<
  Pick<
    ExecutionPolicy,
    | 'profile_job_cooldown_seconds'
    | 'profile_update_cooldown_seconds'
    | 'username_cooldown_seconds'
    | 'profile_photo_cooldown_seconds'
    | 'profile_music_cooldown_seconds'
    | 'story_post_cooldown_seconds'
    | 'story_delete_cooldown_seconds'
    | 'unknown_capability_policy'
    | 'recent_failure_policy'
    | 'fresh_validity_required'
    | 'fresh_validity_max_age_minutes'
    | 'manual_hard_blocker_override_enabled'
  >
>

export type AccountBatchSafetyPreview = {
  operation: SafetyOperation | string
  can_start: boolean
  counts: Record<'ready' | 'needs_login' | 'paused' | 'limited' | 'blocked' | 'unknown', number>
  blocking_account_ids: string[]
  warning_account_ids: string[]
  items: Array<{
    account_id: string
    batch_status: string
    health_status: string
    risk_level: string
    reasons: AccountSafety['reasons']
    cooldowns: AccountOperationCooldown[]
  }>
}

export type StoryPost = DashboardResponse['story_posts'][number]

export type StoryCapabilities = {
  account_id: string
  stories_enabled: boolean
  tdlib_live_publishing_enabled: boolean
  can_prepare_image: boolean
  can_prepare_video: boolean
  allowed_active_period_seconds: number[]
  allowed_privacy_presets: string[]
  max_caption_length: number
  ffprobe_available: boolean
  ffmpeg_available: boolean
  warnings: string[]
}

const typedClient = dashboardApiClient

export function storyDraftReadToPayload(draft: StoryDraftRead): StoryDraftPayload {
  return {
    draftId: draft.id,
    clientId: draft.id,
    action: draft.media_kind === 'image' ? 'post_image' : 'post_video',
    assetId: draft.asset_id,
    fileName: draft.media_kind === 'image' ? 'Story image' : 'Story video',
    caption: draft.caption ?? '',
    privacyPreset: draft.privacy_preset as StoryDraftPayload['privacyPreset'],
    activePeriodSeconds: draft.active_period_seconds as 86400,
    protectContent: draft.protect_content,
  }
}

export function fetchDashboard(accountId: string): Promise<DashboardResponse> {
  return fetchTypedDashboard(typedClient, accountId)
}

export function fetchDisasterState(): Promise<DisasterState> {
  return fetchTypedDisasterState(typedClient)
}

export function fetchAccounts(): Promise<AccountListItem[]> {
  return fetchTypedAccounts(typedClient)
}

export function fetchAccountSafetySummary(): Promise<AccountSafetySummary[]> {
  return fetchTypedAccountSafetySummary(typedClient) as Promise<AccountSafetySummary[]>
}

export function fetchAccountSafety(accountId: string): Promise<AccountSafety> {
  return fetchTypedAccountSafety(typedClient, accountId) as Promise<AccountSafety>
}

export function fetchAccountSafetyGate(
  accountId: string,
  intent: SafetyGateIntent,
): Promise<SafetyGateVerdict> {
  return fetchTypedAccountSafetyGate(typedClient, accountId, intent)
}

export function fetchAccountRiskSummary(): Promise<AccountReadinessRiskSummary> {
  return fetchTypedAccountRiskSummary(typedClient)
}

export function fetchAccountRisk(accountId: string): Promise<AccountReadinessRisk> {
  return fetchTypedAccountRisk(typedClient, accountId)
}

export function fetchAccountDeletionPreview(accountId: string): Promise<AccountDeletionPreview> {
  return fetchTypedAccountDeletionPreview(typedClient, accountId)
}

export function createAccountDeletionRequest(
  accountId: string,
  payload: AccountDeletionRequestCreate,
): Promise<AccountDeletionRequest> {
  return createTypedAccountDeletionRequest(typedClient, accountId, payload)
}

export function fetchAccountDeletionRequests(accountId: string): Promise<AccountDeletionRequest[]> {
  return fetchTypedAccountDeletionRequests(typedClient, accountId)
}

export function createAccountExportRequest(accountId: string): Promise<AccountExportRequest> {
  return createTypedAccountExportRequest(typedClient, accountId)
}

export function fetchAccountExportRequests(accountId: string): Promise<AccountExportRequest[]> {
  return fetchTypedAccountExportRequests(typedClient, accountId)
}

export function fetchAccountAuditEvents(accountId: string, limit = 50): Promise<SensitiveAuditEventPage> {
  return fetchTypedAccountAuditEvents(typedClient, accountId, limit)
}

export function fetchAuditEvents(limit = 100): Promise<SensitiveAuditEventPage> {
  return fetchTypedAuditEvents(typedClient, limit)
}

export function fetchAccountCooldowns(accountId: string): Promise<AccountOperationCooldown[]> {
  return fetchTypedAccountCooldowns(typedClient, accountId)
}

export function fetchActionGate(accountId: string, actionType: string): Promise<ActionGate> {
  return fetchTypedActionGate(typedClient, accountId, actionType)
}

export function fetchWorkerDiagnostics(): Promise<WorkerDiagnostics> {
  return fetchTypedWorkerDiagnostics(typedClient)
}

export function fetchWorkerQueues(): Promise<QueueDescriptor[]> {
  return fetchTypedWorkerQueues(typedClient)
}

export function fetchJobPolicies(): Promise<Record<string, RetryPolicy>> {
  return fetchTypedJobPolicies(typedClient)
}

export function fetchTdlibRuntimeStatus(): Promise<TdlibRuntimeStatus> {
  return fetchTypedTdlibRuntimeStatus(typedClient)
}

export function createTelegramAuthSession(payload: TelegramAuthSessionCreate): Promise<TelegramAuthSession> {
  return createTypedTelegramAuthSession(typedClient, payload)
}

export function fetchTelegramAuthSessions(): Promise<TelegramAuthSession[]> {
  return fetchTypedTelegramAuthSessions(typedClient)
}

export function fetchTelegramAuthSession(authSessionId: string): Promise<TelegramAuthSession> {
  return fetchTypedTelegramAuthSession(typedClient, authSessionId)
}

export function submitTelegramAuthCode(
  authSessionId: string,
  payload: TelegramAuthCodeSubmit,
): Promise<TelegramAuthSession> {
  return submitTypedTelegramAuthCode(typedClient, authSessionId, payload)
}

export function submitTelegramAuthPassword(
  authSessionId: string,
  payload: TelegramAuthPasswordSubmit,
): Promise<TelegramAuthSession> {
  return submitTypedTelegramAuthPassword(typedClient, authSessionId, payload)
}

export function cancelTelegramAuthSession(authSessionId: string): Promise<TelegramAuthSession> {
  return cancelTypedTelegramAuthSession(typedClient, authSessionId)
}

export function createReauthSession(
  accountId: string,
  payload: TelegramAuthSessionCreate,
): Promise<TelegramAuthSession> {
  return createTypedReauthSession(typedClient, accountId, payload)
}

export function createAccountImportBatch(payload: AccountImportBatchCreate): Promise<AccountImportBatch> {
  return createTypedAccountImportBatch(typedClient, payload)
}

export function fetchAccountImportBatches(): Promise<AccountImportBatch[]> {
  return fetchTypedAccountImportBatches(typedClient)
}

export function fetchAccountImportBatch(batchId: string): Promise<AccountImportBatch> {
  return fetchTypedAccountImportBatch(typedClient, batchId)
}

export function validateAccountImportBatch(
  batchId: string,
  payload: AccountImportBatchValidate,
): Promise<AccountImportBatch> {
  return validateTypedAccountImportBatch(typedClient, batchId, payload)
}

export function confirmAccountImportBatch(
  batchId: string,
  payload: AccountImportBatchConfirm,
): Promise<AccountImportBatch> {
  return confirmTypedAccountImportBatch(typedClient, batchId, payload)
}

export function fetchProxySummary(): Promise<AccountProxySummary[]> {
  return fetchTypedProxySummary(typedClient) as Promise<AccountProxySummary[]>
}

export function fetchAccountProxy(accountId: string): Promise<AccountProxy | null> {
  return fetchTypedAccountProxy(typedClient, accountId) as Promise<AccountProxy | null>
}

export function fetchProfileCompleteness(accountId: string): Promise<ProfileCompletenessReport> {
  return fetchTypedProfileCompleteness(typedClient, accountId)
}

export function saveAccountProxy(accountId: string, payload: AccountProxyInput): Promise<AccountProxy> {
  return saveTypedAccountProxy(typedClient, accountId, payload) as Promise<AccountProxy>
}

export function deleteAccountProxy(accountId: string): Promise<void> {
  return deleteTypedAccountProxy(typedClient, accountId)
}

export function checkAccountProxy(accountId: string): Promise<AccountProxy> {
  return checkTypedAccountProxy(typedClient, accountId) as Promise<AccountProxy>
}

export function fetchAccountOperationLogs(accountId: string, limit = 50): Promise<OperationLogPage> {
  return fetchTypedAccountOperationLogs(typedClient, accountId, limit) as Promise<OperationLogPage>
}

export function fetchGlobalOperationLogs(limit = 100): Promise<OperationLogPage> {
  return fetchTypedGlobalOperationLogs(typedClient, limit) as Promise<OperationLogPage>
}

export function previewAccountBatchSafety(
  accountIds: string[],
  operation: SafetyOperation | string,
  allowWarningOverrides = false,
): Promise<AccountBatchSafetyPreview> {
  return previewTypedAccountBatchSafety(typedClient, accountIds, operation, allowWarningOverrides) as Promise<AccountBatchSafetyPreview>
}

export function runAccountValidityCheck(accountId: string, mode = 'db_snapshot'): Promise<AccountValidityCheck> {
  return runTypedAccountValidityCheck(typedClient, accountId, mode) as Promise<AccountValidityCheck>
}

export function fetchAccountValidityChecks(accountId: string): Promise<AccountValidityCheck[]> {
  return fetchTypedAccountValidityChecks(typedClient, accountId) as Promise<AccountValidityCheck[]>
}

export function createAccountSafetyOverride(
  accountId: string,
  payload: { operation: SafetyOperation | string; reason: string; requested_blockers: string[] },
): Promise<SafetyOverride> {
  return createTypedAccountSafetyOverride(typedClient, accountId, payload)
}

export function deleteAccount(accountId: string): Promise<void> {
  return deleteTypedAccount(typedClient, accountId)
}

export function fetchLatestJobs(accountId: string, limit = 10): Promise<JobSummary[]> {
  return fetchTypedLatestJobs(typedClient, accountId, limit)
}

export function fetchLatestJob(accountId: string): Promise<JobSummary> {
  return fetchTypedLatestJob(typedClient, accountId)
}

export function fetchJob(jobId: string): Promise<JobDetail> {
  return fetchTypedJob(typedClient, jobId) as Promise<JobDetail>
}

export function fetchJobSteps(jobId: string): Promise<JobStep[]> {
  return fetchTypedJobSteps(typedClient, jobId) as Promise<JobStep[]>
}

export function cancelJob(jobId: string): Promise<JobSummary> {
  return cancelTypedJob(typedClient, jobId)
}

export function deleteJob(jobId: string): Promise<void> {
  return deleteTypedJob(typedClient, jobId)
}

export function refreshRuntime(accountId: string): Promise<RuntimeRefresh> {
  return refreshTypedRuntime(typedClient, accountId, { signal: AbortSignal.timeout(RUNTIME_REFRESH_TIMEOUT_MS) })
}

export function fetchRuntimeDiagnostics(): Promise<RuntimeDiagnostics> {
  return fetchTypedRuntimeDiagnostics(typedClient)
}

export function fetchHealth(): Promise<{ status: string }> {
  return fetchTypedHealth(typedClient)
}

export function fetchReady(): Promise<Readiness> {
  return fetchTypedReady(typedClient)
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return fetchTypedCurrentUser(typedClient)
}

export function fetchLivePreflight(): Promise<LivePreflight> {
  return fetchTypedLivePreflight(typedClient) as Promise<LivePreflight>
}

export function fetchFrontendDiagnosticsSummary(): Promise<FrontendDiagnosticsSummary> {
  return fetchTypedFrontendDiagnosticsSummary(typedClient)
}

export function fetchAccountRuntimeDiagnostics(accountId: string): Promise<AccountRuntimeDiagnostics> {
  return fetchTypedAccountRuntimeDiagnostics(typedClient, accountId) as Promise<AccountRuntimeDiagnostics>
}

export function fetchExecutionPolicy(): Promise<ExecutionPolicy> {
  return fetchTypedExecutionPolicy(typedClient) as Promise<ExecutionPolicy>
}

export function updateExecutionPolicy(update: number | ExecutionPolicyUpdate): Promise<ExecutionPolicy> {
  const body = typeof update === 'number' ? { profile_job_cooldown_seconds: update } : update
  return updateTypedExecutionPolicy(typedClient, body) as Promise<ExecutionPolicy>
}

export function fetchWorkspaceSafetyPolicy(): Promise<WorkspaceSafetyPolicy> {
  return fetchTypedWorkspaceSafetyPolicy(typedClient)
}

export function updateWorkspaceSafetyPolicy(update: WorkspaceSafetyPolicyUpdate): Promise<WorkspaceSafetyPolicy> {
  return updateTypedWorkspaceSafetyPolicy(typedClient, update)
}

export function fetchStoryDrafts(accountId: string): Promise<StoryDraftRead[]> {
  return fetchTypedStoryDrafts(typedClient, accountId)
}

export function fetchStoryCapabilities(accountId: string): Promise<StoryCapabilities> {
  return fetchTypedStoryCapabilities(typedClient, accountId) as Promise<StoryCapabilities>
}

export function deleteStoryPost(accountId: string, postId: string): Promise<void> {
  return deleteTypedStoryPost(typedClient, accountId, postId, { signal: AbortSignal.timeout(RUNTIME_REFRESH_TIMEOUT_MS) })
}

export function previewProfileJob(accountId: string, form: FormPayload): Promise<ProfilePreview> {
  return previewTypedProfileJob(typedClient, {
    account_id: accountId,
    name: composeDisplayName(form.firstName, form.lastName) || null,
    bio: form.bio || null,
    username: form.username || null,
    photo_asset_id: form.profilePhotoAssetId,
  }) as Promise<ProfilePreview>
}

export function createProfileJob(accountId: string, form: FormPayload): Promise<JobSummary> {
  return createTypedProfileJob(typedClient, {
    account_id: accountId,
    name: composeDisplayName(form.firstName, form.lastName) || null,
    bio: form.bio || null,
    username: form.username || null,
    photo_asset_id: form.profilePhotoAssetId,
  })
}
