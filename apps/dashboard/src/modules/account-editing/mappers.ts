import type {
  ChangeItem,
  CurrentProfile,
  DashboardDiagnostics,
  DashboardHydrationSource,
  FormState,
  PhotoPreviewState,
  RealExecutionChangeGroups,
} from './types'

export const syncStateLabels = {
  telegramCurrent: 'Текущее в Telegram',
  appKnown: 'Известно приложению',
  draft: 'Черновик изменений',
} as const

export const appKnownMediaSyncNote =
  'Фото, музыка и истории могут быть известны приложению только после изменений через StylistTG.'

const changeOperationLabels: Record<ChangeItem['operation'], string> = {
  set_name: 'Имя',
  set_bio: 'Описание',
  set_username: 'Юзернейм',
  set_profile_photo: 'Фото профиля',
  add_profile_audio: 'Музыка профиля',
  remove_profile_audio: 'Удалить музыку',
  keep_profile_audio: 'Музыка без изменений',
  post_story_image: 'Фото в историю',
  post_story_video: 'Видео в историю',
}

const profileOperations = new Set<ChangeItem['operation']>([
  'set_name',
  'set_bio',
  'set_username',
  'set_profile_photo',
])
const musicOperations = new Set<ChangeItem['operation']>(['add_profile_audio', 'remove_profile_audio'])
const storyOperations = new Set<ChangeItem['operation']>(['post_story_image', 'post_story_video'])

const supportedProfileAudioMimes = new Set(['audio/mpeg', 'audio/mp4', 'audio/x-m4a'])
const supportedProfileAudioExtensions = ['.mp3', '.m4a']
const dashboardFormDraftStoragePrefix = 'stylisttg.dashboard.formDraft.'

type DashboardFormDraftStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

export function splitDisplayName(value: string | null | undefined): {
  firstName: string
  lastName: string
} {
  const trimmed = value?.trim() ?? ''
  if (!trimmed) {
    return { firstName: '', lastName: '' }
  }

  const [firstName, ...rest] = trimmed.split(/\s+/)
  return {
    firstName,
    lastName: rest.join(' '),
  }
}

export function composeDisplayName(
  firstName: string | null | undefined,
  lastName: string | null | undefined,
): string {
  return [(firstName ?? '').trim(), (lastName ?? '').trim()].filter(Boolean).join(' ')
}

export function resolveDashboardIdentity(
  currentProfile: CurrentProfile,
  fallback: { display_name: string | null; username: string | null },
): { displayName: string | null; username: string | null } {
  const currentDisplayName = composeDisplayName(currentProfile.first_name, currentProfile.last_name)
  return {
    displayName: currentDisplayName || fallback.display_name,
    username: currentProfile.username ?? fallback.username,
  }
}

export function buildDashboardFormState(source: DashboardHydrationSource): FormState {
  return {
    firstName: source.current_profile.first_name ?? '',
    lastName: source.current_profile.last_name ?? '',
    bio: source.current_profile.bio ?? '',
    username: source.current_profile.username ?? '',
    profilePhotoAssetId:
      source.current_profile.profile_photo_asset_id ?? source.editable_fields.profile_photo,
    profileAudioAction: 'keep',
    profileAudioAssetId: source.profile_audio?.source_asset_id ?? source.current_profile.profile_audio_asset_id ?? null,
    stories: [],
  }
}

export function areDashboardFormStatesEqual(left: FormState, right: FormState): boolean {
  return (
    left.firstName === right.firstName &&
    left.lastName === right.lastName &&
    left.bio === right.bio &&
    left.username === right.username &&
    left.profilePhotoAssetId === right.profilePhotoAssetId &&
    left.profileAudioAction === right.profileAudioAction &&
    left.profileAudioAssetId === right.profileAudioAssetId &&
    JSON.stringify(left.stories) === JSON.stringify(right.stories)
  )
}

export function readStoredDashboardFormDraft(
  storage: Pick<Storage, 'getItem'> | null,
  accountId: string,
): FormState | null {
  if (!storage) {
    return null
  }

  const rawValue = storage.getItem(getDashboardFormDraftStorageKey(accountId))
  if (!rawValue) {
    return null
  }

  const parsed = JSON.parse(rawValue) as FormState
  return {
    firstName: parsed.firstName,
    lastName: parsed.lastName,
    bio: parsed.bio,
    username: parsed.username,
    profilePhotoAssetId: parsed.profilePhotoAssetId,
    profileAudioAction: parsed.profileAudioAction ?? 'keep',
    profileAudioAssetId: parsed.profileAudioAssetId ?? null,
    stories: parsed.stories ?? [],
  }
}

export function reconcileStoredDashboardFormDraft(storedDraft: FormState, serverForm: FormState): FormState {
  const serverStoryIds = new Set(serverForm.stories.map((story) => story.draftId).filter(Boolean))
  return {
    ...storedDraft,
    stories: storedDraft.stories.filter((story) => story.draftId === null || serverStoryIds.has(story.draftId)),
  }
}

