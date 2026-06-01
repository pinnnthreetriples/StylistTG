import type { FormPayload } from './api'
import type { FormState } from './types'

export function toFormPayload(form: FormState): FormPayload {
  return {
    firstName: form.firstName,
    lastName: form.lastName,
    bio: form.bio,
    username: form.username,
    profilePhotoAssetId: form.profilePhotoAssetId,
    pinnedChannelRef: form.pinnedChannelRef,
    profileAudioAction: form.profileAudioAction,
    profileAudioAssetId: form.profileAudioAssetId,
    stories: form.stories,
  }
}
