import type { ReactNode } from 'react'

import { EmptyState } from './EmptyState'
import { cn } from './utils'

export type DataTableColumn = {
  key: string
  header: ReactNode
}

export type DataTableProps = {
  columns?: DataTableColumn[]
  children: ReactNode
  empty?: boolean
  loading?: boolean
  emptyTitle?: string
  className?: string
}

export function DataTable({
  columns,
  children,
  empty = false,
  loading = false,
  emptyTitle = 'Нет данных',
  className,
}: DataTableProps) {
  if (loading) {
    return <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">Загрузка...</div>
  }
  if (empty) {
    return <EmptyState title={emptyTitle} />
  }
  return (
    <div className={cn('overflow-hidden rounded-lg border border-border bg-card', className)}>
      {columns ? (
        <table className="w-full border-collapse text-sm">
          <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {columns.map((column) => (
                <th className="px-3 py-2 font-semibold" key={column.key}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">{children}</tbody>
        </table>
      ) : (
        children
      )}
    </div>
  )
}
