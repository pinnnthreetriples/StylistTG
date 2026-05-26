import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

type StatusTone = 'ok' | 'warning' | 'danger' | 'neutral' | 'info'

const tones: Record<StatusTone, string> = {
  ok: 'border-border bg-muted',
  warning: 'border-border bg-muted',
  danger: 'border-destructive/20 bg-destructive/10',
  neutral: 'border-border bg-card',
  info: 'border-border bg-muted',
}

export type StatusCardProps = HTMLAttributes<HTMLDivElement> & {
  label: string
  value: ReactNode
  tone?: StatusTone
  detail?: ReactNode
}

export function StatusCard({ className, detail, label, tone = 'neutral', value, ...props }: StatusCardProps) {
  return (
    <div className={cn('rounded-lg border p-4', tones[tone], className)} {...props}>
      <div className="text-xs font-bold uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-lg font-bold text-foreground">{value}</div>
      {detail ? <div className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</div> : null}
    </div>
  )
}
