import { useRef, useState, type ReactNode } from 'react'

import { cn } from './utils'

export type TooltipProps = {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'bottom'
  className?: string
}

export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  function show() {
    clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => setVisible(true), 200)
  }

  function hide() {
    clearTimeout(timeoutRef.current)
    setVisible(false)
  }

  return (
    <div
      className={cn('relative inline-flex', className)}
      onBlur={hide}
      onFocus={show}
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      {children}
      {visible ? (
        <div
          className={cn(
            'absolute z-50 max-w-xs rounded-md bg-gray-900 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg',
            'animate-[fade-in_0.15s_ease-out_both]',
            side === 'top'
              ? 'bottom-full left-1/2 mb-1.5 -translate-x-1/2'
              : 'top-full left-1/2 mt-1.5 -translate-x-1/2',
          )}
          role="tooltip"
        >
          {content}
        </div>
      ) : null}
    </div>
  )
}
