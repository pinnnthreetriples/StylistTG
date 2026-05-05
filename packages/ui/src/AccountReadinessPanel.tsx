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
    <div className={cn('rounded-xl border border-gray-200 bg-white p-4', className)}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-gray-900">{title}</h3>
        {actions}
      </div>
      <ul className="mt-3 grid gap-2">
        {items.map((item) => (
          <li className="flex items-center gap-2.5 text-sm" key={item.label}>
            <span
              className={cn(
                'size-2 shrink-0 rounded-full',
                item.ready ? 'bg-emerald-500' : 'bg-gray-300',
              )}
            />
            <span className={cn('text-gray-700', !item.ready && 'text-gray-400')}>
              {item.label}
            </span>
            {item.detail ? (
              <span className="ml-auto text-xs text-gray-400">{item.detail}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
