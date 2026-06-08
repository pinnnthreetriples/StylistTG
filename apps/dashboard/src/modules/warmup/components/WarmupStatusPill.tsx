import { StatusPill } from '@stylisttg/ui'

import { resolveWarmupModuleStatus, type WarmupModuleStatus } from './WarmupStatusPillModel'

type WarmupStatusPillProps = {
  status: WarmupModuleStatus
  lastHeartbeatAt?: Date | string | null
  now?: Date
  heartbeatTimeoutSeconds?: number
}

const STATUS_LABELS: Record<WarmupModuleStatus, string> = {
  STOPPED: 'Остановлено',
  RUNNING: 'Работает',
  OFFLINE: 'Не в сети',
  LIVE: 'В прямом эфире',
}

export function WarmupStatusPill({
  heartbeatTimeoutSeconds = 30,
  lastHeartbeatAt,
  now,
  status,
}: WarmupStatusPillProps) {
  const resolvedStatus = resolveWarmupModuleStatus({
    heartbeatTimeoutSeconds,
    lastHeartbeatAt,
    now,
    status,
  })
  const isPulsing = resolvedStatus === 'RUNNING' || resolvedStatus === 'LIVE'
  return (
    <StatusPill
      className={isPulsing ? 'animate-pulse motion-reduce:animate-none' : undefined}
      tone={statusTone(resolvedStatus)}
    >
      {STATUS_LABELS[resolvedStatus]}
    </StatusPill>
  )
}

function statusTone(status: WarmupModuleStatus): 'muted' | 'green' | 'red' {
  if (status === 'OFFLINE') return 'red'
  if (status === 'RUNNING' || status === 'LIVE') return 'green'
  return 'muted'
}
