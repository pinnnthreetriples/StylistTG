import type { JobSummary } from '@stylisttg/api-client'

import type { AccountSafety, OperationSafety } from '@/lib/accountSafety'

export type { JobSummary }

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

export type CurrentProfile = {
  first_name: string | null
  last_name: string | null
  bio: string | null
  username: string | null
  profile_photo_asset_id: string | null
  profile_audio_asset_id?: string | null
}

export type FormState = {
  firstName: string
  lastName: string
  bio: string
  username: string
  profilePhotoAssetId: string | null
  profileAudioAction: 'keep' | 'add' | 'remove'
  profileAudioAssetId: string | null
  stories: StoryDraftPayload[]
}

export type ChangeItem = {
  operation:
    | 'set_name'
    | 'set_bio'
    | 'set_username'
    | 'set_profile_photo'
    | 'add_profile_audio'
    | 'remove_profile_audio'
    | 'keep_profile_audio'
    | 'post_story_image'
    | 'post_story_video'
  changed: boolean
  value: string
}

export type DashboardDiagnostics = {
  real_execution_enabled?: boolean
  stories_live_execution_enabled?: boolean
}

export type RealExecutionChangeGroups = {
  profile: ChangeItem[]
  music: ChangeItem[]
  stories: ChangeItem[]
}

export type PhotoPreviewState = {
  imageUrl: string | null
  hasPreview: boolean
}

export type DashboardHydrationSource = {
  current_profile: CurrentProfile
  profile_audio?: {
    source_asset_id: string | null
  } | null
  editable_fields: {
    name?: string | null
    bio?: string | null
    username?: string | null
    profile_photo: string | null
  }
}
