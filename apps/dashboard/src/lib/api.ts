import {
  buildAssetContentUrl as buildTypedAssetContentUrl,
  cancelJob as cancelTypedJob,
  checkAccountProxy as checkTypedAccountProxy,
  createAccountSafetyOverride as createTypedAccountSafetyOverride,
  createAccountUpdateJob as createTypedAccountUpdateJob,
  createApiClient,
  createProfileJob as createTypedProfileJob,
  createStoryDraft as createTypedStoryDraft,
  deleteAccount as deleteTypedAccount,
  deleteAccountProxy as deleteTypedAccountProxy,
  deleteJob as deleteTypedJob,
  deleteStoryDraft as deleteTypedStoryDraft,
  deleteStoryPost as deleteTypedStoryPost,
  fetchAccountOperationLogs as fetchTypedAccountOperationLogs,
  fetchAccountProxy as fetchTypedAccountProxy,
  fetchAccountRuntimeDiagnostics as fetchTypedAccountRuntimeDiagnostics,
  fetchAccounts as fetchTypedAccounts,
  fetchAccountSafety as fetchTypedAccountSafety,
  fetchAccountSafetySummary as fetchTypedAccountSafetySummary,
  fetchAccountValidityChecks as fetchTypedAccountValidityChecks,
  fetchDashboard as fetchTypedDashboard,
  fetchExecutionPolicy as fetchTypedExecutionPolicy,
  fetchGlobalOperationLogs as fetchTypedGlobalOperationLogs,
  fetchHealth as fetchTypedHealth,
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
  previewAccountUpdateJob as previewTypedAccountUpdateJob,
  previewProfileJob as previewTypedProfileJob,
  refreshRuntime as refreshTypedRuntime,
  runAccountValidityCheck as runTypedAccountValidityCheck,
  saveAccountProxy as saveTypedAccountProxy,
  updateExecutionPolicy as updateTypedExecutionPolicy,
  updateStoryDraft as updateTypedStoryDraft,
  uploadAsset,
  type AccountListItem,
  type AccountSafetyOverride as SafetyOverride,
  type DashboardProfile as DashboardResponse,
  type JobSummary,
  type RuntimeRefresh,
  type StoryDraftRead,
} from '@stylisttg/api-client'

import type {
  AccountOperationCooldown,
  AccountSafety,
  AccountSafetySummary,
  AccountValidityCheck,
  OperationSafety,
  SafetyOperation,
  FreshValidityPolicy,
  RecentFailurePolicy,
  UnknownCapabilityPolicy,
} from '@/lib/accountSafety'
import { composeDisplayName } from '@/lib/dashboard'
import { getApiBaseUrl } from '@/lib/config'
import type { AccountRuntimeDiagnostics, RuntimeDiagnostics } from '@/lib/diagnostics'
import { isApiError } from '@/lib/http'
import type { OperationLogPage } from '@/lib/operationLogs'
import type { AccountProxy, AccountProxyInput, AccountProxySummary } from '@/lib/proxy'
import type { LivePreflight } from '@/lib/settings'

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
  SafetyOverride,
  StoryDraftRead,
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

