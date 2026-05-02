import type { ReactNode } from 'react'

import { Card } from './Card'
import { cn } from './utils'

export type SectionCardProps = {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}

export function SectionCard({ title, description, actions, children, className }: SectionCardProps) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-950">{title}</h2>
          {description ? <p className="mt-1 text-xs text-gray-500">{description}</p> : null}
        </div>
        {actions}
      </div>
      <div className="p-4">{children}</div>
    </Card>
  )
}
