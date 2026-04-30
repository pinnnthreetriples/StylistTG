import { composeDisplayName } from '@/lib/dashboard'
import type { AccountRuntimeDiagnostics, RuntimeDiagnostics } from '@/lib/diagnostics'
import type {
  AccountSafety,
  AccountSafetySummary,
  AccountValidityCheck,
  AccountOperationCooldown,
  SafetyOperation,
  FreshValidityPolicy,
  RecentFailurePolicy,
  UnknownCapabilityPolicy,
} from '@/lib/accountSafety'
import type { LivePreflight } from '@/lib/settings'
import { getApiBaseUrl } from '@/lib/config'
import { apiRequest, isApiError } from '@/lib/http'

const RUNTIME_REFRESH_TIMEOUT_MS = 45000

type DashboardResponse = {
  account: {
    account_id: string
    display_name: string | null
    username: string | null
    phone_number: string | null
    telegram_user_id: string | null
    account_state: string
    runtime_health: string
    reauth_required: boolean
    is_execution_usable: boolean
  }
  current_profile: {
    first_name: string | null
    last_name: string | null
    bio: string | null
    username: string | null
    profile_photo_asset_id: string | null
  }
  profile_audio: {
    telegram_file_id: string | null
    title: string | null
    performer: string | null
    duration_seconds: number | null
    mime: string | null
    source_asset_id: string | null
  } | null
  story_posts: Array<{
    id: string
    story_poster_chat_id: string | null
    telegram_story_id: string | null
    temporary_story_id: string | null
    media_kind: 'image' | 'video'
    asset_id: string | null
    caption: string | null
    privacy_preset: string
    active_period_seconds: number
    protect_content: boolean
    can_be_deleted: boolean
    status: string
    failure_code: string | null
    failure_message: string | null
    posted_at: string | null
    expires_at: string | null
  }>
  editable_fields: {
    name: string | null
    bio: string | null
    username: string | null
    profile_photo: string | null
  }
  pipeline: {
    latest_job: JobSummary | null
    latest_job_state: string | null
    latest_job_id: string | null
    latest_job_finished_at: string | null
    has_active_job: boolean
    unsaved_changes_supported: boolean
  }
  diagnostics: {
    last_error_code: string | null
    last_error_class: string | null
    authorized_last_confirmed_at: string | null
    real_execution_enabled: boolean
    stories_live_execution_enabled: boolean
  }
}

export type AccountListItem = {
  account_id: string
  display_name: string | null
  username: string | null
  phone_number: string
  telegram_user_id: string | null
  account_state: string
  runtime_health: string
  is_execution_usable: boolean
  is_test_dc: boolean
  profile_photo_asset_id: string | null
  updated_at: string
}

export type JobSummary = {
  job_id: string
  job_state: string
  execution_intent_hash: string
  plan_summary: string[]
  created_at: string | null
  dedup_blocked_by_job_id: string | null
  message: string | null
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
    steps: Array<{
      step_key: string
      step_type: string
      order: number
      required: boolean
      idempotency_class: string
      payload: Record<string, unknown>
    }>
  }
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
}

