import { composeDisplayName } from '@/modules/account-editing'
import type { FormPayload, ProfilePreview, StoryDraftPayload } from '@/modules/account-editing'

import {
  createTypedProfileJob,
  deleteTypedStoryPost,
  fetchTypedStoryCapabilities,
  fetchTypedStoryDrafts,
  previewTypedProfileJob,
  RUNTIME_REFRESH_TIMEOUT_MS,
  typedClient,
  type JobSummary,
  type StoryCapabilities,
  type StoryDraftRead,
} from './core'

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
