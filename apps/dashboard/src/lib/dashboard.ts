import type { StoryCapabilities } from '@/lib/api'
import type { ApiError } from '@/lib/http'
import { labelIssue, labelStoryCapabilityWarning } from '@/lib/uiLabels'

export { buildJobMetrics } from '@/modules/shared'
export {
  appKnownMediaSyncNote,
  areDashboardFormStatesEqual,
  buildChangeItems,
  buildDashboardFormState,
  clearProfilePhotoDraft,
  clearStoredDashboardFormDraft,
  composeDisplayName,
  formatChangeOperationLabel,
  groupRealExecutionChanges,
  isSupportedProfileAudioFile,
  persistStoredDashboardFormDraft,
  readStoredDashboardFormDraft,
  reconcileStoredDashboardFormDraft,
  resolveDashboardIdentity,
  resolvePhotoPreview,
  resolveProfilePhotoPreviewUrl,
  shouldConfirmRealTelegramExecution,
  splitDisplayName,
  syncStateLabels,
} from '@/modules/account-editing'
export type {
  ChangeItem,
  CurrentProfile,
  DashboardDiagnostics,
  FormState,
  PhotoPreviewState,
  RealExecutionChangeGroups,
} from '@/modules/account-editing'
export type { ApiError }

export type RuntimeBanner = {
  title: string
  description: string
  accent: 'error' | 'warning'
}

export type StoryCapabilityStatus = {
  tone: 'ready' | 'warning' | 'blocked'
  title: string
  description: string
  items: string[]
}

type JobActivityLike = {
  job_state: string
  finished_at?: string | null
  message?: string | null
}

export function buildStoryCapabilityStatus(
  capabilities: StoryCapabilities | null,
): StoryCapabilityStatus {
  if (!capabilities) {
    return {
      tone: 'warning',
      title: 'Истории доступны как модуль StylistTG',
      description: 'Проверяем возможность публикации историй для этого аккаунта.',
      items: [],
    }
  }

  const items = capabilities.warnings.map(labelStoryCapabilityWarning)
  if (!capabilities.stories_enabled) {
    return {
      tone: 'blocked',
      title: 'Публикация историй сейчас недоступна',
      description: 'Истории выключены в настройках приложения.',
      items,
    }
  }

  const requiresTdlib = capabilities.warnings.includes(
    'stories live TDLib publishing requires TDLib profile execution',
  )
  if (requiresTdlib) {
    return {
      tone: 'blocked',
      title: 'Публикация историй сейчас недоступна',
      description: 'Проект работает в mock-режиме, поэтому live-публикация в Telegram не запускается.',
      items,
    }
  }

  if (!capabilities.tdlib_live_publishing_enabled) {
    return {
      tone: 'blocked',
      title: 'Публикация историй сейчас недоступна',
      description: 'Live-публикация через TDLib выключена.',
      items,
    }
  }

  if (items.length > 0) {
    return {
      tone: 'warning',
      title: 'Истории можно подготовить',
      description: 'Проверьте ограничения перед запуском задачи.',
      items,
    }
  }

  return {
    tone: 'ready',
    title: 'Истории готовы к публикации',
    description: 'Истории будут опубликованы вместе с задачей обновления профиля.',
    items: [],
  }
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