export type RuntimeRefresh = {
  account_id: string
  account_state: string
  runtime_health: string
  is_execution_usable: boolean
  last_error_code: string | null
  last_error_class: string | null
  refreshed_at: string
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

export type StoryDraftRead = {
  id: string
  account_id: string
  asset_id: string
  media_kind: 'image' | 'video'
  caption: string | null
  privacy_preset: 'contacts' | 'close_friends' | 'public'
  active_period_seconds: 86400
  protect_content: boolean
  validation_status: string
  created_at: string
  updated_at: string
}

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

export function storyDraftReadToPayload(draft: StoryDraftRead): StoryDraftPayload {
  return {
    draftId: draft.id,
    clientId: draft.id,
    action: draft.media_kind === 'image' ? 'post_image' : 'post_video',
    assetId: draft.asset_id,
    fileName: draft.media_kind === 'image' ? 'Story image' : 'Story video',
    caption: draft.caption ?? '',
    privacyPreset: draft.privacy_preset,
    activePeriodSeconds: draft.active_period_seconds,
    protectContent: draft.protect_content,
  }
}

function accountHeader(accountId: string): HeadersInit {
  return { 'X-Account-Id': accountId }
}

export async function fetchDashboard(accountId: string): Promise<DashboardResponse> {
  return apiRequest<DashboardResponse>('/api/dashboard/profile', {
    headers: accountHeader(accountId),
  })
}

export async function fetchAccounts(): Promise<AccountListItem[]> {
  return apiRequest<AccountListItem[]>('/api/accounts')
}

export async function fetchAccountSafetySummary(): Promise<AccountSafetySummary[]> {
  return apiRequest<AccountSafetySummary[]>('/api/accounts/safety-summary')
}

export async function fetchAccountSafety(accountId: string): Promise<AccountSafety> {
  return apiRequest<AccountSafety>(`/api/accounts/${accountId}/safety`)
}

export async function previewAccountBatchSafety(
  accountIds: string[],
  operation: SafetyOperation | string,
  allowWarningOverrides = false,
): Promise<AccountBatchSafetyPreview> {
  return apiRequest<AccountBatchSafetyPreview>('/api/accounts/safety-batch-preview', {
    method: 'POST',
    body: JSON.stringify({
      account_ids: accountIds,
      operation,
      allow_warning_overrides: allowWarningOverrides,
    }),
  })
}

export async function runAccountValidityCheck(accountId: string, mode = 'db_snapshot'): Promise<AccountValidityCheck> {
  return apiRequest<AccountValidityCheck>(`/api/accounts/${accountId}/validity-check`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

export async function fetchAccountValidityChecks(accountId: string): Promise<AccountValidityCheck[]> {
  return apiRequest<AccountValidityCheck[]>(`/api/accounts/${accountId}/validity-checks`)
}

export async function deleteAccount(accountId: string): Promise<void> {
  await apiRequest<void>(`/api/accounts/${accountId}`, {
    method: 'DELETE',
  })
}

export async function fetchLatestJobs(accountId: string, limit = 10): Promise<JobSummary[]> {
  return apiRequest<JobSummary[]>(`/api/accounts/jobs?limit=${limit}`, {
    headers: accountHeader(accountId),
  })
}

export async function fetchLatestJob(accountId: string): Promise<JobSummary> {
  return apiRequest<JobSummary>('/api/accounts/jobs/latest', {
    headers: accountHeader(accountId),
  })
}

export async function fetchJob(jobId: string): Promise<JobDetail> {
  return apiRequest<JobDetail>(`/api/jobs/${jobId}`)
}

export async function fetchJobSteps(jobId: string): Promise<JobStep[]> {
  return apiRequest<JobStep[]>(`/api/jobs/${jobId}/steps`)
}

export async function cancelJob(jobId: string): Promise<JobSummary> {
  return apiRequest<JobSummary>(`/api/jobs/${jobId}/cancel`, {
    method: 'POST',
  })
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiRequest<void>(`/api/jobs/${jobId}`, {
    method: 'DELETE',
  })
}

export async function refreshRuntime(accountId: string): Promise<RuntimeRefresh> {
  return apiRequest<RuntimeRefresh>('/api/accounts/refresh-runtime', {
    method: 'POST',
    headers: accountHeader(accountId),
    timeoutMs: RUNTIME_REFRESH_TIMEOUT_MS,
  })
}

export async function fetchRuntimeDiagnostics(): Promise<RuntimeDiagnostics> {
  return apiRequest<RuntimeDiagnostics>('/diagnostics/runtime')
}

export async function fetchLivePreflight(): Promise<LivePreflight> {
  return apiRequest<LivePreflight>('/diagnostics/live-preflight')
}

export async function fetchAccountRuntimeDiagnostics(accountId: string): Promise<AccountRuntimeDiagnostics> {
  return apiRequest<AccountRuntimeDiagnostics>('/api/accounts/runtime-diagnostics', {
    headers: accountHeader(accountId),
  })
}

export async function fetchExecutionPolicy(): Promise<ExecutionPolicy> {
  return apiRequest<ExecutionPolicy>('/api/settings/execution-policy')
}

export async function updateExecutionPolicy(update: number | ExecutionPolicyUpdate): Promise<ExecutionPolicy> {
  const body = typeof update === 'number' ? { profile_job_cooldown_seconds: update } : update
  return apiRequest<ExecutionPolicy>('/api/settings/execution-policy', {
    method: 'PATCH',
    body: JSON.stringify(body),
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

export async function uploadProfilePhoto(file: File): Promise<{ id: string }> {
  const body = new FormData()
  body.append('file', file)

  return apiRequest<{ id: string }>('/api/assets/profile-photo', {
    method: 'POST',
    body,
  })
}

export async function uploadProfileAudio(file: File): Promise<{ id: string }> {
  const body = new FormData()
  body.append('file', file)

  return apiRequest<{ id: string }>('/api/assets/profile-audio', {
    method: 'POST',
    body,
  })
}

export async function uploadStoryImage(file: File): Promise<{ id: string }> {
  const body = new FormData()
  body.append('file', file)

  return apiRequest<{ id: string }>('/api/assets/story-image', {
    method: 'POST',
    body,
  })
}

export async function uploadStoryVideo(file: File): Promise<{ id: string }> {
  const body = new FormData()
  body.append('file', file)

  return apiRequest<{ id: string }>('/api/assets/story-video', {
    method: 'POST',
    body,
  })
}

export async function fetchStoryDrafts(accountId: string): Promise<StoryDraftRead[]> {
  return apiRequest<StoryDraftRead[]>('/api/story-drafts', {
    headers: accountHeader(accountId),
  })
}

export async function fetchStoryCapabilities(accountId: string): Promise<StoryCapabilities> {
  return apiRequest<StoryCapabilities>('/api/story-capabilities', {
    headers: accountHeader(accountId),
  })
}

export async function createStoryDraft(
  accountId: string,
  draft: Omit<StoryDraftPayload, 'draftId' | 'clientId' | 'fileName' | 'action'>,
  mediaKind: 'image' | 'video',
): Promise<StoryDraftRead> {
  return apiRequest<StoryDraftRead>('/api/story-drafts', {
    method: 'POST',
    body: JSON.stringify({
      account_id: accountId,
      asset_id: draft.assetId,
      media_kind: mediaKind,
      caption: draft.caption || null,
      privacy_preset: draft.privacyPreset,
      active_period_seconds: draft.activePeriodSeconds,
      protect_content: draft.protectContent,
    }),
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

export async function updateStoryDraft(
  draftId: string,
  patch: Partial<Pick<StoryDraftPayload, 'caption' | 'privacyPreset' | 'activePeriodSeconds' | 'protectContent'>>,
): Promise<StoryDraftRead> {
  return apiRequest<StoryDraftRead>(`/api/story-drafts/${draftId}`, {
    method: 'PATCH',
    body: JSON.stringify({
      caption: patch.caption,
      privacy_preset: patch.privacyPreset,
      active_period_seconds: patch.activePeriodSeconds,
      protect_content: patch.protectContent,
    }),
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

export async function deleteStoryDraft(draftId: string): Promise<void> {
  try {
    await apiRequest<void>(`/api/story-drafts/${draftId}`, {
      method: 'DELETE',
    })
  } catch (error) {
    if (isApiError(error) && error.error_code === 'STORY_DRAFT_NOT_FOUND') {
      return
    }
    throw error
  }
}

export async function deleteStoryPost(accountId: string, postId: string): Promise<void> {
  await apiRequest<void>(`/api/story-posts/${postId}`, {
    method: 'DELETE',
    headers: accountHeader(accountId),
    timeoutMs: RUNTIME_REFRESH_TIMEOUT_MS,
  })
}

export function buildAssetContentUrl(assetId: string): string {
  return `${getApiBaseUrl()}/api/assets/${encodeURIComponent(assetId)}/content`
}

export async function previewProfileJob(accountId: string, form: FormPayload): Promise<ProfilePreview> {
  return apiRequest<ProfilePreview>('/api/jobs/profile/preview', {
    method: 'POST',
    body: JSON.stringify({
      account_id: accountId,
      name: composeDisplayName(form.firstName, form.lastName) || null,
      bio: form.bio || null,
      username: form.username || null,
      photo_asset_id: form.profilePhotoAssetId,
    }),
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

export async function previewAccountUpdateJob(
  accountId: string,
  form: FormPayload,
  init?: Pick<RequestInit, 'signal'>,
): Promise<ProfilePreview> {
  return apiRequest<ProfilePreview>('/api/account-update/preview', {
    method: 'POST',
    body: JSON.stringify(buildAccountUpdateBody(accountId, form)),
    signal: init?.signal,
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

export async function createProfileJob(accountId: string, form: FormPayload): Promise<JobSummary> {
  return apiRequest<JobSummary>('/api/jobs/profile', {
    method: 'POST',
    body: JSON.stringify({
      account_id: accountId,
      name: composeDisplayName(form.firstName, form.lastName) || null,
      bio: form.bio || null,
      username: form.username || null,
      photo_asset_id: form.profilePhotoAssetId,
    }),
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

export async function createAccountUpdateJob(accountId: string, form: FormPayload): Promise<JobSummary> {
  return apiRequest<JobSummary>('/api/account-update/jobs', {
    method: 'POST',
    body: JSON.stringify(buildAccountUpdateBody(accountId, form)),
    headers: {
      'Content-Type': 'application/json',
    },
  })
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
