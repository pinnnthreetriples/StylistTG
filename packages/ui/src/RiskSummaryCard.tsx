import type { HTMLAttributes, ReactNode } from 'react'

import type { RiskLevel } from './RiskBadge'
import { cn } from './utils'

const borderStyles: Record<RiskLevel, string> = {
  low: 'border-emerald-200',
  medium: 'border-amber-200',
  high: 'border-orange-200',
  critical: 'border-red-300',
}

const bgStyles: Record<RiskLevel, string> = {
  low: 'bg-emerald-50/40',
  medium: 'bg-amber-50/40',
  high: 'bg-orange-50/40',
  critical: 'bg-red-50/40',
}

export type RiskSummaryCardProps = HTMLAttributes<HTMLDivElement> & {
  level: RiskLevel
  levelLabel: string
  score: number
  description?: ReactNode
  actions?: ReactNode
}

export function RiskSummaryCard({ className, level, levelLabel, score, description, actions, ...props }: RiskSummaryCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border-2 p-5',
        borderStyles[level],
        bgStyles[level],
        className,
      )}
      {...props}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-gray-500">{levelLabel}</div>
          <div className="mt-1 text-3xl font-bold text-gray-900">{score}</div>
        </div>
        {actions}
      </div>
      {description ? <div className="mt-3 text-sm text-gray-600">{description}</div> : null}
    </div>
  )
}
