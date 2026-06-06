import { Alert, Button } from '@stylisttg/ui'
import { Gauge, ListChecks, PowerOff } from 'lucide-react'

import { isApiError } from '@/lib/http'

import { useApplyWarmupActionPreset } from '../hooks'
import type { WarmupActionPreset } from '../types'

const ACTION_PRESETS: Array<{
  preset: WarmupActionPreset
  label: string
  icon: typeof Gauge
}> = [
  { preset: 'economic', label: 'Экономный режим', icon: Gauge },
  { preset: 'all', label: 'Включить всё', icon: ListChecks },
  { preset: 'minimal', label: 'Выключить всё', icon: PowerOff },
]

export function ActionPresetButtons({
  disabled = false,
  onApplied,
  strategyId,
}: {
  disabled?: boolean
  onApplied?: () => void
  strategyId: string
}) {
  const mutation = useApplyWarmupActionPreset()
  const errorMessage =
    mutation.error && isApiError(mutation.error)
      ? mutation.error.message
      : 'Не удалось применить пресет действий.'

  return (
    <div className="mt-4 grid gap-2 border-t border-border pt-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground">Тонкая настройка</div>
          <p className="mt-1 text-sm text-muted-foreground">Быстро меняет daily_action_limits выбранной стратегии.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {ACTION_PRESETS.map(({ preset, label, icon: Icon }) => (
            <Button
              disabled={disabled || mutation.isPending}
              key={preset}
              size="sm"
              type="button"
              variant="outline"
              onClick={() =>
                mutation.mutate(
                  { strategyId, preset },
                  {
                    onSuccess: () => {
                      onApplied?.()
                    },
                  },
                )
              }
            >
              <Icon className="size-3.5" />
              {label}
            </Button>
          ))}
        </div>
      </div>
      {mutation.error ? (
        <Alert variant="error">{errorMessage}</Alert>
      ) : null}
    </div>
  )
}
