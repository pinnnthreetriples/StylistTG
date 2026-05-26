import type { ReactNode } from 'react'

import { cn } from './utils'

export type FormFieldProps = {
  label?: string
  htmlFor?: string
  error?: ReactNode
  hint?: ReactNode
  required?: boolean
  children: ReactNode
  className?: string
}

export function FormField({ label, htmlFor, error, hint, required, children, className }: FormFieldProps) {
  return (
    <div className={cn('grid gap-1.5', className)}>
      {label ? (
        <label className="text-sm font-medium text-foreground" htmlFor={htmlFor}>
          {label}
          {required ? <span className="ml-0.5 text-destructive">*</span> : null}
        </label>
      ) : null}
      {children}
      {error ? <FieldError>{error}</FieldError> : null}
      {hint && !error ? <FieldHint>{hint}</FieldHint> : null}
    </div>
  )
}

export function FieldError({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('text-xs font-medium text-destructive', className)}>{children}</p>
}

export function FieldHint({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('text-xs text-muted-foreground', className)}>{children}</p>
}
