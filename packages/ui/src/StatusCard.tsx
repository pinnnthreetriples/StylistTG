import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

type StatusTone = 'ok' | 'warning' | 'danger' | 'neutral' | 'info'

const tones: Record<StatusTone, string> = {
  ok: 'border-emerald-100 bg-emerald-50/60',
  warning: 'border-amber-100 bg-amber-50/60',
  danger: 'border-red-100 bg-red-50/60',
  neutral: 'border-gray-200 bg-white',
  info: 'border-sky-100 bg-sky-50/60',
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
      <div className="text-xs font-bold uppercase text-gray-500">{label}</div>
      <div className="mt-2 text-lg font-bold text-navy-900">{value}</div>
      {detail ? <div className="mt-1 text-xs leading-5 text-gray-500">{detail}</div> : null}
    </div>
  )
}
