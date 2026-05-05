import type { ReactNode } from 'react'

import { cn } from './utils'

type RiskReasonSeverity = 'info' | 'warning' | 'error' | 'critical'

export type RiskReason = {
  code: string
  severity: RiskReasonSeverity | string
  message: string
}

const severityDots: Record<string, string> = {
  info: 'bg-sky-400',
  warning: 'bg-amber-400',
  error: 'bg-orange-500',
  critical: 'bg-red-500',
}

export type RiskReasonListProps = {
  reasons: RiskReason[]
  emptyMessage?: ReactNode
  className?: string
}

export function RiskReasonList({ reasons, emptyMessage, className }: RiskReasonListProps) {
  if (reasons.length === 0) {
    return emptyMessage ? (
      <p className={cn('text-sm text-gray-500', className)}>{emptyMessage}</p>
    ) : null
  }

  return (
    <ul className={cn('grid gap-2', className)}>
      {reasons.map((reason) => (
        <li className="flex items-start gap-2.5 text-sm" key={reason.code}>
          <span
            className={cn(
              'mt-1.5 size-2 shrink-0 rounded-full',
              severityDots[reason.severity] ?? 'bg-gray-400',
            )}
          />
          <span className="min-w-0 text-gray-700">{reason.message}</span>
        </li>
      ))}
    </ul>
  )
}
