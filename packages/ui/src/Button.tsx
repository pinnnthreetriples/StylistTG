import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'destructive'
type ButtonSize = 'default' | 'sm' | 'icon'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: ReactNode
}

const variants: Record<ButtonVariant, string> = {
  primary: 'border-border bg-primary text-primary-foreground hover:bg-foreground',
  secondary: 'border-border bg-muted text-foreground hover:bg-muted',
  outline: 'border-border bg-card text-foreground hover:bg-muted',
  ghost: 'border-transparent bg-transparent text-foreground hover:bg-muted',
  danger: 'border-destructive/20 bg-destructive/10 text-destructive hover:bg-destructive/10',
  destructive: 'border-destructive/20 bg-destructive/10 text-destructive hover:bg-destructive/10',
}

const sizes: Record<ButtonSize, string> = {
  default: 'h-9 px-3',
  sm: 'h-8 px-2.5 text-xs',
  icon: 'size-9 px-0',
}

export function Button({
  className,
  icon,
  children,
  variant = 'primary',
  size = 'default',
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex shrink-0 items-center justify-center gap-2 rounded-md border text-sm font-medium transition disabled:pointer-events-none disabled:opacity-50',
        variants[variant],
        sizes[size],
        className,
      )}
      type={type}
      {...props}
    >
      {icon}
      {children}
    </button>
  )
}
