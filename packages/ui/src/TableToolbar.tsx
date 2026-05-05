import type { ReactNode } from 'react'

import { cn } from './utils'

export type TableToolbarProps = {
  search?: ReactNode
  filters?: ReactNode
  actions?: ReactNode
  className?: string
}

export function TableToolbar({ search, filters, actions, className }: TableToolbarProps) {
  return (
    <div className={cn('flex flex-wrap items-center gap-3', className)}>
      {search ? <div className="min-w-0 flex-1 sm:max-w-xs">{search}</div> : null}
      {filters ? <div className="flex flex-wrap items-center gap-2">{filters}</div> : null}
      {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
    </div>
  )
}
