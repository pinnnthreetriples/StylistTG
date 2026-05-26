import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Check,
  CheckCircle2,
  Circle,
  Cpu,
  FilePlus,
  Loader2,
  ListOrdered,
  Play,
  X,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'

import { type JobDetail, type JobSummary } from '@/lib/api'
import { buildJobMetrics } from '@/lib/dashboard'
import {
  type JobDisplayItem,
  type JobProgressSummary,
  type JobResultSummary,
  type JobStepDebugDetails,
  type JobStepItem,
  canExpandJobStepDebugDetails,
  shouldShowJobStepDebugDetails,
} from '@/lib/jobs'

const terminalJobStates = new Set([
  'completed',
  'partially_completed',
  'failed',
  'manual_intervention_needed',
  'canceled',
  'dedup_blocked',
])

function Metric({
  label,
  value,
  valueClass,
}: {
  label: string
  value: string
  valueClass: string
}) {
  return (
    <div className="text-center">
      <p className={`text-sm font-bold ${valueClass}`}>{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  )
}

export function JobSummaryCard({
  jobs,
  latestJobState,
}: {
  jobs: JobSummary[]
  latestJobState: string | null
}) {
  const metrics = buildJobMetrics(jobs)
  const latestConfig = jobVisualConfig(latestJobState ?? 'draft')

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-muted">
            <ListOrdered className="size-3.5 text-primary" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Задачи</h3>
            <p className="text-[10px] text-muted-foreground">Сводка запусков</p>
          </div>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${latestJobState ? latestConfig.statusClass : 'bg-muted text-muted-foreground'}`}>
          {latestJobState ? latestConfig.label : 'Нет задач'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 border-t border-border pt-3">
        <Metric label="Всего" value={metrics.total.toString()} valueClass="text-foreground" />
        <Metric label="Успех" value={metrics.success.toString()} valueClass="text-primary" />
        <Metric label="Проблем" value={metrics.issues.toString()} valueClass="text-destructive" />
      </div>
    </section>
  )
}

export function PipelineCard({ latestJobState }: { latestJobState: string | null }) {
  const activeStep = latestJobState === 'queued' ? 'Очередь' : latestJobState && !terminalJobStates.has(latestJobState) ? 'Запуск' : latestJobState ? 'Готово' : 'Черновик'
  const steps = [
    { label: 'Черновик', icon: FilePlus },
    { label: 'Очередь', icon: ListOrdered },
    { label: 'Запуск', icon: Play },
    { label: 'Готово', icon: Check },
  ]

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <Cpu className="size-3.5 text-muted-foreground" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Пайплайн
        </span>
      </div>
      <div className="grid grid-cols-4 gap-1.5">
        {steps.map((step) => {
          const StepIcon = step.icon
          const active = step.label === activeStep
          return (
            <div
              className={`flex min-w-0 flex-col items-center gap-1 rounded-lg px-1.5 py-2 text-[10px] font-semibold ${
                active ? 'bg-muted text-foreground' : 'bg-muted text-muted-foreground'
              }`}
              key={step.label}
            >
              <StepIcon className={`size-3 ${active ? 'text-primary' : 'text-muted-foreground'}`} />
              <span className="truncate">{step.label}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export function JobStepPanel({
  currentJob,
  items,
  onHide,
  progressSummary,
  resultSummary,
}: {
  currentJob: JobDetail | null
  items: JobDisplayItem[]
  onHide?: () => void
  progressSummary: JobProgressSummary
  resultSummary: JobResultSummary
}) {
  const [expanded, setExpanded] = useState(false)
  const [minimized, setMinimized] = useState(false)

  if (minimized) {
    return (
      <aside className="fixed bottom-16 right-3 z-50 sm:bottom-20 sm:right-6">
        <button
          aria-label="Показать план выполнения"
          className="flex size-11 items-center justify-center rounded-full border border-border bg-card/95 shadow-xl shadow-foreground/10 backdrop-blur transition hover:bg-muted"
          onClick={() => setMinimized(false)}
          type="button"
        >
          <span className={`absolute right-2 top-2 size-2 rounded-full ${jobMonitorDotClass(resultSummary.tone)}`} />
          <ChevronUp className="size-4 text-muted-foreground" />
        </button>
      </aside>
    )
  }

  return (
    <aside className="fixed bottom-16 left-3 right-3 z-50 sm:bottom-20 sm:left-auto sm:right-6 sm:w-[420px]">
      <section className="overflow-hidden rounded-xl border border-border bg-card/95 shadow-xl shadow-foreground/10 backdrop-blur">
        <div className="border-b border-border px-3 py-2.5">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className={`size-2 rounded-full ${jobMonitorDotClass(resultSummary.tone)}`} />
                <h3 className="text-xs font-semibold text-foreground">План и выполнение</h3>
              </div>
              <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                {currentJob ? `#${currentJob.job_id.slice(0, 8)} · ${jobVisualConfig(currentJob.job_state).label}` : 'Предпросмотр'}
              </p>
            </div>
            <div className="flex flex-shrink-0 items-center gap-1">
              <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${jobVisualConfig(currentJob?.job_state ?? 'draft').statusClass}`}>
                {currentJob ? jobVisualConfig(currentJob.job_state).label : progressSummary.label}
              </span>
              <button
                aria-label="Скрыть план выполнения"
                className="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                onClick={() => setMinimized(true)}
                type="button"
              >
                <ChevronDown className="size-3.5" />
              </button>
              {onHide ? (
                <button
                  aria-label="Убрать панель задачи"
                  className="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                  onClick={onHide}
                  type="button"
                >
                  <X className="size-3.5" />
                </button>
              ) : null}
            </div>
          </div>
          <JobProgressBlock progress={progressSummary} summary={resultSummary} />
          <button
            aria-expanded={expanded}
            className="mt-2 flex w-full items-center justify-between rounded-lg px-2 py-1 text-[10px] font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setExpanded((value) => !value)}
            type="button"
          >
            <span>{expanded ? 'Скрыть шаги' : 'Показать шаги'}</span>
            <ChevronDown className={`size-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </button>
        </div>

        <div className={`max-h-[42vh] overflow-y-auto px-2.5 py-2 ${expanded ? 'block' : 'hidden'}`}>
          {items.length === 0 ? (
            <div className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
              Измените профиль, чтобы увидеть план.
            </div>
          ) : (
            <ol className="space-y-1" role="list">
              {items.map((item) => (
                <JobMonitorRow currentJobId={currentJob?.job_id ?? null} item={item} key={item.key} />
              ))}
            </ol>
          )}
        </div>
      </section>
    </aside>
  )
}

