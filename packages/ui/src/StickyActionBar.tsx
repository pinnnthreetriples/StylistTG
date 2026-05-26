import type { ReactNode } from 'react'

import { cn } from './utils'

export type StickyActionBarProps = {
  visible: boolean
  children: ReactNode
  className?: string
}

export function StickyActionBar({ visible, children, className }: StickyActionBarProps) {
  if (!visible) return null

  return (
    <div
      className={cn(
        'fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card/95 backdrop-blur',
        'animate-[-up_0.2s_ease-out_both]',
        'xl:left-64',
        className,
      )}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-end gap-3 px-4 sm:px-6">
        {children}
      </div>
    </div>
  )
}
