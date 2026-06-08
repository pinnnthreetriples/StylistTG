import { Badge } from '@stylisttg/ui'

import type { WarmupCycleConfig } from '../types'
import { getWarmupCyclicStatusModel } from './WarmupCyclicStatusModel'

export function WarmupCyclicStatus({
  cycleConfig,
  now = new Date(),
  timezone,
}: {
  cycleConfig: WarmupCycleConfig
  now?: Date
  timezone?: string | null
}) {
  const model = getWarmupCyclicStatusModel(cycleConfig, now, timezone)
  return (
    <div className="rounded-lg border border-border bg-muted px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-foreground">{model.headline}</span>
        <Badge tone={model.isActive ? 'blue' : 'gray'}>{model.progress}</Badge>
      </div>
    </div>
  )
}
