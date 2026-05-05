import type { InputHTMLAttributes, ReactNode } from 'react'

import { cn } from './utils'

export type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  label?: ReactNode
}

export function Checkbox({ className, label, id, ...props }: CheckboxProps) {
  return (
    <label className={cn('inline-flex items-center gap-2 text-sm', className)} htmlFor={id}>
      <input
        className={cn(
          'size-4 rounded border-gray-300 text-navy-500',
          'focus:ring-2 focus:ring-navy-100 focus:ring-offset-0',
          'disabled:cursor-not-allowed disabled:opacity-50',
        )}
        id={id}
        type="checkbox"
        {...props}
      />
      {label ? <span className="select-none text-gray-700">{label}</span> : null}
    </label>
  )
}
