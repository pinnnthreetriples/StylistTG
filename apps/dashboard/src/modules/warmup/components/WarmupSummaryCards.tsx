import { StatusCard } from '@stylisttg/ui'

import { WarmupStatusPill } from './WarmupStatusPill'
import { formatWarmupSummaryDuration, type WarmupModuleStatus } from './WarmupStatusPillModel'

type WarmupSummaryCardsProps = {
  accountCount: number
  durationSeconds: number
  status: WarmupModuleStatus
  lastHeartbeatAt?: Date | string | null
  now?: Date
}

export function WarmupSummaryCards({
  accountCount,
  durationSeconds,
  lastHeartbeatAt,
  now,
  status,
}: WarmupSummaryCardsProps) {
  return (
    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-stretch">
      <StatusCard
        label="АККАУНТЫ"
        value={
          <span className="inline-flex items-center gap-2">
            <span className="text-blue-700" aria-hidden="true">
              👥
            </span>
            {accountCount}
          </span>
        }
        detail="Выбрано для прогрева"
        tone="info"
      />
      <StatusCard
        label="ДЛИТЕЛЬНОСТЬ"
        value={
          <span className="inline-flex items-center gap-2">
            <span className="text-emerald-700" aria-hidden="true">
              ⏱
            </span>
            {formatWarmupSummaryDuration(durationSeconds)}
          </span>
        }
        detail="Общее окно запуска"
        tone="ok"
      />
      <div className="flex items-center rounded-lg border border-border bg-card px-4 py-3">
        <WarmupStatusPill status={status} lastHeartbeatAt={lastHeartbeatAt} now={now} />
      </div>
    </div>
  )
}
