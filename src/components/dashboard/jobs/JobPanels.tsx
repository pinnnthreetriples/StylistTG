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
  XCircle,
} from 'lucide-react'
import { useState } from 'react'

import { type JobDetail, type JobSummary } from '@/lib/api'
import { buildJobMetrics } from '@/lib/dashboard'
import { type JobDisplayItem, type JobProgressSummary, type JobResultSummary, type JobStepItem } from '@/lib/jobs'

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
      <p className="text-[10px] text-gray-400">{label}</p>
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
    <section className="ui-surface-enter rounded-2xl border border-gray-200/60 bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-navy-50">
            <ListOrdered className="size-3.5 text-navy-400" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500">Задачи</h3>
            <p className="text-[10px] text-gray-400">Сводка запусков</p>
          </div>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${latestJobState ? latestConfig.statusClass : 'bg-gray-100 text-gray-500'}`}>
          {latestJobState ? latestConfig.label : 'Нет задач'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 border-t border-gray-100 pt-3">
        <Metric label="Всего" value={metrics.total.toString()} valueClass="text-navy-900" />
        <Metric label="Успех" value={metrics.success.toString()} valueClass="text-emerald-600" />
        <Metric label="Проблем" value={metrics.issues.toString()} valueClass="text-red-500" />
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
    <section className="ui-surface-enter rounded-2xl border border-gray-200/60 bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-center gap-2">
        <Cpu className="size-3.5 text-gray-400" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
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
                active ? 'bg-navy-50 text-navy-700' : 'bg-gray-50 text-gray-500'
              }`}
              key={step.label}
            >
              <StepIcon className={`size-3 ${active ? 'text-navy-400' : 'text-gray-400'}`} />
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
  progressSummary,
  resultSummary,
}: {
  currentJob: JobDetail | null
  items: JobDisplayItem[]
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
          className="flex size-11 items-center justify-center rounded-full border border-gray-200 bg-white/95 shadow-xl shadow-navy-900/10 backdrop-blur transition hover:bg-gray-50"
          onClick={() => setMinimized(false)}
          type="button"
        >
          <span className={`absolute right-2 top-2 size-2 rounded-full ${jobMonitorDotClass(resultSummary.tone)}`} />
          <ChevronUp className="size-4 text-gray-600" />
        </button>
      </aside>
    )
  }

  return (
    <aside className="fixed bottom-16 left-3 right-3 z-50 sm:bottom-20 sm:left-auto sm:right-6 sm:w-[420px]">
      <section className="ui-surface-enter overflow-hidden rounded-xl border border-gray-200/80 bg-white/95 shadow-xl shadow-navy-900/10 backdrop-blur">
        <div className="border-b border-gray-100 px-3 py-2.5">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className={`size-2 rounded-full ${jobMonitorDotClass(resultSummary.tone)}`} />
                <h3 className="text-xs font-semibold text-gray-800">План и выполнение</h3>
              </div>
              <p className="mt-0.5 truncate text-[10px] text-gray-400">
                {currentJob ? `#${currentJob.job_id.slice(0, 8)} · ${jobVisualConfig(currentJob.job_state).label}` : 'Предпросмотр'}
              </p>
            </div>
            <div className="flex flex-shrink-0 items-center gap-1">
              <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${jobVisualConfig(currentJob?.job_state ?? 'draft').statusClass}`}>
                {currentJob ? jobVisualConfig(currentJob.job_state).label : progressSummary.label}
              </span>
              <button
                aria-label="Скрыть план выполнения"
                className="flex size-7 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-50 hover:text-gray-700"
                onClick={() => setMinimized(true)}
                type="button"
              >
                <ChevronDown className="size-3.5" />
              </button>
            </div>
          </div>
          <JobProgressBlock progress={progressSummary} summary={resultSummary} />
          <button
            aria-expanded={expanded}
            className="mt-2 flex w-full items-center justify-between rounded-lg px-2 py-1 text-[10px] font-semibold text-gray-500 transition hover:bg-gray-50 hover:text-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-navy-200"
            onClick={() => setExpanded((value) => !value)}
            type="button"
          >
            <span>{expanded ? 'Скрыть шаги' : 'Показать шаги'}</span>
            <ChevronDown className={`size-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </button>
        </div>

        <div className={`max-h-[42vh] overflow-y-auto px-2.5 py-2 ${expanded ? 'block' : 'hidden'}`}>
          {items.length === 0 ? (
            <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-400">
              Измените профиль, чтобы увидеть план.
            </div>
          ) : (
            <ol className="space-y-1" role="list">
              {items.map((item) => (
                <JobMonitorRow item={item} key={item.key} />
              ))}
            </ol>
          )}
        </div>
      </section>
    </aside>
  )
}

