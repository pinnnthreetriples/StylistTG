import type { ReactNode } from 'react'

import { cn } from './utils'

export type ProductEmptyStateProps = {
  title: string
  description: string
  action?: ReactNode
  secondaryAction?: ReactNode
  className?: string
}

export function ProductEmptyState({ action, className, description, secondaryAction, title }: ProductEmptyStateProps) {
  return (
    <div className={cn('rounded-xl border border-dashed border-border bg-card p-6 text-center shadow-sm', className)}>
      <p className="text-base font-semibold text-foreground">{title}</p>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>
      {action || secondaryAction ? (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  )
}
