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
            'absolute top-full z-50 mt-1 min-w-[160px] overflow-hidden rounded-lg border border-border bg-card py-1 shadow-lg',
            '',
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
          ? 'text-destructive hover:bg-destructive/10'
          : 'text-foreground hover:bg-muted',
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
  return <div className="my-1 h-px bg-muted" role="separator" />
}
