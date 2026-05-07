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
  primary: 'border-navy-600 bg-navy-600 text-white hover:bg-navy-700',
  secondary: 'border-gray-200 bg-gray-50 text-gray-900 hover:bg-gray-100',
  outline: 'border-gray-200 bg-white text-gray-900 hover:bg-gray-50',
  ghost: 'border-transparent bg-transparent text-gray-700 hover:bg-gray-100',
  danger: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100',
  destructive: 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100',
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
