import { createColumnHelper } from '@tanstack/react-table'
import { Badge, RiskBadge, StatusPill } from '@stylisttg/ui'

import type { AccountRisk } from '@/features/accounts/accountRisk'
import type { AccountListItem } from '@/lib/api'
import { accountStatus, maskPhone } from '@/lib/accounts'
import { labelRiskLevelShort, labelRuntimeHealth, labelProxyStatus, runtimeHealthTone } from '@/lib/uiLabels'
import { GGRBadge, type GgrBucket } from '@/modules/shared/GGRBadge'
import { QuarantineStateBanner } from '@/modules/shared/QuarantineStateBanner'

export type AccountTableRow = AccountListItem & {
  risk?: AccountRisk
  ggr_score?: number
  ggr_bucket?: GgrBucket
}

const columnHelper = createColumnHelper<AccountTableRow>()

export const accountColumns = [
  columnHelper.display({
    id: 'select',
    header: ({ table }) => (
      <input
        aria-label="Выбрать все аккаунты"
        checked={table.getIsAllRowsSelected()}
        onChange={table.getToggleAllRowsSelectedHandler()}
        type="checkbox"
      />
    ),
    cell: ({ row }) => (
      <input
        aria-label={`Выбрать ${row.original.display_name ?? row.original.phone_number}`}
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        onClick={(e) => e.stopPropagation()}
        type="checkbox"
      />
    ),
    enableSorting: false,
  }),
  columnHelper.accessor((account) => account.display_name || account.phone_number, {
    id: 'account',
    header: 'Аккаунт',
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
    header: 'Статус',
    cell: ({ row }) => {
      const status = accountStatus(row.original)
      const tone = status.kind === 'authorized' ? 'green' : status.kind === 'error' ? 'red' : 'amber'
      return <StatusPill tone={tone}>{status.label}</StatusPill>
    },
  }),
  columnHelper.accessor('runtime_health', {
    header: 'Среда',
    cell: ({ getValue }) => {
      const value = getValue()
      const label = labelRuntimeHealth(value)
      return <Badge tone={runtimeHealthTone(value)}>{label}</Badge>
    },
  }),
  columnHelper.display({
    id: 'quarantine',
    header: 'Карантин',
    cell: ({ row }) => <QuarantineStateBanner accountId={row.original.account_id} compact />,
    enableSorting: false,
  }),
  columnHelper.display({
    id: 'lastJob',
    header: 'Последняя задача',
    cell: () => <span className="text-xs text-gray-400">Нет задач</span>,
  }),
  columnHelper.accessor((account) => account.risk?.score ?? 0, {
    id: 'risk',
    header: 'Риск',
    cell: ({ row }) =>
      row.original.risk ? (
        <RiskBadge
          label={labelRiskLevelShort(row.original.risk.level)}
          level={row.original.risk.level}
          score={row.original.risk.score}
          title={row.original.risk.reasons[0]?.message}
        />
      ) : (
        <Badge tone="gray">Неизвестно</Badge>
      ),
  }),
  columnHelper.accessor((account) => account.ggr_score ?? 0, {
    id: 'ggr',
    header: 'GGR',
    cell: ({ row }) =>
      row.original.ggr_score != null && row.original.ggr_bucket ? (
        <GGRBadge score={row.original.ggr_score} bucket={row.original.ggr_bucket} />
      ) : (
        <Badge tone="gray">—</Badge>
      ),
  }),
  columnHelper.display({
    id: 'proxy',
    header: 'Прокси',
    cell: ({ row }) => {
      const proxyStatus = (row.original as AccountTableRow & { proxy_status?: string }).proxy_status
      return (
        <span className="text-xs text-gray-500">
          {labelProxyStatus(proxyStatus ?? 'none')}
        </span>
      )
    },
  }),
  columnHelper.accessor('updated_at', {
    header: 'Обновлён',
    cell: ({ getValue }) => {
      const value = getValue()
      if (!value) return <span className="text-xs text-gray-400">—</span>
      return (
        <span className="text-xs text-gray-500">
          {new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
        </span>
      )
    },
  }),
]
