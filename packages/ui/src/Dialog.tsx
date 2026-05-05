import { useCallback, useEffect, type ReactNode } from 'react'

import { cn } from './utils'

export type DialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false)
    },
    [onOpenChange],
  )

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
      return () => {
        document.removeEventListener('keydown', handleKeyDown)
        document.body.style.overflow = ''
      }
    }
  }, [open, handleKeyDown])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        aria-hidden
        className="fixed inset-0 bg-black/40 backdrop-blur-sm animate-[fade-in_0.2s_ease-out_both]"
        onClick={() => onOpenChange(false)}
      />
      <div className="relative z-10">{children}</div>
    </div>
  )
}

export function DialogContent({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      aria-modal="true"
      className={cn(
        'w-full max-w-lg overflow-hidden rounded-xl border border-gray-200 bg-white shadow-xl',
        'animate-[modalIn_0.25s_cubic-bezier(0.4,0,0.2,1)_both]',
        className,
      )}
      role="dialog"
    >
      {children}
    </div>
  )
}

export function DialogHeader({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('border-b border-gray-100 px-5 py-4', className)}>{children}</div>
  )
}

export function DialogTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn('text-base font-bold text-gray-900', className)}>{children}</h2>
}

export function DialogDescription({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('mt-1 text-sm text-gray-500', className)}>{children}</p>
}

export function DialogBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('px-5 py-4', className)}>{children}</div>
}

export function DialogFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex justify-end gap-2 border-t border-gray-100 bg-gray-50 px-5 py-3', className)}>
      {children}
    </div>
  )
}
