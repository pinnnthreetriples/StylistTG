import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type CooldownPillProps = HTMLAttributes<HTMLSpanElement> & {
  remainingLabel: string
}

export function CooldownPill({ className, remainingLabel, ...props }: CooldownPillProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-semibold text-muted-foreground',
        className,
      )}
      {...props}
    >
      <span className="size-1.5 animate-pulse rounded-full bg-muted" />
      {remainingLabel}
    </span>
  )
}
