import type { HTMLAttributes } from 'react'

import { cn } from './utils'

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'gray' | 'green' | 'amber' | 'red' | 'blue'

const tones: Record<BadgeTone, string> = {
  neutral: 'bg-muted text-foreground border-border',
  success: 'bg-muted text-primary border-border',
  warning: 'bg-muted text-muted-foreground border-border',
  danger: 'bg-destructive/10 text-destructive border-destructive/20',
  info: 'bg-muted text-muted-foreground border-border',
  gray: 'bg-muted text-foreground border-border',
  green: 'bg-muted text-primary border-border',
  amber: 'bg-muted text-muted-foreground border-border',
  red: 'bg-destructive/10 text-destructive border-destructive/20',
  blue: 'bg-muted text-muted-foreground border-border',
}

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone
}

export function Badge({ className, tone = 'neutral', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        tones[tone],
        className,
      )}
      {...props}
    />
  )
}
