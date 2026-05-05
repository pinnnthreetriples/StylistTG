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
    <div className={cn('flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-4', className)}>
      {icon ? <span className="mt-0.5 shrink-0 text-gray-400">{icon}</span> : null}
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-gray-900">{title}</div>
        {description ? <div className="mt-1 text-xs text-gray-500">{description}</div> : null}
      </div>
      {action}
    </div>
  )
}