export function persistStoredDashboardFormDraft(
  storage: DashboardFormDraftStorage | null,
  accountId: string,
  form: FormState,
): void {
  storage?.setItem(getDashboardFormDraftStorageKey(accountId), JSON.stringify(form))
}

export function clearStoredDashboardFormDraft(
  storage: Pick<Storage, 'removeItem'> | null,
  accountId: string,
): void {
  storage?.removeItem(getDashboardFormDraftStorageKey(accountId))
}

export function resolvePhotoPreview(imageUrl: string | null): PhotoPreviewState {
  return {
    imageUrl,
    hasPreview: Boolean(imageUrl),
  }
}

export function resolveProfilePhotoPreviewUrl(
  selectedPhotoPreviewUrl: string | null,
  profilePhotoAssetId: string | null,
  buildAssetUrl: (assetId: string) => string,
): string | null {
  if (selectedPhotoPreviewUrl) {
    return selectedPhotoPreviewUrl
  }

  return profilePhotoAssetId ? buildAssetUrl(profilePhotoAssetId) : null
}

export function clearProfilePhotoDraft(form: FormState): FormState {
  return {
    ...form,
    profilePhotoAssetId: null,
  }
}

export function buildChangeItems(current: CurrentProfile, draft: FormState): ChangeItem[] {
  const currentName = composeDisplayName(current.first_name ?? '', current.last_name ?? '')
  const draftName = composeDisplayName(draft.firstName, draft.lastName)

  const items: ChangeItem[] = [
    {
      operation: 'set_name',
      changed: currentName !== draftName,
      value: currentName !== draftName ? `${currentName || 'Пусто'} -> ${draftName || 'Пусто'}` : 'Без изменений',
    },
    {
      operation: 'set_bio',
      changed: (current.bio ?? '') !== draft.bio,
      value: (current.bio ?? '') !== draft.bio ? draft.bio || 'Пусто' : 'Без изменений',
    },
    {
      operation: 'set_username',
      changed: (current.username ?? '') !== draft.username,
      value: (current.username ?? '') !== draft.username ? (draft.username || 'Пусто') : 'Без изменений',
    },
    {
      operation: 'set_profile_photo',
      changed: (current.profile_photo_asset_id ?? null) !== draft.profilePhotoAssetId,
      value:
        (current.profile_photo_asset_id ?? null) !== draft.profilePhotoAssetId
          ? 'Фото будет обновлено'
          : 'Без изменений',
    },
  ]
  if (draft.profileAudioAction === 'add') {
    items.push({
      operation: 'add_profile_audio',
      changed: true,
      value: 'Музыка будет обновлена',
    })
  } else if (draft.profileAudioAction === 'remove') {
    items.push({
      operation: 'remove_profile_audio',
      changed: Boolean(current.profile_audio_asset_id),
      value: current.profile_audio_asset_id ? 'Музыка будет удалена' : 'Без изменений',
    })
  } else {
    items.push({
      operation: 'keep_profile_audio',
      changed: false,
      value: 'Без изменений',
    })
  }
  for (const story of draft.stories) {
    items.push({
      operation: story.action === 'post_image' ? 'post_story_image' : 'post_story_video',
      changed: true,
      value: `${story.fileName}${story.caption ? ` · ${story.caption}` : ''}`,
    })
  }
  return items
}

export function formatChangeOperationLabel(operation: ChangeItem['operation']): string {
  return changeOperationLabels[operation]
}

export function groupRealExecutionChanges(changedItems: ChangeItem[]): RealExecutionChangeGroups {
  return {
    profile: changedItems.filter((item) => profileOperations.has(item.operation)),
    music: changedItems.filter((item) => musicOperations.has(item.operation)),
    stories: changedItems.filter((item) => storyOperations.has(item.operation)),
  }
}

export function shouldConfirmRealTelegramExecution(
  diagnostics: DashboardDiagnostics | null | undefined,
  changedItems: ChangeItem[],
): boolean {
  const groups = groupRealExecutionChanges(changedItems)
  const profileOrMusicWillRun = groups.profile.length > 0 || groups.music.length > 0
  const storiesWillRun = groups.stories.length > 0

  return Boolean(
    (diagnostics?.real_execution_enabled && profileOrMusicWillRun) ||
      (diagnostics?.stories_live_execution_enabled && storiesWillRun),
  )
}

export function isSupportedProfileAudioFile(file: Pick<File, 'name' | 'type'>): boolean {
  const mime = file.type.trim().toLowerCase()
  const name = file.name.trim().toLowerCase()
  return supportedProfileAudioMimes.has(mime) || supportedProfileAudioExtensions.some((ext) => name.endsWith(ext))
}

function getDashboardFormDraftStorageKey(accountId: string): string {
  return `${dashboardFormDraftStoragePrefix}${encodeURIComponent(accountId)}`
}
