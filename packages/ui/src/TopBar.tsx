import type { ReactNode } from 'react'

import { cn } from './utils'

export type TopBarProps = {
  brand?: ReactNode
  children?: ReactNode
  trailing?: ReactNode
  className?: string
}

export function TopBar({ brand, children, trailing, className }: TopBarProps) {
  return (
    <header className={cn('sticky top-0 z-20 border-b border-border bg-card/90 backdrop-blur', className)}>
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
        {brand ? <div className="flex min-w-0 flex-1 items-center gap-2">{brand}</div> : null}
        {children ? <div className="flex items-center gap-2">{children}</div> : null}
        {trailing ? <div className="ml-auto flex items-center gap-2">{trailing}</div> : null}
      </div>
    </header>
  )
}
