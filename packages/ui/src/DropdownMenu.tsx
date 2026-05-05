import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { cn } from './utils'

export type DropdownMenuProps = {
  trigger: ReactNode
  children: ReactNode
  align?: 'start' | 'end'
  className?: string
}

export function DropdownMenu({ trigger, children, align = 'end', className }: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (ref.current && !ref.current.contains(e.target as Node)) {
      setOpen(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open, handleClickOutside])

  return (
    <div className={cn('relative inline-flex', className)} ref={ref}>
      <div onClick={() => setOpen((v) => !v)} role="button" tabIndex={0}>
        {trigger}
      </div>
      {open ? (
        <div
          className={cn(
            'absolute top-full z-50 mt-1 min-w-[160px] overflow-hidden rounded-lg border border-gray-200 bg-white py-1 shadow-lg',
            'animate-[fade-in_0.15s_ease-out_both]',
            align === 'end' ? 'right-0' : 'left-0',
          )}
          onClick={() => setOpen(false)}
          role="menu"
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}

export type DropdownMenuItemProps = {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  destructive?: boolean
  className?: string
}

export function DropdownMenuItem({ children, onClick, disabled, destructive, className }: DropdownMenuItemProps) {
  return (
    <button
      className={cn(
        'flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition',
        destructive
          ? 'text-red-600 hover:bg-red-50'
          : 'text-gray-700 hover:bg-gray-50',
        disabled && 'pointer-events-none opacity-50',
        className,
      )}
      disabled={disabled}
      onClick={onClick}
      role="menuitem"
      type="button"
    >
      {children}
    </button>
  )
}

export function DropdownMenuSeparator() {
  return <div className="my-1 h-px bg-gray-100" role="separator" />
}
