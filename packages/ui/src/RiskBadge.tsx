import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

const styles: Record<RiskLevel, string> = {
  low: 'border-emerald-100 bg-emerald-50 text-emerald-700',
  medium: 'border-amber-100 bg-amber-50 text-amber-700',
  high: 'border-orange-100 bg-orange-50 text-orange-700',
  critical: 'border-red-100 bg-red-50 text-red-700',
}

export type RiskBadgeProps = HTMLAttributes<HTMLSpanElement> & {
  level: RiskLevel
  score?: number
}

export function RiskBadge({ className, level, score, ...props }: RiskBadgeProps) {
  return (
    <span
      className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold', styles[level], className)}
      {...props}
    >
      {level}
      {typeof score === 'number' ? <span className="ml-1 opacity-75">{score}</span> : null}
    </span>
  )
}
