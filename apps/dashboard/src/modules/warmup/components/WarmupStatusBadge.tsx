import { StatusPill, type StatusPillTone } from '@stylisttg/ui'

import { WARMUP_STATUS_LABELS } from '../labels'
import type { WarmupStatus } from '../types'

const STATUS_TONES: Record<WarmupStatus, StatusPillTone> = {
  draft: 'muted',
  validating: 'amber',
  scheduled: 'warn',
  active: 'green',
  paused_risk: 'red',
  paused_manual: 'amber',
  completed: 'green',
  failed: 'red',
}

export function WarmupStatusBadge({ status }: { status: WarmupStatus }) {
  return <StatusPill tone={STATUS_TONES[status]}>{WARMUP_STATUS_LABELS[status]}</StatusPill>
}