export type ProfilePreview = {
  can_create_job: boolean
  blocking_errors: string[]
  warnings: string[]
  normalized_payload: Record<string, unknown>
  execution_intent_hash: string
  plan_json_snapshot: {
    steps?: Array<{
      step_key: string
      step_type: string
      order: number
      required: boolean
      idempotency_class: string
      payload: Record<string, unknown>
    }>
  } & Record<string, unknown>
  steps: Array<{
    step_key: string
    step_type: string
    order: number
    required: boolean
    idempotency_class: string
    payload: Record<string, unknown>
  }>
  requires_execution_usable: boolean
  dedup_would_block: boolean
  dedup_blocked_by_job_id: string | null
  account_safety?: AccountSafety | null
  risk_by_operation?: AccountSafety['risk_by_operation']
  cooldowns_by_operation?: AccountSafety['cooldowns_by_operation']
  safety_warnings?: string[]
  safety_blockers?: string[]
  operation_safety?: OperationSafety[]
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

export type FormPayload = {
  firstName: string
  lastName: string
  bio: string
  username: string
  profilePhotoAssetId: string | null
  profileAudioAction: 'keep' | 'add' | 'remove'
  profileAudioAssetId: string | null
  stories: StoryDraftPayload[]
}

export type StoryDraftPayload = {
  draftId: string | null
  clientId: string
  action: 'post_image' | 'post_video'
  assetId: string
  fileName: string
  caption: string
  privacyPreset: 'contacts' | 'close_friends' | 'public'
  activePeriodSeconds: 86400
  protectContent: boolean
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

const typedClient = createApiClient({
  baseUrl: getTypedApiBaseUrl(),
  fetch: (...args) => globalThis.fetch(...args),
})

function getTypedApiBaseUrl(): string {
  const configuredBaseUrl = getApiBaseUrl()
  if (configuredBaseUrl) return configuredBaseUrl
  if (typeof window !== 'undefined') return window.location.origin
  return 'http://localhost'
}

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

export function fetchAccounts(): Promise<AccountListItem[]> {
  return fetchTypedAccounts(typedClient)
}

export function fetchAccountSafetySummary(): Promise<AccountSafetySummary[]> {
  return fetchTypedAccountSafetySummary(typedClient) as Promise<AccountSafetySummary[]>
}

export function fetchAccountSafety(accountId: string): Promise<AccountSafety> {
  return fetchTypedAccountSafety(typedClient, accountId) as Promise<AccountSafety>
}

export function fetchProxySummary(): Promise<AccountProxySummary[]> {
  return fetchTypedProxySummary(typedClient) as Promise<AccountProxySummary[]>
}

export function fetchAccountProxy(accountId: string): Promise<AccountProxy | null> {
  return fetchTypedAccountProxy(typedClient, accountId) as Promise<AccountProxy | null>
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

export function fetchReady(): Promise<RuntimeDiagnostics> {
  return fetchTypedReady(typedClient)
}

export function fetchLivePreflight(): Promise<LivePreflight> {
  return fetchTypedLivePreflight(typedClient) as Promise<LivePreflight>
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

export function uploadProfilePhoto(file: File): Promise<{ id: string }> {
  return uploadAsset(typedClient, '/api/assets/profile-photo', file)
}

export function uploadProfileAudio(file: File): Promise<{ id: string }> {
  return uploadAsset(typedClient, '/api/assets/profile-audio', file)
}

export function uploadStoryImage(file: File): Promise<{ id: string }> {
  return uploadAsset(typedClient, '/api/assets/story-image', file)
}

export function uploadStoryVideo(file: File): Promise<{ id: string }> {
  return uploadAsset(typedClient, '/api/assets/story-video', file)
}

export function fetchStoryDrafts(accountId: string): Promise<StoryDraftRead[]> {
  return fetchTypedStoryDrafts(typedClient, accountId)
}

export function fetchStoryCapabilities(accountId: string): Promise<StoryCapabilities> {
  return fetchTypedStoryCapabilities(typedClient, accountId) as Promise<StoryCapabilities>
}

export function createStoryDraft(
  accountId: string,
  draft: Omit<StoryDraftPayload, 'draftId' | 'clientId' | 'fileName' | 'action'>,
  mediaKind: 'image' | 'video',
): Promise<StoryDraftRead> {
  return createTypedStoryDraft(typedClient, {
    account_id: accountId,
    asset_id: draft.assetId,
    media_kind: mediaKind,
    caption: draft.caption || null,
    privacy_preset: draft.privacyPreset,
    active_period_seconds: draft.activePeriodSeconds,
    protect_content: draft.protectContent,
  })
}

export function updateStoryDraft(
  draftId: string,
  patch: Partial<Pick<StoryDraftPayload, 'caption' | 'privacyPreset' | 'activePeriodSeconds' | 'protectContent'>>,
): Promise<StoryDraftRead> {
  return updateTypedStoryDraft(typedClient, draftId, {
    caption: patch.caption,
    privacy_preset: patch.privacyPreset,
    active_period_seconds: patch.activePeriodSeconds,
    protect_content: patch.protectContent,
  })
}

export async function deleteStoryDraft(draftId: string): Promise<void> {
  try {
    await deleteTypedStoryDraft(typedClient, draftId)
  } catch (error) {
    if (
      (isApiError(error) && error.error_code === 'STORY_DRAFT_NOT_FOUND') ||
      (typeof error === 'object' &&
        error !== null &&
        'code' in error &&
        (error as { code?: string }).code === 'STORY_DRAFT_NOT_FOUND')
    ) {
      return
    }
    throw error
  }
}

export function deleteStoryPost(accountId: string, postId: string): Promise<void> {
  return deleteTypedStoryPost(typedClient, accountId, postId, { signal: AbortSignal.timeout(RUNTIME_REFRESH_TIMEOUT_MS) })
}

export function buildAssetContentUrl(assetId: string): string {
  return buildTypedAssetContentUrl(typedClient, assetId)
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

export function previewAccountUpdateJob(
  accountId: string,
  form: FormPayload,
  init?: Pick<RequestInit, 'signal'>,
): Promise<ProfilePreview> {
  return previewTypedAccountUpdateJob(typedClient, buildAccountUpdateBody(accountId, form), init) as Promise<ProfilePreview>
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

export function createAccountUpdateJob(accountId: string, form: FormPayload): Promise<JobSummary> {
  return createTypedAccountUpdateJob(typedClient, buildAccountUpdateBody(accountId, form))
}

function buildAccountUpdateBody(accountId: string, form: FormPayload) {
  return {
    account_id: accountId,
    profile: {
      name: composeDisplayName(form.firstName, form.lastName) || null,
      bio: form.bio || null,
      username: form.username || null,
      photo_asset_id: form.profilePhotoAssetId,
    },
    profile_audio: {
      action: form.profileAudioAction,
      audio_asset_id: form.profileAudioAction === 'add' ? form.profileAudioAssetId : null,
    },
    stories: form.stories.map((story) => ({
      client_id: story.clientId,
      action: story.action,
      asset_id: story.assetId,
      caption: story.caption || null,
      privacy_preset: story.privacyPreset,
      active_period_seconds: story.activePeriodSeconds,
      protect_content: story.protectContent,
    })),
  }
}
