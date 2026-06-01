import type { DashboardProfile as DashboardResponse } from '@stylisttg/api-client'
import type {
  AccountOperationCooldown,
  AccountSafety,
  FreshValidityPolicy,
  RecentFailurePolicy,
  SafetyOperation,
  UnknownCapabilityPolicy,
} from '@/lib/accountSafety'
import { dashboardApiClient } from '@/lib/apiClient'

export {
  cancelTelegramAuthSession as cancelTypedTelegramAuthSession,
  cancelJob as cancelTypedJob,
  checkAccountProxy as checkTypedAccountProxy,
  createAccountDeletionRequest as createTypedAccountDeletionRequest,
  createAccountExportRequest as createTypedAccountExportRequest,
  createAccountImportBatch as createTypedAccountImportBatch,
  createAccountSafetyOverride as createTypedAccountSafetyOverride,
  createProfileJob as createTypedProfileJob,
  createReauthSession as createTypedReauthSession,
  createTelegramAuthSession as createTypedTelegramAuthSession,
  deleteAccount as deleteTypedAccount,
  deleteAccountProxy as deleteTypedAccountProxy,
  deleteJob as deleteTypedJob,
  deleteStoryPost as deleteTypedStoryPost,
  fetchAccountAuditEvents as fetchTypedAccountAuditEvents,
  fetchAccountCooldowns as fetchTypedAccountCooldowns,
  fetchAccountDeletionPreview as fetchTypedAccountDeletionPreview,
  fetchAccountDeletionRequests as fetchTypedAccountDeletionRequests,
  fetchAccountExportRequests as fetchTypedAccountExportRequests,
  fetchAccountImportBatch as fetchTypedAccountImportBatch,
  fetchAccountImportBatches as fetchTypedAccountImportBatches,
  fetchAccountOperationLogs as fetchTypedAccountOperationLogs,
  fetchProfileCompleteness as fetchTypedProfileCompleteness,
  fetchAccountProxy as fetchTypedAccountProxy,
  fetchAccountRisk as fetchTypedAccountRisk,
  fetchAccountRiskSummary as fetchTypedAccountRiskSummary,
  fetchAccountRuntimeDiagnostics as fetchTypedAccountRuntimeDiagnostics,
  fetchAccountSafety as fetchTypedAccountSafety,
  fetchAccountSafetyGate as fetchTypedAccountSafetyGate,
  fetchAccountSafetySummary as fetchTypedAccountSafetySummary,
  fetchAccountValidityChecks as fetchTypedAccountValidityChecks,
  fetchAccounts as fetchTypedAccounts,
  fetchActionGate as fetchTypedActionGate,
  fetchAuditEvents as fetchTypedAuditEvents,
  fetchCurrentUser as fetchTypedCurrentUser,
  fetchDashboard as fetchTypedDashboard,
  fetchDisasterState as fetchTypedDisasterState,
  fetchExecutionPolicy as fetchTypedExecutionPolicy,
  fetchFrontendDiagnosticsSummary as fetchTypedFrontendDiagnosticsSummary,
  fetchGlobalOperationLogs as fetchTypedGlobalOperationLogs,
  fetchHealth as fetchTypedHealth,
  fetchJob as fetchTypedJob,
  fetchJobPolicies as fetchTypedJobPolicies,
  fetchJobSteps as fetchTypedJobSteps,
  fetchLatestJob as fetchTypedLatestJob,
  fetchLatestJobs as fetchTypedLatestJobs,
  fetchLivePreflight as fetchTypedLivePreflight,
  fetchProxySummary as fetchTypedProxySummary,
  fetchReady as fetchTypedReady,
  fetchRuntimeDiagnostics as fetchTypedRuntimeDiagnostics,
  fetchStoryCapabilities as fetchTypedStoryCapabilities,
  fetchStoryDrafts as fetchTypedStoryDrafts,
  fetchTdlibRuntimeStatus as fetchTypedTdlibRuntimeStatus,
  fetchTelegramAuthSession as fetchTypedTelegramAuthSession,
  fetchTelegramAuthSessions as fetchTypedTelegramAuthSessions,
  fetchWorkerDiagnostics as fetchTypedWorkerDiagnostics,
  fetchWorkerQueues as fetchTypedWorkerQueues,
  fetchWorkspaceSafetyPolicy as fetchTypedWorkspaceSafetyPolicy,
  previewAccountBatchSafety as previewTypedAccountBatchSafety,
  previewProfileJob as previewTypedProfileJob,
  refreshRuntime as refreshTypedRuntime,
  runAccountValidityCheck as runTypedAccountValidityCheck,
  saveAccountProxy as saveTypedAccountProxy,
  submitTelegramAuthCode as submitTypedTelegramAuthCode,
  submitTelegramAuthPassword as submitTypedTelegramAuthPassword,
  updateExecutionPolicy as updateTypedExecutionPolicy,
  updateWorkspaceSafetyPolicy as updateTypedWorkspaceSafetyPolicy,
  validateAccountImportBatch as validateTypedAccountImportBatch,
  confirmAccountImportBatch as confirmTypedAccountImportBatch,
} from '@stylisttg/api-client'

export type {
  AccountDeletionPreview,
  AccountDeletionRequest,
  AccountDeletionRequestCreate,
  AccountExportRequest,
  AccountImportBatch,
  AccountImportBatchConfirm,
  AccountImportBatchCreate,
  AccountImportBatchValidate,
  AccountListItem,
  AccountReadinessRisk,
  AccountReadinessRiskSummary,
  ActionGate,
  CurrentUser,
  DashboardProfile as DashboardResponse,
  DisasterState,
  FrontendDiagnosticsSummary,
  JobSummary,
  ProfileCompletenessReport,
  QueueDescriptor,
  Readiness,
  RetryPolicy,
  RuntimeRefresh,
  SafetyGateIntent,
  SafetyGateVerdict,
  SensitiveAuditEventPage,
  StoryDraftRead,
  TdlibRuntimeStatus,
  TelegramAuthCodeSubmit,
  TelegramAuthPasswordSubmit,
  TelegramAuthSession,
  TelegramAuthSessionCreate,
  WorkerDiagnostics,
  WorkspaceSafetyPolicy,
  WorkspaceSafetyPolicyUpdate,
  AccountSafetyOverride as SafetyOverride,
} from '@stylisttg/api-client'
export type {
  AccountOperationCooldown,
  AccountSafety,
  AccountSafetySummary,
  AccountValidityCheck,
  SafetyOperation,
} from '@/lib/accountSafety'
export type { AccountRuntimeDiagnostics, RuntimeDiagnostics } from '@/lib/diagnostics'
export type { OperationLogPage } from '@/lib/operationLogs'
export type { AccountProxy, AccountProxyInput, AccountProxySummary } from '@/lib/proxy'
export type { LivePreflight } from '@/lib/settings'

export const RUNTIME_REFRESH_TIMEOUT_MS = 45000
export const typedClient = dashboardApiClient

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
