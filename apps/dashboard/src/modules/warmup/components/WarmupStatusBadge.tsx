import { StatusPill, type StatusPillTone } from '@stylisttg/ui'

import { WARMUP_STATUS_LABELS, formatWarmupDate } from '../labels'
import type { WarmupStatus } from '../types'

const STATUS_TONES: Record<WarmupStatus, StatusPillTone> = {
  draft: 'muted',
  validating: 'amber',
  scheduled: 'warn',
  cold_soak: 'muted',
  active: 'green',
  paused_risk: 'red',
  paused_manual: 'amber',
  completed: 'green',
  failed: 'red',
}

export function WarmupStatusBadge({
  status,
  coldSoakUntil,
}: {
  status: WarmupStatus
  coldSoakUntil?: string | null
}) {
  const label =
    status === 'cold_soak' && coldSoakUntil
      ? `Cold soak до ${formatWarmupDate(coldSoakUntil)}`
      : WARMUP_STATUS_LABELS[status]
  return <StatusPill tone={STATUS_TONES[status]}>{label}</StatusPill>
}
