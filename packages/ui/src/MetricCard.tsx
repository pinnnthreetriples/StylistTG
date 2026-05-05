import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

export type MetricCardProps = HTMLAttributes<HTMLDivElement> & {
  label: string
  value: ReactNode
  change?: ReactNode
  icon?: ReactNode
}

export function MetricCard({ className, label, value, change, icon, ...props }: MetricCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-gray-200 bg-white p-4 shadow-sm',
        className,
      )}
      {...props}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</span>
        {icon ? <span className="text-gray-400">{icon}</span> : null}
      </div>
      <div className="mt-2 text-2xl font-bold text-gray-900">{value}</div>
      {change ? <div className="mt-1 text-xs text-gray-500">{change}</div> : null}
    </div>
  )
}
