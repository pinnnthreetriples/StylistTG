import type { ReactNode } from 'react'

import { cn } from './utils'

export type EmptyStateProps = {
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('rounded-lg border border-dashed border-gray-200 bg-gray-50 p-6 text-center', className)}>
      <p className="text-sm font-semibold text-gray-900">{title}</p>
      {description ? <p className="mt-1 text-sm text-gray-500">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
