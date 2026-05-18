import { Badge } from '@stylisttg/ui'

const toneMap: Record<string, 'neutral' | 'success' | 'warning' | 'danger'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  edited: 'neutral',
}

export function ApprovalBadge({ status }: { status: string }) {
  return <Badge tone={toneMap[status] ?? 'neutral'}>{status}</Badge>
}
