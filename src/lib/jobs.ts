import type { JobDetail, JobStep, ProfilePreview } from '@/lib/api'
import { labelIssue, labelJobState, labelStep, labelStepStatus } from '@/lib/uiLabels'

type JobStepPlan = {
  steps: Array<{ step_key: string }>
}

export type JobStepItem = {
  key: string
  title: string
  status: string
  statusLabel: string
  detail: string
  tone: 'neutral' | 'active' | 'success' | 'warning' | 'error'
}

export type JobDisplayItem = JobStepItem & {
  kind: 'step' | 'story'
  children?: Array<JobStepItem & { shortTitle: string }>
}

export type JobResultSummary = {
  tone: 'neutral' | 'active' | 'success' | 'warning' | 'error'
  title: string
  description: string
  detail: string | null
}

export type JobProgressSummary = {
  total: number
  completed: number
  failed: number
  active: number
  notStarted: number
  progressValue: number
  label: string
}

export function shouldResetDraftAfterJobState(jobState: string | null | undefined): boolean {
  return jobState === 'completed'
}

export function buildJobStepItems(
  steps: JobStep[],
  preview: JobStepPlan | ProfilePreview | null,
  jobState?: string | null,
): JobStepItem[] {
  const stepsByKey = new Map(steps.map((step) => [step.step_key, step]))
  const plannedKeys = preview?.steps.map((step) => step.step_key) ?? steps.map((step) => step.step_key)
  const keys = Array.from(new Set([...plannedKeys, ...steps.map((step) => step.step_key)]))
  const stopped = Boolean(jobState && ['failed', 'partially_completed', 'manual_intervention_needed', 'canceled'].includes(jobState))

  return keys.map((key) => {
    const step = stepsByKey.get(key)
    if (!step) {
      const status = stopped ? 'not_started' : 'planned'
      return {
        key,
        title: labelStep(key),
        status,
        statusLabel: labelStepStatus(status),
        detail: stopped ? 'Остановлено из-за ошибки выше' : 'Ожидает запуска',
        tone: 'neutral',
      }
    }

    const status = normalizeTerminalStepStatus(step.status, stopped)
    return {
      key,
      title: labelStep(step.step_key ?? step.step_type),
      status,
      statusLabel: jobStepStatusLabel(status),
      detail: jobStepDetail(step, status),
      tone: jobStepTone(status),
    }
  })
}

export function buildJobProgressSummary(items: readonly JobStepItem[]): JobProgressSummary {
  const total = items.length
  const completed = items.filter((item) => item.status === 'succeeded').length
  const failed = items.filter((item) => item.status === 'failed').length
  const active = items.filter((item) => item.status === 'started').length
  const notStarted = items.filter((item) => item.status === 'not_started' || item.status === 'planned').length
  const progressValue = total > 0 ? Math.round((completed / total) * 100) : 0

  return {
    total,
    completed,
    failed,
    active,
    notStarted,
    progressValue,
    label: total > 0 ? `Применено ${completed} из ${total}` : 'Нет шагов',
  }
}

export function buildJobDisplayItems(items: readonly JobStepItem[]): JobDisplayItem[] {
  const result: JobDisplayItem[] = []
  const storyGroups = new Map<string, Array<JobStepItem & { shortTitle: string }>>()

  for (const item of items) {
    const story = parseStoryStep(item)
    if (!story) {
      result.push({ ...item, kind: 'step' })
      continue
    }

    const group = storyGroups.get(story.groupKey) ?? []
    group.push({ ...item, shortTitle: story.shortTitle })
    storyGroups.set(story.groupKey, group)

    if (!result.some((existing) => existing.key === story.groupKey)) {
      result.push({
        ...item,
        key: story.groupKey,
        title: `История ${story.storyNumber}`,
        kind: 'story',
        children: group,
      })
    }
  }

  return result.map((item) => {
    if (item.kind !== 'story') return item
    const children = storyGroups.get(item.key) ?? []
    const worst = pickMostImportantStoryStep(children)
    return {
      ...item,
      status: worst.status,
      statusLabel: worst.statusLabel,
      detail: worst.detail,
      tone: worst.tone,
      children,
    }
  })
}

