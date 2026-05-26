import type { TextareaHTMLAttributes } from 'react'

import { cn } from './utils'

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: boolean
}

export function Textarea({ className, error, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        'flex min-h-[80px] w-full rounded-md border bg-card px-3 py-2 text-sm transition',
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
