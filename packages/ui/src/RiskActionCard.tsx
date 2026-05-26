import type { ReactNode } from 'react'

import { cn } from './utils'

export type RiskActionCardProps = {
  title: string
  description?: ReactNode
  icon?: ReactNode
  action?: ReactNode
  className?: string
}

export function RiskActionCard({ title, description, icon, action, className }: RiskActionCardProps) {
  return (
    <div className={cn('flex items-start gap-3 rounded-lg border border-border bg-card p-4', className)}>
      {icon ? <span className="mt-0.5 shrink-0 text-muted-foreground">{icon}</span> : null}
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-foreground">{title}</div>
        {description ? <div className="mt-1 text-xs text-muted-foreground">{description}</div> : null}
      </div>
      {action}
    </div>
  )
}
