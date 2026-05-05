import type { SelectHTMLAttributes } from 'react'

import { cn } from './utils'

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  error?: boolean
}

export function Select({ className, error, children, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        'flex h-9 w-full appearance-none rounded-md border bg-white px-3 py-1.5 text-sm transition',
        'focus:outline-none focus:ring-2 focus:ring-offset-0',
        'disabled:cursor-not-allowed disabled:opacity-50',
        error
          ? 'border-red-300 focus:border-red-400 focus:ring-red-100'
          : 'border-gray-200 focus:border-navy-400 focus:ring-navy-100',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}
