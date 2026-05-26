import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

const styles: Record<RiskLevel, string> = {
  low: 'border-border bg-muted text-primary',
  medium: 'border-border bg-muted text-muted-foreground',
  high: 'border-border bg-muted text-muted-foreground',
  critical: 'border-destructive/20 bg-destructive/10 text-destructive',
}

export type RiskBadgeProps = HTMLAttributes<HTMLSpanElement> & {
  level: RiskLevel
  label?: string
  score?: number
}

export function RiskBadge({ className, level, label, score, ...props }: RiskBadgeProps) {
  return (
    <span
      className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold', styles[level], className)}
      {...props}
    >
      {label ?? level}
      {typeof score === 'number' ? <span className="ml-1 opacity-75">{score}</span> : null}
    </span>
  )
}
