import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from '@tanstack/react-table'
import { DataTable, EmptyState } from '@stylisttg/ui'
import { Search } from 'lucide-react'
import { useState } from 'react'

import { accountColumns } from '@/features/accounts/accountColumns'
import type { AccountListItem } from '@/lib/api'

export function AccountsTable({
  accounts,
  isLoading = false,
  onSelectAccount,
}: {
  accounts: AccountListItem[]
  isLoading?: boolean
  onSelectAccount?: (accountId: string) => void
}) {
  const [globalFilter, setGlobalFilter] = useState('')
  const [sorting, setSorting] = useState<SortingState>([])
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  // TanStack Table intentionally returns table helpers that React Compiler cannot memoize.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: accounts,
    columns: accountColumns,
    state: { globalFilter, sorting, rowSelection, columnVisibility },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableRowSelection: true,
  })

  if (isLoading) {
    return (
      <DataTable>
        <div className="p-8 text-center text-sm font-medium text-gray-500">Loading accounts...</div>
      </DataTable>
    )
  }

  return (
    <div className="grid gap-3">
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
        <input
          className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm"
          onChange={(event) => setGlobalFilter(event.target.value)}
          placeholder="Search accounts..."
          type="text"
          value={globalFilter}
        />
      </div>

      <DataTable>
        <table className="w-full border-collapse text-left">
          <thead className="bg-gray-50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-500" key={header.id}>
                    {header.isPlaceholder ? null : (
                      <button
                        className="inline-flex items-center gap-1"
                        onClick={header.column.getToggleSortingHandler()}
                        type="button"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === 'asc' ? '↑' : header.column.getIsSorted() === 'desc' ? '↓' : ''}
                      </button>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                className="border-t border-gray-100 transition-colors hover:bg-gray-50"
                key={row.id}
                onClick={() => onSelectAccount?.(row.original.account_id)}
              >
                {row.getVisibleCells().map((cell) => (
                  <td className="px-4 py-3" key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {table.getRowModel().rows.length === 0 ? (
          <EmptyState
            title="No accounts found"
            description="Adjust the search or add accounts from the current onboarding flow."
          />
        ) : null}
      </DataTable>
    </div>
  )
}
