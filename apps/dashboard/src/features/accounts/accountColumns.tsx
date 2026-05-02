import { createColumnHelper } from '@tanstack/react-table'
import { Badge, RiskBadge, StatusPill } from '@stylisttg/ui'

import type { AccountRisk } from '@/features/accounts/accountRisk'
import type { AccountListItem } from '@/lib/api'
import { accountStatus, maskPhone } from '@/lib/accounts'

export type AccountTableRow = AccountListItem & {
  risk?: AccountRisk
}

const columnHelper = createColumnHelper<AccountTableRow>()

export const accountColumns = [
  columnHelper.display({
    id: 'select',
    header: ({ table }) => (
      <input
        aria-label="Select all accounts"
        checked={table.getIsAllRowsSelected()}
        onChange={table.getToggleAllRowsSelectedHandler()}
        type="checkbox"
      />
    ),
    cell: ({ row }) => (
      <input
        aria-label={`Select ${row.original.display_name ?? row.original.phone_number}`}
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        type="checkbox"
      />
    ),
    enableSorting: false,
  }),
  columnHelper.accessor((account) => account.display_name || account.phone_number, {
    id: 'account',
    header: 'Account',
    cell: ({ row, getValue }) => (
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-navy-900">{getValue()}</div>
        <div className="truncate text-xs text-gray-400">
          {row.original.username ? `@${row.original.username} · ` : ''}
          {maskPhone(row.original.phone_number)}
        </div>
      </div>
    ),
  }),
  columnHelper.accessor('account_state', {
    header: 'State',
    cell: ({ row }) => {
      const status = accountStatus(row.original)
      const tone = status.kind === 'authorized' ? 'green' : status.kind === 'error' ? 'red' : 'amber'
      return <StatusPill tone={tone}>{status.label}</StatusPill>
    },
  }),
  columnHelper.accessor('runtime_health', {
    header: 'Runtime',
    cell: ({ getValue }) => <Badge tone={getValue() === 'ready' ? 'green' : 'gray'}>{getValue()}</Badge>,
  }),
  columnHelper.accessor((account) => account.risk?.score ?? 0, {
    id: 'risk',
    header: 'Risk',
    cell: ({ row }) =>
      row.original.risk ? (
        <RiskBadge level={row.original.risk.level} score={row.original.risk.score} title={row.original.risk.reasons[0]?.message} />
      ) : (
        <Badge tone="gray">unknown</Badge>
      ),
  }),
  columnHelper.accessor('updated_at', {
    header: 'Updated',
    cell: ({ getValue }) => <span className="text-xs text-gray-500">{getValue()}</span>,
  }),
]