function JobMonitorRow({ currentJobId, item }: { currentJobId: string | null; item: JobDisplayItem }) {
  const [debugOpen, setDebugOpen] = useState(false)
  const debugDetails = item.debugDetails
  const canExpandDebug = canExpandJobStepDebugDetails(item)

  return (
    <li className={`rounded-lg px-2 py-1.5 ${item.tone === 'error' ? 'bg-destructive/10' : item.tone === 'active' ? 'bg-muted' : ''}`}>
      <div className="flex items-center gap-2">
        <span className={`flex size-5 flex-shrink-0 items-center justify-center rounded-full ${jobCompactIconClass(item.tone)}`}>
          <JobStepIcon item={item} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center justify-between gap-2">
            <span className="truncate text-[11px] font-semibold text-foreground">{item.title}</span>
            <span className={`flex-shrink-0 text-[10px] font-semibold ${jobCompactStatusClass(item.tone)}`}>
              {item.statusLabel}
            </span>
          </div>
          {item.kind === 'story' && item.children ? <StoryMiniPipeline steps={item.children} /> : null}
          {item.tone === 'error' || item.tone === 'warning' || item.status === 'not_started' ? (
            <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">{item.detail}</p>
          ) : null}
          {canExpandDebug && debugDetails ? (
            <div className="mt-1">
              <button
                aria-expanded={debugOpen}
                className="rounded-md px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground transition hover:bg-card/70 hover:text-foreground"
                onClick={() => setDebugOpen((value) => !value)}
                type="button"
              >
                {debugOpen ? 'Скрыть технические детали' : 'Технические детали'}
              </button>
              {shouldShowJobStepDebugDetails(item, debugOpen) ? (
                <JobStepDebugDetailsBlock currentJobId={currentJobId} details={debugDetails} />
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  )
}

function JobStepDebugDetailsBlock({
  currentJobId,
  details,
}: {
  currentJobId: string | null
  details: JobStepDebugDetails
}) {
  return (
    <div className="mt-1 max-w-full overflow-hidden rounded-lg border border-border bg-card/80 p-2">
      <dl className="grid grid-cols-[88px_minmax(0,1fr)] gap-x-2 gap-y-1 text-[10px]">
        {currentJobId ? (
          <>
            <dt className="font-semibold text-muted-foreground">Job ID</dt>
            <dd className="min-w-0 break-all font-mono text-muted-foreground">{currentJobId}</dd>
          </>
        ) : null}
        {details.rows.map((row) => (
          <span className="contents" key={`${row.label}:${row.value}`}>
            <dt className="font-semibold text-muted-foreground">{row.label}</dt>
            <dd className="min-w-0 break-words font-mono text-muted-foreground">{row.value}</dd>
          </span>
        ))}
      </dl>
      {details.rawJson ? (
        <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-2 text-[10px] leading-relaxed text-muted-foreground">
          {details.rawJson}
        </pre>
      ) : null}
    </div>
  )
}

function StoryMiniPipeline({ steps }: { steps: NonNullable<JobDisplayItem['children']> }) {
  return (
    <div className="mt-1 flex items-center gap-1.5">
      {steps.map((step, index) => (
        <div className="flex min-w-0 items-center gap-1" key={step.key}>
          <span className={`size-1.5 rounded-full ${jobMiniDotClass(step.tone)}`} title={`${step.shortTitle}: ${step.statusLabel}`} />
          <span className="truncate text-[9px] text-muted-foreground">{step.shortTitle}</span>
          {index < steps.length - 1 ? <span className="text-[9px] text-muted-foreground">→</span> : null}
        </div>
      ))}
    </div>
  )
}

function JobProgressBlock({
  progress,
  summary,
}: {
  progress: JobProgressSummary
  summary: JobResultSummary
}) {
  return (
    <div className="mt-2" role="status" aria-live="polite">
      <div className="flex justify-end">
        <span className="text-[10px] font-semibold text-muted-foreground">{progress.label}</span>
      </div>
      {progress.total > 0 ? (
        <div
          aria-label={progress.label}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={progress.progressValue}
          className="mt-2 h-1 overflow-hidden rounded-full bg-muted"
          role="progressbar"
        >
          <div
            className={`h-full rounded-full transition-all duration-500 ${jobProgressBarClass(summary.tone)}`}
            style={{ width: `${progress.progressValue}%` }}
          />
        </div>
      ) : null}
    </div>
  )
}

function JobStepIcon({ item }: { item: JobStepItem }) {
  if (item.tone === 'success') return <CheckCircle2 className="size-3.5" />
  if (item.tone === 'error') return <XCircle className="size-3.5" />
  if (item.tone === 'warning') return <AlertTriangle className="size-3.5" />
  if (item.tone === 'active') return <Loader2 className="size-3.5 animate-spin" />
  return <Circle className="size-2.5" />
}

function jobMonitorDotClass(tone: JobResultSummary['tone']): string {
  if (tone === 'success') {
    return 'bg-muted'
  }
  if (tone === 'warning') {
    return 'bg-muted'
  }
  if (tone === 'error') {
    return 'bg-destructive'
  }
  if (tone === 'active') {
    return 'animate-pulse bg-primary'
  }
  return 'bg-foreground'
}

function jobProgressBarClass(tone: JobResultSummary['tone']): string {
  if (tone === 'success') {
    return 'bg-muted'
  }
  if (tone === 'warning') {
    return 'bg-muted'
  }
  if (tone === 'error') {
    return 'bg-destructive'
  }
  if (tone === 'active') {
    return 'bg-primary'
  }
  return 'bg-foreground'
}

function jobCompactIconClass(tone: JobStepItem['tone']): string {
  if (tone === 'success') {
    return 'bg-muted text-primary'
  }
  if (tone === 'warning') {
    return 'bg-muted text-muted-foreground'
  }
  if (tone === 'error') {
    return 'bg-destructive/10 text-destructive'
  }
  if (tone === 'active') {
    return 'bg-muted text-primary'
  }
  return 'bg-muted text-muted-foreground'
}

function jobCompactStatusClass(tone: JobStepItem['tone']): string {
  if (tone === 'success') {
    return 'text-primary'
  }
  if (tone === 'warning') {
    return 'text-muted-foreground'
  }
  if (tone === 'error') {
    return 'text-destructive'
  }
  if (tone === 'active') {
    return 'text-primary'
  }
  return 'text-muted-foreground'
}

function jobMiniDotClass(tone: JobStepItem['tone']): string {
  if (tone === 'success') {
    return 'bg-muted'
  }
  if (tone === 'warning') {
    return 'bg-muted'
  }
  if (tone === 'error') {
    return 'bg-destructive'
  }
  if (tone === 'active') {
    return 'animate-pulse bg-primary'
  }
  return 'bg-foreground'
}

function jobVisualConfig(jobState: string) {
  switch (jobState) {
    case 'completed':
      return { label: 'Готово', statusClass: 'bg-muted text-primary' }
    case 'partially_completed':
      return { label: 'Частично', statusClass: 'bg-muted text-muted-foreground' }
    case 'queued':
      return { label: 'В очереди', statusClass: 'bg-muted text-foreground' }
    case 'running':
      return { label: 'В работе', statusClass: 'bg-primary text-primary-foreground' }
    case 'failed':
      return { label: 'Ошибка', statusClass: 'bg-destructive/10 text-destructive' }
    case 'manual_intervention_needed':
      return { label: 'Нужно действие', statusClass: 'bg-muted text-muted-foreground' }
    case 'dedup_blocked':
      return { label: 'Дубликат', statusClass: 'bg-muted text-muted-foreground' }
    default:
      return { label: 'Черновик', statusClass: 'bg-muted text-muted-foreground' }
  }
}
