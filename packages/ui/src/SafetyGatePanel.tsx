import type { ReactNode } from 'react'

import { cn } from './utils'

export type SafetyGatePanelProps = {
  title: string
  reason: ReactNode
  retryLabel?: ReactNode
  icon?: ReactNode
  className?: string
}

export function SafetyGatePanel({ title, reason, retryLabel, icon, className }: SafetyGatePanelProps) {
  return (
    <div
      className={cn(
        'rounded-xl border-2 border-border bg-muted px-5 py-4',
        className,
      )}
    >
      <div className="flex items-start gap-3">
        {icon ? <span className="mt-0.5 shrink-0 text-muted-foreground">{icon}</span> : null}
        <div className="min-w-0">
          <div className="text-sm font-bold text-muted-foreground">{title}</div>
          <div className="mt-1 text-sm text-muted-foreground">{reason}</div>
          {retryLabel ? (
            <div className="mt-2 text-xs font-medium text-muted-foreground">{retryLabel}</div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
