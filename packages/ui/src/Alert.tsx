import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

type AlertVariant = 'info' | 'success' | 'warning' | 'error'

const variants: Record<AlertVariant, string> = {
  info: 'border-border bg-muted text-muted-foreground',
  success: 'border-border bg-muted text-primary',
  warning: 'border-border bg-muted text-muted-foreground',
  error: 'border-destructive/20 bg-destructive/10 text-destructive',
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
