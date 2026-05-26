import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type StatusPillTone = 'ok' | 'warn' | 'error' | 'muted' | 'green' | 'amber' | 'red'

const tones: Record<StatusPillTone, string> = {
  ok: 'bg-muted',
  warn: 'bg-muted',
  error: 'bg-destructive',
  muted: 'bg-foreground',
  green: 'bg-muted',
  amber: 'bg-muted',
  red: 'bg-destructive',
}

export type StatusPillProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: StatusPillTone
}

export function StatusPill({ className, tone = 'muted', children, ...props }: StatusPillProps) {
  return (
    <span
      className={cn('inline-flex items-center gap-2 rounded-full bg-muted px-2.5 py-1 text-xs text-foreground', className)}
      {...props}
    >
      <span className={cn('size-2 rounded-full', tones[tone])} />
      {children}
    </span>
  )
}
