import type { HTMLAttributes, ReactNode } from 'react'

import type { RiskLevel } from './RiskBadge'
import { cn } from './utils'

const borderStyles: Record<RiskLevel, string> = {
  low: 'border-border',
  medium: 'border-border',
  high: 'border-border',
  critical: 'border-destructive/20',
}

const bgStyles: Record<RiskLevel, string> = {
  low: 'bg-muted',
  medium: 'bg-muted',
  high: 'bg-muted',
  critical: 'bg-destructive/10',
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
          <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{levelLabel}</div>
          <div className="mt-1 text-3xl font-bold text-foreground">{score}</div>
        </div>
        {actions}
      </div>
      {description ? <div className="mt-3 text-sm text-muted-foreground">{description}</div> : null}
    </div>
  )
}
