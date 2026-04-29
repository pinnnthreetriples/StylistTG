/**
 * DashboardActionBar – sticky bottom bar with "Create job" and "Reset" actions.
 *
 * Extracted from App.tsx render section.
 */

import { Loader2, Play } from 'lucide-react'
import type { ProfilePreview } from '@/lib/api'
import { formatChangeOperationLabel, type ChangeItem } from '@/lib/dashboard'

interface DashboardActionBarProps {
  changedItems: ChangeItem[]
  preview: ProfilePreview | null
  isSubmittingJob: boolean
  onReset: () => void
  onCreateJob: () => void
}

export function DashboardActionBar({
  changedItems,
  preview,
  isSubmittingJob,
  onReset,
  onCreateJob,
}: DashboardActionBarProps) {
  const isJobBlocked = preview
    ? !preview.can_create_job || preview.dedup_would_block
    : false

  const isCreateDisabled =
    isSubmittingJob || isJobBlocked || changedItems.length === 0

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-40">
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
