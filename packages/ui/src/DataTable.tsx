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
    return <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500">Загрузка...</div>
  }
  if (empty) {
    return <EmptyState title={emptyTitle} />
  }
  return (
    <div className={cn('overflow-hidden rounded-lg border border-gray-200 bg-white', className)}>
      {columns ? (
        <table className="w-full border-collapse text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
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
