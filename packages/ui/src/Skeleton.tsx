import type { HTMLAttributes } from 'react'

import { cn } from './utils'

export type SkeletonProps = HTMLAttributes<HTMLDivElement>

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      aria-hidden
      className={cn(
        'rounded-md bg-gray-200/60',
        'bg-[length:240%_100%]',
        'bg-gradient-to-r from-gray-200/60 via-gray-100 to-gray-200/60',
        'animate-[skeleton-shimmer_1.35s_ease-in-out_infinite]',
        className,
      )}
      {...props}
    />
  )
}
