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
import { Button, DataTable, ProductEmptyState, RiskBadge, StatusPill } from '@stylisttg/ui'
import { useState, useEffect, useMemo } from 'react'

import type { AccountRisk } from '@/features/accounts/accountRisk'
import { accountColumns } from '@/features/accounts/accountColumns'
import type { AccountListItem } from '@/lib/api'
import { accountStatus, maskPhone } from '@/lib/accounts'
import { labelProxyStatus, labelRiskLevelShort } from '@/lib/uiLabels'
import { accountsViewStorageKey } from './accountsViewStorage'
import { AccountsTableToolbar, type AccountsView } from './AccountsTableToolbar'

export function AccountsTable({
  accounts,
  isLoading = false,
  onSelectAccount,
  riskByAccount,
  userId,
  workspaceId,
}: {
  accounts: AccountListItem[]
  isLoading?: boolean
  onSelectAccount?: (accountId: string) => void
  riskByAccount?: Map<string, AccountRisk>
  userId?: string | null
  workspaceId?: string | null
}) {
  const [globalFilter, setGlobalFilter] = useState('')
  const [sorting, setSorting] = useState<SortingState>([])
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [activeView, setActiveView] = useState<AccountsView>('all')
  const storageKey = accountsViewStorageKey({ workspaceId: workspaceId ?? undefined, userId: userId ?? undefined })

  useEffect(() => {
    const saved = localStorage.getItem(storageKey) as AccountsView
    if (saved && ['all', 'ready', 'high_risk'].includes(saved)) {
      setActiveView(saved)
    }
  }, [storageKey])

  const handleViewChange = (view: AccountsView) => {
    setActiveView(view)
    localStorage.setItem(storageKey, view)
  }

  const filteredData = useMemo(() => {
    const dataWithRisk = accounts.map((account) => ({ ...account, risk: riskByAccount?.get(account.account_id) }))

    if (activeView === 'ready') {
      return dataWithRisk.filter(a => accountStatus(a).kind === 'authorized' && a.is_execution_usable)
    }
    if (activeView === 'high_risk') {
      return dataWithRisk.filter(a => (a.risk?.level === 'high' || a.risk?.level === 'critical'))
    }
    return dataWithRisk
  }, [accounts, riskByAccount, activeView])

  // TanStack Table intentionally returns table helpers that React Compiler cannot memoize.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: filteredData,
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
        <div className="p-8 text-center text-sm font-medium text-gray-500">Загружаем аккаунты...</div>
      </DataTable>
    )
  }

  return (
    <div className="grid gap-3">
      <AccountsTableToolbar
        globalFilter={globalFilter}
        onGlobalFilterChange={setGlobalFilter}
        activeView={activeView}
        onViewChange={handleViewChange}
        selectedCount={Object.keys(rowSelection).length}
      />

      <div className="grid gap-3 md:hidden">
        {table.getRowModel().rows.map((row) => {
          const account = row.original
          const status = accountStatus(account)
          const risk = account.risk
          return (
            <article className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm" key={account.account_id}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-navy-900">{account.display_name || maskPhone(account.phone_number)}</h3>
                  <p className="mt-1 truncate text-xs text-gray-500">
                    {account.username ? `@${account.username} · ` : ''}
                    {maskPhone(account.phone_number)}
                  </p>
                </div>
                {risk ? (
                  <RiskBadge label={labelRiskLevelShort(risk.level)} level={risk.level} score={risk.score} />
                ) : null}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <StatusPill tone={status.kind === 'authorized' ? 'green' : status.kind === 'error' ? 'red' : 'amber'}>{status.label}</StatusPill>
                <span className="rounded-full bg-gray-50 px-2.5 py-1 text-xs text-gray-600">{labelProxyStatus('none')}</span>
              </div>
              <Button className="mt-4 w-full" onClick={() => onSelectAccount?.(account.account_id)} type="button" variant="secondary">
                Открыть
              </Button>
            </article>
          )
        })}
      </div>

      <DataTable className="hidden md:block">
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
                className="cursor-pointer border-t border-gray-100 transition-colors hover:bg-gray-50"
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
          <ProductEmptyState
            title={activeView === 'all' ? 'Добавьте первый Telegram-аккаунт' : 'Ничего не найдено'}
            description={
              activeView === 'all'
                ? 'После добавления вы сможете редактировать профиль, истории, музыку, прокси и видеть риск блокировки.'
                : 'Измените фильтры или сбросьте поиск.'
            }
          />
        ) : null}
      </DataTable>
    </div>
  )
}
