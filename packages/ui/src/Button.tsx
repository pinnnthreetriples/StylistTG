import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  icon?: ReactNode
}

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-gray-950 text-white border-gray-950 hover:bg-gray-800',
  secondary: 'bg-white text-gray-900 border-gray-200 hover:bg-gray-50',
  ghost: 'bg-transparent text-gray-700 border-transparent hover:bg-gray-100',
  danger: 'bg-red-600 text-white border-red-600 hover:bg-red-700',
}

export function Button({ className, icon, children, variant = 'primary', type = 'button', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition disabled:pointer-events-none disabled:opacity-50',
        variants[variant],
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