function JobMonitorRow({ item }: { item: JobDisplayItem }) {
  return (
    <li className={`rounded-lg px-2 py-1.5 ${item.tone === 'error' ? 'bg-red-50' : item.tone === 'active' ? 'bg-navy-50' : ''}`}>
      <div className="flex items-center gap-2">
        <span className={`flex size-5 flex-shrink-0 items-center justify-center rounded-full ${jobCompactIconClass(item.tone)}`}>
          <JobStepIcon item={item} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center justify-between gap-2">
            <span className="truncate text-[11px] font-semibold text-gray-800">{item.title}</span>
            <span className={`flex-shrink-0 text-[10px] font-semibold ${jobCompactStatusClass(item.tone)}`}>
              {item.statusLabel}
            </span>
          </div>
          {item.kind === 'story' && item.children ? <StoryMiniPipeline steps={item.children} /> : null}
          {item.tone === 'error' || item.tone === 'warning' || item.status === 'not_started' ? (
            <p className="mt-0.5 text-[10px] leading-snug text-gray-500">{item.detail}</p>
          ) : null}
        </div>
      </div>
    </li>
  )
}

function StoryMiniPipeline({ steps }: { steps: NonNullable<JobDisplayItem['children']> }) {
  return (
    <div className="mt-1 flex items-center gap-1.5">
      {steps.map((step, index) => (
        <div className="flex min-w-0 items-center gap-1" key={step.key}>
          <span className={`size-1.5 rounded-full ${jobMiniDotClass(step.tone)}`} title={`${step.shortTitle}: ${step.statusLabel}`} />
          <span className="truncate text-[9px] text-gray-400">{step.shortTitle}</span>
          {index < steps.length - 1 ? <span className="text-[9px] text-gray-300">→</span> : null}
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
        <span className="text-[10px] font-semibold text-gray-500">{progress.label}</span>
      </div>
      {progress.total > 0 ? (
        <div
          aria-label={progress.label}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={progress.progressValue}
          className="mt-2 h-1 overflow-hidden rounded-full bg-gray-100"
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
    return 'bg-emerald-500'
  }
  if (tone === 'warning') {
    return 'bg-honey-500'
  }
  if (tone === 'error') {
    return 'bg-red-500'
  }
  if (tone === 'active') {
    return 'animate-pulse-dot bg-navy-400'
  }
  return 'bg-gray-300'
}

function jobProgressBarClass(tone: JobResultSummary['tone']): string {
  if (tone === 'success') {
    return 'bg-emerald-500'
  }
  if (tone === 'warning') {
    return 'bg-honey-500'
  }
  if (tone === 'error') {
    return 'bg-red-500'
  }
  if (tone === 'active') {
    return 'bg-navy-400'
  }
  return 'bg-gray-400'
}

function jobCompactIconClass(tone: JobStepItem['tone']): string {
  if (tone === 'success') {
    return 'bg-emerald-50 text-emerald-600'
  }
  if (tone === 'warning') {
    return 'bg-honey-50 text-honey-700'
  }
  if (tone === 'error') {
    return 'bg-red-100 text-red-600'
  }
  if (tone === 'active') {
    return 'bg-navy-50 text-navy-500'
  }
  return 'bg-gray-50 text-gray-300'
}

function jobCompactStatusClass(tone: JobStepItem['tone']): string {
  if (tone === 'success') {
    return 'text-emerald-600'
  }
  if (tone === 'warning') {
    return 'text-honey-700'
  }
  if (tone === 'error') {
    return 'text-red-600'
  }
  if (tone === 'active') {
    return 'text-navy-500'
  }
  return 'text-gray-400'
}

function jobMiniDotClass(tone: JobStepItem['tone']): string {
  if (tone === 'success') {
    return 'bg-emerald-500'
  }
  if (tone === 'warning') {
    return 'bg-honey-500'
  }
  if (tone === 'error') {
    return 'bg-red-500'
  }
  if (tone === 'active') {
    return 'animate-pulse-dot bg-navy-400'
  }
  return 'bg-gray-300'
}

function jobVisualConfig(jobState: string) {
  switch (jobState) {
    case 'completed':
      return { label: 'Готово', statusClass: 'bg-emerald-50 text-emerald-700' }
    case 'partially_completed':
      return { label: 'Частично', statusClass: 'bg-honey-50 text-honey-700' }
    case 'queued':
      return { label: 'В очереди', statusClass: 'bg-navy-50 text-navy-700' }
    case 'running':
      return { label: 'В работе', statusClass: 'bg-navy-400 text-white' }
    case 'failed':
      return { label: 'Ошибка', statusClass: 'bg-red-50 text-red-600' }
    case 'manual_intervention_needed':
      return { label: 'Нужно действие', statusClass: 'bg-honey-50 text-honey-700' }
    case 'dedup_blocked':
      return { label: 'Дубликат', statusClass: 'bg-gray-100 text-gray-500' }
    default:
      return { label: 'Черновик', statusClass: 'bg-gray-100 text-gray-500' }
  }
}