export function buildJobResultSummary(job: JobDetail | null, steps: JobStep[]): JobResultSummary {
  if (!job) {
    return {
      tone: 'neutral',
      title: 'Задача ещё не создана',
      description: 'Проверьте план и создайте задачу, когда всё готово.',
      detail: null,
    }
  }

  const problemStep = steps.find((step) => step.error_code || step.uncertain_reason)
  const interruptedStep = isTerminalJobState(job.job_state) ? steps.find((step) => step.status === 'started') : null
  const detail = interruptedStep
    ? 'Выполнение оборвалось'
    : labelIssue(problemStep ? jobStepIssueKey(problemStep) : job.failure_reason)

  switch (job.job_state) {
    case 'queued':
      return {
        tone: 'active',
        title: 'Задача в очереди',
        description: 'Ожидаем запуска worker.',
        detail: null,
      }
    case 'waiting_lock':
    case 'running':
      return {
        tone: 'active',
        title: 'Задача выполняется',
        description: 'Следим за шагами выполнения.',
        detail: null,
      }
    case 'completed':
      return {
        tone: 'success',
        title: 'Всё применено',
        description: 'Профиль обновлён без ошибок.',
        detail: null,
      }
    case 'partially_completed':
      return {
        tone: 'warning',
        title: 'Часть изменений требует проверки',
        description: 'Проверьте Telegram и проблемные шаги.',
        detail: detail === 'Проблема не указан' ? null : detail,
      }
    case 'manual_intervention_needed':
      return {
        tone: 'error',
        title: 'Нужна ручная проверка',
        description: 'Автоматическое выполнение остановлено для безопасности аккаунта.',
        detail: detail === 'Проблема не указан' ? null : detail,
      }
    case 'dedup_blocked':
      return {
        tone: 'warning',
        title: 'Такая задача уже есть',
        description: 'Повторный запуск с тем же набором изменений не нужен.',
        detail: job.failure_reason ? labelIssue(job.failure_reason) : null,
      }
    case 'failed':
      return {
        tone: 'error',
        title: 'Ошибка выполнения',
        description: 'Проверьте проблемный шаг перед повторным запуском.',
        detail: detail === 'Проблема не указан' ? null : detail,
      }
    default:
      return {
        tone: 'neutral',
        title: labelJobState(job.job_state),
        description: 'Статус задачи обновляется.',
        detail: detail === 'Проблема не указан' ? null : detail,
      }
  }
}

function jobStepStatusLabel(status: string): string {
  return labelStepStatus(status)
}

function jobStepDetail(step: JobStep, displayStatus = step.status): string {
  const issueKey = jobStepIssueKey(step)
  if (issueKey) {
    return labelIssue(issueKey)
  }
  if (step.status === 'started' && displayStatus === 'uncertain') {
    return 'Выполнение оборвалось'
  }
  if (step.status === 'succeeded') {
    return 'Применено'
  }
  if (step.status === 'started') {
    return 'Выполняется'
  }
  if (step.status === 'skipped') {
    return 'Шаг не запускался'
  }
  return 'Нет деталей'
}

function jobStepIssueKey(step: JobStep): string | null {
  const payloadMessage =
    typeof step.result_payload_json?.message === 'string' ? step.result_payload_json.message : null
  if (payloadMessage?.includes('Unknown class "uploadFile"')) {
    return 'TDLIB_UNSUPPORTED_UPLOAD_FILE_METHOD'
  }
  if (step.error_code === 'tdlib_error' && payloadMessage) {
    return payloadMessage
  }
  return step.error_code ?? step.uncertain_reason
}

function normalizeTerminalStepStatus(status: string, stopped: boolean): string {
  if (stopped && status === 'started') {
    return 'uncertain'
  }
  return status
}

function isTerminalJobState(jobState: string | null | undefined): boolean {
  return Boolean(
    jobState && ['failed', 'partially_completed', 'manual_intervention_needed', 'canceled'].includes(jobState),
  )
}

function jobStepTone(status: string): JobStepItem['tone'] {
  switch (status) {
    case 'started':
      return 'active'
    case 'succeeded':
      return 'success'
    case 'failed':
      return 'error'
    case 'uncertain':
      return 'warning'
    default:
      return 'neutral'
  }
}

function parseStoryStep(item: JobStepItem): { groupKey: string; storyNumber: string; shortTitle: string } | null {
  const match = /^story_(\d+)_(validate_capabilities|prepare_media|post)$/.exec(item.key)
  if (!match) return null

  const shortTitle =
    match[2] === 'validate_capabilities'
      ? 'Проверка'
      : match[2] === 'prepare_media'
        ? 'Подготовка'
        : 'Публикация'

  return {
    groupKey: `story_${match[1]}`,
    storyNumber: match[1],
    shortTitle,
  }
}

function pickMostImportantStoryStep(items: Array<JobStepItem & { shortTitle: string }>): JobStepItem {
  return (
    items.find((item) => item.tone === 'error') ??
    items.find((item) => item.tone === 'warning') ??
    items.find((item) => item.tone === 'active') ??
    items.find((item) => item.status === 'not_started') ??
    items.find((item) => item.status === 'planned') ??
    items[items.length - 1]
  )
}
