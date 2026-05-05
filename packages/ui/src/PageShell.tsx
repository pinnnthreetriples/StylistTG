import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

export type PageShellProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode
}

export function PageShell({ className, children, ...props }: PageShellProps) {
  return (
    <div
      className={cn('mx-auto max-w-6xl px-4 py-6 sm:px-6', className)}
      {...props}
    >
      {children}
    </div>
  )
}
