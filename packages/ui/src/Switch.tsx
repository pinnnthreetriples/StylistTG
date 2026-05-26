import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

export type SwitchProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> & {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label?: ReactNode
}

export function Switch({ className, checked, onCheckedChange, label, disabled, ...props }: SwitchProps) {
  return (
    <label className={cn('inline-flex items-center gap-2.5', disabled && 'opacity-50', className)}>
      <button
        aria-checked={checked}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed',
          checked ? 'bg-primary' : 'bg-muted',
        )}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        role="switch"
        type="button"
        {...props}
      >
        <span
          className={cn(
            'pointer-events-none block size-4 rounded-full bg-card shadow-sm transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0',
          )}
        />
      </button>
      {label ? <span className="select-none text-sm text-foreground">{label}</span> : null}
    </label>
  )
}
