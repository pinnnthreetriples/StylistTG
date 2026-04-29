/**
 * ProfileEditor – thin orchestrator that composes the profile editor's three
 * feature blocks (avatar, music, stories) plus the text fields and change summary.
 *
 * Heavy per-block logic lives in:
 *   - AvatarBlock.tsx
 *   - MusicBlock.tsx
 *   - StoriesBlock.tsx
 */

import { memo } from 'react'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { type StoryCapabilities, type StoryDraftPayload, type StoryPost } from '@/lib/api'
import {
  buildChangeItems,
  formatChangeOperationLabel,
  type CurrentProfile,
  type FormState,
} from '@/lib/dashboard'

import { AvatarBlock } from './AvatarBlock'
import { MusicBlock } from './MusicBlock'
import { StoriesBlock } from './StoriesBlock'

export const ProfileEditor = memo(function ProfileEditor({
  changeItems,
  hasSelectedPhoto,
  photoPreviewUrl,
  onClearPhoto,
  onChoosePhoto,
  isUploadingPhoto,
  selectedPhotoName,
  profileAudio,
  profileAudioAction,
  selectedAudioName,
  isUploadingAudio,
  onChooseAudio,
  onKeepAudio,
  onRemoveAudio,
  stories,
  isUploadingStory,
  deletingStoryPostId,
  onChooseStoryImage,
  onUpdateStory,
  onRemoveStory,
  onDeleteStoryPost,
  storyPosts,
  storyCapabilities,
  currentProfile,
  form,
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
  const characterCount = form.bio.length

  return (
    <>
      {/* ════════ BLOCK 1: PROFILE ════════ */}
      <div className="section-card bg-white rounded-xl border border-gray-200 p-4 mb-4 delay-1">
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
                  className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-500"
                  htmlFor="first-name"
                >
                  Имя
                </label>
                <div className="relative">
                  <Input
                    className="h-9 rounded-lg border-gray-200 bg-gray-50/50 hover:bg-white focus:bg-white px-3 text-sm transition-colors"
                    id="first-name"
                    onChange={(e) => onChange((prev) => ({ ...prev, firstName: e.target.value }))}
                    value={form.firstName}
                    placeholder="Имя"
                  />
                  {(currentProfile.first_name ?? '') !== form.firstName && (
                    <DirtyDot />
                  )}
                </div>
              </div>

              <div>
                <label
                  className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-500"
                  htmlFor="last-name"
                >
                  Фамилия
                </label>
                <div className="relative">
                  <Input
                    className="h-9 rounded-lg border-gray-200 bg-gray-50/50 hover:bg-white focus:bg-white px-3 text-sm transition-colors"
                    id="last-name"
                    onChange={(e) => onChange((prev) => ({ ...prev, lastName: e.target.value }))}
                    value={form.lastName}
                    placeholder="Фамилия"
                  />
                  {(currentProfile.last_name ?? '') !== form.lastName && <DirtyDot />}
                </div>
              </div>
            </div>

            {/* Username */}
            <div>
              <label
                className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-500"
                htmlFor="username"
              >
                Юзернейм
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[13px] font-medium text-gray-400">
                  @
                </span>
                <Input
                  className="h-9 rounded-lg border-gray-200 bg-gray-50/50 hover:bg-white focus:bg-white pl-7 pr-3 text-sm transition-colors font-mono"
                  id="username"
                  onChange={(e) =>
                    onChange((prev) => ({
                      ...prev,
                      username: e.target.value.replace(/^@/, ''),
                    }))
                  }
                  value={form.username}
                  placeholder="username"
                />
                {(currentProfile.username ?? '') !== form.username && <DirtyDot />}
              </div>
            </div>

            {/* Bio */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label
                  className="block text-[11px] font-semibold uppercase tracking-wider text-gray-500"
                  htmlFor="bio"
                >
                  Описание
                </label>
                <span
                  className={`text-[10px] font-medium ${
                    characterCount > 70 ? 'text-red-500' : 'text-gray-400'
                  }`}
                >
                  {characterCount} / 70
                </span>
              </div>
              <div className="relative">
                <Textarea
                  className="min-h-[72px] resize-none rounded-lg border-gray-200 bg-gray-50/50 hover:bg-white focus:bg-white px-3 py-2 text-sm leading-relaxed transition-colors"
                  id="bio"
                  onChange={(e) => onChange((prev) => ({ ...prev, bio: e.target.value }))}
                  value={form.bio}
                  placeholder="Расскажите о себе"
                />
                {(currentProfile.bio ?? '') !== form.bio && (
                  <span className="absolute right-2.5 top-3 size-1.5 rounded-full bg-tangerine-400" />
                )}
              </div>
              {/* Character progress bar */}
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-gray-100">
                <div
                  className={`h-full rounded-full transition-all ${
                    characterCount > 70
                      ? 'bg-red-400'
                      : 'bg-gradient-to-r from-navy-400 to-tangerine-400'
                  }`}
                  style={{ width: `${Math.min(100, (characterCount / 70) * 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ════════ BLOCK 2: MUSIC ════════ */}
      <MusicBlock
        profileAudio={profileAudio}
        profileAudioAction={profileAudioAction}
        selectedAudioName={selectedAudioName}
        isUploadingAudio={isUploadingAudio}
        onChooseAudio={onChooseAudio}
        onKeepAudio={onKeepAudio}
        onRemoveAudio={onRemoveAudio}
      />

      {/* ════════ BLOCK 3: STORIES ════════ */}
      <StoriesBlock
        stories={stories}
        storyPosts={storyPosts}
        storyCapabilities={storyCapabilities}
        isUploadingStory={isUploadingStory}
        deletingStoryPostId={deletingStoryPostId}
        onChooseStoryImage={onChooseStoryImage}
        onUpdateStory={onUpdateStory}
        onRemoveStory={onRemoveStory}
        onDeleteStoryPost={onDeleteStoryPost}
      />

      {/* ════════ BLOCK 4: CHANGE SUMMARY ════════ */}
      <div className="section-card bg-white rounded-xl border border-gray-200 p-4 delay-4">
        <label className="mb-3 block text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          Сводка изменений
        </label>
        {changeItems.filter((c) => c.changed).length === 0 ? (
          <div className="text-xs text-gray-400">Нет изменений</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {changeItems
              .filter((c) => c.changed)
              .map((change, index) => (
                <div
                  key={`${change.operation}-${index}`}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-tangerine-200/50 bg-tangerine-50"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-tangerine-400 flex-shrink-0" />
                  <span className="text-[10px] font-semibold text-gray-500">
                    {formatChangeOperationLabel(change.operation)}
                  </span>
                  {change.value && (
                    <span className="text-[11px] font-medium text-gray-800 truncate max-w-[150px]">
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

/** Tiny orange dot indicating a field has been edited. */
function DirtyDot() {
  return (
    <span className="absolute right-2.5 top-1/2 -translate-y-1/2 size-1.5 rounded-full bg-tangerine-400" />
  )
}
