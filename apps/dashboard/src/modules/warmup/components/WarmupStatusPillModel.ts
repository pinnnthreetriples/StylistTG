export type WarmupModuleStatus = 'STOPPED' | 'RUNNING' | 'OFFLINE' | 'LIVE'

type ResolveWarmupModuleStatusOptions = {
  status: WarmupModuleStatus
  lastHeartbeatAt?: Date | string | null
  now?: Date
  heartbeatTimeoutSeconds?: number
}

export function resolveWarmupModuleStatus({
  heartbeatTimeoutSeconds = 30,
  lastHeartbeatAt,
  now,
  status,
}: ResolveWarmupModuleStatusOptions): WarmupModuleStatus {
  if ((status === 'LIVE' || status === 'RUNNING') && lastHeartbeatAt) {
    const heartbeatMs =
      lastHeartbeatAt instanceof Date ? lastHeartbeatAt.getTime() : new Date(lastHeartbeatAt).getTime()
    const nowMs = now?.getTime() ?? Date.now()
    if (Number.isFinite(heartbeatMs) && nowMs - heartbeatMs > heartbeatTimeoutSeconds * 1000) {
      return 'OFFLINE'
    }
  }
  return status
}

export function formatWarmupSummaryDuration(durationSeconds: number): string {
  if (durationSeconds <= 0) return '0мин'
  const minutes = Math.max(1, Math.round(durationSeconds / 60))
  if (minutes < 60) return `${minutes}мин`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}ч`
  return `${Math.round(hours / 24)}д`
}
