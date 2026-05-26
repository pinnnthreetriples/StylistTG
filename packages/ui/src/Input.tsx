import type { InputHTMLAttributes } from 'react'

import { cn } from './utils'

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: boolean
}

export function Input({ className, error, ...props }: InputProps) {
  return (
    <input
      className={cn(
        'flex h-9 w-full rounded-md border bg-card px-3 py-1.5 text-sm transition',
        'placeholder:text-muted-foreground',
        'focus:outline-none focus:ring-2 focus:ring-offset-0',
        'disabled:cursor-not-allowed disabled:opacity-50',
        error
          ? 'border-destructive/20 focus:border-destructive/20 focus:ring-ring'
          : 'border-border focus:border-border focus:ring-ring',
        className,
      )}
      {...props}
    />
  )
}
