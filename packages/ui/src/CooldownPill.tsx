import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type CooldownPillProps = HTMLAttributes<HTMLSpanElement> & {
  remainingLabel: string
}

export function CooldownPill({ className, remainingLabel, ...props }: CooldownPillProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700',
        className,
      )}
      {...props}
    >
      <span className="size-1.5 animate-pulse rounded-full bg-amber-500" />
      {remainingLabel}
    </span>
  )
}
