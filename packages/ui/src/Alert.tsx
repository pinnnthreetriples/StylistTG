import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

type AlertVariant = 'info' | 'success' | 'warning' | 'error'

const variants: Record<AlertVariant, string> = {
  info: 'border-sky-200 bg-sky-50 text-sky-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-red-200 bg-red-50 text-red-800',
}

export type AlertProps = HTMLAttributes<HTMLDivElement> & {
  variant?: AlertVariant
  icon?: ReactNode
}

export function Alert({ className, variant = 'info', icon, children, ...props }: AlertProps) {
  return (
    <div
      className={cn(
        'flex items-start gap-2.5 rounded-lg border px-4 py-3 text-sm',
        variants[variant],
        className,
      )}
      role="alert"
      {...props}
    >
      {icon ? <span className="mt-0.5 shrink-0">{icon}</span> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
