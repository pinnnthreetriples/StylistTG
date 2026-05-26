import type { ReactNode } from 'react'

import { cn } from './utils'

type ReadinessItem = {
  label: string
  ready: boolean
  detail?: string
}

export type AccountReadinessPanelProps = {
  title: string
  items: ReadinessItem[]
  actions?: ReactNode
  className?: string
}

export function AccountReadinessPanel({ title, items, actions, className }: AccountReadinessPanelProps) {
  return (
    <div className={cn('rounded-xl border border-border bg-card p-4', className)}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-foreground">{title}</h3>
        {actions}
      </div>
      <ul className="mt-3 grid gap-2">
        {items.map((item) => (
          <li className="flex items-center gap-2.5 text-sm" key={item.label}>
            <span
              className={cn(
                'size-2 shrink-0 rounded-full',
                item.ready ? 'bg-muted' : 'bg-foreground',
              )}
            />
            <span className={cn('text-foreground', !item.ready && 'text-muted-foreground')}>
              {item.label}
            </span>
            {item.detail ? (
              <span className="ml-auto text-xs text-muted-foreground">{item.detail}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
