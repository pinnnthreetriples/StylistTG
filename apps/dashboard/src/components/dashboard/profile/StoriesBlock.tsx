/**
 * StoriesBlock – stories grid with add / remove / edit modal.
 */

import { AlertTriangle, ImagePlus, Loader2, Trash2, UploadCloud, User, Video, X, Link } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { type StoryCapabilities, type StoryDraftPayload, type StoryPost } from '@/lib/api'
import { appKnownMediaSyncNote, buildStoryCapabilityStatus, syncStateLabels } from '@/lib/dashboard'

// Inline chevron-down used as the privacy-preset <select> background icon.
const SELECT_CHEVRON_BG_IMAGE =
  `url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e")`

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
    <div className="bg-card rounded-xl border border-border p-4 mb-4">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ImagePlus className="text-primary size-4" />
            <h2 className="font-sans font-bold text-sm tracking-tight text-foreground">
              Истории ({stories.length})
            </h2>
            {isUploadingStory && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
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
        <div className="mb-3 rounded-lg border border-dashed border-border bg-muted px-3 py-5 text-center">
          <p className="text-sm font-semibold text-foreground">Историй пока нет</p>
          <p className="mt-1 text-xs text-muted-foreground">Добавьте фото или видео, чтобы подготовить историю.</p>
        </div>
      ) : null}

      {/* ── Grid ── */}
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
        {stories.map((story) => (
          <div
            key={story.clientId}
            aria-label={`Настроить историю ${story.fileName}`}
            className="group relative aspect-[9/16] rounded-lg border border-border bg-muted overflow-hidden cursor-pointer hover:ring-2 hover:ring-ring hover:ring-offset-1 transition-all"
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
            <div className="absolute inset-0 flex flex-col items-center justify-center p-2 text-center text-muted-foreground bg-muted">
              {story.action === 'post_image' ? (
                <ImagePlus className="size-6 mb-1 opacity-50" />
              ) : (
                <Video className="size-6 mb-1 opacity-50" />
              )}
              <span className="text-[9px] font-medium truncate w-full">{story.fileName}</span>
            </div>

            {/* Privacy badge */}
            <div className="absolute top-1.5 left-1.5 flex gap-1">
              <div className="w-5 h-5 rounded-md bg-foreground/60 backdrop-blur-sm flex items-center justify-center text-primary-foreground">
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
              className="absolute top-1.5 right-1.5 w-6 h-6 rounded-md bg-foreground/60 backdrop-blur-sm flex items-center justify-center text-primary-foreground opacity-0 group-hover:opacity-100 hover:bg-destructive transition-all"
              type="button"
            >
              <Trash2 className="size-3" />
            </button>

            {/* Caption overlay */}
            {story.caption && (
              <div className="absolute bottom-0 inset-x-0 bg-muted p-2 pt-4">
                <p className="text-[9px] text-primary-foreground line-clamp-2 leading-tight">{story.caption}</p>
              </div>
            )}
          </div>
        ))}

        {/* Add placeholder */}
        <button
          aria-label="Добавить историю"
          onClick={onChooseStoryImage}
          className="aspect-[9/16] rounded-lg border-2 border-dashed border-border bg-muted flex flex-col items-center justify-center cursor-pointer hover:border-border hover:bg-muted transition-all text-muted-foreground hover:text-primary"
          type="button"
        >
          <div className="w-8 h-8 rounded-full bg-card shadow-sm flex items-center justify-center mb-2">
            <UploadCloud className="size-4" />
          </div>
          <span className="text-[10px] font-semibold">Добавить</span>
        </button>
      </div>

      {/* ── Recent story posts from profile ── */}
      {storyPosts.length > 0 && (
        <div className="mt-5 border-t border-border pt-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Сейчас в профиле · {syncStateLabels.appKnown}
          </p>
          <p className="mb-2 text-[10px] leading-snug text-muted-foreground">
            {appKnownMediaSyncNote}
          </p>
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            {storyPosts.slice(0, 5).map((post) => (
              <div
                key={post.id}
                className="group/profile-story flex-shrink-0 w-32 aspect-video rounded-lg border border-border bg-muted flex flex-col justify-end p-2 relative overflow-hidden"
              >
                <div className="absolute left-1 top-1 rounded bg-muted px-1.5 py-0.5 text-[8px] font-bold uppercase text-primary ring-1 ring-ring">
                  {formatStoryStatus(post.status)}
                </div>
                {post.can_be_deleted ? (
                  <button
                    aria-label={`Удалить историю ${post.caption || post.telegram_story_id || ''}`}
                    className="absolute bottom-1 right-1 z-20 flex size-6 items-center justify-center rounded-md bg-card/90 text-muted-foreground opacity-100 shadow-sm transition hover:bg-destructive/10 hover:text-destructive focus:opacity-100 disabled:opacity-70 sm:opacity-0 sm:group-hover/profile-story:opacity-100"
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
                <span className="relative z-10 w-[calc(100%-1.75rem)] truncate text-[10px] font-medium text-muted-foreground">
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
            className="absolute inset-0 bg-foreground backdrop-blur-sm"
            onClick={closeDeleteModal}
            type="button"
          />
          <div className="relative z-10 w-full max-w-sm overflow-hidden rounded-2xl bg-card shadow-xl">
            <div className="flex items-start gap-3 p-4">
              <div className="flex size-9 flex-shrink-0 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
                <AlertTriangle className="size-4" />
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-foreground">Удалить историю?</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  История исчезнет из Telegram и из блока «Сейчас в профиле».
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-border bg-muted p-3">
              <button
                className="rounded-lg px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground"
                onClick={closeDeleteModal}
                type="button"
              >
                Отмена
              </button>
              <button
                className="rounded-lg bg-destructive px-3 py-2 text-xs font-semibold text-primary-foreground transition hover:bg-destructive"
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
          <button
            aria-label="Закрыть настройки истории"
            className="absolute inset-0 bg-foreground backdrop-blur-sm"
            onClick={closeModal}
            type="button"
          />
          <div className="bg-card rounded-2xl shadow-xl w-full max-w-sm overflow-hidden z-10">
            {/* Modal header */}
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h3 className="font-bold text-sm text-foreground">Настройка истории</h3>
              <button
                aria-label="Закрыть настройки истории"
                onClick={closeModal}
                className="p-1 text-muted-foreground hover:bg-muted rounded-lg transition-colors"
                type="button"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* Modal body */}
            <div className="p-4 space-y-4">
              {/* Caption */}
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground" htmlFor="story-caption">
                  Подпись
                </label>
                <Input
                  id="story-caption"
                  aria-label="Подпись истории"
                  className="h-9 rounded-lg border-border bg-muted hover:bg-card focus:bg-card px-3 text-sm transition-colors"
                  maxLength={1024}
                  onChange={(e) => onUpdateStory(editingStory.clientId, { caption: e.target.value })}
                  placeholder="Добавьте текст..."
                  value={editingStory.caption}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Privacy */}
                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground" htmlFor="story-privacy">
                    Приватность
                  </label>
                  <select
                    id="story-privacy"
                    aria-label="Приватность истории"
                    className="w-full h-9 rounded-lg border border-border bg-muted px-2 text-xs text-foreground outline-none transition-colors hover:bg-card focus:bg-card focus:border-border focus:ring-2 focus:ring-ring appearance-none"
                    onChange={(e) =>
                      onUpdateStory(editingStory.clientId, {
                        privacyPreset: e.target.value as StoryDraftPayload['privacyPreset'],
                      })
                    }
                    value={editingStory.privacyPreset}
                    style={{
                      backgroundImage: SELECT_CHEVRON_BG_IMAGE,
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
                  <div className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Срок
                  </div>
                  <div className="w-full h-9 rounded-lg border border-border bg-muted px-3 flex items-center text-xs text-muted-foreground font-medium">
                    24 часа
                  </div>
                </div>
              </div>

              {/* Protect content */}
              <div>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <div className="relative flex items-center justify-center">
                    <input
                      aria-label="Защитить контент от пересылки"
                      type="checkbox"
                      className="peer sr-only"
                      checked={editingStory.protectContent}
                      onChange={(e) =>
                        onUpdateStory(editingStory.clientId, { protectContent: e.target.checked })
                      }
                    />
                    <div className="w-4 h-4 rounded border border-border bg-card peer-checked:bg-primary peer-checked:border-border transition-colors" />
                    <svg
                      className="absolute w-3 h-3 text-primary-foreground opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={3}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span className="text-[12px] font-medium text-foreground group-hover:text-foreground transition-colors">
                    Запретить пересылку и сохранение
                  </span>
                </label>
              </div>
            </div>

            {/* Modal footer */}
            <div className="p-4 border-t border-border bg-muted flex justify-end">
              <Button
                onClick={closeModal}
                className="h-8 rounded-lg bg-primary hover:bg-primary text-primary-foreground text-xs px-4"
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
  if (tone === 'blocked') return 'text-muted-foreground'
  if (tone === 'warning') return 'text-muted-foreground'
  return 'text-muted-foreground'
}

function capabilityBoxClass(tone: ReturnType<typeof buildStoryCapabilityStatus>['tone']): string {
  if (tone === 'blocked') return 'border-border bg-muted text-muted-foreground'
  if (tone === 'warning') return 'border-border bg-muted text-muted-foreground'
  return 'border-border bg-muted text-primary'
}
