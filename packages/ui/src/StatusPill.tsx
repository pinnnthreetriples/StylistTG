import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type StatusPillTone = 'ok' | 'warn' | 'error' | 'muted' | 'green' | 'amber' | 'red'

const tones: Record<StatusPillTone, string> = {
  ok: 'bg-emerald-500',
  warn: 'bg-amber-500',
  error: 'bg-red-500',
  muted: 'bg-gray-400',
  green: 'bg-emerald-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
}

export type StatusPillProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: StatusPillTone
}

export function StatusPill({ className, tone = 'muted', children, ...props }: StatusPillProps) {
  return (
    <span
      className={cn('inline-flex items-center gap-2 rounded-full bg-gray-50 px-2.5 py-1 text-xs text-gray-700', className)}
      {...props}
    >
      <span className={cn('size-2 rounded-full', tones[tone])} />
      {children}
    </span>
  )
}
