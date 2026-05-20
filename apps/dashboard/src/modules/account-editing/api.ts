import {
  buildAssetContentUrl as buildTypedAssetContentUrl,
  createAccountUpdateJob as createTypedAccountUpdateJob,
  createStoryDraft as createTypedStoryDraft,
  deleteStoryDraft as deleteTypedStoryDraft,
  previewAccountUpdateJob as previewTypedAccountUpdateJob,
  updateStoryDraft as updateTypedStoryDraft,
  uploadAsset,
  type StoryDraftRead,
} from '@stylisttg/api-client'

import { isApiError } from '@/lib/http'
import { dashboardApiClient } from '@/modules/shared'

import { composeDisplayName } from './mappers'
import type { FormPayload, JobSummary, ProfilePreview, StoryDraftPayload } from './types'

export type { FormPayload, JobSummary, ProfilePreview, StoryDraftPayload }
export type { StoryDraftRead }

const typedClient = dashboardApiClient

export function previewAccountUpdateJob(
  accountId: string,
  form: FormPayload,
  init?: Pick<RequestInit, 'signal'>,
): Promise<ProfilePreview> {
  return previewTypedAccountUpdateJob(typedClient, buildAccountUpdateBody(accountId, form), init) as Promise<ProfilePreview>
}

export function createAccountUpdateJob(accountId: string, form: FormPayload): Promise<JobSummary> {
  return createTypedAccountUpdateJob(typedClient, buildAccountUpdateBody(accountId, form))
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

export function buildAssetContentUrl(assetId: string): string {
  return buildTypedAssetContentUrl(typedClient, assetId)
}

function buildAccountUpdateBody(accountId: string, form: FormPayload) {
  return {
    account_id: accountId,
    profile: {
      name: composeDisplayName(form.firstName, form.lastName) || null,
      bio: form.bio || null,
      username: form.username || null,
      photo_asset_id: form.profilePhotoAssetId,
      pinned_channel_ref: form.pinnedChannelRef || null,
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
