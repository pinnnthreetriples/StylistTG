import { Card, EmptyState, Skeleton } from '@stylisttg/ui'

import { useNeuroCampaignAccounts } from '../hooks'

export function AccountsSection({ campaignId }: { campaignId: string }) {
  const accountsQuery = useNeuroCampaignAccounts(campaignId)
  const accounts = accountsQuery.data?.items ?? []

  if (accountsQuery.isLoading) return <Skeleton className="h-20 w-full" />

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">Аккаунты ({accountsQuery.data?.total ?? 0})</h3>
      {accounts.length === 0 ? (
        <EmptyState title="Нет аккаунтов" description="Добавьте аккаунты к кампании" />
      ) : (
        <div className="space-y-1.5">
          {accounts.map((account) => (
            <div key={account.id} className="flex items-center justify-between rounded border border-gray-100 px-3 py-2 text-sm">
              <span className="font-medium text-gray-700">{account.account_id}</span>
              <span className="text-xs text-gray-400">w:{account.rotation_weight} o:{account.rotation_order}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
