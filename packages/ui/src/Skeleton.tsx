import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type SkeletonProps = HTMLAttributes<HTMLDivElement>

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      aria-hidden
      data-slot="skeleton"
      className={cn(
        'rounded-md bg-muted',
        'bg-[length:240%_100%]',
        'animate-pulse',
        className,
      )}
      {...props}
    />
  )
}
