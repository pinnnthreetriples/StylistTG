/**
 * ProfileEditor – thin orchestrator that composes the profile editor's three
 * feature blocks (avatar, music, stories) plus the text fields and change summary.
 *
 * Heavy per-block logic lives in:
 *   - AvatarBlock.tsx
 *   - MusicBlock.tsx
 *   - StoriesBlock.tsx
 */

import { memo, useEffect } from 'react'
import { useForm } from '@tanstack/react-form'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { type StoryCapabilities, type StoryDraftPayload, type StoryPost } from '@/lib/api'
import {
  buildChangeItems,
  formatChangeOperationLabel,
  appKnownMediaSyncNote,
  syncStateLabels,
  type CurrentProfile,
  type FormState,
} from '@/lib/dashboard'

import { PinnedChannelField } from '@/modules/account-editing/components/PinnedChannelField'
import { AvatarBlock } from './AvatarBlock'

type ProfileTextField = 'firstName' | 'lastName' | 'username' | 'bio'

export const ProfileEditor = memo(function ProfileEditor({
  changeItems,
  hasSelectedPhoto,
  photoPreviewUrl,
  onClearPhoto,
  onChoosePhoto,
  isUploadingPhoto,
  selectedPhotoName,
  currentProfile,
  form: draftForm,
  onChange,
}: {
  changeItems: ReturnType<typeof buildChangeItems>
  hasSelectedPhoto: boolean
  photoPreviewUrl: string | null
  onClearPhoto: () => void
  onChoosePhoto: () => void
  isUploadingPhoto: boolean
  selectedPhotoName: string | null
  profileAudio: {
    title: string | null
    performer: string | null
    duration_seconds: number | null
    source_asset_id: string | null
  } | null
  profileAudioAction: 'keep' | 'add' | 'remove'
  selectedAudioName: string | null
  isUploadingAudio: boolean
  onChooseAudio: () => void
  onKeepAudio: () => void
  onRemoveAudio: () => void
  stories: StoryDraftPayload[]
  isUploadingStory: boolean
  deletingStoryPostId: string | null
  onChooseStoryImage: () => void
  onUpdateStory: (clientId: string, patch: Partial<StoryDraftPayload>) => void
  onRemoveStory: (clientId: string) => void
  onDeleteStoryPost: (post: StoryPost) => void
  storyPosts: StoryPost[]
  storyCapabilities: StoryCapabilities | null
  currentProfile: CurrentProfile
  form: FormState
  onChange: (next: FormState | ((previous: FormState) => FormState)) => void
}) {
  const form = useForm({
    defaultValues: {
      firstName: draftForm.firstName,
      lastName: draftForm.lastName,
      username: draftForm.username,
      bio: draftForm.bio,
    },
  })

  function updateDraftField(fieldName: ProfileTextField, value: string) {
    onChange((prev) => ({ ...prev, [fieldName]: value }))
  }

  // Support external resets (e.g. from DashboardActionBar)
  useEffect(() => {
    if (
      draftForm.firstName !== form.state.values.firstName ||
      draftForm.lastName !== form.state.values.lastName ||
      draftForm.username !== form.state.values.username ||
      draftForm.bio !== form.state.values.bio
    ) {
      form.setFieldValue('firstName', draftForm.firstName)
      form.setFieldValue('lastName', draftForm.lastName)
      form.setFieldValue('username', draftForm.username)
      form.setFieldValue('bio', draftForm.bio)
    }
  }, [draftForm, form])

  const characterCount = draftForm.bio.length

  return (
    <>
      {/* ════════ BLOCK 1: PROFILE ════════ */}
      <div id="account-workspace-profile" className="bg-card rounded-xl border border-border p-4 mb-4">
        <div className="mb-3 flex flex-col gap-1 border-b border-border pb-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
            {syncStateLabels.telegramCurrent}
          </span>
          <span className="text-[10px] text-muted-foreground">
            Данные профиля синхронизируются после проверки аккаунта. {appKnownMediaSyncNote}
          </span>
        </div>
        <div className="flex flex-col sm:flex-row gap-5">
          {/* Avatar */}
          <AvatarBlock
            photoPreviewUrl={photoPreviewUrl}
            hasSelectedPhoto={hasSelectedPhoto}
            isUploadingPhoto={isUploadingPhoto}
            selectedPhotoName={selectedPhotoName}
            currentProfile={currentProfile}
            onChoosePhoto={onChoosePhoto}
            onClearPhoto={onClearPhoto}
          />

          {/* Text fields */}
          <div className="flex-grow space-y-3">
            {/* First name + Last name */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
                  htmlFor="first-name"
                >
                  Имя
                </label>
                <div className="relative">
                  <form.Field name="firstName">
                    {(field) => (
                      <Input
                        className="h-9 rounded-lg border-border bg-muted hover:bg-card focus:bg-card px-3 text-sm transition-colors"
                        id="first-name"
                        onChange={(e) => {
                          field.handleChange(e.target.value)
                          updateDraftField('firstName', e.target.value)
                        }}
                        onBlur={field.handleBlur}
                        value={field.state.value}
                        placeholder="Имя"
                      />
                    )}
                  </form.Field>
                  {(currentProfile.first_name ?? '') !== draftForm.firstName && (
                    <DirtyDot />
                  )}
                </div>
              </div>

              <div>
                <label
                  className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
                  htmlFor="last-name"
                >
                  Фамилия
                </label>
                <div className="relative">
                  <form.Field name="lastName">
                    {(field) => (
                      <Input
                        className="h-9 rounded-lg border-border bg-muted hover:bg-card focus:bg-card px-3 text-sm transition-colors"
                        id="last-name"
                        onChange={(e) => {
                          field.handleChange(e.target.value)
                          updateDraftField('lastName', e.target.value)
                        }}
                        onBlur={field.handleBlur}
                        value={field.state.value}
                        placeholder="Фамилия"
                      />
                    )}
                  </form.Field>
                  {(currentProfile.last_name ?? '') !== draftForm.lastName && <DirtyDot />}
                </div>
              </div>
            </div>

            {/* Username */}
            <div>
              <label
                className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
                htmlFor="username"
              >
                Юзернейм
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[13px] font-medium text-muted-foreground">
                  @
                </span>
                <form.Field name="username">
                  {(field) => (
                    <Input
                      className="h-9 rounded-lg border-border bg-muted hover:bg-card focus:bg-card pl-7 pr-3 text-sm transition-colors font-mono"
                      id="username"
                      onChange={(e) => {
                        const nextValue = e.target.value.replace(/^@/, '')
                        field.handleChange(nextValue)
                        updateDraftField('username', nextValue)
                      }}
                      onBlur={field.handleBlur}
                      value={field.state.value}
                      placeholder="username"
                    />
                  )}
                </form.Field>
                {(currentProfile.username ?? '') !== draftForm.username && <DirtyDot />}
              </div>
            </div>

            {/* Bio */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label
                  className="block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
                  htmlFor="bio"
                >
                  Описание
                </label>
                <span
                  className={`text-[10px] font-medium ${
                    characterCount > 70 ? 'text-destructive' : 'text-muted-foreground'
                  }`}
                >
                  {characterCount} / 70
                </span>
              </div>
              <div className="relative">
                <form.Field name="bio">
                  {(field) => (
                    <Textarea
                      className="min-h-[72px] resize-none rounded-lg border-border bg-muted hover:bg-card focus:bg-card px-3 py-2 text-sm leading-relaxed transition-colors"
                      id="bio"
                      onChange={(e) => {
                        field.handleChange(e.target.value)
                        updateDraftField('bio', e.target.value)
                      }}
                      onBlur={field.handleBlur}
                      value={field.state.value}
                      placeholder="Расскажите о себе"
                    />
                  )}
                </form.Field>
                {(currentProfile.bio ?? '') !== draftForm.bio && (
                  <span className="absolute right-2.5 top-3 size-1.5 rounded-full bg-muted" />
                )}
              </div>
              {/* Character progress bar */}
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full rounded-full transition-all ${
                    characterCount > 70
                      ? 'bg-destructive'
                      : 'bg-muted  '
                  }`}
                  style={{ width: `${Math.min(100, (characterCount / 70) * 100)}%` }}
                />
              </div>
            </div>

            {/* Pinned channel */}
            <PinnedChannelField
              value={draftForm.pinnedChannelRef}
              currentValue={currentProfile.pinned_channel_ref ?? null}
              onChange={(next) => onChange((prev) => ({ ...prev, pinnedChannelRef: next }))}
            />
          </div>
        </div>
      </div>



      {/* ════════ BLOCK 4: CHANGE SUMMARY ════════ */}
      <div className="bg-card rounded-xl border border-border p-4">
        <label className="mb-3 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Сводка изменений
        </label>
        {changeItems.filter((c) => c.changed).length === 0 ? (
          <div className="text-xs text-muted-foreground">Нет изменений</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {changeItems
              .filter((c) => c.changed)
              .map((change, index) => (
                <div
                  key={`${change.operation}-${index}`}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-muted"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-muted flex-shrink-0" />
                  <span className="text-[10px] font-semibold text-muted-foreground">
                    {formatChangeOperationLabel(change.operation)}
                  </span>
                  {change.value && (
                    <span className="text-[11px] font-medium text-foreground truncate max-w-[150px]">
                      {change.value}
                    </span>
                  )}
                </div>
              ))}
          </div>
        )}
      </div>
    </>
  )
})

/** Tiny dot indicating a field has been edited. */
function DirtyDot() {
  return (
    <span className="absolute right-2.5 top-1/2 -translate-y-1/2 size-1.5 rounded-full bg-muted" />
  )
}
