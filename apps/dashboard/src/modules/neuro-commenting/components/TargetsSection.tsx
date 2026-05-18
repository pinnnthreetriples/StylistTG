import { Card, EmptyState, Skeleton } from '@stylisttg/ui'

import { useNeuroCampaignTargets } from '../hooks'

export function TargetsSection({ campaignId }: { campaignId: string }) {
  const targetsQuery = useNeuroCampaignTargets(campaignId)
  const targets = targetsQuery.data?.items ?? []

  if (targetsQuery.isLoading) return <Skeleton className="h-20 w-full" />

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">Каналы ({targetsQuery.data?.total ?? 0})</h3>
      {targets.length === 0 ? (
        <EmptyState title="Нет каналов" description="Добавьте целевые каналы для мониторинга" />
      ) : (
        <div className="space-y-1.5">
          {targets.map((target) => (
            <div key={target.id} className="flex items-center justify-between rounded border border-gray-100 px-3 py-2 text-sm">
              <span className="font-medium text-gray-700">{target.channel_ref}</span>
              {target.title ? <span className="text-xs text-gray-400">{target.title}</span> : null}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
