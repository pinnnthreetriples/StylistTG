/**
 * DashboardActionBar – sticky bottom bar with "Create job" and "Reset" actions.
 *
 * Extracted from App.tsx render section.
 */

import { Loader2, Play, UserRoundCheck } from 'lucide-react'
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
    <div className="fixed bottom-0 left-0 right-0 bg-card border-t border-border z-40">
      {preview?.operation_safety?.length ? (
        <OperationSafetyStrip items={preview.operation_safety} onCreateOverride={onCreateSafetyOverride} />
      ) : null}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-2.5 flex items-center justify-between gap-3">
        {/* ── Change summary ── */}
        <div className="flex items-center gap-2.5">
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-muted rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-muted" />
            <span className="text-[11px] font-semibold text-muted-foreground">
              {changedItems.length} изменения
            </span>
          </span>
          {preview?.profile_uniqueness && preview.profile_uniqueness.similar_count > 0 ? (
            <ProfileUniquenessBadge profileUniqueness={preview.profile_uniqueness} />
          ) : null}
          <span className="text-[11px] text-muted-foreground hidden sm:inline">
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
            className="px-4 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all disabled:opacity-50"
          >
            Отменить
          </button>

          <button
            onClick={onCreateJob}
            disabled={isCreateDisabled}
            className="px-5 py-1.5 bg-primary hover:bg-primary text-primary-foreground text-xs font-semibold rounded-lg transition-all hover:shadow-lg hover:shadow-foreground/10 active:scale-[0.98] flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
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

function ProfileUniquenessBadge({
  profileUniqueness,
}: {
  profileUniqueness: NonNullable<ProfilePreview['profile_uniqueness']>
}) {
  const blocked = profileUniqueness.severity === 'blocked'
  const count = blocked ? profileUniqueness.blocking_count : profileUniqueness.similar_count
  return (
    <span
      className={`hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold sm:flex ${
        blocked ? 'bg-destructive/10 text-destructive' : 'bg-muted text-muted-foreground'
      }`}
      title={`max score ${profileUniqueness.max_score.toFixed(2)}`}
    >
      <UserRoundCheck className="size-3.5" />
      {blocked ? `Слишком похож: ${count}` : `Похожий профиль: ${count}`}
    </span>
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
    <div className="border-b border-border bg-muted">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-2 text-[11px] text-muted-foreground sm:px-6">
        {items.map((item) => (
          <span
            className={`rounded-full px-2 py-1 font-medium ${
              item.state === 'blocked'
                ? 'bg-destructive/10 text-destructive'
                : item.state === 'warning'
                  ? 'bg-muted text-muted-foreground'
                  : 'bg-muted text-primary'
            }`}
            key={item.operation}
          >
            {operationSafetyLabel(item)}
          </span>
        ))}
        {overridable && onCreateOverride ? (
          <span className="ml-auto flex min-w-0 items-center gap-1.5">
            <input
              aria-label="Причина ручного разбора"
              className="w-56 rounded-lg border border-border bg-card px-2 py-1 text-[11px]"
              onChange={(event) => setReason(event.currentTarget.value)}
              placeholder="Причина ручного разбора"
              value={reason}
            />
            <button
              className="rounded-lg bg-destructive/10 px-2 py-1 font-semibold text-destructive disabled:opacity-50"
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
