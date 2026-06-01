// fallow-ignore-file complexity
import type { ToastItem } from '@/components/ui/toast'
import { normalizeError } from '@/lib/appErrors'
import { labelIssue } from '@/lib/uiLabels'

import {
  createStoryDraft,
  deleteStoryDraft,
  updateStoryDraft,
  uploadStoryImage,
  uploadStoryVideo,
} from './api'
import type { FormState } from './types'

export function createStoryDraftHandlers({
  accountId,
  form,
  notify,
  setIsUploadingStory,
  updateForm,
}: {
  accountId: string | null
  form: FormState
  notify: (toast: Omit<ToastItem, 'id'>) => void
  setIsUploadingStory: (value: boolean) => void
  updateForm: (next: FormState | ((prev: FormState) => FormState)) => void
}) {
  async function handleStoryUpload(file: File | null, kind: 'image' | 'video') {
    if (!file) return
    setIsUploadingStory(true)
    try {
      const asset = kind === 'image' ? await uploadStoryImage(file) : await uploadStoryVideo(file)
      const draft = accountId
        ? await createStoryDraft(
            accountId,
            { assetId: asset.id, caption: '', privacyPreset: 'contacts', activePeriodSeconds: 86400, protectContent: false },
            kind,
          )
        : null
      updateForm((prev) => ({
        ...prev,
        stories: [
          ...prev.stories,
          {
            draftId: draft?.id ?? null,
            clientId: draft?.id ?? crypto.randomUUID(),
            action: kind === 'image' ? 'post_image' : 'post_video',
            assetId: asset.id,
            fileName: file.name,
            caption: '',
            privacyPreset: 'contacts',
            activePeriodSeconds: 86400,
            protectContent: false,
          },
        ],
      }))
      notify({ tone: 'success', title: kind === 'image' ? 'Фото-история добавлена' : 'Видео-история добавлена' })
    } catch (error) {
      const normalized = normalizeError(error)
      notify({ tone: 'error', title: 'Не удалось добавить историю', description: labelIssue(normalized.error_code) })
    } finally {
      setIsUploadingStory(false)
    }
  }

  function handleUpdateStory(clientId: string, patch: Partial<FormState['stories'][number]>) {
    const previousStory = form.stories.find((s) => s.clientId === clientId)
    const draftId = previousStory?.draftId
    updateForm((prev) => ({
      ...prev,
      stories: prev.stories.map((s) => (s.clientId === clientId ? { ...s, ...patch } : s)),
    }))
    if (draftId) {
      void updateStoryDraft(draftId, patch).catch((error) => {
        const normalized = normalizeError(error)
        if (previousStory) {
          updateForm((prev) => ({
            ...prev,
            stories: prev.stories.map((s) => (s.clientId === clientId ? previousStory : s)),
          }))
        }
        notify({ tone: 'error', title: 'Изменение истории отменено', description: labelIssue(normalized.error_code) })
      })
    }
  }

  function handleRemoveStory(clientId: string) {
    const removedStory = form.stories.find((s) => s.clientId === clientId)
    const draftId = removedStory?.draftId
    updateForm((prev) => ({
      ...prev,
      stories: prev.stories.filter((s) => s.clientId !== clientId),
    }))
    notify({ tone: 'info', title: 'История удалена из черновика' })
    if (draftId) {
      void deleteStoryDraft(draftId).catch((error) => {
        const normalized = normalizeError(error)
        if (removedStory) {
          updateForm((prev) => ({
            ...prev,
            stories: prev.stories.some((s) => s.clientId === clientId) ? prev.stories : [...prev.stories, removedStory],
          }))
        }
        notify({ tone: 'error', title: 'История восстановлена', description: labelIssue(normalized.error_code) })
      })
    }
  }

  return { handleStoryUpload, handleUpdateStory, handleRemoveStory }
}
