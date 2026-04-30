/**
 * DashboardActionBar – sticky bottom bar with "Create job" and "Reset" actions.
 *
 * Extracted from App.tsx render section.
 */

import { Loader2, Play } from 'lucide-react'
import { useState } from 'react'
import type { ProfilePreview } from '@/lib/api'
import { operationSafetyLabel, type OperationSafety } from '@/lib/accountSafety'
import { formatChangeOperationLabel, type ChangeItem } from '@/lib/dashboard'

interface DashboardActionBarProps {
  changedItems: ChangeItem[]
  preview: ProfilePreview | null
  isSubmittingJob: boolean
  onReset: () => void
  onCreateJob: () => void
  onCreateSafetyOverride?: (item: OperationSafety, reason: string) => void
}

export function DashboardActionBar({
  changedItems,
  preview,
  isSubmittingJob,
  onReset,
  onCreateJob,
  onCreateSafetyOverride,
}: DashboardActionBarProps) {
  const isJobBlocked = preview
    ? !preview.can_create_job || preview.dedup_would_block
    : false

  const isCreateDisabled =
    isSubmittingJob || isJobBlocked || changedItems.length === 0

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-40">
      {preview?.operation_safety?.length ? (
        <OperationSafetyStrip items={preview.operation_safety} onCreateOverride={onCreateSafetyOverride} />
      ) : null}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-2.5 flex items-center justify-between gap-3">
        {/* ── Change summary ── */}
        <div className="flex items-center gap-2.5">
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-tangerine-50 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-tangerine-400" />
            <span className="text-[11px] font-semibold text-tangerine-700">
              {changedItems.length} изменения
            </span>
          </span>
          <span className="text-[11px] text-gray-400 hidden sm:inline">
            {changedItems.length > 0
              ? changedItems.map((item) => formatChangeOperationLabel(item.operation)).join(', ')
              : 'Нет изменений'}
          </span>
        </div>

        {/* ── Actions ── */}
        <div className="flex items-center gap-2">
          <button
            onClick={onReset}
            disabled={changedItems.length === 0}
            className="px-4 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all disabled:opacity-50"
          >
            Отменить
          </button>

          <button
            onClick={onCreateJob}
            disabled={isCreateDisabled}
            className="px-5 py-1.5 bg-navy-400 hover:bg-navy-500 text-white text-xs font-semibold rounded-lg transition-all hover:shadow-lg hover:shadow-navy-400/20 active:scale-[0.98] flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmittingJob ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Play className="size-4" />
            )}
            {preview?.dedup_would_block ? 'Уже в очереди' : 'Создать задачу'}
          </button>
        </div>
      </div>
    </div>
  )
}

function OperationSafetyStrip({
  items,
  onCreateOverride,
}: {
  items: OperationSafety[]
  onCreateOverride?: (item: OperationSafety, reason: string) => void
}) {
  const overridable = items.find((item) => item.can_override)
  const [reason, setReason] = useState('')
  return (
    <div className="border-b border-gray-100 bg-gray-50">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-2 text-[11px] text-gray-600 sm:px-6">
        {items.map((item) => (
          <span
            className={`rounded-full px-2 py-1 font-medium ${
              item.state === 'blocked'
                ? 'bg-red-50 text-red-700'
                : item.state === 'warning'
                  ? 'bg-honey-50 text-honey-700'
                  : 'bg-emerald-50 text-emerald-700'
            }`}
            key={item.operation}
          >
            {operationSafetyLabel(item)}
          </span>
        ))}
        {overridable && onCreateOverride ? (
          <span className="ml-auto flex min-w-0 items-center gap-1.5">
            <input
              className="w-56 rounded-lg border border-gray-200 bg-white px-2 py-1 text-[11px]"
              onChange={(event) => setReason(event.currentTarget.value)}
              placeholder="Причина ручного разбора"
              value={reason}
            />
            <button
              className="rounded-lg bg-red-50 px-2 py-1 font-semibold text-red-700 disabled:opacity-50"
              disabled={reason.trim().length < 3}
              onClick={() => onCreateOverride(overridable, reason)}
              type="button"
            >
              Разобрать
            </button>
          </span>
        ) : null}
      </div>
    </div>
  )
}
