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

export function FormField(props: FormFieldProps) {
  const { label, htmlFor, error, hint, required, children, className } = props

  return (
    <div className={cn('grid gap-1.5', className)}>
      <FieldLabel htmlFor={htmlFor} label={label} required={required} />
      {children}
      <FieldFeedback error={error} hint={hint} />
    </div>
  )
}

function FieldLabel({
  htmlFor,
  label,
  required,
}: {
  htmlFor?: string
  label?: string
  required?: boolean
}) {
  if (!label) return null
  return (
    <label className="text-sm font-medium text-foreground" htmlFor={htmlFor}>
      {label}
      <RequiredMark required={required} />
    </label>
  )
}

function RequiredMark({ required }: { required?: boolean }) {
  if (!required) return null
  return <span className="ml-0.5 text-destructive">*</span>
}

function FieldFeedback({ error, hint }: { error?: ReactNode; hint?: ReactNode }) {
  if (error) return <FieldError>{error}</FieldError>
  if (hint) return <FieldHint>{hint}</FieldHint>
  return null
}

export function FieldError({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('text-xs font-medium text-destructive', className)}>{children}</p>
}

export function FieldHint({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('text-xs text-muted-foreground', className)}>{children}</p>
}
