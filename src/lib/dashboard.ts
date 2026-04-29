import type { StoryDraftPayload } from '@/lib/api'
import type { ApiError } from '@/lib/http'
import { labelIssue } from '@/lib/uiLabels'

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

export type { ApiError }

export type RuntimeBanner = {
  title: string
  description: string
  accent: 'error' | 'warning'
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

export type PhotoPreviewState = {
  imageUrl: string | null
  hasPreview: boolean
}

type DashboardHydrationSource = {
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

type JobStateLike = {
  job_state: string
}

type JobActivityLike = JobStateLike & {
  finished_at?: string | null
  message?: string | null
}

type DashboardFormDraftStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

const dashboardFormDraftStoragePrefix = 'stylisttg.dashboard.formDraft.'

export function resolveAccountId(search: string, fallback: string | undefined): string | null {
  const params = new URLSearchParams(search)
  return params.get('account_id') ?? fallback ?? null
}

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

function getDashboardFormDraftStorageKey(accountId: string): string {
  return `${dashboardFormDraftStoragePrefix}${encodeURIComponent(accountId)}`
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

export function buildRuntimeBanner({ apiError }: { apiError: ApiError | null }): RuntimeBanner | null {
  if (!apiError) {
    return null
  }

  if (apiError.error_class === 'runtime') {
    return {
      title: labelIssue(apiError.error_code),
      description: apiError.message,
      accent: 'error',
    }
  }

  return {
    title: labelIssue(apiError.error_code),
    description: apiError.message,
    accent: 'error',
  }
}

export function formatAccountStateLabel(accountState: string | null | undefined): string {
  switch (accountState) {
    case 'execution_usable':
    case 'authorized_ready':
      return 'Авторизован'
    case 'reauth_required':
      return 'Нужен вход'
    case 'runtime_broken':
      return 'Runtime недоступен'
    case 'auth_pending':
    case 'awaiting_code':
      return 'Ожидает код'
    default:
      return accountState ?? 'unknown'
  }
}

export function buildJobMetrics(jobs: JobStateLike[]): {
  total: number
  success: number
  issues: number
} {
  const materialJobs = jobs.filter((job) => job.job_state !== 'dedup_blocked')
  return {
    total: materialJobs.length,
    success: materialJobs.filter((job) => job.job_state === 'completed').length,
    issues: materialJobs.filter((job) =>
      ['failed', 'manual_intervention_needed', 'partially_completed', 'canceled'].includes(job.job_state),
    ).length,
  }
}

export function formatJobActivityText(job: JobActivityLike | null): string {
  if (!job) {
    return 'Синхронизация ещё не запускалась'
  }

  switch (job.job_state) {
    case 'queued':
      return 'Задача в очереди'
    case 'waiting_lock':
      return 'Ожидает доступ к аккаунту'
    case 'running':
      return 'Задача выполняется'
    case 'dedup_blocked':
      return 'Такая задача уже стоит в очереди'
    default:
      return job.finished_at ? `Последняя задача ${formatRelativeTimestamp(job.finished_at)}` : 'Статус обновляется'
  }
}

export function formatRelativeTimestamp(value: string | null | undefined): string {
  if (!value) {
    return 'нет данных'
  }

  const date = parseApiTimestamp(value)
  if (Number.isNaN(date.getTime())) {
    return 'нет данных'
  }

  const diffMs = Date.now() - date.getTime()
  const diffMinutes = Math.max(0, Math.round(diffMs / 60000))
  if (diffMinutes < 1) {
    return 'сейчас'
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} мин назад`
  }

  const diffHours = Math.round(diffMinutes / 60)
  return `${diffHours} ч назад`
}

function parseApiTimestamp(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
  return new Date(hasTimezone ? value : `${value}Z`)
}
