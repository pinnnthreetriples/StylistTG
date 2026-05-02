import type { HTMLAttributes } from 'react'

import { cn } from './utils'

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'gray' | 'green' | 'amber' | 'red' | 'blue'

const tones: Record<BadgeTone, string> = {
  neutral: 'bg-gray-100 text-gray-700 border-gray-200',
  success: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  warning: 'bg-amber-50 text-amber-700 border-amber-100',
  danger: 'bg-red-50 text-red-700 border-red-100',
  info: 'bg-sky-50 text-sky-700 border-sky-100',
  gray: 'bg-gray-100 text-gray-700 border-gray-200',
  green: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  amber: 'bg-amber-50 text-amber-700 border-amber-100',
  red: 'bg-red-50 text-red-700 border-red-100',
  blue: 'bg-sky-50 text-sky-700 border-sky-100',
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
