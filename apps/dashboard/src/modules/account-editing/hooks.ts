/**
 * useProfileDraft – manages the editable form state for the profile editor.
 *
 * Covers photo / audio / story uploads, form dirty-tracking, preview fetching,
 * and job creation.  Extracted from App.tsx.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  buildAssetContentUrl,
  createAccountUpdateJob,
  createStoryDraft,
  deleteStoryDraft,
  previewAccountUpdateJob,
  updateStoryDraft,
  uploadProfileAudio,
  uploadProfilePhoto,
  uploadStoryImage,
  uploadStoryVideo,
  type FormPayload,
  type JobSummary,
  type ProfilePreview,
} from './api'
import { normalizeError } from '@/lib/appErrors'
import {
  areDashboardFormStatesEqual,
  buildChangeItems,
  buildDashboardFormState,
  clearProfilePhotoDraft,
  clearStoredDashboardFormDraft,
  isSupportedProfileAudioFile,
  persistStoredDashboardFormDraft,
  resolvePhotoPreview,
  resolveProfilePhotoPreviewUrl,
} from './mappers'
import { buildJobMetrics } from '@/modules/shared'
import { labelIssue } from '@/lib/uiLabels'
import type { ToastItem } from '@/components/ui/toast'
import type { CurrentProfile, FormState } from './types'
import { invalidateAccountSafetyQueries } from '@/lib/queries'

type Dashboard = {
  current_profile: CurrentProfile
  profile_audio?: { source_asset_id: string | null } | null
  story_posts?: unknown[]
}

export function useCreateAccountUpdateJobMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ accountId, form }: { accountId: string; form: FormPayload }) =>
      createAccountUpdateJob(accountId, form),
    onSuccess: (_result, variables) => {
      invalidateAccountSafetyQueries(queryClient, variables.accountId)
    },
  })
}

export function useProfileDraft({
  accountId,
  dashboard,
  initialForm,
  initialDashboard,
  notify,
}: {
  accountId: string | null
  dashboard: Dashboard | null
  initialForm: FormState
  initialDashboard: Dashboard | null
  notify: (toast: Omit<ToastItem, 'id'>) => void
}) {
  const createAccountUpdateJobMutation = useCreateAccountUpdateJobMutation()

  // ── Form state ──────────────────────────────────────────────────────────────
  const formInitializedRef = useRef(Boolean(initialDashboard))
  const formBaselineRef = useRef<FormState | null>(
    initialDashboard ? buildDashboardFormState(initialDashboard as Parameters<typeof buildDashboardFormState>[0]) : null,
  )
  const formRef = useRef<FormState>(initialForm)

  const [form, setFormState] = useState<FormState>(initialForm)
  const [isFormInitialized, setIsFormInitialized] = useState(Boolean(initialDashboard))

  // ── Upload state ────────────────────────────────────────────────────────────
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false)
  const [isUploadingAudio, setIsUploadingAudio] = useState(false)
  const [isUploadingStory, setIsUploadingStory] = useState(false)
  const [selectedPhotoName, setSelectedPhotoName] = useState<string | null>(null)
  const [selectedAudioName, setSelectedAudioName] = useState<string | null>(null)
  const [selectedPhotoPreviewUrl, setSelectedPhotoPreviewUrl] = useState<string | null>(null)

  // ── Job / preview state ─────────────────────────────────────────────────────
  const [preview, setPreview] = useState<ProfilePreview | null>(null)
  const [isSubmittingJob, setIsSubmittingJob] = useState(false)
  const [isRefreshingRuntime, setIsRefreshingRuntime] = useState(false)
  const previewAbortRef = useRef<AbortController | null>(null)
  const previewRequestSeqRef = useRef(0)

  // ── Derived values ───────────────────────────────────────────────────────────
  const currentProfile: CurrentProfile = useMemo(
    () => ({
      first_name: dashboard?.current_profile.first_name ?? null,
      last_name: dashboard?.current_profile.last_name ?? null,
      bio: dashboard?.current_profile.bio ?? null,
      username: dashboard?.current_profile.username ?? null,
      profile_photo_asset_id: dashboard?.current_profile.profile_photo_asset_id ?? null,
      profile_audio_asset_id: dashboard?.profile_audio?.source_asset_id ?? null,
      pinned_channel_ref: dashboard?.current_profile.pinned_channel_ref ?? null,
    }),
    [dashboard],
  )

  const changeItems = useMemo(() => buildChangeItems(currentProfile, form), [currentProfile, form])
  const changedItems = useMemo(() => changeItems.filter((item) => item.changed), [changeItems])
  const photoPreview = useMemo(
    () =>
      resolvePhotoPreview(
        resolveProfilePhotoPreviewUrl(selectedPhotoPreviewUrl, form.profilePhotoAssetId, buildAssetContentUrl),
      ),
    [form.profilePhotoAssetId, selectedPhotoPreviewUrl],
  )

  // ── Form helpers ─────────────────────────────────────────────────────────────

  /** Stable updater that also persists draft and updates the ref. */
  const updateForm = useCallback(
    (next: FormState | ((prev: FormState) => FormState)) => {
      setFormState((prev) => {
        const nextForm = typeof next === 'function' ? next(prev) : next
        formRef.current = nextForm

        if (accountId && formBaselineRef.current) {
          if (areDashboardFormStatesEqual(nextForm, formBaselineRef.current)) {
            clearStoredDashboardFormDraft(window.localStorage, accountId)
          } else {
            persistStoredDashboardFormDraft(window.localStorage, accountId, nextForm)
          }
        }
        return nextForm
      })
    },
    [accountId],
  )

  const clearSelectedPhotoPreview = useCallback(() => {
    setSelectedPhotoPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
  }, [])

  const setForm = useCallback((next: FormState) => {
    formRef.current = next
    setFormState(next)
    setIsFormInitialized(true)
    formInitializedRef.current = true
  }, [])

  // ── Photo ────────────────────────────────────────────────────────────────────

  async function handlePhotoUpload(file: File | null) {
    if (!file) return
    const previewUrl = URL.createObjectURL(file)
    setSelectedPhotoPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return previewUrl
    })
    setIsUploadingPhoto(true)
    try {
      const asset = await uploadProfilePhoto(file)
      updateForm((prev) => ({ ...prev, profilePhotoAssetId: asset.id }))
      setSelectedPhotoName(file.name)
      notify({ tone: 'success', title: 'Фото добавлено', description: 'Создайте задачу, чтобы применить его в Telegram.' })
    } catch (error) {
      const normalized = normalizeError(error)
      notify({ tone: 'error', title: 'Не удалось загрузить фото', description: labelIssue(normalized.error_code) })
    } finally {
      setIsUploadingPhoto(false)
    }
  }

  function handleClearProfilePhoto() {
    clearSelectedPhotoPreview()
    updateForm((prev) => clearProfilePhotoDraft(prev))
    setSelectedPhotoName(null)
    notify({ tone: 'info', title: 'Фото убрано из черновика' })
  }

  // ── Audio ────────────────────────────────────────────────────────────────────

  async function handleAudioUpload(file: File | null) {
    if (!file) return
    if (!isSupportedProfileAudioFile(file)) {
      notify({ tone: 'error', title: 'Формат музыки не поддерживается', description: labelIssue('PROFILE_AUDIO_UNSUPPORTED_FORMAT') })
      return
    }
    setIsUploadingAudio(true)
    try {
      const asset = await uploadProfileAudio(file)
      updateForm((prev) => ({
        ...prev,
        profileAudioAction: 'add',
        profileAudioAssetId: asset.id,
      }))
      setSelectedAudioName(file.name)
      notify({ tone: 'success', title: 'Музыка добавлена', description: 'Создайте задачу, чтобы применить её в профиль.' })
    } catch (error) {
      const normalized = normalizeError(error)
      notify({ tone: 'error', title: 'Не удалось загрузить музыку', description: labelIssue(normalized.error_code) })
    } finally {
      setIsUploadingAudio(false)
    }
  }

  function handleKeepProfileAudio() {
    updateForm((prev) => ({
      ...prev,
      profileAudioAction: 'keep',
      profileAudioAssetId: dashboard?.profile_audio?.source_asset_id ?? null,
    }))
    setSelectedAudioName(null)
    notify({ tone: 'info', title: 'Музыка оставлена без изменений' })
  }

  function handleRemoveProfileAudio() {
    updateForm((prev) => ({
      ...prev,
      profileAudioAction: 'remove',
      profileAudioAssetId: null,
    }))
    setSelectedAudioName(null)
    notify({ tone: 'info', title: 'Музыка будет удалена после запуска задачи' })
  }

  // ── Stories ──────────────────────────────────────────────────────────────────

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
    const previousStory = formRef.current.stories.find((s) => s.clientId === clientId)
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
    const removedStory = formRef.current.stories.find((s) => s.clientId === clientId)
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
            stories: prev.stories.some((s) => s.clientId === clientId)
              ? prev.stories
              : [...prev.stories, removedStory],
          }))
        }
        notify({ tone: 'error', title: 'История восстановлена', description: labelIssue(normalized.error_code) })
      })
    }
  }

  // ── Preview ──────────────────────────────────────────────────────────────────

  const loadPreview = useCallback(
    async (acctId: string, draft: FormState) => {
      previewAbortRef.current?.abort()
      const controller = new AbortController()
      previewAbortRef.current = controller
      const seq = ++previewRequestSeqRef.current
      try {
        const payload = await previewAccountUpdateJob(acctId, toFormPayload(draft), {
          signal: controller.signal,
        })
        if (controller.signal.aborted || seq !== previewRequestSeqRef.current) return
        setPreview(payload)
      } catch {
        if (controller.signal.aborted || seq !== previewRequestSeqRef.current) return
        setPreview(null)
      } finally {
        if (previewAbortRef.current === controller) previewAbortRef.current = null
      }
    },
    [],
  )

  // Re-run preview whenever relevant form fields change
  const storyPreviewKey = useMemo(
    () =>
      JSON.stringify(
        form.stories.map((story) => ({
          draftId: story.draftId,
          assetId: story.assetId,
          action: story.action,
          caption: story.caption,
          privacyPreset: story.privacyPreset,
          activePeriodSeconds: story.activePeriodSeconds,
          protectContent: story.protectContent,
        })),
      ),
    [form.stories],
  )

  useEffect(() => {
    if (!accountId) return
    if (formBaselineRef.current && areDashboardFormStatesEqual(form, formBaselineRef.current)) {
      previewAbortRef.current?.abort()
      previewRequestSeqRef.current += 1
      setPreview(null)
      return
    }
    const id = window.setTimeout(() => void loadPreview(accountId, form), 250)
    return () => window.clearTimeout(id)
  }, [
    accountId,
    form.firstName,
    form.lastName,
    form.bio,
    form.username,
    form.profilePhotoAssetId,
    form.profileAudioAction,
    form.profileAudioAssetId,
    storyPreviewKey,
    form,
    loadPreview,
  ])

  // ── Job submission ────────────────────────────────────────────────────────────

  async function handleCreateJob(
    onJobCreated: (job: JobSummary) => void,
    onError: (err: ReturnType<typeof normalizeError>) => void,
  ) {
    if (!accountId) return
    setIsSubmittingJob(true)
    try {
      const job = await createAccountUpdateJobMutation.mutateAsync({ accountId, form: toFormPayload(form) })
      onJobCreated(job)
    } catch (error) {
      const normalized = normalizeError(error)
      onError(normalized)
      notify({ tone: 'error', title: 'Не удалось создать задачу', description: labelIssue(normalized.error_code) })
    } finally {
      setIsSubmittingJob(false)
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────────

  function handleReset() {
    const serverForm =
      formBaselineRef.current ??
      (dashboard ? buildDashboardFormState(dashboard as Parameters<typeof buildDashboardFormState>[0]) : null)
    if (!serverForm) return
    formBaselineRef.current = serverForm
    formInitializedRef.current = true
    setIsFormInitialized(true)
    formRef.current = serverForm
    setFormState(serverForm)
    setSelectedAudioName(null)
    if (accountId) clearStoredDashboardFormDraft(window.localStorage, accountId)
    clearSelectedPhotoPreview()
    setSelectedPhotoName(null)
    notify({ tone: 'info', title: 'Черновик сброшен' })
  }

  // ── Cleanup ───────────────────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (selectedPhotoPreviewUrl) URL.revokeObjectURL(selectedPhotoPreviewUrl)
    }
  }, [selectedPhotoPreviewUrl])

  return {
    // State
    form,
    preview,
    isFormInitialized,
    isSubmittingJob,
    isRefreshingRuntime,
    setIsRefreshingRuntime,
    isUploadingPhoto,
    isUploadingAudio,
    isUploadingStory,
    selectedPhotoName,
    selectedAudioName,
    selectedPhotoPreviewUrl,
    photoPreview,
    currentProfile,
    changeItems,
    changedItems,
    // Setters (used during boot reconciliation)
    setForm,
    formRef,
    formBaselineRef,
    formInitializedRef,
    updateForm,
    clearSelectedPhotoPreview,
    // Handlers
    handlePhotoUpload,
    handleClearProfilePhoto,
    handleAudioUpload,
    handleKeepProfileAudio,
    handleRemoveProfileAudio,
    handleStoryUpload,
    handleUpdateStory,
    handleRemoveStory,
    handleCreateJob,
    handleReset,
    loadPreview,
    buildJobMetrics,
  }
}

function toFormPayload(form: FormState): FormPayload {
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
