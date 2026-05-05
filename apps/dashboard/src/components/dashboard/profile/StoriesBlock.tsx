/**
 * StoriesBlock – stories grid with add / remove / edit modal.
 */

import { AlertTriangle, ImagePlus, Loader2, Trash2, UploadCloud, User, Video, X, Link } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { type StoryCapabilities, type StoryDraftPayload, type StoryPost } from '@/lib/api'
import { appKnownMediaSyncNote, buildStoryCapabilityStatus, syncStateLabels } from '@/lib/dashboard'

interface StoriesBlockProps {
  stories: StoryDraftPayload[]
  storyPosts: StoryPost[]
  storyCapabilities: StoryCapabilities | null
  isUploadingStory: boolean
  deletingStoryPostId: string | null
  onChooseStoryImage: () => void
  onUpdateStory: (clientId: string, patch: Partial<StoryDraftPayload>) => void
  onRemoveStory: (clientId: string) => void
  onDeleteStoryPost: (post: StoryPost) => void
}

export function StoriesBlock({
  stories,
  storyPosts,
  storyCapabilities,
  isUploadingStory,
  deletingStoryPostId,
  onChooseStoryImage,
  onUpdateStory,
  onRemoveStory,
  onDeleteStoryPost,
}: StoriesBlockProps) {
  const [editingStoryId, setEditingStoryId] = useState<string | null>(null)
  const [pendingDeletePost, setPendingDeletePost] = useState<StoryPost | null>(null)
  const editingStory = stories.find((s) => s.clientId === editingStoryId)
  const closeModal = () => setEditingStoryId(null)
  const closeDeleteModal = () => setPendingDeletePost(null)
  const capabilityStatus = buildStoryCapabilityStatus(storyCapabilities)
  const confirmDelete = () => {
    if (!pendingDeletePost) return
    onDeleteStoryPost(pendingDeletePost)
    setPendingDeletePost(null)
  }

  return (
    <div className="section-card bg-white rounded-xl border border-gray-200 p-4 mb-4 delay-3">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ImagePlus className="text-navy-400 size-4" />
            <h2 className="font-display font-bold text-sm tracking-tight text-gray-900">
              Истории ({stories.length})
            </h2>
            {isUploadingStory && <Loader2 className="size-3.5 animate-spin text-gray-400" />}
          </div>
          <p className={`mt-1 text-[10px] ${capabilityStatusClass(capabilityStatus.tone)}`}>
            Создайте историю для этого аккаунта. Перед публикацией система проверит ограничения и риск.
          </p>
        </div>
      </div>

      <div className={`mb-3 rounded-lg border px-3 py-2 ${capabilityBoxClass(capabilityStatus.tone)}`}>
        <p className="text-[11px] font-semibold">{capabilityStatus.title}</p>
        {capabilityStatus.items.length > 0 ? (
          <ul className="mt-1 space-y-0.5">
            {capabilityStatus.items.slice(0, 3).map((item) => (
              <li className="text-[10px] leading-snug" key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-[10px] leading-snug">
            {stories.length > 0 ? syncStateLabels.draft : 'Публикация в live-режиме выключена безопасно. Можно подготовить черновик и задачу без live-запуска.'}
          </p>
        )}
      </div>

      {stories.length === 0 ? (
        <div className="mb-3 rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-5 text-center">
          <p className="text-sm font-semibold text-gray-900">Историй пока нет</p>
          <p className="mt-1 text-xs text-gray-500">Добавьте фото или видео, чтобы подготовить историю.</p>
        </div>
      ) : null}

      {/* ── Grid ── */}
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
        {stories.map((story) => (
          <div
            key={story.clientId}
            aria-label={`Настроить историю ${story.fileName}`}
            className="group relative aspect-[9/16] rounded-lg border border-gray-200 bg-gray-100 overflow-hidden cursor-pointer hover:ring-2 hover:ring-navy-400 hover:ring-offset-1 transition-all"
            onClick={() => setEditingStoryId(story.clientId)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                setEditingStoryId(story.clientId)
              }
            }}
            role="button"
            tabIndex={0}
          >
            {/* Placeholder */}
            <div className="absolute inset-0 flex flex-col items-center justify-center p-2 text-center text-gray-400 bg-gray-50">
              {story.action === 'post_image' ? (
                <ImagePlus className="size-6 mb-1 opacity-50" />
              ) : (
                <Video className="size-6 mb-1 opacity-50" />
              )}
              <span className="text-[9px] font-medium truncate w-full">{story.fileName}</span>
            </div>

            {/* Privacy badge */}
            <div className="absolute top-1.5 left-1.5 flex gap-1">
              <div className="w-5 h-5 rounded-md bg-black/60 backdrop-blur-sm flex items-center justify-center text-white">
                {story.privacyPreset === 'public' ? (
                  <User className="size-3" />
                ) : (
                  <Link className="size-3" />
                )}
              </div>
            </div>

            {/* Remove button */}
            <button
              aria-label={`Удалить историю ${story.fileName}`}
              onClick={(e) => { e.stopPropagation(); onRemoveStory(story.clientId) }}
              className="absolute top-1.5 right-1.5 w-6 h-6 rounded-md bg-black/60 backdrop-blur-sm flex items-center justify-center text-white opacity-0 group-hover:opacity-100 hover:bg-red-500 transition-all"
              type="button"
            >
              <Trash2 className="size-3" />
            </button>

            {/* Caption overlay */}
            {story.caption && (
              <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-2 pt-4">
                <p className="text-[9px] text-white line-clamp-2 leading-tight">{story.caption}</p>
              </div>
            )}
          </div>
        ))}

        {/* Add placeholder */}
        <button
          aria-label="Добавить историю"
          onClick={onChooseStoryImage}
          className="aspect-[9/16] rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 flex flex-col items-center justify-center cursor-pointer hover:border-navy-300 hover:bg-navy-50/30 transition-all text-gray-400 hover:text-navy-400"
          type="button"
        >
          <div className="w-8 h-8 rounded-full bg-white shadow-sm flex items-center justify-center mb-2">
            <UploadCloud className="size-4" />
          </div>
          <span className="text-[10px] font-semibold">Добавить</span>
        </button>
      </div>

      {/* ── Recent story posts from profile ── */}
      {storyPosts.length > 0 && (
        <div className="mt-5 border-t border-gray-100 pt-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
            Сейчас в профиле · {syncStateLabels.appKnown}
          </p>
          <p className="mb-2 text-[10px] leading-snug text-gray-400">
            {appKnownMediaSyncNote}
          </p>
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            {storyPosts.slice(0, 5).map((post) => (
              <div
                key={post.id}
                className="group/profile-story flex-shrink-0 w-32 aspect-video rounded-lg border border-gray-100 bg-gray-50 flex flex-col justify-end p-2 relative overflow-hidden"
              >
                <div className="absolute left-1 top-1 rounded bg-emerald-50 px-1.5 py-0.5 text-[8px] font-bold uppercase text-emerald-700 ring-1 ring-emerald-100">
                  {formatStoryStatus(post.status)}
                </div>
                {post.can_be_deleted ? (
                  <button
                    aria-label={`Удалить историю ${post.caption || post.telegram_story_id || ''}`}
                    className="absolute bottom-1 right-1 z-20 flex size-6 items-center justify-center rounded-md bg-white/90 text-gray-400 opacity-100 shadow-sm transition hover:bg-red-50 hover:text-red-500 focus:opacity-100 disabled:opacity-70 sm:opacity-0 sm:group-hover/profile-story:opacity-100"
                    disabled={deletingStoryPostId === post.id}
                    onClick={() => setPendingDeletePost(post)}
                    title="Удалить историю из Telegram"
                    type="button"
                  >
                    {deletingStoryPostId === post.id ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <Trash2 className="size-3" />
                    )}
                  </button>
                ) : null}
                <span className="relative z-10 w-[calc(100%-1.75rem)] truncate text-[10px] font-medium text-gray-600">
                  {post.caption || 'Без подписи'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {pendingDeletePost ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            aria-label="Отменить удаление истории"
            className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm backdrop-animate"
            onClick={closeDeleteModal}
            type="button"
          />
          <div className="modal-animate relative z-10 w-full max-w-sm overflow-hidden rounded-2xl bg-white shadow-xl">
            <div className="flex items-start gap-3 p-4">
              <div className="flex size-9 flex-shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-500">
                <AlertTriangle className="size-4" />
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-gray-900">Удалить историю?</h3>
                <p className="mt-1 text-xs leading-relaxed text-gray-500">
                  История исчезнет из Telegram и из блока «Сейчас в профиле».
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-gray-100 bg-gray-50 p-3">
              <button
                className="rounded-lg px-3 py-2 text-xs font-semibold text-gray-500 transition hover:bg-gray-100 hover:text-gray-700"
                onClick={closeDeleteModal}
                type="button"
              >
                Отмена
              </button>
              <button
                className="rounded-lg bg-red-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-red-600"
                onClick={confirmDelete}
                type="button"
              >
                Удалить
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* ── Edit modal ── */}
      {editingStory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm backdrop-animate"
            onClick={closeModal}
          />
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm overflow-hidden z-10 modal-animate">
            {/* Modal header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-100">
              <h3 className="font-bold text-sm text-gray-900">Настройка истории</h3>
              <button
                aria-label="Закрыть настройки истории"
                onClick={closeModal}
                className="p-1 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors"
                type="button"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* Modal body */}
            <div className="p-4 space-y-4">
              {/* Caption */}
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  Подпись
                </label>
                <Input
                  className="h-9 rounded-lg border-gray-200 bg-gray-50/50 hover:bg-white focus:bg-white px-3 text-sm transition-colors"
                  maxLength={1024}
                  onChange={(e) => onUpdateStory(editingStory.clientId, { caption: e.target.value })}
                  placeholder="Добавьте текст..."
                  value={editingStory.caption}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Privacy */}
                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                    Приватность
                  </label>
                  <select
                    className="w-full h-9 rounded-lg border border-gray-200 bg-gray-50/50 px-2 text-xs text-gray-700 outline-none transition-colors hover:bg-white focus:bg-white focus:border-navy-300 focus:ring-2 focus:ring-navy-100 appearance-none"
                    onChange={(e) =>
                      onUpdateStory(editingStory.clientId, {
                        privacyPreset: e.target.value as StoryDraftPayload['privacyPreset'],
                      })
                    }
                    value={editingStory.privacyPreset}
                    style={{
                      backgroundImage: `url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e")`,
                      backgroundRepeat: 'no-repeat',
                      backgroundPosition: 'right 0.5rem center',
                      backgroundSize: '1em',
                    }}
                  >
                    <option value="contacts">Контакты</option>
                    <option value="close_friends">Близкие</option>
                    <option value="public">Публично</option>
                  </select>
                </div>

                {/* Duration (read-only) */}
                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                    Срок
                  </label>
                  <div className="w-full h-9 rounded-lg border border-gray-200 bg-gray-100 px-3 flex items-center text-xs text-gray-500 font-medium">
                    24 часа
                  </div>
                </div>
              </div>

              {/* Protect content */}
              <div>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <div className="relative flex items-center justify-center">
                    <input
                      type="checkbox"
                      className="peer sr-only"
                      checked={editingStory.protectContent}
                      onChange={(e) =>
                        onUpdateStory(editingStory.clientId, { protectContent: e.target.checked })
                      }
                    />
                    <div className="w-4 h-4 rounded border border-gray-300 bg-white peer-checked:bg-navy-400 peer-checked:border-navy-400 transition-colors" />
                    <svg
                      className="absolute w-3 h-3 text-white opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={3}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span className="text-[12px] font-medium text-gray-700 group-hover:text-gray-900 transition-colors">
                    Запретить пересылку и сохранение
                  </span>
                </label>
              </div>
            </div>

            {/* Modal footer */}
            <div className="p-4 border-t border-gray-100 bg-gray-50 flex justify-end">
              <Button
                onClick={closeModal}
                className="h-8 rounded-lg bg-navy-400 hover:bg-navy-500 text-white text-xs px-4"
                type="button"
              >
                Готово
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function formatStoryStatus(status: string): string {
  if (status === 'active') return 'Активна'
  if (status === 'posted') return 'Опубликована'
  if (status === 'expired') return 'Истекла'
  return status
}

function capabilityStatusClass(tone: ReturnType<typeof buildStoryCapabilityStatus>['tone']): string {
  if (tone === 'blocked') return 'text-honey-700'
  if (tone === 'warning') return 'text-honey-600'
  return 'text-gray-400'
}

function capabilityBoxClass(tone: ReturnType<typeof buildStoryCapabilityStatus>['tone']): string {
  if (tone === 'blocked') return 'border-honey-100 bg-honey-50 text-honey-800'
  if (tone === 'warning') return 'border-honey-100 bg-honey-50/50 text-honey-700'
  return 'border-emerald-100 bg-emerald-50 text-emerald-800'
}
