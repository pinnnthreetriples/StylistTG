import type { TextareaHTMLAttributes } from 'react'

import { cn } from './utils'

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: boolean
}

export function Textarea({ className, error, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        'flex min-h-[80px] w-full rounded-md border bg-white px-3 py-2 text-sm transition',
        'placeholder:text-gray-400',
        'focus:outline-none focus:ring-2 focus:ring-offset-0',
        'disabled:cursor-not-allowed disabled:opacity-50',
        error
          ? 'border-red-300 focus:border-red-400 focus:ring-red-100'
          : 'border-gray-200 focus:border-navy-400 focus:ring-navy-100',
        className,
      )}
      {...props}
    />
  )
}
