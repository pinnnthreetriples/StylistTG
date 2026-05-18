import { Badge } from '@stylisttg/ui'

const toneMap: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  draft: 'neutral',
  running: 'success',
  paused: 'warning',
  stopped: 'danger',
  completed: 'info',
}

export function CampaignStatusBadge({ status }: { status: string }) {
  return <Badge tone={toneMap[status] ?? 'neutral'}>{status}</Badge>
}
