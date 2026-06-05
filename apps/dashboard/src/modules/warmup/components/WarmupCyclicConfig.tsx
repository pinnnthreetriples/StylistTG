import { Alert } from '@stylisttg/ui'
import { CalendarClock } from 'lucide-react'

import type { ApiError } from '@/lib/http'

import { buildWarmupCyclePreview, validateWarmupCycleConfig } from './WarmupCyclicConfigModel'
import type { WarmupCycleValidation } from './WarmupCyclicConfigModel'

export function WarmupCyclicConfig({
  apiError,
  daysTotal,
  enabled,
  endHour,
  onDaysTotalChange,
  onEnabledChange,
  onEndHourChange,
  onStartHourChange,
  startHour,
}: {
  apiError?: ApiError | null
  daysTotal: number
  enabled: boolean
  endHour: number
  onDaysTotalChange: (value: number) => void
  onEnabledChange: (value: boolean) => void
  onEndHourChange: (value: number) => void
  onStartHourChange: (value: number) => void
  startHour: number
}) {
  const validation = validateWarmupCycleConfig({ daysTotal, enabled, endHour, startHour })
  const fieldErrors = mergeApiFieldErrors(validation.errors, apiError)
  const preview = buildWarmupCyclePreview({ daysTotal, enabled, endHour, startHour })

  return (
    <div className="mt-5 rounded-lg border border-border bg-card px-3 py-3">
      <label className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <input
          checked={enabled}
          className="size-4"
          type="checkbox"
          onChange={(event) => onEnabledChange(event.target.checked)}
        />
        <CalendarClock className="size-4 text-muted-foreground" />
        Циклический режим
      </label>
      {enabled ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <WarmupCycleNumberField
            error={fieldErrors.startHour}
            label="Начало"
            max={23}
            min={0}
            value={startHour}
            onChange={onStartHourChange}
          />
          <WarmupCycleNumberField
            error={fieldErrors.endHour}
            label="Конец"
            max={23}
            min={0}
            value={endHour}
            onChange={onEndHourChange}
          />
          <WarmupCycleNumberField
            error={fieldErrors.daysTotal}
            label="Дней"
            max={30}
            min={1}
            value={daysTotal}
            onChange={onDaysTotalChange}
          />
          <div className="sm:col-span-3">
            {validation.isValid ? (
              <div className="text-xs text-muted-foreground">{preview}</div>
            ) : (
              <Alert variant="error">{Object.values(fieldErrors)[0]}</Alert>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function WarmupCycleNumberField({
  error,
  label,
  max,
  min,
  onChange,
  value,
}: {
  error?: string
  label: string
  max: number
  min: number
  onChange: (value: number) => void
  value: number
}) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <input
        className={`h-9 rounded-md border px-3 text-sm ${
          error ? 'border-destructive bg-background' : 'border-border bg-background'
        }`}
        max={max}
        min={min}
        type="number"
        value={value}
        onChange={(event) => onChange(parseNumber(event.target.value, min))}
      />
      {error ? <span className="text-xs font-semibold text-destructive">{error}</span> : null}
    </label>
  )
}

function mergeApiFieldErrors(
  errors: WarmupCycleValidation['errors'],
  apiError: ApiError | null | undefined,
): WarmupCycleValidation['errors'] {
  const next = { ...errors }
  for (const fieldError of apiError?.field_errors ?? []) {
    if (fieldError.field === 'start_hour') next.startHour = fieldError.message
    if (fieldError.field === 'end_hour') next.endHour = fieldError.message
    if (fieldError.field === 'days_total') next.daysTotal = fieldError.message
  }
  return next
}

function parseNumber(value: string, fallback: number): number {
  const parsed = Number.parseInt(value || String(fallback), 10)
  if (Number.isNaN(parsed)) return fallback
  return parsed
}
