import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-lg border border-gray-200 bg-white shadow-sm', className)} {...props} />
}
